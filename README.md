## Table of Contents

- [Features](#features)
- [Architecture](#architecture)
- [Quick Start](#quick-start)
- [Configuration](#configuration)
- [API Reference](#api-reference)
- [Authentication Flow](#authentication-flow)
- [Azure Setup](#azure-setup)
- [Docker](#docker)
- [Project Structure](#project-structure)

---

## Features

| Feature | Details |
|---|---|
| **VNET CRUD** | Create, list, get, and delete Azure VNETs |
| **Multi-subnet** | Create multiple subnets in a single API call |
| **JWT Auth** | All resource endpoints require a Bearer token |
| **Open Authorization** | Any registered/authenticated user can manage VNETs |
| **Azure SDK** | Real provisioning via `azure-mgmt-network` ||
| **Async** | Fully async via `asyncio` + `aiosqlite`/`asyncpg` |
| **OpenAPI Docs** | Auto-generated Swagger UI at `/docs` |

---

## Architecture

```
┌─────────────────────────────────────────────┐
│            Azure VNET API                   │
│                                             │
│  POST /api/v1/auth/register                 │
│  POST /api/v1/auth/login  ──► JWT token     │
│                                             │
│  [Protected with Bearer token]              │
│  POST   /api/v1/vnets/         ──► Azure    │
│  GET    /api/v1/vnets/                      │
│  GET    /api/v1/vnets/{id}                  │
│  DELETE /api/v1/vnets/{id}     ──► Azure    │
│  GET    /api/v1/vnets/{id}/subnets          │
│  GET    /api/v1/vnets/{id}/subnets/{sid}    │
└──────────────┬──────────────────────────────┘
               │
       ┌───────▼────────┐        ┌──────────────────┐
       │   SQLite       │        │  Azure Network   │
       │                │        │  Management API  │
       └────────────────┘        └──────────────────┘
```

---

## Quick Start

### Prerequisites

- Python 3.12+
- (Optional) Azure subscription with Contributor access

### 1. Clone the repository

```bash
git https://github.com/ashutosh-p1987/azurevnet.git
cd azurevnet
```

### 2. Create a virtual environment

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure environment

```bash
cp .env.example .env
# Edit .env with your values (Azure credentials optional for mock mode)
```

### 5. Run the server

```bash
uvicorn app.main:app --reload
```

Open **http://localhost:8000/docs** for the interactive Swagger UI.

---

## Configuration

All settings are loaded from environment variables or a `.env` file.

| Variable | Default | Description |
|---|---|---|
| `SECRET_KEY` | *(required)* | HMAC secret for JWT signing |
| `ALGORITHM` | `HS256` | JWT signing algorithm |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `60` | Token lifetime |
| `AZURE_SUBSCRIPTION_ID` | – | Azure Subscription ID |
| `AZURE_TENANT_ID` | – | Azure AD Tenant ID |
| `AZURE_CLIENT_ID` | – | Service Principal App ID |
| `AZURE_CLIENT_SECRET` | – | Service Principal secret |
| `AZURE_RESOURCE_GROUP` | `rg-vnet-api` | Default resource group |
| `AZURE_LOCATION` | `eastus` | Default Azure region |
| `DATABASE_URL` | SQLite | DB connection string |

> **Mock mode**: If any Azure variable is missing, the API simulates Azure calls and returns synthetic resource IDs. Perfect for local development.

---

## API Reference

### Authentication

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/v1/auth/register` | Register a new user |
| `POST` | `/api/v1/auth/login` | Login and receive JWT |
| `GET` | `/api/v1/auth/me` | Get current user info |

### Virtual Networks *(require Bearer token)*

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/v1/vnets/` | Create VNET + subnets |
| `GET` | `/api/v1/vnets/` | List your VNETs |
| `GET` | `/api/v1/vnets/{id}` | Get single VNET |
| `DELETE` | `/api/v1/vnets/{id}` | Delete VNET |

### Subnets *(require Bearer token)*

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/v1/vnets/{id}/subnets` | List subnets in VNET |
| `GET` | `/api/v1/vnets/{id}/subnets/{sid}` | Get single subnet |

### Example: Create a VNET

```bash
# 1. Register
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username":"users","email":"users@example.com","password":"securepass123"}'

# 2. Login
TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -d "username=users&password=securepass123" | jq -r .access_token)

# 3. Create VNET
curl -X POST http://localhost:8000/api/v1/vnets/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "vnet-production",
    "resource_group": "rg-production",
    "location": "eastus",
    "address_space": ["10.0.0.0/16"],
    "subnets": [
      {"name": "subnet-frontend", "address_prefix": "10.0.1.0/24"},
      {"name": "subnet-backend",  "address_prefix": "10.0.2.0/24"},
      {"name": "subnet-data",     "address_prefix": "10.0.3.0/24"}
    ]
  }'
```

---

## Authentication Flow

```
Client                          API
  │                              │
  │── POST /auth/register ──────►│  Hash password, store user
  │◄─ 201 {id, username, ...} ───│
  │                              │
  │── POST /auth/login ─────────►│  Verify password
  │◄─ 200 {access_token} ────────│  Return signed JWT
  │                              │
  │── GET /vnets/ ──────────────►│
  │   Authorization: Bearer <jwt>│  Decode & validate JWT
  │◄─ 200 {total, items} ────────│  Return resources
```

- Tokens are signed with **HMAC-SHA256**.
- All protected routes use **OAuth2 Bearer** scheme.
- Authorization is **open to all authenticated users** – any registered user may manage VNETs.

---

## Azure Setup

### 1. Create a Service Principal

```bash
az ad sp create-for-rbac \
  --name vnet-api-sp \
  --role Contributor \
  --scopes /subscriptions/<SUBSCRIPTION_ID>
```

Copy `appId` → `AZURE_CLIENT_ID`, `password` → `AZURE_CLIENT_SECRET`, `tenant` → `AZURE_TENANT_ID`.

### 2. Create the Resource Group

```bash
az group create --name rg-vnet-api --location eastus
```

### 3. Set environment variables

Populate your `.env` file with the values above.

---

## Running Tests

```bash
pytest tests/ -v
```

Tests use an **in-memory SQLite** database and the **mock Azure service** – no Azure credentials required.

---

## Docker

### Build and run

```bash
docker compose up --build
```

The API is available at **http://localhost:8000**.

### Production notes

- Replace `DATABASE_URL` with a PostgreSQL connection string.
- Set a strong `SECRET_KEY`.
- Use Azure Key Vault or GitHub Secrets for credential management.
- Enable HTTPS via a reverse proxy (nginx / Azure API Management).

---

## Project Structure

```
azure-vnet-api/
├── app/
│   ├── main.py              # FastAPI application factory
│   ├── config.py            # Pydantic settings
│   ├── database.py          # SQLAlchemy async engine & session
│   ├── models.py            # ORM models (User, VNet, Subnet)
│   ├── schemas.py           # Pydantic request/response schemas
│   ├── auth.py              # JWT utilities & dependencies
│   ├── routers/
│   │   ├── auth.py          # /auth endpoints
│   │   ├── vnets.py         # /vnets CRUD endpoints
│   │   └── subnets.py       # /vnets/{id}/subnets endpoints
│   └── services/
│       └── azure_network.py # Azure SDK wrapper (+ mock mode)
├── tests/
│   └── test_api.py          # Async integration tests
├── .github/
│   └── workflows/ci.yml     # GitHub Actions CI
├── .env.example             # Environment template
├── .gitignore
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── README.md