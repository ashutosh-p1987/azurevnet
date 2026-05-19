"""
Application configuration – loaded from environment variables / .env file.
"""
from pydantic_settings import BaseSettings
from pydantic import Field
from typing import List


class Settings(BaseSettings):
    # ------------------------------------------------------------------
    # App
    # ------------------------------------------------------------------
    APP_NAME: str = "Azure VNET API"
    DEBUG: bool = False
    ALLOWED_ORIGINS: List[str] = ["*"]

    # ------------------------------------------------------------------
    # JWT / Auth
    # ------------------------------------------------------------------
    SECRET_KEY: str = Field(
        default="change-me-to-a-strong-random-secret-key-in-production",
        description="HMAC secret used to sign JWT tokens",
    )
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # ------------------------------------------------------------------
    # Azure credentials
    # ------------------------------------------------------------------
    AZURE_SUBSCRIPTION_ID: str = Field(
        default="", description="Azure Subscription ID"
    )
    AZURE_TENANT_ID: str = Field(default="", description="Azure AD Tenant ID")
    AZURE_CLIENT_ID: str = Field(
        default="", description="Service Principal / App Registration Client ID"
    )
    AZURE_CLIENT_SECRET: str = Field(
        default="", description="Service Principal Client Secret"
    )
    AZURE_RESOURCE_GROUP: str = Field(
        default="rg-vnet-api", description="Default resource group name"
    )
    AZURE_LOCATION: str = Field(
        default="eastus", description="Default Azure region"
    )

    # ------------------------------------------------------------------
    # Database (SQLite for local dev; swap URL for PostgreSQL in prod)
    # ------------------------------------------------------------------
    DATABASE_URL: str = "sqlite+aiosqlite:///./vnet_api.db"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
