# Backend Agent Instructions

## Context
Read `docs/API-Reference.md` (full endpoint list, 23-table data model, migrations, business logic) and `docs/CONTEXT.md` (product/domain context) before making any changes. The backend now spans bookings, scheduling, admin CRUD, and cafe POS (orders/KOT/payments/GST invoices) — not just seed content.

## Rules
1. Routes are thin — business logic goes in `services/`, data access in `repositories/`
2. All Pydantic models go in `models.py` — suffix `Dto` for responses, `Create`/`Update` for inputs
3. Use `with _session() as s:` pattern (from `db.py`) for all DB access — auto-commit/rollback
4. Add `s.flush()` before returning inside `_session` block (no explicit commit needed)
5. New routes: register in `main.py` via `app.include_router()`
6. Auth: use `Depends(get_current_admin)` on all admin endpoints; `Depends(require_superadmin)` for user management only
7. Soft-delete pattern: set `active=False`, never `DELETE` rows for business entities
8. New DB columns: create Alembic migration with `op.batch_alter_table(..., recreate="always")` for SQLite
9. Tests: add to `apps/api/tests/`; `conftest.py` autouse fixture resets all repos + re-seeds each test
10. Slot IDs: format `slot-{court.id}-{date}-{HHMM}` — do not change

## Common patterns
```python
# Route
@router.post("/admin/thing", response_model=ThingDto, status_code=201)
def create_thing(data: ThingCreate, _=Depends(get_current_admin)):
    return thing_repo.create(...)

# Repo method
def create(self, ...) -> ThingRow:
    with _session() as s:
        row = ThingRow(id=str(uuid.uuid4()), ...)
        s.add(row); s.flush(); return row
```
