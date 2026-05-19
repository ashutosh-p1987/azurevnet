
from __future__ import annotations
from datetime import datetime, timezone
from typing import List, Optional
from sqlalchemy import (
    String, Boolean, DateTime, ForeignKey, Text, Integer
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    email: Mapped[str] = mapped_column(String(128), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(256), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    vnets: Mapped[List["VNet"]] = relationship("VNet", back_populates="owner", cascade="all, delete-orphan")


class VNet(Base):
    __tablename__ = "vnets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    resource_group: Mapped[str] = mapped_column(String(128), nullable=False)
    location: Mapped[str] = mapped_column(String(64), nullable=False)
    address_space: Mapped[str] = mapped_column(String(256), nullable=False, comment="JSON array of CIDR strings")

    # Azure-side metadata
    azure_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="Full Azure resource ID")
    provisioning_state: Mapped[str] = mapped_column(String(32), default="Pending")

    owner_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    owner: Mapped["User"] = relationship("User", back_populates="vnets")
    subnets: Mapped[List["Subnet"]] = relationship("Subnet", back_populates="vnet", cascade="all, delete-orphan")


class Subnet(Base):
    __tablename__ = "subnets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    address_prefix: Mapped[str] = mapped_column(String(64), nullable=False, comment="CIDR e.g. 10.0.1.0/24")

    # Azure-side metadata
    azure_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    provisioning_state: Mapped[str] = mapped_column(String(32), default="Pending")

    vnet_id: Mapped[int] = mapped_column(Integer, ForeignKey("vnets.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    vnet: Mapped["VNet"] = relationship("VNet", back_populates="subnets")
