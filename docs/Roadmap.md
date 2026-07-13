# Dazy.club — Enhancement Roadmap

> **Status: partially superseded.** This is the original gap-analysis-driven roadmap (6 phases, growth-first sequencing). **[Detailed-Roadmap.md](Detailed-Roadmap.md) re-sequences this for the actual launch context** (counter-only café, online prepay from day one, MVP-in-weeks) — treat that doc as authoritative for what to build next; this one remains as the fuller gap analysis and the source for later growth-track detail. For what currently exists, see [Features.md](Features.md) and [API-Reference.md](API-Reference.md). Items move out of this file into the feature docs as they land.

## Why

The pilot outgrew its "public website only" scope into four apps (web / admin / kiosk POS / FastAPI). A full-system exploration found consistent gaps between what the **data model already supports** and what the **UI/endpoints actually expose**, plus missing operator-grade capabilities. Four directions were chosen: POS completeness, business intelligence, booking growth, foundation & security.

## Gap analysis (current shortfalls)

**Cafe POS**
- **Dine-in loop disconnected** — kiosk hardcodes `orderType:"quick"` and never sets `table_id`; the Tables page is decorative; no occupy→settle→free cycle. `orderType` (quick/dine_in/takeaway) and `discountAmount` columns exist in the DB but are unused.
- No order-level discount/comp endpoint (field exists), no receipt/KOT reprint, no table transfer, no split/merge bill, no tips.
- **Inventory fields exist in DB** (`trackInventory`, `currentQty`, `reorderLevel`, `unit`, `purchaseCost`) with **zero UI** and no deduction on sale.
- KDS is single hardcoded station, no per-item status, no prep timers, no bump/recall, no new-order sound.

**Business intelligence**
- ~~Dashboard shows placeholder counts only — no revenue, occupancy, or cafe sales. No aggregation endpoints.~~ **Closed** in Detailed-Roadmap Phase 4 — real KPIs (`reporting_repo`, `analytics_service`) + day-close (Z-report by payment mode). Still open: 7-day trend, CSV/PDF export, date-range reports, GST period summary — growth-track Phase 9.

**Bookings**
- ~~Payment-decoupled (honor system) — no payment status, deposit, or refund tracking.~~ **Closed** in Detailed-Roadmap Phase 3 — Razorpay/noop adapter, `paymentStatus`, admin refund endpoint.
- Dead-ends after booking — ~~no customer lookup / "my bookings", no email/SMS confirmation~~ **closed** (self-service `/bookings/lookup` + `/my-bookings` page; email/console notifications on confirm + payment-pending). Still open: cancel/reschedule request.
- Admin can't create a manual/phone booking, reschedule, or block 1–2h for maintenance (only whole-day close).
- No CRM (customers table is a phone→name index), no comms beyond booking-lifecycle notifications (no enquiry-reply, no announcements).

**Security / foundation**
- ~~Cashier PIN login has no rate limiting~~ (admin login does) — brute-force hole. **Closed** — see DEC-029 (shared `SlidingWindowLimiter`).
- No token refresh, no password reset, no login/audit log (table scaffolded, unwired), role checks are all-or-nothing.
- Service layer sparse, **no UnitOfWork** — multi-repo flows (order→items→KOT→invoice) aren't atomic (the invoice-issuance slice was made atomic — DEC-032 — the rest is still open).

**Latent bugs found**
- ~~Invoice-number sequence can gap on a crash (`next_number` commits independently of the invoice insert).~~ **Fixed** in Detailed-Roadmap Phase 2 — see DEC-032.
- ~~Admin dashboard computes "today" via `new Date().toISOString()` (UTC), not venue tz (Asia/Kolkata IST) — so "bookings today" is wrong for the 00:00–05:29 IST window.~~ **Fixed** in Detailed-Roadmap Phase 4 — see DEC-033.

## Planned phases

Single linear Alembic chain after current head `e1f2a3b4c5d6`: m1 audit_log → m2 stock_movements → m3 order discount/comp → m4 booking payment → m5 booking holdType → m6 notifications_log → m7 customer CRM.

> This 6-phase sequencing was superseded by [Detailed-Roadmap.md](Detailed-Roadmap.md) before most of it was built — actual delivery order and phase numbers differ. Status noted per row below; unmarked items are still open.

| Phase | Theme | Highlights |
|-------|-------|-----------|
| **1** | Security + quick wins | Cashier PIN rate-limit ✅, audit log (table scaffolded, hooks/UI not wired), token refresh, password reset; inventory admin UI + void-reason UI (both use existing DB fields — no schema) |
| **2** | Business intelligence | ✅ **Dashboard + Z-report shipped** (Detailed-Roadmap Phase 4: `reporting_repo` + `analytics_service`, real KPIs + day-close by payment mode). Still open: 7-day trend, top-items/funnel/GST reports, server-side CSV export — growth-track |
| **3** | POS completeness | Stock movement log + auto-deduct on invoice; order discount/comp (tax-correct); **dine-in table loop** (toggle + table picker + occupy→free); receipt/KOT reprint; table transfer — all still open (counter/takeaway-only launch deprioritized dine-in) |
| **4** | Booking growth | ✅ **Payment status + refund shipped** (Detailed-Roadmap Phase 3, Razorpay/noop adapter). ✅ **Customer "my bookings" lookup shipped** (self-service `/bookings/lookup` + resume). Still open: cancel/reschedule request, admin manual booking + reschedule + maintenance block |
| **5** | CRM + comms | ✅ **Notification adapter + delivery log shipped** (Detailed-Roadmap Phase 5: console/email, fires on booking confirm + payment-pending). Still open: enquiry-reply notifications, admin CRM customers page (history, lifetime spend, segments, do-not-contact) |
| **6** | Foundation | Service layer + UnitOfWork so order→items→KOT→invoice is atomic. The **invoice-issuance slice only** was made atomic (DEC-032/DEC-025) — the full order→items→KOT→invoice UnitOfWork is still open, highest regression risk, done last |

## Design principles

- **Adapters for external services** — payment and notifications sit behind provider interfaces with dev no-op/console implementations; real Razorpay/SMTP/Twilio pluggable via env (`DAZY_PAYMENT_PROVIDER`, `DAZY_NOTIFY_PROVIDER`).
- **DB stays swappable** — SQLite → PostgreSQL via `DAZY_DB_URL`.
- **Backward-compatible refactors** — UnitOfWork uses an optional injected `session=None`; existing repo callers unchanged.
- **Tests stay green** — every phase extends pytest + Playwright; migrations verified with an upgrade→downgrade→upgrade round-trip.

## Deferred (documented, not planned for these phases)

Split/merge bills; full self-service reschedule; sub-day schedule exceptions; SMS provider wiring (live payment gateway + email provider **are** wired — see Detailed-Roadmap Phases 3/5); scheduled reminder cron; fine-grained per-page RBAC; multi-venue UI; cash-drawer/shift sessions; offline-first kiosk; direct thermal/ESC-POS printing.
