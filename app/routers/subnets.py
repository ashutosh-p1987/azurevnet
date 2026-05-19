"""
Subnets router – list and retrieve subnets nested under a VNET.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app import models, schemas
from app.auth import get_current_active_user
from app.database import get_db

router = APIRouter()


@router.get(
    "/{vnet_id}/subnets",
    response_model=list[schemas.SubnetResponse],
    summary="List all subnets for a VNET",
)
async def list_subnets(
    vnet_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user),
):
    """Return all subnets belonging to a specific VNET."""
    vnet_result = await db.execute(
        select(models.VNet).where(models.VNet.id == vnet_id)
    )
    vnet = vnet_result.scalar_one_or_none()
    if not vnet:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="VNET not found")
    if vnet.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    result = await db.execute(
        select(models.Subnet).where(models.Subnet.vnet_id == vnet_id)
    )
    return result.scalars().all()


@router.get(
    "/{vnet_id}/subnets/{subnet_id}",
    response_model=schemas.SubnetResponse,
    summary="Get a single subnet",
)
async def get_subnet(
    vnet_id: int,
    subnet_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user),
):
    """Retrieve a single subnet by ID within a VNET."""
    # Verify VNET ownership
    vnet_result = await db.execute(
        select(models.VNet).where(models.VNet.id == vnet_id)
    )
    vnet = vnet_result.scalar_one_or_none()
    if not vnet:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="VNET not found")
    if vnet.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    result = await db.execute(
        select(models.Subnet).where(
            (models.Subnet.id == subnet_id) & (models.Subnet.vnet_id == vnet_id)
        )
    )
    subnet = result.scalar_one_or_none()
    if not subnet:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subnet not found")
    return subnet
