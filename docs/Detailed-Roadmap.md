# Dazy.club — Detailed Implementation Roadmap

> Phase-by-phase build plan to launch and then grow revenue at the venue.
> **Re-sequences the existing `Roadmap.md`** for the launch reality: café is **counter/takeaway only**, bookings take **online prepay from day one**, target is **MVP in weeks**, focus is **customers + owner**.
> Conventions for every phase: new migrations chain **after head `e1f2a3b4c5d6`**; follow `Naming-Standards.md` (snake_case tables, camelCase columns, `…Row` classes, kebab-case routes under `/api/v1`, `Dto`/`Create`/`Update`); **all existing tests stay green**; migrations must round-trip (upgrade→downgrade→upgrade); **don't touch turf/booking code paths** except where a phase says so.

---

## What changed vs the current `Roadmap.md`

Your existing 6-phase enhancement roadmap was written before the launch context. Three deliberate re-sequences:

1. **Booking payment moved from Phase 4 → launch-blocker (Phase 3 here).** You chose online prepay from day one, so Razorpay is now critical path, not a growth item.
2. **Invoice-sequence atomicity moved from Phase 6 → launch-blocker (Phase 2 here).** You can't issue gap-free GST invoices at volume without it; a targeted fix (not the full UnitOfWork refactor) ships now.
3. **Café completeness (dine-in loop, table transfer, inventory UI) pushed to post-launch.** Counter/takeaway-only means the disconnected dine-in loop is out of scope for launch — real work you don't have to do yet.
   Meanwhile the **owner-BI slice** (dashboard numbers + Z-report) is pulled *forward* because owner visibility is a launch priority.

---

## Phase summary

| Phase | Focus | Type | Key dependency |
|---|---|---|---|
| **1** | Production hardening & deploy | 🔴 Launch-blocker | VPS + domain |
| **2** | Café GST correctness | 🔴 Launch-blocker | CA scheme decision |
| **3** | Booking online prepay (Razorpay) | 🔴 Launch-blocker | Razorpay KYC · CA turf-GST answer |
| **4** | Owner visibility (dashboard + Z-report) | 🟠 Launch-important | none (parallel with 3) |
| **5** | Customer confirmation (SMS/email) | 🟠 Launch-important | notification provider (fires after 3) |
| — | **🚀 GO LIVE** | — | — |
| **6** | Off-peak / peak pricing | 🟢 Growth | none |
| **7** | Café × turf synergy (pre-order + wallet) | 🟢 Growth | 3, 6 |
| **8** | Memberships / prepaid packs + loyalty | 🟢 Growth | 7 (wallet) |
| **9** | Ops & BI depth + foundation | 🟢 Growth | none |
| **10** | Retention & scale | 🟢 Growth | usage/scale signals |

**Critical path:** Phase 3 (Razorpay) — largest build + external KYC dependency. Phases 4 and 5 can run in parallel with it. Phases 1–2 come first and can overlap.

---

# LAUNCH TRACK

## Phase 1 — Production hardening & deploy 🔴

**Goal:** the current app running live on HTTPS with persistent data, secured, and free of demo content.

**Data model / migrations:** none.

**Backend**
- Add a per-IP sliding-window rate limiter to `POST /cafe/login`, mirroring the existing `/admin/login` limiter (reuse the same utility). Return `429` after N attempts.
- Confirm `/media` uploads and `dazy.db` write to a path inside the mounted volume (`/data`); adjust the media dir if it's hardcoded.

**Infra / ops**
- Deploy via the Docker setup (`Docker-Deployment.md`): compose, Caddy auto-HTTPS, `api_data` volume, scheduled `dazy.db` + media backups.
- Rotate `JWT_SECRET`, `ADMIN_USERNAME`, `ADMIN_PASSWORD` off defaults; set real CORS origins for the production domains.

**Content**
- Replace/remove seeded demo data: real menu (café), real gallery photos, real or removed testimonials, real promo codes (drop `WELCOME10`/`FLAT100`), real venue details in CMS. Remove the `admin`/`admin` default account.

**Tests:** PIN endpoint returns `429` after the threshold; existing suite green; production smoke test (health, one booking read, one café read).

**Acceptance:** app reachable on HTTPS at all four hostnames; data survives `docker compose down && up`; cashier PIN is throttled; no demo content visible.

**Out of scope:** any feature work.

---

## Phase 2 — Café GST correctness 🔴

**Goal:** legally correct, gap-free café GST invoices.

**Data model / migrations:** none new (fields already exist on `cafe_settings`).

**Backend**
- Populate `cafe_settings`: scheme (`regular` / `composition` / `unregistered`, per CA), real **GSTIN** + **FSSAI number**, state code, `priceIncludesTax`, invoice series/prefix, declaration/footer.
- **Verify/fix per-line tax:** invoice tax must be computed from each `order_items.taxRatePercent`, summed per line, then rounded — not a single flat settings rate on the total (needed for mixed-rate bills, e.g. 5% food + 18% packaged).
- **Invoice-atomicity fix (targeted UnitOfWork):** wrap the sequence increment + `invoices` insert + `invoice_lines` insert + order-status update in **one `_session` transaction**, using the DEC-025 optional-injected-`session` pattern so existing callers are unchanged. This closes the gap-on-crash bug.
- Thermal template (`GET /cafe/invoices/{id}/print`): render **FSSAI number**, a **rate-wise tax summary** block, and switch title `Tax Invoice` / `Bill of Supply` by scheme.

**Tests:** mixed-rate bill computes correct per-line CGST/SGST + totals; invoice numbering stays gap-free when the invoice insert is forced to fail after the sequence bump (atomicity); FSSAI + rate-wise summary present in the print HTML.

**Acceptance:** a two-item mixed-rate order produces a correct invoice; a simulated mid-issue crash leaves no consumed-but-unused number; receipt is compliant.

**Dependencies:** CA scheme + rate confirmation.

**Out of scope:** the broader UnitOfWork refactor (Phase 9) — only the invoice flow is wrapped here.

---

## Phase 3 — Booking online prepay (Razorpay) 🔴

**Goal:** customers pay online to confirm a booking; unpaid holds never block slots.

**Data model / migrations (m-after-head)**
- `bookings`: add `paymentStatus` (`unpaid`|`paid`|`refunded`), `depositAmount NUMERIC` (via `batch_alter_table(recreate="always")`).
- New `booking_payments` (mirrors café `payments`): `id, booking_id FK, provider, providerOrderId, providerPaymentId, amount, status, signature, createdAt`.
- **Conditional (only if CA says turf bookings need a GST invoice):** add `invoices.refType` (`order`|`booking`) + nullable `booking_id`, so the existing invoice engine can bill a booking (turf service, typically 18% — different from café 5%).

**Backend**
- **Payment adapter (DEC-026):** `DAZY_PAYMENT_PROVIDER` with a Razorpay implementation + a dev no-op/console implementation. Interface: `create_order(amount, ref)`, `verify(payload)`, `refund(paymentId, amount)`.
- **Booking flow rework** (in `booking_service`, keep routes thin):
  1. `POST /bookings` creates the booking as `pending` — this **reserves the slot** via the existing capacity-aware unique index — and returns a provider order for checkout.
  2. `POST /bookings/{id}/payment/verify` (client callback) **and** `POST /payments/razorpay/webhook` (source of truth) verify the signature → mark `confirmed` + `paymentStatus=paid` → (if required) issue the booking GST invoice.
  3. Failure/abandon → booking stays `pending`; a **timeout sweep** releases `pending` bookings older than N minutes (cancel → frees the slot). Implement as a cleanup on availability read and/or a lightweight periodic task.
- Refund path: `POST /admin/bookings/{id}/refund` → provider refund → `paymentStatus=refunded` + status `cancelled` (frees slot). Manual dashboard refund acceptable as a v1 fallback.

**Frontend (web `Book.tsx`)**
- After slot + form: open Razorpay checkout → on success show confirmation (with ref); on failure/close show a retry state. Handle the `pending` window gracefully.

**Tests:** happy path (mock provider) pending→pay→confirm; failed payment leaves slot re-bookable after timeout; webhook signature verification; no double-book while a `pending` hold exists; refund frees the slot; (if enabled) booking invoice issued at the correct rate.

**Acceptance:** a slot cannot be held past the timeout without payment; successful payment confirms and (if required) invoices; failed/abandoned payment frees the slot; webhook is verified and idempotent.

**Dependencies:** Razorpay KYC (external — start immediately); CA turf-GST answer (for the invoice sub-part); payment adapter.

**Out of scope:** subscriptions/autopay (Phase 8); split payments; wallet.

> Note: concurrent bookings + payment webhooks add write pressure. SQLite is fine for pilot volume, but this is the phase that most argues for the Postgres swap (DEC-006/014) if traffic is real — a `DAZY_DB_URL` change, no code rewrite.

---

## Phase 4 — Owner visibility 🟠  *(parallel with Phase 3)*

**Goal:** the owner sees today's real numbers and can reconcile the till.

**Data model / migrations:** none (aggregate existing rows).

**Backend**
- New `reporting_repo` + `analytics_service` (DEC-024).
- `GET /admin/reports/dashboard`: today's bookings (count + revenue), today's café revenue, occupancy snapshot.
- `GET /admin/reports/day-close?date=`: café totals by payment mode (cash/UPI/card) for the shift (the Z-report).
- **Timezone fix:** compute "today" / day boundaries in the venue's IANA tz (Asia/Kolkata), not browser/server local — fixes the dashboard bug noted in `Roadmap.md`.

**Frontend (admin `Dashboard.tsx`)**
- Replace placeholder counts with the live dashboard numbers; add a Day-Close view.

**Tests:** dashboard figures correct against seeded data; Z-report mode totals sum to the day's payments; day boundary correct across the IST midnight edge.

**Acceptance:** owner sees accurate today-in-IST numbers; Z-report reconciles the café cash drawer.

**Out of scope:** full reports/CSV export/7-day trends (Phase 9).

---

## Phase 5 — Customer confirmation 🟠  *(parallel; fires after Phase 3)*

**Goal:** a paid booking sends the customer a confirmation.

**Data model / migrations (optional):** `notifications_log` (`id, refType, refId, channel, status, createdAt`) for delivery tracking — include if cheap, else defer.

**Backend**
- **Notification adapter (DEC-026):** `DAZY_NOTIFY_PROVIDER` with a dev console impl + one real provider — **SMS (MSG91/Twilio) or email (SMTP)** for MVP. Trigger on booking `confirmed`.
- Content: slot(s), date, court/sport, party size, amount paid, booking ref.

**Tests:** confirmation fires exactly once on `confirmed` (mock provider); content assembled correctly; failure is logged, not fatal to the booking.

**Acceptance:** completing payment produces a confirmation message with the booking details.

**Out of scope:** WhatsApp (Phase 10 — has its own onboarding/template friction); reminders; marketing sends.

---

# 🚀 GO LIVE  (after Phases 1–3 hard-done; 4–5 strongly recommended)

Run the go/no-go checklist from [Launch-Plan.md §5](Launch-Plan.md#5-gono-go-checklist). Soft-launch with a handful of real customers, fix, then open.

---

# GROWTH TRACK  (grow revenue at the venue — detail firms up once live)

## Phase 6 — Off-peak / peak pricing 🟢
**Goal:** fill dead weekday hours; capture more at prime time. **Revenue lever #1.**
- Engine already supports it: `schedule_rules.price` + `discount_percent` per court/weekday/block. Add an admin UI to set price/discount per block; surface `finalPrice` in `GET /slots` (already in `SlotDto`).
- Mostly admin UI + display; minimal backend. Tests: price varies by block; discount applied correctly.

## Phase 7 — Café × turf synergy 🟢
**Goal:** exploit your unique café-inside-booking asset. **Differentiator.**
- **Pre-order with a slot / order-to-court:** link a café order to a booking (`orders.booking_id`), let a customer add items to their slot.
- **Unified wallet:** `customer_wallets` (balance) + `wallet_ledger` (credits/debits), spendable on both turf and café; top-up via the payment adapter.
- Ship in sub-steps (order↔booking link first, wallet second). Data model: order link + wallet tables.

## Phase 8 — Memberships / prepaid packs + loyalty 🟢
**Goal:** recurring revenue + retention.
- `membership_plans`, prepaid credit packs (reuse wallet ledger), loyalty points across turf+café.
- Recurring billing via Razorpay subscriptions / UPI AutoPay.
- Best once you have a repeat customer base.

## Phase 9 — Ops & BI depth + foundation 🟢
**Goal:** operator-grade tooling and the deferred hardening.
- Full reports (revenue/occupancy/top-items/funnel/**GST period summary** for the CA/returns/Z history) + server-side CSV export; dashboard 7-day trend.
- **Complete the UnitOfWork refactor** beyond the invoice flow (order→items→KOT→invoice atomic everywhere) — DEC-025; highest regression risk, so done here with tests.
- Audit log + token refresh + password reset (security depth).
- **If you add table service later:** wire the dine-in loop (toggle, table picker, occupy→settle→free), KOT-for-tables, receipt/KOT reprint, table transfer.
- **If you want stock control:** inventory admin UI + auto-deduct on invoice (product-level; fields already exist).

## Phase 10 — Retention & scale 🟢
**Goal:** grow and retain; scale infra when volume demands.
- **WhatsApp** upgrade for confirmations/reminders/re-engagement (highest-ROI channel once onboarded); referrals + tiered loyalty; reviews / Google Business; waitlist + slot-free alerts.
- Customer accounts / "my bookings" (self-serve rebook, cancel, receipts, wallet balance); mobile PWA.
- **Postgres swap** (DEC-006/014) when concurrent write volume warrants — `DAZY_DB_URL` change; optionally Redis for slot locking.

---

## Notes on sequencing & risk

- **Parallelize:** 1↔2 overlap; 4 and 5 run alongside 3. The gating item is always Phase 3 (Razorpay KYC + build).
- **Two non-code dependencies decide the timeline more than code:** the CA answers (café scheme + turf-booking GST) and Razorpay activation. Start both on day one.
- **Every phase is independently shippable** and leaves the turf/booking flows working — the same discipline your existing roadmap already follows.
- Growth-phase detail (6–10) is intentionally lighter; firm it up with real post-launch usage data rather than guessing now.
