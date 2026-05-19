"""
VNET router – full CRUD for Virtual Networks.
"""
from __future__ import annotations
import json
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload

from app import models, schemas
from app.auth import get_current_active_user
from app.database import get_db
from app.services.azure_network import create_vnet, delete_vnet_from_azure

logger = logging.getLogger(__name__)
router = APIRouter()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _get_vnet_or_404(vnet_id: int, db: AsyncSession) -> models.VNet:
    result = await db.execute(
        select(models.VNet)
        .where(models.VNet.id == vnet_id)
        .options(selectinload(models.VNet.subnets))
    )
    vnet = result.scalar_one_or_none()
    if not vnet:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="VNET not found")
    return vnet


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.post(
    "/",
    response_model=schemas.VNetResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new VNET with subnets",
)
async def create_vnet_endpoint(
    payload: schemas.VNetCreate,
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user),
):
    """
    Create an Azure Virtual Network with one or more subnets.

    - Calls the Azure SDK (or mock) to provision the network
    - Persists the result in the local database
    - Returns the full VNET record including subnet details
    """
    subnet_dicts = [s.model_dump() for s in payload.subnets]

    try:
        azure_result = await create_vnet(
            name=payload.name,
            resource_group=payload.resource_group,
            location=payload.location,
            address_space=payload.address_space,
            subnets=subnet_dicts,
        )
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        )

    # Persist VNET
    db_vnet = models.VNet(
        name=payload.name,
        resource_group=payload.resource_group,
        location=payload.location,
        address_space=json.dumps(payload.address_space),
        azure_id=azure_result.azure_id,
        provisioning_state=azure_result.provisioning_state,
        owner_id=current_user.id,
    )
    db.add(db_vnet)
    await db.flush()  # get db_vnet.id

    # Map Azure subnet results by name for easy lookup
    azure_subnet_map = {s["name"]: s for s in azure_result.subnets}

    for s in payload.subnets:
        az = azure_subnet_map.get(s.name, {})
        db_subnet = models.Subnet(
            name=s.name,
            address_prefix=s.address_prefix,
            azure_id=az.get("azure_id"),
            provisioning_state=az.get("provisioning_state", "Succeeded"),
            vnet_id=db_vnet.id,
        )
        db.add(db_subnet)

    await db.flush()
    await db.refresh(db_vnet)

    # Reload with subnets
    return await _get_vnet_or_404(db_vnet.id, db)


@router.get(
    "/",
    response_model=schemas.VNetListResponse,
    summary="List all VNETs for the current user",
)
async def list_vnets(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    location: Optional[str] = Query(None, description="Filter by Azure region"),
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user),
):
    """Return a paginated list of VNETs owned by the authenticated user."""
    query = (
        select(models.VNet)
        .where(models.VNet.owner_id == current_user.id)
        .options(selectinload(models.VNet.subnets))
        .order_by(models.VNet.created_at.desc())
    )
    if location:
        query = query.where(models.VNet.location == location)

    count_query = select(func.count()).select_from(
        query.subquery()
    )
    total = (await db.execute(count_query)).scalar_one()

    result = await db.execute(query.offset(skip).limit(limit))
    vnets = result.scalars().all()

    return {"total": total, "items": vnets}


@router.get(
    "/{vnet_id}",
    response_model=schemas.VNetResponse,
    summary="Get a single VNET by ID",
)
async def get_vnet(
    vnet_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user),
):
    """Retrieve details of a single VNET (must belong to the current user)."""
    vnet = await _get_vnet_or_404(vnet_id, db)
    if vnet.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    return vnet


@router.delete(
    "/{vnet_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a VNET (and its subnets) from Azure and the database",
)
async def delete_vnet(
    vnet_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user),
):
    """Delete a VNET from Azure and remove the local record."""
    vnet = await _get_vnet_or_404(vnet_id, db)
    if vnet.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    deleted = await delete_vnet_from_azure(vnet.name, vnet.resource_group)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to delete VNET in Azure",
        )

    await db.delete(vnet)
