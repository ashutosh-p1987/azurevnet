
from __future__ import annotations
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, EmailStr, Field, field_validator
import ipaddress


class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=64, example="testuser")
    email: EmailStr = Field(..., example="testuser@example.com")
    password: str = Field(..., min_length=8, example="securepassword123")


class UserResponse(BaseModel):
    id: int
    username: str
    email: str
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TokenData(BaseModel):
    username: Optional[str] = None


class SubnetCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=128, example="subnet-frontend")
    address_prefix: str = Field(..., example="10.0.1.0/24")

    @field_validator("address_prefix")
    @classmethod
    def validate_cidr(cls, v: str) -> str:
        try:
            ipaddress.IPv4Network(v, strict=False)
        except ValueError:
            raise ValueError(f"'{v}' is not a valid IPv4 CIDR block")
        return v


class SubnetResponse(BaseModel):
    id: int
    name: str
    address_prefix: str
    azure_id: Optional[str]
    provisioning_state: str
    vnet_id: int
    created_at: datetime

    model_config = {"from_attributes": True}


class VNetCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=128, example="vnet-production")
    resource_group: str = Field(..., min_length=1, max_length=128, example="rg-production")
    location: str = Field(..., example="eastus")
    address_space: List[str] = Field(
        ...,
        min_length=1,
        example=["10.0.0.0/16"],
        description="List of CIDR address prefixes for the VNET",
    )
    subnets: List[SubnetCreate] = Field(
        default_factory=list,
        description="Subnets to create inside the VNET",
    )

    @field_validator("address_space")
    @classmethod
    def validate_address_space(cls, v: List[str]) -> List[str]:
        for cidr in v:
            try:
                ipaddress.IPv4Network(cidr, strict=False)
            except ValueError:
                raise ValueError(f"'{cidr}' is not a valid IPv4 CIDR block")
        return v


class VNetResponse(BaseModel):
    id: int
    name: str
    resource_group: str
    location: str
    address_space: str  # stored as JSON string
    azure_id: Optional[str]
    provisioning_state: str
    owner_id: int
    created_at: datetime
    updated_at: datetime
    subnets: List[SubnetResponse] = []

    model_config = {"from_attributes": True}


class VNetListResponse(BaseModel):
    total: int
    items: List[VNetResponse]
