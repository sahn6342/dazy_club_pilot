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
| DEC-028 | Production deploy: single Docker Compose stack — Caddy edge (auto-HTTPS) + api + 3 static Vite frontends + one `/data` volume (SQLite + media) | Accepted — implemented; see [Docker-Deployment.md](Docker-Deployment.md) |
| DEC-029 | Cashier PIN login rate-limited (shared `SlidingWindowLimiter`, extracted from the admin-login limiter) | Accepted — implemented |
| DEC-030 | Frontend API base URL (admin/kiosk) and backend CORS origins made env-configurable at build/deploy time | Accepted — implemented (previously hardcoded to `localhost:8000`/`:5173-5175` — a launch-blocking bug) |
| DEC-031 | Password-strength rule (manager 8+ chars / staff 4-digit PIN) enforced on user *update*, not just create | Accepted — implemented (fixed a bypass) |
| DEC-032 | Invoice numbering made atomic: `next_number()` runs inside `invoice_repo.create()`'s own session (optional injected `session=`, DEC-025's pattern) instead of a separate commit | Accepted — implemented (Detailed-Roadmap Phase 2; closes the gap-on-crash bug noted in [Roadmap.md](Roadmap.md)) |

### Launch sequencing (see [Detailed-Roadmap.md](Detailed-Roadmap.md) — supersedes the ordering below, not the content)

| ID | Decision | Status |
|---|---|---|
| DEC-021 | Cancellation window stored as CMS key (`booking_cancel_window_hours`), not a new table | Planned |
| DEC-022 | Public reschedule is request-only in v1 (admin actions it); full self-service deferred | Planned |
| DEC-023 | Maintenance block = booking row + `holdType` (excluded from CRM/revenue), not sub-day exceptions | Planned — post-launch (dine-in is out of scope for a counter/takeaway-only launch) |
| DEC-024 | Reporting via dedicated `reporting_repo` + `analytics_service`; CSV export server-side (stdlib) | Planned — dashboard + Z-report slice pulled forward to launch-important (Detailed-Roadmap Phase 4); full report suite + CSV stays growth-track |
| DEC-025 | UnitOfWork = optional injected `session=None`; `with _session()` stays default (backward-compatible) | Planned — a **targeted** version (invoice issuance only) is a launch-blocker (Detailed-Roadmap Phase 2); the full order→items→KOT→invoice refactor stays growth-track |
| DEC-026 | Payment + notifications behind provider adapters with dev no-op/console impls (extends DEC-007/008) | Planned — payment adapter (Razorpay) is now a launch-blocker (Detailed-Roadmap Phase 3), not growth-track |
| DEC-027 | Booking payment status (unpaid/deposit/paid/refunded) tracked; pay-at-venue stays default | Superseded — bookings take **online prepay from day one** (Detailed-Roadmap Phase 3), not pay-at-venue |

## Open
- Production hosting / deployment provider (VPS choice) — Docker/Caddy stack ready, VPS not yet provisioned
- PostgreSQL migration timeline
- Razorpay KYC (external — gates Detailed-Roadmap Phase 3)
- CA decisions: café GST scheme, whether turf bookings need a GST invoice
- SMS/OTP + email provider selection (Twilio/MSG91/SMTP) — gates Phase 5 (customer confirmation)
- Final brand assets (logo, copy, photos)
