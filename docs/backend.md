# Backend Quick Reference

FastAPI (Python 3.12) + Pydantic v2 + SQLAlchemy 2.0 (sync) + Alembic + SQLite. JWT auth (admin password + cashier 4-digit PIN). Serves all three frontends: public bookings + enquiries, admin CRUD (bookings/schedule/courts/promos/CMS/gallery/testimonials/users), and cafe POS (orders, KOT routing, payments, GST invoices, KDS).

See `docs/API-Reference.md` for the full endpoint list, data model, and business logic.
See `docs/CONTEXT.md` for product/domain context.
See `docs/architecture/Backend-Architecture.md` for layer structure.
See `apps/api/` for source code.
