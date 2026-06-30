# Repo Setup

## Prerequisites
- Node 20+, pnpm 9+
- Python 3.12+, uv

## Install

```bash
# Frontend deps
pnpm install

# Backend deps
cd apps/api
uv sync
```

## Run

```bash
# All three (separate terminals)
pnpm dev:web          # http://localhost:5173
pnpm dev:admin        # http://localhost:5174
cd apps/api && .venv/Scripts/python.exe -m uvicorn main:app --reload --port 8000
```

## DB migrations

```bash
cd apps/api
uv run alembic upgrade head      # apply all migrations
uv run alembic revision --autogenerate -m "description"  # new migration
```

## Tests

```bash
# Backend (278 tests)
cd apps/api && .venv/Scripts/python.exe -m pytest tests -q

# E2E (requires all 3 servers running)
pnpm e2e
```

## Env vars (`.env` at repo root or `apps/api/.env`)

```
DAZY_DB_URL=sqlite:///./dazy.db
ADMIN_USERNAME=admin
ADMIN_PASSWORD=admin
JWT_SECRET=changeme
```

## Seeded data

`seed_if_empty()` runs on API startup and populates:
- 1 venue (`venue-dazy`)
- 3 courts (`court-cricket`, `court-badminton`, `court-pickleball`)
- 63 schedule rules (3 time blocks × 7 days × 3 courts → 12 slots/day/court)
- Gallery items, testimonials, CMS entries
- Promos: `WELCOME10` (10% off), `FLAT100` (₹100 off)
