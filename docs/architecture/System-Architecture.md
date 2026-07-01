# System Architecture

## Current (pilot)

```
┌────────────────────┐  ┌────────────────────┐  ┌────────────────────┐
│  apps/web (:5173)  │  │ apps/admin (:5174) │  │ apps/kiosk (:5175) │
│  React + Vite      │  │  React + Vite      │  │  React + Vite      │
│  Public booking UI │  │  Staff back-office │  │  Cafe POS + KDS    │
└────────┬───────────┘  └─────────┬──────────┘  └─────────┬──────────┘
         │                        │                       │
         └────────────┬───────────┴───────────────────────┘
                      ▼ HTTP REST
         ┌──────────────────────────────┐
         │  apps/api (:8000)            │
         │  FastAPI + Pydantic v2       │
         │  SQLAlchemy 2.0 + Alembic    │
         │  bookings · scheduling ·     │
         │  admin CRUD · cafe POS/GST   │
         └────────┬─────────────────────┘
                  ▼
         ┌─────────────────────┐
         │  dazy.db (SQLite)   │
         │  Alembic migrations │
         └─────────────────────┘

packages/shared  →  TypeScript types shared by web + admin + kiosk
```

## Future (production)

- SQLite → **PostgreSQL** (change `DAZY_DB_URL`, zero app code changes)
- Local `/media/` → **S3 / CDN** for gallery images
- Add **Redis** for slot locking (high concurrency)
- Add background jobs for booking confirmation emails/SMS
- Multi-venue: Venue entity already in schema; add venue selector to web
