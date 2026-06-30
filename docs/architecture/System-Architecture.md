# System Architecture

## Current (pilot)

```
┌─────────────────────┐   ┌─────────────────────┐
│  apps/web (:5173)   │   │  apps/admin (:5174)  │
│  React + Vite       │   │  React + Vite        │
│  Public booking UI  │   │  Admin portal        │
└────────┬────────────┘   └──────────┬───────────┘
         │                           │
         └─────────┬─────────────────┘
                   ▼ HTTP REST
         ┌─────────────────────┐
         │  apps/api (:8000)   │
         │  FastAPI + Python   │
         │  Pydantic v2        │
         │  SQLAlchemy 2.0     │
         └────────┬────────────┘
                  ▼
         ┌─────────────────────┐
         │  dazy.db (SQLite)   │
         │  Alembic migrations │
         └─────────────────────┘

packages/shared  →  TypeScript types shared by web + admin
```

## Future (production)

- SQLite → **PostgreSQL** (change `DAZY_DB_URL`, zero app code changes)
- Local `/media/` → **S3 / CDN** for gallery images
- Add **Redis** for slot locking (high concurrency)
- Add background jobs for booking confirmation emails/SMS
- Multi-venue: Venue entity already in schema; add venue selector to web
