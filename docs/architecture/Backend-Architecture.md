# Backend Architecture

## Stack
- FastAPI (Python 3.12) — see ADR-011.
- Pydantic v2 for validation.
- uvicorn ASGI server.
- SQLAlchemy (async) + asyncpg with PostgreSQL (Phase 2).
- Alembic for migrations (Phase 2).

## Launch Modules
- Public Content.
- Sports.
- Gallery.
- Testimonials.
- Notifications.
- Leads.
- Corporate Enquiries.
- Audit foundation.

## Deferred Modules
- Availability.
- Booking.
- Pricing.
- Payment.
- OTP/Auth.
- CRM automation.
- CMS workflows.

## Cross-Cutting
- OpenAPI.
- Validation pipeline.
- Central exception handling.
- Structured logging.
- CORS for web/admin apps.
- Environment-based configuration.
