# Backend Architecture

## Stack
- **FastAPI** (Python 3.12) + Pydantic v2 + uvicorn
- **SQLAlchemy 2.0** (sync) + **Alembic** for migrations
- **SQLite** (`dazy.db`) — swap to PostgreSQL via `DAZY_DB_URL`
- **uv** as Python package manager

## Layer structure

```
Route handler (thin)
    ↓
Service layer (business rules: availability, booking, promo calc)
    ↓
Repository (data access only — one class per entity)
    ↓
SQLAlchemy session (db.py _session context manager)
    ↓
SQLite / PostgreSQL
```

## Key modules

| Module | Location | Responsibility |
|---|---|---|
| App bootstrap | `main.py` | Router registration, CORS, GZip, media static mount |
| Models | `models.py` | All Pydantic DTOs |
| DB models | `db_models.py` | SQLAlchemy ORM row classes |
| DB init | `db.py` | Engine, session, `init_db()`, `seed_if_empty()` |
| Dependencies | `deps.py` | Singleton repo instances wired to routes |
| Auth | `auth.py` | JWT encode/decode, `get_current_admin` dependency |
| Availability | `services/availability_service.py` | Slot generation from rules + exceptions |
| Booking | `services/booking_service.py` | Create booking, concurrency guard (409) |

## Cross-cutting
- CORS: allows web (:5173) and admin (:5174)
- GZip middleware on all responses
- Rate limiter on `/admin/login` (5 attempts per IP)
- Pydantic auto-validates → 422 on bad input
- OpenAPI UI at `/docs`, ReDoc at `/redoc`
- All errors: `{"detail": "message"}` format
