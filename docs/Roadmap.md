# Dazy.club — Enhancement Roadmap

> **Status: PLANNED, not yet built.** This document captures a full-system gap analysis and the agreed enhancement plan. Nothing here is shipped — for what currently exists, see [Features.md](Features.md) and [API-Reference.md](API-Reference.md). Items move out of this file into the feature docs as they land.

## Why

The pilot outgrew its "public website only" scope into four apps (web / admin / kiosk POS / FastAPI). A full-system exploration found consistent gaps between what the **data model already supports** and what the **UI/endpoints actually expose**, plus missing operator-grade capabilities. Four directions were chosen: POS completeness, business intelligence, booking growth, foundation & security.

## Gap analysis (current shortfalls)

**Cafe POS**
- **Dine-in loop disconnected** — kiosk hardcodes `orderType:"quick"` and never sets `table_id`; the Tables page is decorative; no occupy→settle→free cycle. `orderType` (quick/dine_in/takeaway) and `discountAmount` columns exist in the DB but are unused.
- No order-level discount/comp endpoint (field exists), no receipt/KOT reprint, no table transfer, no split/merge bill, no tips.
- **Inventory fields exist in DB** (`trackInventory`, `currentQty`, `reorderLevel`, `unit`, `purchaseCost`) with **zero UI** and no deduction on sale.
- KDS is single hardcoded station, no per-item status, no prep timers, no bump/recall, no new-order sound.

**Business intelligence**
- Dashboard shows placeholder counts only — no revenue, occupancy, or cafe sales. No aggregation endpoints.
- No CSV/PDF export, no date-range reports, no GST period summary (statutory need), no POS daily-close/Z-report.

**Bookings**
- Payment-decoupled (honor system) — no payment status, deposit, or refund tracking.
- Dead-ends after booking — no customer lookup / "my bookings", no email/SMS confirmation, no cancel/reschedule.
- Admin can't create a manual/phone booking, reschedule, or block 1–2h for maintenance (only whole-day close).
- No CRM (customers table is a phone→name index), no comms (email/SMS/announcements).

**Security / foundation**
- **Cashier PIN login has no rate limiting** (admin login does) — brute-force hole.
- No token refresh, no password reset, no login/audit log, role checks are all-or-nothing.
- Service layer sparse, **no UnitOfWork** — multi-repo flows (order→items→KOT→invoice) aren't atomic.

**Latent bugs found**
- Invoice-number sequence can gap on a crash (`next_number` commits independently of the invoice insert).
- Admin dashboard computes "today" via `new Date().toISOString()` (UTC), not venue tz (Asia/Kolkata IST) — so "bookings today" is wrong for the 00:00–05:29 IST window.

## Planned phases

Single linear Alembic chain after current head `e1f2a3b4c5d6`: m1 audit_log → m2 stock_movements → m3 order discount/comp → m4 booking payment → m5 booking holdType → m6 notifications_log → m7 customer CRM.

| Phase | Theme | Highlights |
|-------|-------|-----------|
| **1** | Security + quick wins | Cashier PIN rate-limit, audit log + hooks, token refresh, password reset; inventory admin UI + void-reason UI (both use existing DB fields — no schema) |
| **2** | Business intelligence | `reporting_repo` + `analytics_service`; real dashboard (revenue/occupancy/alerts + 7-day trend via inline SVG); reports (revenue/occupancy/top-items/funnel/GST/Z-report); server-side CSV export |
| **3** | POS completeness | Stock movement log + auto-deduct on invoice; order discount/comp (tax-correct); **dine-in table loop** (toggle + table picker + occupy→free); receipt/KOT reprint; table transfer |
| **4** | Booking growth | Booking payment status + deposit/refund (behind a payment adapter); customer "my bookings" lookup + cancel/reschedule request; admin manual booking + reschedule + maintenance block |
| **5** | CRM + comms | Notification adapter (booking confirm/remind, enquiry reply) + delivery log; admin CRM customers page (history, lifetime spend, segments, do-not-contact) |
| **6** | Foundation | Service layer + UnitOfWork so order→items→KOT→invoice is atomic (fixes the invoice-sequence-gap bug). Highest regression risk — done last |

## Design principles

- **Adapters for external services** — payment and notifications sit behind provider interfaces with dev no-op/console implementations; real Razorpay/SMTP/Twilio pluggable via env (`DAZY_PAYMENT_PROVIDER`, `DAZY_NOTIFY_PROVIDER`).
- **DB stays swappable** — SQLite → PostgreSQL via `DAZY_DB_URL`.
- **Backward-compatible refactors** — UnitOfWork uses an optional injected `session=None`; existing repo callers unchanged.
- **Tests stay green** — every phase extends pytest + Playwright; migrations verified with an upgrade→downgrade→upgrade round-trip.

## Deferred (documented, not planned for these phases)

Split/merge bills; full self-service reschedule; sub-day schedule exceptions; live payment gateway + SMS/email provider wiring; scheduled reminder cron; fine-grained per-page RBAC; multi-venue UI; cash-drawer/shift sessions; offline-first kiosk; direct thermal/ESC-POS printing.
