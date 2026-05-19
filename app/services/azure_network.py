"""
Azure Network service – wraps the azure-mgmt-network SDK.

If Azure credentials are not configured (local dev / CI), the service falls
back to a "mock" mode that returns synthetic responses so that the rest of
the application can be exercised without a real Azure subscription.
"""
from __future__ import annotations
import logging
import json
from typing import List, Optional

from app.config import settings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Try to import Azure SDK; fall back gracefully if not installed / not configured
# ---------------------------------------------------------------------------
try:
    from azure.identity import ClientSecretCredential
    from azure.mgmt.network import NetworkManagementClient
    from azure.mgmt.network.models import (
        VirtualNetwork,
        AddressSpace,
        Subnet as AzureSubnet,
    )
    from azure.core.exceptions import AzureError

    _AZURE_SDK_AVAILABLE = True
except ImportError:
    _AZURE_SDK_AVAILABLE = False
    logger.warning("azure-mgmt-network not installed – running in MOCK mode.")


def _is_azure_configured() -> bool:
    return (
        _AZURE_SDK_AVAILABLE
        and bool(settings.AZURE_SUBSCRIPTION_ID)
        and bool(settings.AZURE_TENANT_ID)
        and bool(settings.AZURE_CLIENT_ID)
        and bool(settings.AZURE_CLIENT_SECRET)
    )


def _get_network_client() -> "NetworkManagementClient":
    credential = ClientSecretCredential(
        tenant_id=settings.AZURE_TENANT_ID,
        client_id=settings.AZURE_CLIENT_ID,
        client_secret=settings.AZURE_CLIENT_SECRET,
    )
    return NetworkManagementClient(credential, settings.AZURE_SUBSCRIPTION_ID)


# ---------------------------------------------------------------------------
# Public interface
# ---------------------------------------------------------------------------

class VNetCreationResult:
    """Normalised result returned by create_vnet regardless of mode."""
    def __init__(
        self,
        azure_id: Optional[str],
        provisioning_state: str,
        subnets: List[dict],
    ):
        self.azure_id = azure_id
        self.provisioning_state = provisioning_state
        self.subnets = subnets  # list of {name, address_prefix, azure_id, provisioning_state}


async def create_vnet(
    name: str,
    resource_group: str,
    location: str,
    address_space: List[str],
    subnets: List[dict],  # [{"name": str, "address_prefix": str}]
) -> VNetCreationResult:
    """
    Create a VNET (+ subnets) in Azure or return a mock result.

    Parameters
    ----------
    name            : VNET name
    resource_group  : Azure resource group (must already exist for real calls)
    location        : Azure region, e.g. "eastus"
    address_space   : List of CIDR strings, e.g. ["10.0.0.0/16"]
    subnets         : List of subnet dicts with 'name' and 'address_prefix'

    Returns
    -------
    VNetCreationResult with azure_id, provisioning_state, and per-subnet info.
    """
    if not _is_azure_configured():
        return _mock_create_vnet(name, resource_group, location, address_space, subnets)

    return await _azure_create_vnet(name, resource_group, location, address_space, subnets)


# ---------------------------------------------------------------------------
# Real Azure implementation
# ---------------------------------------------------------------------------

async def _azure_create_vnet(
    name: str,
    resource_group: str,
    location: str,
    address_space: List[str],
    subnets: List[dict],
) -> VNetCreationResult:
    client = _get_network_client()

    subnet_models = [
        AzureSubnet(name=s["name"], address_prefix=s["address_prefix"])
        for s in subnets
    ]

    vnet_params = VirtualNetwork(
        location=location,
        address_space=AddressSpace(address_prefixes=address_space),
        subnets=subnet_models,
    )

    try:
        poller = client.virtual_networks.begin_create_or_update(
            resource_group_name=resource_group,
            virtual_network_name=name,
            parameters=vnet_params,
        )
        result: VirtualNetwork = poller.result()

        subnet_results = []
        for subnet in result.subnets or []:
            subnet_results.append(
                {
                    "name": subnet.name,
                    "address_prefix": subnet.address_prefix,
                    "azure_id": subnet.id,
                    "provisioning_state": subnet.provisioning_state,
                }
            )

        return VNetCreationResult(
            azure_id=result.id,
            provisioning_state=result.provisioning_state,
            subnets=subnet_results,
        )

    except AzureError as exc:
        logger.error(f"Azure VNET creation failed: {exc}")
        raise RuntimeError(f"Azure error: {exc}") from exc


# ---------------------------------------------------------------------------
# Mock implementation (no Azure credentials required)
# ---------------------------------------------------------------------------

def _mock_create_vnet(
    name: str,
    resource_group: str,
    location: str,
    address_space: List[str],
    subnets: List[dict],
) -> VNetCreationResult:
    logger.info(
        f"[MOCK] Simulating VNET creation: name={name}, rg={resource_group}, location={location}"
    )
    mock_subscription = "00000000-0000-0000-0000-000000000000"
    base_id = (
        f"/subscriptions/{mock_subscription}/resourceGroups/{resource_group}"
        f"/providers/Microsoft.Network/virtualNetworks/{name}"
    )

    subnet_results = []
    for s in subnets:
        subnet_results.append(
            {
                "name": s["name"],
                "address_prefix": s["address_prefix"],
                "azure_id": f"{base_id}/subnets/{s['name']}",
                "provisioning_state": "Succeeded",
            }
        )

    return VNetCreationResult(
        azure_id=base_id,
        provisioning_state="Succeeded",
        subnets=subnet_results,
    )


async def get_vnet_from_azure(name: str, resource_group: str) -> Optional[dict]:
    """Fetch live VNET details from Azure (best-effort, returns None on any error)."""
    if not _is_azure_configured():
        return None
    try:
        client = _get_network_client()
        vnet = client.virtual_networks.get(resource_group, name)
        return {
            "provisioning_state": vnet.provisioning_state,
            "azure_id": vnet.id,
        }
    except Exception as exc:
        logger.warning(f"Could not fetch VNET from Azure: {exc}")
        return None


async def delete_vnet_from_azure(name: str, resource_group: str) -> bool:
    """Delete a VNET in Azure. Returns True on success, False otherwise."""
    if not _is_azure_configured():
        logger.info(f"[MOCK] Simulating deletion of VNET {name}")
        return True
    try:
        client = _get_network_client()
        poller = client.virtual_networks.begin_delete(resource_group, name)
        poller.result()
        return True
    except Exception as exc:
        logger.error(f"Azure VNET deletion failed: {exc}")
        return False
