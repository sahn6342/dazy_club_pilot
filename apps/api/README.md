# Dazy.club API

FastAPI backend powering all three Dazy.club frontends — the public booking website, the staff admin back-office, and the cafe POS/KDS kiosk. SQLAlchemy 2.0 over SQLite (swappable to PostgreSQL via `DAZY_DB_URL`), Alembic migrations, JWT auth.

## Dev

```bash
# Requires Python 3.12+ and uv (https://docs.astral.sh/uv/)
uv sync
uv run uvicorn main:app --reload --port 8000
```

Or from repo root: `pnpm api:dev`

The server auto-migrates to the Alembic head and seeds demo data into empty tables on first boot. Auto OpenAPI docs at `http://localhost:8000/docs`.

## Endpoints
~70 routes across public, admin, and cafe/POS surfaces — full reference (with auth, data model, migrations, and business logic) in [docs/API-Reference.md](../../docs/API-Reference.md). Highlights: public booking + enquiries + availability slots, admin CRUD for bookings/schedule/courts/promos/CMS/gallery/testimonials/users, and cafe POS orders/KOTs/payments/GST invoices.

## Tests

```bash
.venv/Scripts/python -m pytest tests -q   # or: uv run pytest tests -q
```

## Docker

Standalone image (for local testing — `uv.lock` must be in the build context):

```bash
docker build -t dazy-api .
docker run -p 8000:8000 -e JWT_SECRET=dev-secret dazy-api
```

Full production stack (this API + all three frontends + Caddy HTTPS): see [docs/Docker-Deployment.md](../../docs/Docker-Deployment.md).
