# Plan Gastos API

A REST API for **Plan Gastos**, a personal finance application. Built with Python and FastAPI, it uses PostgreSQL for persistence and Firebase Authentication to identify users.

## Overview

Plan Gastos helps users organize monthly budgets and review the income, expenses, salary discounts, and overtime entries associated with each budget.

This backend is responsible for:

- exposing resource-oriented HTTP endpoints;
- validating request and response data;
- authenticating requests with Firebase ID tokens;
- enforcing ownership of budgets and their related records;
- persisting application data in PostgreSQL;
- calculating financial values in the domain module.

A budget is scoped to its authenticated owner and identified by a month key. Income, expenses, salary discounts, and detailed overtime entries belong to a budget. The API does not accept a user identity from the request body as the source of authorization.

## Tech Stack

The versions below reflect the declarations in `pyproject.toml`; most Python dependencies are minimum-version constraints rather than exact pins.

| Technology | Project declaration / use |
| --- | --- |
| Python | `>=3.11` |
| FastAPI | `>=0.111.0` |
| Uvicorn | `[standard] >=0.30.0` |
| Pydantic | v2 APIs used by schemas; installed through the FastAPI dependency, not pinned directly in `pyproject.toml` |
| Pydantic Settings | `>=2.2.1` |
| SQLAlchemy | `>=2.0.30` |
| Psycopg | `[binary] >=3.1.18` |
| Alembic | `>=1.13.0` |
| Firebase Admin SDK | `>=6.5.0` |
| pytest | `>=8.0.0` (development extra) |
| httpx | `>=0.27.0` (development extra) |
| PostgreSQL | `16-alpine` in Docker Compose |
| Docker application image | `python:3.13-slim` |

## Architecture

The codebase uses a small, explicit module structure rather than a separate repository or service layer. Route handlers coordinate HTTP requests, schemas define the API boundary, domain functions contain financial calculations, and infrastructure modules handle persistence and Firebase verification.

```text
app/
├── main.py                         # FastAPI application, middleware, routers, health and /api/me
├── api/routes/                     # Budget and budget-owned resource endpoints
├── schemas/                        # Pydantic request and response models
├── domain/
│   └── financial_calculations.py   # Decimal-based financial calculations
└── infrastructure/
    ├── database/
    │   ├── config.py               # Environment-based settings
    │   ├── connection.py           # SQLAlchemy engine, Base and session factory
    │   ├── dependencies.py         # Request-scoped DB session and budget ownership check
    │   └── models/                 # SQLAlchemy models
    ├── firebase_auth.py            # Firebase token verification and user synchronization
    └── migration/                  # Explicit Firestore-to-PostgreSQL migration utility

alembic/                            # Versioned database schema migrations
Dockerfile
docker-compose.yml
docker/entrypoint.sh               # Waits for PostgreSQL, migrates, starts Uvicorn
tests/                              # API, auth, ownership, calculation and migration tests
```

A typical request flows from a route through FastAPI dependencies for the authenticated user and database session, then uses SQLAlchemy models and queries. Financial calculations are kept in `app/domain/financial_calculations.py` and use `Decimal` for money calculations.

## Key Features

- REST endpoints for budgets, income, expenses, salary discounts, and overtime entries.
- Firebase ID token verification using `Authorization: Bearer <ID_TOKEN>`.
- User synchronization based on the verified Firebase UID.
- Budget ownership checks for nested resources.
- Pydantic validation at request boundaries.
- PostgreSQL persistence through SQLAlchemy.
- Alembic-managed schema migrations.
- Docker Compose development environment with PostgreSQL and the API.
- Automated pytest coverage for API behavior, authentication, ownership, calculations, and migration logic.
- Detailed overtime entries with date, hours, type, shift, optional time range, and optional description.

## API Documentation

When the API is running, FastAPI's generated documentation is available at:

- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`
- OpenAPI schema: `http://localhost:8000/openapi.json`

These are FastAPI's default documentation routes; the application does not override them.

### Endpoints

`GET /health` is public. The remaining endpoints below require a valid Firebase Bearer token.

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/health` | Public health check. |
| `GET` | `/api/me` | Return the authenticated user. |
| `GET` | `/api/budgets` | List budgets owned by the current user. |
| `POST` | `/api/budgets` | Create a monthly budget. |
| `GET` | `/api/budgets/{budget_id}` | Retrieve an owned budget. |
| `PATCH` | `/api/budgets/{budget_id}` | Update an owned budget. |
| `DELETE` | `/api/budgets/{budget_id}` | Delete an owned budget and its related records. |
| `GET` | `/api/budgets/{budget_id}/incomes` | List income entries for an owned budget. |
| `POST` | `/api/budgets/{budget_id}/incomes` | Create an income entry. |
| `GET` | `/api/budgets/{budget_id}/incomes/{income_id}` | Retrieve an income entry. |
| `PATCH` | `/api/budgets/{budget_id}/incomes/{income_id}` | Update an income entry. |
| `DELETE` | `/api/budgets/{budget_id}/incomes/{income_id}` | Delete an income entry. |
| `GET` | `/api/budgets/{budget_id}/expenses` | List expenses for an owned budget. |
| `POST` | `/api/budgets/{budget_id}/expenses` | Create an expense. |
| `GET` | `/api/budgets/{budget_id}/expenses/{expense_id}` | Retrieve an expense. |
| `PATCH` | `/api/budgets/{budget_id}/expenses/{expense_id}` | Update an expense. |
| `DELETE` | `/api/budgets/{budget_id}/expenses/{expense_id}` | Delete an expense. |
| `GET` | `/api/budgets/{budget_id}/discounts` | List salary discounts for an owned budget. |
| `POST` | `/api/budgets/{budget_id}/discounts` | Create a salary discount. |
| `GET` | `/api/budgets/{budget_id}/discounts/{discount_id}` | Retrieve a salary discount. |
| `PATCH` | `/api/budgets/{budget_id}/discounts/{discount_id}` | Update a salary discount. |
| `DELETE` | `/api/budgets/{budget_id}/discounts/{discount_id}` | Delete a salary discount. |
| `GET` | `/api/budgets/{budget_id}/overtime` | List detailed overtime entries, ordered by date and creation time. |
| `POST` | `/api/budgets/{budget_id}/overtime` | Create an overtime entry. |
| `GET` | `/api/budgets/{budget_id}/overtime/{entry_id}` | Retrieve an overtime entry. |
| `PUT` | `/api/budgets/{budget_id}/overtime/{entry_id}` | Update an overtime entry. |
| `DELETE` | `/api/budgets/{budget_id}/overtime/{entry_id}` | Delete an overtime entry. |

A budget or nested resource that is missing or not owned by the authenticated user returns `404 Not Found`.

## Database and Migrations

PostgreSQL stores users, budgets, incomes, expenses, salary discounts, and individual overtime entries. Financial amounts and overtime hours use PostgreSQL `NUMERIC` columns; calculations use Python `Decimal`.

Notable constraints include:

- one budget per user and month (`user_id`, `month_key`);
- expense type restricted to `fixed` or `other`;
- salary discount percentage between `0` and `100`;
- overtime hours greater than zero, with allowed type and shift values.

Alembic migration files are under `alembic/versions/`. Apply the current schema with:

```bash
alembic upgrade head
```

The Docker API entrypoint also runs `alembic upgrade head` before starting Uvicorn.

## Testing

The test suite uses pytest and includes API CRUD, Firebase authentication, ownership checks, financial calculations, database configuration, and Firestore migration utility tests.

Run the suite from the repository root after configuring a reachable PostgreSQL database:

```bash
python -m pytest -q
```

The CRUD and authentication tests use PostgreSQL. For a repeatable local setup, start the Compose environment first. The latest verified run for this repository state completed with **74 tests passed**.

## Running Locally

### Prerequisites

- Python 3.11 or newer for local execution.
- Docker Desktop or Docker Engine with Docker Compose for the containerized setup.
- PostgreSQL when running the API directly on the host.
- Firebase service-account configuration for authenticated Firebase-backed requests.

### Configure environment variables

Copy the example file:

```powershell
Copy-Item .env.example .env
```

Set local values in `.env`. The settings consumed by the application and Compose include:

| Variable | Purpose |
| --- | --- |
| `DATABASE_URL` | SQLAlchemy PostgreSQL connection URL. |
| `POSTGRES_DB` | PostgreSQL database name. |
| `POSTGRES_USER` | PostgreSQL user. |
| `POSTGRES_PASSWORD` | PostgreSQL password. |
| `POSTGRES_HOST` | PostgreSQL host used by the container entrypoint. |
| `POSTGRES_PORT` | PostgreSQL port. |
| `FIREBASE_PROJECT_ID` | Firebase project identifier. |
| `FIREBASE_CLIENT_EMAIL` | Firebase service-account email. |
| `FIREBASE_PRIVATE_KEY` | Firebase service-account private key. |
| `CORS_ALLOWED_ORIGINS` | Allowed CORS origins; defaults to `http://localhost:4200`. |

The checked-in `.env.example` contains placeholders/default development values only. Never commit a real `.env`, Firebase private key, token, or credential.

### Start with Docker Compose

```bash
docker compose up --build -d
docker compose ps
```

Compose starts two services:

- `db`: PostgreSQL 16 with a persistent named volume and health check.
- `api`: FastAPI on port `8000`; waits for the database, applies Alembic migrations, then starts Uvicorn.

Open `http://localhost:8000/docs` to explore the API. Stop the services with:

```bash
docker compose down
```

### Run the API on the host

Start PostgreSQL and configure `DATABASE_URL` in `.env`, then create a virtual environment and install the development dependencies:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
alembic upgrade head
uvicorn app.main:app --reload
```

On macOS/Linux, activate with `source .venv/bin/activate`. The API listens at `http://127.0.0.1:8000` by default.

### Authentication

Send a Firebase ID token on protected endpoints:

```http
Authorization: Bearer <ID_TOKEN>
```

The server verifies the token with Firebase Admin SDK and derives the user identity from the verified UID. It creates or synchronizes that user in PostgreSQL before handling the request.

## Project Structure

```text
app/
├── api/routes/                   # HTTP endpoints by resource
├── domain/                       # Financial calculation functions
├── infrastructure/
│   ├── database/                 # Settings, SQLAlchemy connection, dependencies, models
│   ├── firebase_auth.py          # Token verification and current-user dependency
│   └── migration/                # Firestore reader, mapping, migration orchestration
├── schemas/                      # Pydantic request/response contracts
└── main.py                       # FastAPI app assembly
alembic/versions/                 # Versioned PostgreSQL migrations
docker/entrypoint.sh               # Container startup and migration sequence
tests/                             # pytest suite
```

## Engineering Notes

- Routes derive the current user from a server-verified Firebase token.
- Budget-owned endpoints check ownership before accessing child resources.
- Pydantic schemas validate incoming values; database constraints provide additional integrity checks where defined.
- SQLAlchemy sessions are request-scoped through FastAPI dependencies.
- Alembic tracks schema changes; Docker startup applies the current revision before launching the API.
- Financial formulas use `Decimal` and are kept in the domain calculation module.
- An explicit Firestore-to-PostgreSQL migration utility exists for supported legacy user and budget records. It is not part of normal API startup.

## Portfolio Context

Plan Gastos API is a hands-on backend portfolio project demonstrating practical work with Python, FastAPI, PostgreSQL, authentication, ownership-aware REST resources, schema validation, migrations, Docker, and automated tests. The repository documents the current implementation and does not claim a production deployment or client engagement.

## GitHub Repository Metadata Proposal

**Description**

> REST API for a personal finance application built with FastAPI, PostgreSQL, SQLAlchemy, and Docker.

**Suggested topics**

`python` · `fastapi` · `postgresql` · `rest-api` · `sqlalchemy` · `alembic` · `docker` · `pytest` · `firebase-auth`
