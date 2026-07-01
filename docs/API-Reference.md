# Dazy.club — API Reference

FastAPI backend. Base URL: **`http://localhost:8000/api/v1`**. Interactive docs available at `http://localhost:8000/docs` while the server runs.

**Auth:**
- **Public** — no token.
- **Admin** — `Authorization: Bearer <token>` from `POST /admin/login` (guarded by `get_current_admin`).
- **Cashier** — `Authorization: Bearer <token>` from `POST /cafe/login`; `get_current_cashier` accepts `cashier`, `kitchen`, `manager`, and `admin` roles.

---

## Endpoints

### Public

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/health` | Liveness check |
| GET | `/sports` | List sports (Cricket, Badminton, Pickleball) + metadata |
| GET | `/venue` | Venue details (name, contact, hours from CMS) |
| GET | `/slots` | Live availability slots for a sport/date |
| GET | `/gallery` | Approved gallery items (DB-driven, realtime) |
| GET | `/testimonials` | Approved testimonials |
| GET | `/notifications` | Public notifications/announcements |
| GET | `/promos/validate` | Validate a promo code |
| POST | `/bookings` | Create a booking (201) |
| POST | `/contact-enquiries` | Submit general enquiry (201) |
| POST | `/corporate-enquiries` | Submit corporate/event enquiry (201) |
| GET | `/cafe/invoices/{id}/print` | **Public** 80mm thermal invoice HTML (auto-prints) |

### Admin (Bearer admin)

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/admin/login` | Admin login → JWT |
| GET / PATCH / DELETE | `/admin/bookings` · `/admin/bookings/{id}` | List, update status, cancel |
| GET / PATCH | `/admin/enquiries` · `/admin/enquiries/{id}` | List, update status |
| GET | `/admin/customers` | Customer records |
| GET / POST / PUT / DELETE | `/admin/cms` · `/admin/cms/{key}` | CMS CRUD (PUT label+value; 409 on dup key) |
| GET / POST / PATCH / DELETE | `/admin/courts` · `/admin/courts/{id}` | Court CRUD |
| GET / POST / PATCH / DELETE | `/admin/promos` · `/admin/promos/{id}` | Promo CRUD |
| GET / POST / PATCH / DELETE | `/admin/schedule/rules` · `/admin/schedule/rules/{id}` | Weekly schedule rule CRUD |
| GET / POST / DELETE | `/admin/schedule/exceptions` · `/admin/schedule/exceptions/{id}` | Date exceptions (venue-wide or per-court) |
| GET / POST / PATCH / DELETE | `/admin/gallery` · `/admin/gallery/{id}` | Gallery CRUD |
| POST | `/admin/gallery/upload` | Upload image → `/media/gallery/...` |
| GET / POST / PATCH / PUT / DELETE | `/admin/testimonials` · `/admin/testimonials/{id}` | Testimonials CRUD + approve |
| GET / POST / PATCH / DELETE | `/admin/users` · `/admin/users/{id}` | User/role CRUD |
| GET / POST / PATCH / DELETE | `/admin/cafe/categories` · `/{id}` | Menu category CRUD |
| GET / POST / PATCH / DELETE | `/admin/cafe/items` · `/{id}` | Menu item CRUD |
| GET / POST / PATCH / DELETE | `/admin/cafe/tables` · `/{id}` | Table CRUD |
| GET / PUT | `/admin/cafe/settings` | Cafe/GST settings |
| GET | `/cafe/invoices` | All invoices (admin) |

### Cafe / POS (Bearer cashier)

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/cafe/login` | Cashier PIN login → JWT |
| GET | `/cafe/menu` | Menu (categories + items) |
| GET | `/cafe/tables` | Dine-in tables |
| POST / GET | `/cafe/orders` | Create order (201) / list orders |
| GET / PATCH | `/cafe/orders/{id}` | Get / update order |
| POST | `/cafe/orders/{id}/items` | Add line item (201) |
| DELETE | `/cafe/orders/{id}/items/{itemId}` | Void item (204) |
| POST | `/cafe/orders/{id}/kot` | Fire KOT(s) — one per station |
| POST | `/cafe/orders/{id}/payments` | Record payment (auto-marks paid) (201) |
| POST | `/cafe/orders/{id}/invoice` | Issue GST invoice (201) |
| GET | `/cafe/kots` | KOTs filtered by `station` + `status` |
| PATCH | `/cafe/kots/{id}/status` | Advance KOT (sent → preparing → ready) |
| GET | `/cafe/invoices/{id}` | Invoice detail |

---

## Data Model (23 tables)

**Venue & scheduling**
- `venues` — venue (name, timezone, active).
- `courts` — one court per sport (venue_id, sport, capacity, active).
- `schedule_rules` — weekly open/close time blocks per court/weekday.
- `schedule_exceptions` — date overrides; `court_id` nullable (null = venue-wide holiday).

**Bookings & customers**
- `customers` — customer records (name/contact), linked from bookings.
- `bookings` — slot bookings; party_size, price, status lifecycle, `is_primary` for multi-slot, capacity-aware unique index.
- `enquiries` — general + corporate enquiries with status.

**Content**
- `gallery` — gallery items (title, sportSlug, tone, `imageUrl`, approved).
- `testimonials` — testimonials (name, context, quote, approved).
- `cms` — key/label/value content entries.
- `promo_codes` — discount codes.

**Auth**
- `users` — admin/manager/cashier/kitchen accounts (bcrypt password / 4-digit PIN, role).

**Cafe POS**
- `cafe_settings` — business/GST config (GSTIN, invoice series, tax mode).
- `menu_categories` — categories (kind food/beverage, vegType, sort, active).
- `menu_items` — items (price, taxRatePercent, vegType, **station**, packaged, available, imageUrl).
- `cafe_tables` — dine-in tables (label, area, capacity, status free/occupied/reserved).
- `orders` — POS orders (orderNo, orderType, table_id, status, subtotal/taxAmount/total, notes).
- `order_items` — order lines (nameSnapshot, qty, unitPrice, taxRatePercent, line totals, kotStatus, voided).
- `kots` — kitchen order tickets (kotNo, station, status), grouped per station on fire.
- `payments` — payments (mode cash/upi/card, amount, reference).
- `invoices` — GST invoices (invoiceNo, order_id, totals, CGST/SGST, issuedAt).
- `invoice_lines` — invoice line items.
- `invoice_sequences` — atomic per-series/financial-year invoice counters.

---

## Migrations (Alembic)

Linear chain — head is `e1f2a3b4c5d6`. The API auto-upgrades to head on boot (`init_db`).

| # | Revision | Description |
|---|----------|-------------|
| 1 | `ffdacb7fb201` | Baseline current schema |
| 2 | `39c7650a6232` | Phase 0 — venues, courts, `court_id` |
| 3 | `cbcc5e7f4b05` | Phase 1 — schedule rules + exceptions |
| 4 | `d4e5f6a7b8c9` | Phase 2 — party_size (replaces players), price, capacity-aware unique index |
| 5 | `e5f6a7b8c9d0` | Phase 3 — customers table + `bookings.customer_id` |
| 6 | `f6a7b8c9d0e1` | Phase 4 — pricing + promo codes |
| 7 | `a1b2c3d4e5f6` | Phase 5a — `schedule_exceptions.court_id` nullable (venue-wide holidays) |
| 8 | `b2c3d4e5f6a7` | Phase 5b — `gallery.imageUrl` column |
| 9 | `c3d4e5f6a7b8` | Multi-slot booking — `is_primary` flag |
| 10 | `d0e1f2a3b4c5` | Cafe POS Phase 0 — foundation tables |
| 11 | `e1f2a3b4c5d6` | Cafe POS Phase 1 — orders, order_items, kots, payments, invoices, invoice_lines, invoice_sequences **(head)** |

```bash
# from apps/api
alembic upgrade head        # apply all
alembic downgrade -1        # roll back one
alembic heads               # show current head
```

---

## Business Logic

**Availability** — `GET /slots` derives open slots from a court's weekly `schedule_rules`, applies any `schedule_exceptions` for that date (per-court override wins over a venue-wide holiday), subtracts capacity already consumed by existing bookings. Default seeded grid: blocks 06:00–12:00, 14:00–17:00, 18:00–21:00 (12 one-hour slots). Default per-slot price: Cricket ₹1200, Badminton ₹500, Pickleball ₹700.

**Booking integrity** — a capacity-aware unique index prevents double-booking the same court/slot beyond capacity (race-safe). Party size is validated against the sport max (Cricket 11, Pickleball 6, Badminton 4). Multi-slot bookings flag one row `is_primary`.

**GST invoicing** — on invoice issue, the order total is split into **CGST + SGST** per the cafe settings tax rate. Invoice numbers are allocated per **financial year** (e.g. FY 2025-26 → `2526`) from the atomic `invoice_sequences` table. The total is rendered as **amount in words** using Indian numbering (no external dependency). The printable invoice is 80mm thermal HTML served publicly (the invoice UUID is unguessable) that calls `window.print()` on load.

**KOT routing** — firing a KOT groups an order's pending items by their menu item's **station** (`kitchen` / `bar`) and creates one KOT per station; items are marked `sent`. The KDS advances each KOT `sent → preparing → ready`.

**Auth** — JWT signed server-side. Admin login uses `ADMIN_USERNAME`/`ADMIN_PASSWORD` (default `admin`/`admin`). Cashier login uses staff name + 4-digit PIN (bcrypt-hashed in `users.hashed_password`). The cafe guard accepts cashier/kitchen/manager/admin so back-office staff can operate the POS.

**Persistence** — SQLAlchemy 2.0 sync sessions via a `with _session()` context manager (commit on success, rollback on error). SQLite by default; set `DAZY_DB_URL` to point at PostgreSQL with no repo changes. Empty tables are seeded on boot (gallery, testimonials, CMS, venue, one court per sport, schedule rules, promos).
