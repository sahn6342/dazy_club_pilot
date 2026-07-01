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
| Pricing | `services/pricing_service.py` | Promo validation + Decimal money math |
| Cafe POS | `services/pos_service.py` | Order creation, KOT station routing, payments, GST invoice orchestration |
| Route namespaces | `routes/admin/`, `routes/cafe/` | Admin (Bearer admin) and cafe/POS (Bearer cashier) endpoint groups; cafe repos: menu/order/kot/payment/invoice/table/settings |

## Cross-cutting
- CORS: allows web (:5173), admin (:5174), and kiosk (:5175)
- Auth: `get_current_admin` (password login) guards admin routes; `get_current_cashier` (cashier/kitchen/manager/admin, 4-digit PIN) guards cafe routes; invoice print endpoint is public (unguessable UUID)
- GZip middleware on all responses
- Rate limiter on `/admin/login` (per-IP sliding window)
- Pydantic auto-validates → 422 on bad input
- OpenAPI UI at `/docs`, ReDoc at `/redoc`
- All errors: `{"detail": "message"}` format
