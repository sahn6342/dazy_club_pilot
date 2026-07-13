# Dazy.club — Master AI Context

> Single source of truth. Feed this file to any AI assistant for full project context.
> Last updated: 2026-07-03 (Detailed-Roadmap Phases 3-7 sub-step 1: booking online prepay, owner dashboard, notifications, café pre-order, self-service booking lookup)
> Feature detail + screenshots: [Features.md](Features.md) · REST/data reference: [API-Reference.md](API-Reference.md) · planned work: [Roadmap.md](Roadmap.md)

---

## What is Dazy.club?

A premium multi-sport venue platform for a single pilot venue offering **Cricket, Badminton, and Pickleball**, plus an on-site **cafe**. It is now four apps:

- **web** (:5173) — public booking site: browse slots, select consecutive slots, confirm + pay for a booking (Razorpay or dev-noop), self-service `/my-bookings` lookup/resume + café pre-order, general + corporate enquiries.
- **admin** (:5174) — staff back-office: courts, schedules, bookings, content (gallery/testimonials/CMS), promos, users, enquiries, owner dashboard + Z-report, notification log, and cafe menu/tables/orders/settings.
- **kiosk** (:5175) — cafe POS + Kitchen Display System: cashier PIN login, menu/cart, payments (cash/UPI/card), GST invoices, order history (incl. "🎫 Pre-order" badge for booking-linked orders), tables, KDS.
- **api** (:8000) — FastAPI backend serving all three (~80 endpoints, 26 tables).

---

## Monorepo Structure

```
dazy_club_pilot/
├── apps/
│   ├── web/          React 18 + Vite + TypeScript — public booking site (:5173)
│   ├── admin/        React 18 + Vite + TypeScript — staff back-office (:5174)
│   ├── kiosk/        React 18 + Vite + TypeScript — cafe POS + KDS (:5175)
│   └── api/          FastAPI + Python 3.12 — REST API (:8000)
├── packages/
│   ├── shared/       TypeScript types shared across frontends
│   └── ui/           Shared UI primitives
├── docs/             This folder
├── e2e/              Playwright E2E tests (web/, admin/, kiosk/ suites)
└── playwright.config.ts
```

**Package manager:** pnpm workspaces  
**Shared package:** `@dazy/shared` — exports `Slot`, `BookingRequest`, `SPORT_LABELS`, etc.

---

## Tech Stack (actual, as implemented)

| Layer | Tech |
|---|---|
| Frontends (web / admin / kiosk) | React 18, TypeScript, Vite, react-router-dom v7, CSS (no Tailwind) |
| API | FastAPI (Python 3.12), Pydantic v2, uvicorn, SQLAlchemy 2.0 (sync), Alembic |
| Database | SQLite (`apps/api/dazy.db`), Alembic migrations |
| Auth | JWT HS256 (pyjwt). Admin/manager via password (8h token); cashier/kitchen via 4-digit PIN (2h token). bcrypt hashes |
| Testing (backend) | pytest + starlette TestClient |
| Testing (E2E) | Playwright — web, admin, kiosk suites |
| Python env | uv (lockfile: `apps/api/uv.lock`) |

> **SQLite → PostgreSQL:** Swap `DAZY_DB_URL` env var. Repository pattern means zero route changes.

---

## Database Schema

All tables live in `dazy.db`. Managed by Alembic (`apps/api/alembic/`).

### Core tables

**venues** — one row seeded (`venue-dazy`)
```
id TEXT PK, name TEXT, timezone TEXT (IANA), active BOOL, createdAt TEXT
```

**courts** — one per sport seeded (`court-cricket`, `court-badminton`, `court-pickleball`)
```
id TEXT PK, venue_id FK→venues, sport TEXT, name TEXT, capacity INT,
active BOOL, createdAt TEXT
```
Soft-deleted: `DELETE /admin/courts/{id}` sets `active=False`.

**schedule_rules** — time blocks per court per weekday
```
id TEXT PK, court_id FK→courts, weekday INT (0=Mon..6=Sun),
open_time TEXT (HH:MM), close_time TEXT (HH:MM),
slot_minutes INT, price NUMERIC, discount_percent NUMERIC
```
Seeded: 3 blocks × 7 days × 3 courts → 12 slots/day/court.

**schedule_exceptions** — holiday/closure overrides
```
id TEXT PK, court_id TEXT NULLABLE FK→courts (NULL = venue-wide),
day TEXT (ISO date), closed BOOL, open_time TEXT, close_time TEXT, note TEXT
```
`court_id = NULL` = all courts closed (venue-wide holiday).

**bookings** — one row per slot; multi-slot bookings share one `bookingRef`, one row flagged `is_primary` (carries price/promo/message)
```
id TEXT PK, bookingRef TEXT, customer_id FK→customers NULLABLE,
court_id FK→courts NULLABLE, slotId TEXT (format: slot-{court.id}-{date}-{HHMM}),
name TEXT, contact TEXT, sportSlug TEXT, date TEXT, startTime TEXT, endTime TEXT,
party_size INT, price NUMERIC NULLABLE, promo_code TEXT, message TEXT,
status TEXT (pending|confirmed|completed|cancelled|no_show),
paymentStatus TEXT (unpaid|paid|refunded), depositAmount NUMERIC,
is_primary BOOL, createdAt TEXT
```

**booking_payments** — one row per payment order on a booking (Razorpay or noop)
```
id TEXT PK, bookingRef TEXT, provider TEXT (razorpay|noop),
providerOrderId TEXT, providerPaymentId TEXT NULLABLE, amount NUMERIC,
status TEXT (created|verified|refunded), signature TEXT NULLABLE,
checkoutJson TEXT NULLABLE (the exact checkout payload, replayed verbatim on
  GET /bookings/lookup so a resumed payment never gets a second gateway order),
createdAt TEXT
```

**notification_messages** — outbound notification delivery log
```
id TEXT PK, refType TEXT, refId TEXT, channel TEXT (email|sms),
recipient TEXT, status TEXT (sent|skipped|failed), errorMessage TEXT NULLABLE,
createdAt TEXT
```

**customers**
```
id TEXT PK, name TEXT, phone TEXT UNIQUE, email TEXT, createdAt TEXT
```

**gallery**
```
id TEXT PK, title TEXT, sportSlug TEXT, tone TEXT, imageUrl TEXT,
approved BOOL
```
Images: URL (external) or `/media/gallery/{uuid}.ext` (local upload served via `/media` static mount).

**testimonials**
```
id TEXT PK, name TEXT, context TEXT, quote TEXT, approved BOOL
```

**cms**
```
key TEXT PK, label TEXT, value TEXT
```
Seeded keys: `hero_tagline`, `hero_copy`, `footer_tagline`, `faq_booking`, `faq_sports`, `faq_corporate`, `faq_group_size`, `venue_name`, `venue_address`, `venue_phone`, `venue_email`, `venue_hours`, `social_instagram`, `social_facebook`.

**promo_codes**
```
id TEXT PK, code TEXT UNIQUE, kind TEXT (percent|flat), value NUMERIC,
active BOOL, valid_from TEXT, valid_to TEXT, max_uses INT, used_count INT,
sport_slug TEXT (NULL=all sports), createdAt TEXT
```

**users**
```
id TEXT PK, username TEXT UNIQUE, hashed_password TEXT,
role TEXT (manager|cashier|kitchen), active BOOL, createdAt TEXT, createdBy TEXT
```
Superadmin (`admin`) from env vars (`ADMIN_USERNAME`, `ADMIN_PASSWORD`) — not a DB row. Managers/cashiers/kitchen stored here; cashier/kitchen use a 4-digit PIN as their password for kiosk login.

**enquiries**
```
id TEXT PK, name TEXT, contact TEXT, message TEXT, sport TEXT,
handled BOOL, createdAt TEXT
```

### Cafe POS tables (kiosk + admin cafe)

**cafe_settings** — GST/business config (legal name, GSTIN, FSSAI, address, state code, GST scheme, default tax rate, price-includes-tax, invoice series/prefix, rounding, declaration/footer).
**menu_categories** — `name, kind (food|beverage), vegType, sortOrder, active`.
**menu_items** — `category_id, name, description, price, taxRatePercent, vegType, station (kitchen|bar), isPackaged, available, imageUrl, sortOrder` + inventory fields `trackInventory, currentQty, reorderLevel, unit, purchaseCost`.
**cafe_tables** — `label, area, capacity, status (free|occupied|reserved), sortOrder, active`.
**orders** — `orderNo, orderType (quick|dine_in|takeaway), table_id, booking_id (nullable — links a café pre-order to a turf booking), status (open|in_kitchen|served|billed|paid|cancelled|void), subtotal, taxAmount, discountAmount, total, notes, createdBy, createdAt, updatedAt`.
**order_items** — `order_id, menu_item_id, nameSnapshot, qty, unitPrice, taxRatePercent, lineSubtotal, lineTax, lineTotal, kot_id, kotStatus, voided, voidReason`.
**kots** — kitchen order tickets: `kotNo, order_id, station, status (sent|preparing|ready|served), printedAt`.
**payments** — `order_id, mode (cash|card|upi|wallet|other), amount, reference, createdAt`.
**invoices** — GST invoices: `invoiceNo, order_id, type (tax_invoice|bill_of_supply), totals + CGST/SGST, financialYear, issuedAt, issuedBy, status`.
**invoice_lines** — per-line taxable value + CGST/SGST split.
**invoice_sequences** — atomic per-series/financial-year invoice counter (gap-free numbering).

---

## Slot ID Format

```
slot-{court.id}-{date}-{HHMM}
```
Examples:
- `slot-court-cricket-2026-07-01-0600`
- `slot-court-badminton-2026-07-01-1400`

Slots are **generated dynamically** from `ScheduleRule` rows — not stored in DB.

---

## API Endpoints

All prefixed `/api/v1`. API runs on `:8000`. OpenAPI at `http://localhost:8000/docs`.

### Public (no auth)

| Method | Path | Description |
|---|---|---|
| GET | `/health` | `{"status":"ok"}` |
| GET | `/sports` | Sports list + metadata. |
| GET | `/venue` | Venue details (name/contact/hours from CMS). |
| GET | `/slots?sport=&date=` | Available slots for sport + date. Returns `SlotDto[]`. |
| POST | `/bookings` | Create booking. Body: `BookingCreate`. Returns `BookingResponse` — `pending`+checkout if priced, `confirmed` if free. |
| POST | `/bookings/{ref}/payment/verify` | Client payment-verify callback (idempotent). |
| GET | `/bookings/lookup?ref=&contact=` | Self-service lookup/resume (no login) — same ref+contact identity as pre-order. |
| GET | `/menu` | Public café menu for pre-orders (slimmer than `/cafe/menu`). |
| POST | `/bookings/{ref}/preorder` | Add café items to a confirmed booking. |
| POST | `/payments/razorpay/webhook` | Razorpay webhook — source of truth for confirmation. |
| GET | `/promos/validate?code=&sport=&amount=` | Validate promo code. Returns discount info. |
| GET | `/gallery` | Approved gallery items (DB-driven). |
| GET | `/testimonials` | Approved testimonials. |
| GET | `/cms` | All CMS key-value entries. |
| GET | `/notifications` | Public announcements/notifications. |
| POST | `/contact-enquiries` | Submit general enquiry. |
| POST | `/corporate-enquiries` | Submit corporate/event enquiry. |
| GET | `/cafe/invoices/{id}/print` | Public 80mm thermal invoice HTML (unguessable UUID; auto-prints). |
| POST | `/admin/login` | Admin/manager JWT. Body: `{username, password}`. |
| POST | `/cafe/login` | Cashier JWT. Body: `{username, pin}` (4-digit PIN). |

### Admin (Bearer JWT required)

**Courts**
| Method | Path | Description |
|---|---|---|
| GET | `/admin/courts` | All courts (active + inactive). |
| POST | `/admin/courts` | Create court. Body: `CourtCreate {venue_id, sport, name, capacity}`. |
| PATCH | `/admin/courts/{id}` | Update name/capacity/active. Body: `CourtUpdate`. |
| DELETE | `/admin/courts/{id}` | Soft-deactivate (sets `active=False`). |

**Schedule**
| Method | Path | Description |
|---|---|---|
| GET | `/admin/schedule/rules?court_id=` | List rules for court. |
| POST | `/admin/schedule/rules` | Create rule. |
| PATCH | `/admin/schedule/rules/{id}` | Update rule. |
| DELETE | `/admin/schedule/rules/{id}` | Delete rule. |
| GET | `/admin/schedule/exceptions?court_id=` | List exceptions. |
| POST | `/admin/schedule/exceptions` | Create exception. `court_id=null` = venue-wide. |
| DELETE | `/admin/schedule/exceptions/{id}` | Delete exception. |

**Bookings**
| Method | Path | Description |
|---|---|---|
| GET | `/admin/bookings?sport=&date=&status=` | List bookings with filters. |
| PATCH | `/admin/bookings/{id}` | Update status. Body: `{status}`. |
| DELETE | `/admin/bookings/{id}` | Hard delete booking. |
| POST | `/admin/bookings/{id}/refund` | Refund a paid booking (provider refund + frees the slot). |

**Enquiries & customers**
| Method | Path | Description |
|---|---|---|
| GET | `/admin/enquiries` | List enquiries (general + corporate). |
| PATCH | `/admin/enquiries/{id}` | Update handled status. |
| GET | `/admin/customers` | Customer records. |

**Content**
| Method | Path | Description |
|---|---|---|
| GET/POST | `/admin/gallery` | List / create gallery item. |
| PATCH/DELETE | `/admin/gallery/{id}` | Update / delete gallery item. |
| POST | `/admin/gallery/upload` | Upload image file → returns `{imageUrl}`. |
| GET/POST | `/admin/testimonials` | List / create testimonial. |
| PATCH/DELETE | `/admin/testimonials/{id}` | Update / delete testimonial. |
| GET/POST | `/admin/cms` | List / create CMS entry (409 on duplicate key). |
| PUT/DELETE | `/admin/cms/{key}` | Update value+label / delete entry. |

**Promos**
| Method | Path | Description |
|---|---|---|
| GET/POST | `/admin/promos` | List / create promo code. |
| PATCH/DELETE | `/admin/promos/{id}` | Update / delete promo code. |

**Users (superadmin only)**
| Method | Path | Description |
|---|---|---|
| GET/POST | `/admin/users` | List / create manager/cashier/kitchen accounts. |
| PATCH/DELETE | `/admin/users/{id}` | Update / delete user. |

**Cafe admin**
| Method | Path | Description |
|---|---|---|
| GET/POST/PATCH/DELETE | `/admin/cafe/categories` (`/{id}`) | Menu category CRUD. |
| GET/POST/PATCH/DELETE | `/admin/cafe/items` (`/{id}`) | Menu item CRUD (price, tax %, station, veg, inventory fields). |
| GET/POST/PATCH/DELETE | `/admin/cafe/tables` (`/{id}`) | Table CRUD (label/area/capacity/status). |
| GET/PUT | `/admin/cafe/settings` | GST/business config. |
| GET | `/cafe/invoices` | All invoices (admin). |

**Reports & notifications**
| Method | Path | Description |
|---|---|---|
| GET | `/admin/reports/dashboard` | Owner KPIs (bookings/revenue/occupancy today, venue-local timezone). |
| GET | `/admin/reports/day-close?date=` | Café Z-report — payment-mode totals for a date. |
| GET | `/admin/notifications?refType=&refId=` | Notification delivery log. |

### Cafe / POS (Bearer cashier — cashier/kitchen/manager/admin)

| Method | Path | Description |
|---|---|---|
| GET | `/cafe/menu` | Menu (categories + items). |
| GET | `/cafe/tables` | Dine-in tables. |
| POST/GET | `/cafe/orders` | Create / list orders. |
| GET/PATCH | `/cafe/orders/{id}` | Get / update order. |
| POST | `/cafe/orders/{id}/items` | Add line item. |
| DELETE | `/cafe/orders/{id}/items/{iid}` | Void item (reason required). |
| POST | `/cafe/orders/{id}/kot` | Fire KOT(s) — one per station. |
| POST | `/cafe/orders/{id}/payments` | Record payment (auto-marks paid). |
| POST | `/cafe/orders/{id}/invoice` | Issue GST invoice. |
| GET | `/cafe/kots?station=&status=` | KOTs for a station. |
| PATCH | `/cafe/kots/{id}/status` | Advance KOT (sent→preparing→ready). |
| GET | `/cafe/invoices/{id}` | Invoice detail. |

---

## Key Pydantic Models

```python
# Slot (read)
SlotDto: id, courtId, courtName, sportSlug, date, startTime, endTime,
         available, maxPlayers, price, discountPercent, finalPrice

# Booking (create)
BookingCreate: name, contact, slotId, slotIds[], sportSlug, date,
               startTime, players, promoCode, message

# Booking (response)
BookingResponse: id, bookingRef, slotId, sportSlug, date, startTime, endTime,
                 name, contact, players, status, price, promoCode, slotCount

# Court
CourtCreate: venue_id, sport (cricket|badminton|pickleball), name, capacity
CourtUpdate: name?, capacity?, active?
CourtDto: id, venue_id, sport, name, capacity, active, createdAt

# Schedule
ScheduleRuleCreate: court_id, weekday, open_time, close_time, slot_minutes, price?, discount_percent?
ScheduleExceptionCreate: court_id (nullable), day, closed, open_time?, close_time?, note?

# Booking payment + self-service lookup
CheckoutConfig (opaque, provider-dependent): provider, providerOrderId | order_id, amount, currency, key?
BookingPaymentVerifyRequest: providerOrderId, providerPaymentId, signature?
BookingLookupResult: bookingRef, name, status, sport, date, startTime, endTime,
                     slotCount, price?, paymentRequired, checkout? (same CheckoutConfig, replayed — not regenerated)

# Café pre-order
PreOrderRequest: contact, items[] ({menu_item_id, qty})
PreOrderResult: orderNo, total, items[] ({name, qty, lineTotal})
PublicMenuItemDto: id, category_id, name, description?, price, vegType?, available   # no inventory/cost fields

# Owner dashboard
DashboardDto: date, bookingsToday, bookingRevenueToday, cafeRevenueToday, occupancyToday
DayCloseDto: date, totalRevenue, totalTransactions, byMode[] ({mode, total, count})

# Notifications
NotificationMessageDto: id, refType, refId, channel, recipient, status, errorMessage?, createdAt
```

---

## Frontend — Web App (`:5173`)

**Pages / sections:**
- `Home` — hero, sports highlights, gallery carousel, testimonials (single-page, scroll-nav)
- `Book` — full booking flow, incl. payment + pre-order
- `MyBookings` (`/my-bookings`) — self-service booking lookup/resume, no login
- `Contact` — general enquiry form + corporate enquiry form

**Book page flow:**
1. Sport tabs: Cricket / Badminton / Pickleball
2. Date pills: 7-day rolling window (today → today+6)
3. Court pills: appear only when >1 court exists for sport ("All courts" + per-court filter)
4. Slot grid: chips per available time slot
   - Gold border = available, dimmed = booked
   - Click to select; click adjacent slot to extend (consecutive booking, same court only)
   - When "All courts" view: small court name badge on each chip
5. Booking form (appears on selection): name, contact, players, promo code (optional), message
   - Live promo validation: debounced 600ms, fires at 3+ chars, shows discount inline
6. Confirm → if priced, `PaymentPanel` (noop dev-simulate buttons or real Razorpay checkout.js, chosen by `checkout.provider`) → success screen with booking ref; if free, success immediately
7. Success screen → `PreOrderPanel` ("Add food & drinks for your visit") to attach café items to the just-confirmed booking

**State reset:** switching sport, date, or court clears selected slots — **except** while `bookingStatus` is `payment` or `success`, when those controls are disabled (prevents an accidental click from silently abandoning a pending payment or a just-confirmed booking with no way back, since there's no login/profile system).

**MyBookings page (`/my-bookings`):** form takes a booking ref (`?ref=` query param pre-fills it, e.g. from the payment-pending reminder email) + the contact used at booking time. On lookup: a `pending` booking renders the same `PaymentPanel`, replaying the *original* stored checkout order (never a new gateway order); a `confirmed` booking shows details + the `PreOrderPanel`.

**TypeScript types** (from `@dazy/shared`):
```ts
type Slot = {
  id: string; courtId?: string | null; courtName?: string | null;
  sportSlug: string; date: string; startTime: string; endTime: string;
  available: boolean; maxPlayers: number;
  price?: number | null; discountPercent?: number | null; finalPrice?: number | null;
}
```

---

## Frontend — Admin Portal (`:5174`)

**Auth:** JWT stored in localStorage. `AuthGuard` component redirects to `/login` if no token.

**Pages:**
| Route | Page | Description |
|---|---|---|
| `/login` | Login | Username + password → JWT |
| `/` | Dashboard | Real KPIs (bookings/revenue/occupancy today, venue-local tz) + day-close (Z-report) table with a date picker |
| `/bookings` | Bookings | Table + filter (sport, date, status). Confirm/cancel/complete/no-show actions. |
| `/schedule` | Schedule | Court selector, weekly block editor, per-day accordion, date exceptions |
| `/courts` | Courts | Add/edit/deactivate courts grouped by sport |
| `/promos` | Promos | Promo code CRUD with kind/value/sport/dates |
| `/enquiries` | Enquiries | Triage general + corporate enquiries |
| `/gallery` | Gallery | Image grid with add (URL or file upload) / edit / delete / approve/reject |
| `/testimonials` | Testimonials | List with add / edit / delete / approve/reject |
| `/cms` | CMS | Create / edit / delete key-value content entries |
| `/contact-details` | ContactDetails | Edit venue contact block (address/phone/email/hours/socials) |
| `/users` | Users | Manager/cashier/kitchen account CRUD (superadmin only) |
| `/cafe/categories` | Cafe Categories | Menu category CRUD |
| `/cafe/items` | Cafe Items | Menu item CRUD |
| `/cafe/tables` | Cafe Tables | Table CRUD (incl. status) |
| `/cafe/orders` | Cafe Orders | Read-only orders view (filter + expand) |
| `/cafe/settings` | Cafe Settings | GST/business configuration |

**Schedule page detail:**
- Court dropdown to select which court to configure
- Weekly editor: table of Mon–Sun with open/close/price per block; "Make continuous", "Copy to all days"
- Advanced section (collapsible): per-day override rows — add/remove time blocks
- Date exceptions panel: add closed dates or special-hours overrides; "Apply to all courts" toggle (default on = venue-wide holiday)

---

## Frontend — Kiosk (Cafe POS + KDS) (`:5175`)

**Auth:** cashier logs in with staff name + 4-digit PIN (`/cafe/login`); JWT in `localStorage` key `dazy_kiosk_token`. `AuthGuard` bounces unauthenticated access to `/login`.

**Pages:**
| Route | Page | Description |
|---|---|---|
| `/login` | Login | Staff name + 4-digit PIN pad (keyboard entry supported) |
| `/menu` | Menu | Category rail + item grid + cart; Place Order → Payment modal |
| `/orders` | Orders | Open / History tabs; Pay action on open orders; "🎫 Pre-order" badge when `booking_id` is set; auto-refresh 15s |
| `/tables` | Tables | Floor view with status; auto-refresh 30s |
| `/kds` | KDS | Pending KOTs for a station; Mark Preparing / Ready; poll 10s |

**Order → payment flow:** build cart → `POST /cafe/orders` → PaymentModal (Cash/UPI/Card + optional reference; round-off disclosed) → `POST …/payments` (auto-marks paid) → `POST …/invoice` → **Print Receipt** opens the public 80mm thermal invoice HTML.

---

## Business Rules

| Rule | Detail |
|---|---|
| Slot generation | Dynamic from `ScheduleRule` rows. Not stored. Generated per request. |
| Slot ID uniqueness | `slot-{court.id}-{date}-{HHMM}` — court-specific, so two courts same sport produce unique IDs |
| Multi-court booking | User sees court pills; consecutive selection allowed only within same court |
| Court deactivation | Soft-delete. Inactive courts generate no slots. Bookings preserved. |
| Schedule exceptions | `court_id=NULL` closes entire venue. Court-specific exception overrides for that court only. |
| Booking statuses | `pending → confirmed → completed / no_show / cancelled` |
| Booking payment | Priced booking = `pending` + a payment order (`DAZY_PAYMENT_PROVIDER=noop\|razorpay`); confirms only via payment-verify or webhook (both idempotent). A `pending` booking older than 15 min is swept and the slot freed on the next availability read. |
| Booking self-service lookup | `GET /bookings/lookup?ref=&contact=` — no login; replays the *same* stored checkout order on resume, never a second gateway order for one booking. Rate-limited per IP. |
| Café pre-order | `POST /bookings/{ref}/preorder` — same ref+contact identity, confirmed bookings only; creates a normal café order tagged `orders.booking_id`. |
| Notifications | Fire on booking `confirmed` and once on `pending` (payment reminder with the `/my-bookings` resume link); every attempt logged to `notification_messages`, never fatal to the triggering flow. Provider pluggable (`DAZY_NOTIFY_PROVIDER=console\|email`). |
| Owner dashboard | "Today" / day boundaries resolved in the venue's IANA timezone, not browser/server local. |
| Promo codes | `percent` (e.g. 10% off) or `flat` (e.g. ₹100 off). Can be sport-specific. Applied at booking. |
| Cancelled bookings | Do NOT block slot. Availability re-derived excluding `cancelled`/`no_show`. |
| Double-booking guard | Unique constraint on `(court_id, date, start_time)` where status not cancelled/no_show → 409 on race. |
| Auth roles | `admin` (env-var superadmin) = full access. `manager` (DB) = all except user management. `cashier`/`kitchen` (DB, 4-digit PIN) = kiosk POS / KDS only. |
| JWT | HS256, `JWT_SECRET` env var. Admin/manager 8h, cashier 2h. Admin login rate-limited (per-IP). |
| GST invoicing | On invoice issue, total splits into CGST + SGST per cafe settings; invoice numbers allocated **per financial year** (e.g. `2526`) from an atomic sequence (gap-free); amount rendered in words (Indian numbering); printable as 80mm thermal HTML. |
| KOT routing | Firing a KOT groups an order's pending items by menu-item **station** (kitchen/bar) → one KOT per station; items marked `sent`. KDS advances `sent→preparing→ready`. |
| Payments | Modes cash/UPI/card (+wallet/other); multiple payments per order; order auto-marked `paid` when total paid ≥ order total. |
| Media | Images as URL strings or local `/media/gallery/` files. Served via FastAPI StaticFiles at `/media`. |
| Seeded data | 1 venue, 3 courts, 63 schedule rules (3 blocks × 7 days × 3 courts), gallery, testimonials, CMS entries, 2 promos (WELCOME10, FLAT100). Cafe menu/tables are created via admin, not seeded. |

---

## Environment Variables

```
DAZY_DB_URL=sqlite:///./dazy.db        # swap to postgres://... for prod
ADMIN_USERNAME=admin
ADMIN_PASSWORD=admin
JWT_SECRET=changeme

# Loaded from apps/api/.env via python-dotenv (db.py, earliest config-reading module).
# apps/api/.env is gitignored — never committed; holds real credentials for local dev.
DAZY_PAYMENT_PROVIDER=noop             # or razorpay
RAZORPAY_KEY_ID=                       # required if DAZY_PAYMENT_PROVIDER=razorpay
RAZORPAY_KEY_SECRET=
RAZORPAY_WEBHOOK_SECRET=               # optional — only needed to test the webhook path

DAZY_NOTIFY_PROVIDER=console           # or email
SMTP_HOST=                             # required if DAZY_NOTIFY_PROVIDER=email
SMTP_PORT=587
SMTP_USER=
SMTP_PASSWORD=
SMTP_FROM=                             # defaults to SMTP_USER

DAZY_WEB_BASE_URL=http://localhost:5173  # used to build the /my-bookings resume link in notifications
```

> **Test isolation:** `apps/api/tests/conftest.py` force-pins `DAZY_PAYMENT_PROVIDER=noop` and `DAZY_NOTIFY_PROVIDER=console` before any app import, so a developer's local `.env` (e.g. real Razorpay test creds for manual verification) never leaks into the automated suite.

---

## Running Locally

```bash
# API
cd apps/api
uv sync
.venv/Scripts/python.exe -m uvicorn main:app --reload --port 8000

# Web
pnpm dev:web       # http://localhost:5173

# Admin
pnpm dev:admin     # http://localhost:5174

# Kiosk (cafe POS + KDS)
pnpm dev:kiosk     # http://localhost:5175
```

**Run tests:**
```bash
cd apps/api
.venv/Scripts/python.exe -m pytest tests -q
# 377 tests, full backend suite passes
```

**Run E2E:**
```bash
pnpm e2e
# Requires all 3 servers running
```

---

## Key Architecture Decisions

| Decision | Choice | Reason |
|---|---|---|
| Backend language | Python / FastAPI | Lighter than .NET for pilot; hot-reload; auto OpenAPI docs |
| Database | SQLite (pilot) | Zero infra; swap to PostgreSQL via `DAZY_DB_URL` |
| Schema management | Alembic | Safe incremental migrations (vs `create_all`) |
| Slot model | Generated from rules (not stored) | Schedule-as-data; avoids write amplification |
| Slot ID format | `slot-{court.id}-{date}-{HHMM}` | Court-specific → enables multi-court per sport |
| Court deletion | Soft-delete (`active=False`) | Preserves booking history |
| Venue-wide exceptions | `court_id=NULL` in schedule_exceptions | One action closes all courts |
| Auth | JWT HS256, env-var superadmin + DB managers | Simple, no auth service needed for pilot |
| Frontend state | React `useState` + direct API calls | No Redux/Zustand; fits complexity level |
| CSS | Plain CSS with CSS variables | No Tailwind; dark theme with gold accent (`#d8b456`) |
| Payment provider | Adapter (`base.py` ABC) + noop (dev) / Razorpay (stdlib `urllib`+`hmac`, zero SDK dep) | Swap via `DAZY_PAYMENT_PROVIDER` with zero call-site changes; matches deferred-provider decision |
| Notification provider | Adapter + console (dev) / SMTP email (stdlib `smtplib`, zero dep) | Same pattern as payments; swap via `DAZY_NOTIFY_PROVIDER` |
| Booking self-service | Ref + matching contact, no login/profile system | Cheapest way to let a customer resume a payment or add a pre-order; same trust model reused for both features |

---

## File Map (key source files)

```
apps/api/
  main.py                    FastAPI app, router registration, CORS, GZip
  models.py                  All Pydantic request/response models
  db.py                      SQLAlchemy engine, Base, session, init_db(), seed_if_empty()
  db_models.py               SQLAlchemy ORM row classes
  deps.py                    Singleton repo instances
  auth.py                    JWT encode/decode, get_current_admin dependency
  seed.py                    SPORTS, GALLERY_ITEMS, TESTIMONIALS constants
  services/
    availability_service.py  Slot generation from rules + exceptions; 15-min pending-payment timeout sweep
    booking_service.py       Booking creation + concurrency guard
    pricing_service.py       Promo validation + Decimal money math
    pos_service.py           Order creation, KOT station routing, payments, GST invoice orchestration
    venue_tz.py              Venue IANA-timezone day-boundary helper (owner dashboard)
    analytics_service.py     Dashboard + day-close (Z-report) composition
    notification_service.py  Single logged send_and_log() entry point; notify_booking_confirmed/payment_pending
    notification_templates.py  Message content for booking notifications
  repositories/
    court_repo.py            Court CRUD + clear()
    schedule_repo.py         Rules + exceptions CRUD + clear()
    booking_repo.py          Booking CRUD
    gallery_repo.py          Gallery CRUD + image cleanup
    testimonial_repo.py      Testimonial CRUD
    cms_repo.py              CMS CRUD
    promo_repo.py            Promo CRUD + validation
    customer_repo.py         Customer upsert-by-contact
    user_repo.py             Manager/cashier/kitchen account CRUD
    menu_item_repo.py        Menu item CRUD (+ inventory fields)
    menu_category_repo.py    Menu category CRUD
    cafe_table_repo.py       Cafe table CRUD
    order_repo.py            Orders + items + total recalc
    kot_repo.py              KOT CRUD + status
    payment_repo.py          Payments
    invoice_repo.py          GST invoice + lines + sequence (CGST/SGST, amount-in-words)
    booking_payment_repo.py  Payment order tracking + stored checkoutJson
    notification_repo.py     Notification delivery log
    reporting_repo.py        Cross-table aggregates for the owner dashboard
    audit_repo.py            Audit log (scaffolded, unwired)
  integrations/
    payments/                base.py (ABC), noop.py, razorpay.py (stdlib urllib+hmac), factory.py (DAZY_PAYMENT_PROVIDER)
    notifications/           base.py (ABC), console.py, email_smtp.py (stdlib smtplib), factory.py (DAZY_NOTIFY_PROVIDER)
  routes/
    slots.py                 GET /slots
    bookings.py              POST /bookings, payment/verify, /bookings/lookup, GET /promos/validate
    payments.py              POST /payments/razorpay/webhook
    preorders.py             GET /menu, POST /bookings/{ref}/preorder
    gallery.py                GET /gallery (public, approved only, DB-driven)
    testimonials.py          GET /testimonials (approved only)
    cms.py                   GET /cms
    enquiries.py             POST /contact-enquiries, /corporate-enquiries
    sports.py, venue.py, notifications.py   Public metadata
    cafe/
      auth.py                POST /cafe/login (cashier PIN)
      menu.py, tables.py     GET /cafe/menu, /cafe/tables
      orders.py              Order lifecycle: create/items/kot/payments/invoice
      kots.py                KOT list + status (KDS)
      invoices.py            Invoice detail + public /print
    admin/
      auth.py                POST /admin/login, rate limiter
      courts.py              Courts CRUD
      schedule.py            Rules + exceptions CRUD
      bookings.py            Admin booking management + refund
      gallery.py             Gallery CRUD + upload
      testimonials.py        Testimonial CRUD
      cms.py                 CMS update
      promos.py              Promo CRUD + validate
      users.py               Manager/cashier/kitchen CRUD
      enquiries.py           Enquiry triage
      customers.py           Customer records
      reports.py             GET /admin/reports/dashboard, /admin/reports/day-close
      notifications.py       GET /admin/notifications
      cafe/                  categories.py, items.py, tables.py, settings.py
  rate_limit.py               SlidingWindowLimiter — admin/cashier login + booking lookup
  alembic/
    versions/                Migration scripts (chained; head e8f9a0b1c2d3)
  tests/
    conftest.py              autouse fixture resets all repos + re-seeds each test; pins DAZY_PAYMENT_PROVIDER=noop / DAZY_NOTIFY_PROVIDER=console
    test_positive.py         Happy-path slot/booking/promo/auth tests
    test_schedule.py         Schedule rules/exceptions tests
    test_admin_courts.py     Courts CRUD tests (24 tests)
    test_edge_cases.py       Boundary/error tests
    test_bookings.py         Booking lifecycle tests
    test_booking_payments.py  Online prepay: pending/checkout, verify, webhook, timeout sweep, refund
    test_razorpay_provider.py  Pure HMAC signature verification (payment + webhook)
    test_reports.py          Dashboard + day-close, incl. IST midnight boundary
    test_notifications.py    Confirmation + payment-pending notifications, content, failure isolation
    test_preorders.py        Café pre-order: public menu, identity check, confirmed-only gate
    test_booking_lookup.py   Self-service lookup: resume same checkout, wrong contact, rate limit
    (+ more test files — 377 total)

apps/web/src/
  pages/Book.tsx             Full booking flow (sport→date→court→slot→form→pay→confirm→pre-order)
  pages/MyBookings.tsx       Self-service booking lookup/resume (no login)
  pages/Home.tsx             Landing page with gallery carousel
  components/PaymentPanel.tsx    Noop dev-simulate buttons or real Razorpay checkout.js
  components/PreOrderPanel.tsx   Café item cart, attaches to a confirmed booking
  lib/api.ts                 All API calls (getSlots, createBooking, verifyBookingPayment, lookupBooking, getPublicMenu, createPreorder, etc.)
  lib/validate.ts            Client-side field validators
  styles.css                 Dark theme CSS with gold accent

apps/admin/src/
  pages/Schedule.tsx         Weekly editor + per-day overrides + date exceptions
  pages/Courts.tsx           Court add/edit/deactivate grouped by sport
  pages/Bookings.tsx         Booking table + status actions
  pages/Gallery.tsx          Image grid CRUD + file upload
  pages/Testimonials.tsx     Testimonial CRUD
  pages/CMS.tsx              Inline CMS editor
  pages/Promos.tsx           Promo code CRUD
  pages/Users.tsx            Manager/cashier/kitchen account CRUD
  pages/Dashboard.tsx        Real KPIs + day-close (Z-report) table
  pages/Enquiries.tsx        Enquiry triage
  pages/ContactDetails.tsx   Venue contact editor
  pages/Cafe*.tsx            CafeCategories/Items/Tables/Orders/Settings
  components/Sidebar.tsx     Nav with all page links
  components/ConfirmDialog.tsx  In-app confirm (useConfirm) — replaces window.confirm
  lib/api.ts                 Admin API client (get/post/patch/put/delete/upload)

apps/kiosk/src/
  pages/Login.tsx            Cashier PIN login
  pages/Menu.tsx             Category rail + item grid + cart → Payment
  pages/Orders.tsx           Open / History tabs; "🎫 Pre-order" badge
  pages/Tables.tsx           Floor view
  pages/KDS.tsx              Kitchen Display — pending KOTs
  components/PaymentModal.tsx  Cash/UPI/card + GST invoice + print
  lib/api.ts, lib/auth.ts    Kiosk API client + token (dazy_kiosk_token)

packages/shared/src/index.ts  Slot, BookingRequest types + SPORT_LABELS
packages/ui/                   Shared UI primitives

e2e/
  web/booking.spec.ts        Web booking flow E2E, incl. online prepay + café pre-order
  web/pricing.spec.ts        Promo code E2E
  web/my-bookings.spec.ts    Self-service lookup/resume E2E
  web/contact.spec.ts        Contact + corporate enquiry E2E
  admin/bookings.spec.ts     Admin booking management E2E
  admin/schedule.spec.ts     Schedule management E2E
  admin/courts.spec.ts       Courts admin E2E
  admin/gallery.spec.ts      Gallery admin E2E
  kiosk/login.spec.ts        Kiosk cashier login E2E
  {web,admin,kiosk}/zz-screenshots.spec.ts  Doc-screenshot generation
```
