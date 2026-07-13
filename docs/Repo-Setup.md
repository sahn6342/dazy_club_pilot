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
# Four apps (separate terminals)
pnpm dev:web          # http://localhost:5173  (customer booking site)
pnpm dev:admin        # http://localhost:5174  (staff back-office)
pnpm dev:kiosk        # http://localhost:5175  (cafe POS + KDS)
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
# Backend suite
cd apps/api && .venv/Scripts/python.exe -m pytest tests -q

# E2E (requires all 3 servers running)
pnpm e2e
```

## Env vars (`apps/api/.env`, loaded via python-dotenv — gitignored, never committed)

```
DAZY_DB_URL=sqlite:///./dazy.db
ADMIN_USERNAME=admin
ADMIN_PASSWORD=admin
JWT_SECRET=changeme

# Payment (dev default noop — no real gateway needed to exercise the flow)
DAZY_PAYMENT_PROVIDER=noop             # or razorpay
RAZORPAY_KEY_ID=
RAZORPAY_KEY_SECRET=
RAZORPAY_WEBHOOK_SECRET=

# Notifications (dev default console — prints to stdout)
DAZY_NOTIFY_PROVIDER=console           # or email
SMTP_HOST=
SMTP_PORT=587
SMTP_USER=
SMTP_PASSWORD=

DAZY_WEB_BASE_URL=http://localhost:5173  # used in notification links (e.g. /my-bookings resume)
```

> pytest force-pins `DAZY_PAYMENT_PROVIDER=noop` / `DAZY_NOTIFY_PROVIDER=console` in `conftest.py` regardless of `.env` — the automated suite never makes real Razorpay/SMTP calls.

## Seeded data

`seed_if_empty()` runs on API startup and populates:
- 1 venue (`venue-dazy`)
- 3 courts (`court-cricket`, `court-badminton`, `court-pickleball`)
- 63 schedule rules (3 time blocks × 7 days × 3 courts → 12 slots/day/court)
- Gallery items, testimonials, CMS entries
- Promos: `WELCOME10` (10% off), `FLAT100` (₹100 off)
