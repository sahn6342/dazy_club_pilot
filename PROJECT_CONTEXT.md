# Dazy.club Project Context

## Product
Dazy.club is a premium sports-venue platform for **Cricket, Badminton, and Pickleball**. It has grown beyond its original "public website only" launch into a full venue operating system spanning four apps:

- **Web** — public booking website + enquiry capture.
- **Admin** — staff back-office: bookings, scheduling, content, cafe menu/orders, users.
- **Kiosk** — cafe POS with GST billing + a Kitchen Display System (KDS).
- **API** — FastAPI backend powering all of the above.

## Current Scope (shipped)
- **Public booking** — sport → date → live availability slots → multi-slot booking with party size, price, and promo codes.
- **Enquiries** — general + corporate/event.
- **Admin back-office** — booking management, data-driven scheduling (weekly rules + venue-wide/per-court holiday exceptions), courts, promos, CMS, gallery (with upload), testimonials, users/roles, enquiry triage.
- **Cafe POS** — cashier PIN login, menu + cart, cash/UPI/card payments, **GST invoices** (CGST/SGST, financial-year numbering, amount-in-words, 80mm thermal print), order history, table status.
- **Kitchen Display System** — station-routed KOTs (kitchen/bar) with live polling and prepare/ready flow.

> The original "deferred" list (live booking, payment, full admin CMS, cafe) is now **built**. OTP/SMS auth and a public payment gateway remain out of scope for this pilot.

## Architecture
- **Monorepo** (pnpm): `apps/web`, `apps/admin`, `apps/kiosk`, `apps/api`, `packages/ui`, `packages/shared`, `packages/config`, `infra`, `docs`.
- **Frontends**: React 18, Vite, TypeScript, React Router, plain CSS (dark gold-accent theme). Three separate SPAs (web/admin/kiosk).
- **Backend**: FastAPI (Python 3.12), Pydantic v2, SQLAlchemy 2.0 (sync), Alembic — see [ADR-011](docs/adr/ADR-011-Backend-FastAPI.md). **Not .NET.**
- **Database**: SQLite by default, swappable to PostgreSQL via `DAZY_DB_URL` with zero repo changes.
- **Auth**: JWT — admin password login + cashier 4-digit PIN. Roles: admin / manager / cashier / kitchen.
- **Testing**: pytest (backend) + Playwright E2E (web / admin / kiosk).

## Roadmap
**[docs/Detailed-Roadmap.md](docs/Detailed-Roadmap.md)** is the authoritative, launch-sequenced build plan — production hardening and Docker deploy first, then café GST correctness, then online prepay (Razorpay), then owner visibility and customer confirmation, then 🚀 go-live, then a growth track. It re-sequences [docs/Roadmap.md](docs/Roadmap.md) (the fuller gap analysis) for the real launch context: counter/takeaway-only café, prepay-from-day-one bookings, weeks-not-months MVP.

## Working Rule
Read this file, [README.md](README.md), [docs/Features.md](docs/Features.md), [docs/API-Reference.md](docs/API-Reference.md), [docs/Detailed-Roadmap.md](docs/Detailed-Roadmap.md), and [docs/Decision-Log.md](docs/Decision-Log.md) before design or code work. Do not invent requirements that conflict with these docs.
