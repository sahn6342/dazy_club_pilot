# Decision Log

| ID | Decision | Status |
|---|---|---|
| DEC-001 | Documentation-first AI workflow | Superseded (docs pruned) |
| DEC-002 | Figma-first design | Skipped (went straight to code) |
| DEC-003 | pnpm monorepo | Accepted |
| DEC-004 | ASP.NET Core 9 backend | Superseded by DEC-011 |
| DEC-005 | React + Vite + TypeScript (web/admin) | Accepted |
| DEC-006 | PostgreSQL primary DB | Deferred — using SQLite for pilot |
| DEC-007 | Defer payment provider | Accepted |
| DEC-008 | Defer OTP/SMS provider | Accepted |
| DEC-009 | Launch without live booking | Superseded — booking is live |
| DEC-010 | Seeded demo content | Accepted |
| DEC-011 | FastAPI (Python 3.12) replaces ASP.NET | Accepted — see ADR-011 |
| DEC-012 | Resource-scheduling domain model | Accepted — see ADR-012 |
| DEC-013 | JWT auth: env-var admin + DB managers; cashier/kitchen via 4-digit PIN | Accepted |
| DEC-014 | SQLite for pilot, swap via DAZY_DB_URL | Accepted |
| DEC-015 | Soft-delete courts; slot IDs include court.id | Accepted |
| DEC-016 | Venue-wide exceptions via court_id=NULL | Accepted |
| DEC-017 | Café POS + GST billing + kiosk app (menu/orders/KOT/payments/invoices/KDS) | Accepted — implemented (Phases 0–1; ADR-012 chain; see Cafe-POS-Plan.md) |
| DEC-018 | In-app ConfirmDialog (`useConfirm`) replaces `window.confirm` in admin | Accepted — implemented |
| DEC-019 | Multi-slot booking + capacity-aware unique index (race-safe) | Accepted — implemented |
| DEC-020 | Gallery images via `imageUrl` (URL or `/media` upload); DB-driven public gallery | Accepted — implemented |

### Planned (enhancement roadmap — see [Roadmap.md](Roadmap.md), not yet built)

| ID | Decision | Status |
|---|---|---|
| DEC-021 | Cancellation window stored as CMS key (`booking_cancel_window_hours`), not a new table | Planned |
| DEC-022 | Public reschedule is request-only in v1 (admin actions it); full self-service deferred | Planned |
| DEC-023 | Maintenance block = booking row + `holdType` (excluded from CRM/revenue), not sub-day exceptions | Planned |
| DEC-024 | Reporting via dedicated `reporting_repo` + `analytics_service`; CSV export server-side (stdlib) | Planned |
| DEC-025 | UnitOfWork = optional injected `session=None`; `with _session()` stays default (backward-compatible) | Planned — resolves service-layer/UoW task |
| DEC-026 | Payment + notifications behind provider adapters with dev no-op/console impls (extends DEC-007/008) | Planned |
| DEC-027 | Booking payment status (unpaid/deposit/paid/refunded) tracked; pay-at-venue stays default | Planned |

## Open
- Production hosting / deployment provider
- PostgreSQL migration timeline
- Payment provider selection (Razorpay vs alternatives)
- SMS/OTP + email provider selection (Twilio/MSG91/SMTP)
- Enhancement roadmap phase sequencing / go-live scope (see Roadmap.md)
- Final brand assets (logo, copy, photos)
