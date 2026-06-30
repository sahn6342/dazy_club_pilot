# Dazy.club — Master AI Context

> Single source of truth. Feed this file to any AI assistant for full project context.
> Last updated: 2026-06-30

---

## What is Dazy.club?

A premium multi-sport venue booking platform for a single pilot venue offering **Cricket, Badminton, and Pickleball**. Users browse available time slots, select one or more consecutive slots, and confirm a booking. Admins manage courts, schedules, bookings, content (gallery, testimonials, CMS), and promo codes through a separate admin portal.

---

## Monorepo Structure

```
dazy_club_pilot/
├── apps/
│   ├── web/          React 18 + Vite + TypeScript — public booking site (:5173)
│   ├── admin/        React 18 + Vite + TypeScript — admin portal (:5174)
│   └── api/          FastAPI + Python 3.12 — REST API (:8000)
├── packages/
│   └── shared/       TypeScript types shared between web and admin
├── docs/             This folder
├── e2e/              Playwright E2E tests (web/ and admin/ suites)
└── playwright.config.ts
```

**Package manager:** pnpm workspaces  
**Shared package:** `@dazy/shared` — exports `Slot`, `BookingRequest`, `SPORT_LABELS`, etc.

---

## Tech Stack (actual, as implemented)

| Layer | Tech |
|---|---|
| Web / Admin frontend | React 18, TypeScript, Vite, react-router-dom v7, CSS (no Tailwind) |
| API | FastAPI (Python 3.12), Pydantic v2, uvicorn, SQLAlchemy 2.0 (sync), Alembic |
| Database | SQLite (`apps/api/dazy.db`), Alembic migrations |
| Auth | JWT HS256 (pyjwt), 8h expiry, admin/manager roles, bcrypt passwords |
| Testing (backend) | pytest + starlette TestClient — 278 tests |
| Testing (E2E) | Playwright — web and admin suites |
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

**bookings**
```
id TEXT PK, slot_id TEXT (format: slot-{court.id}-{date}-{HHMM}),
court_id FK→courts, sport_slug TEXT, date TEXT, start_time TEXT,
end_time TEXT, name TEXT, contact TEXT, players INT,
status TEXT (pending|confirmed|completed|cancelled|no_show),
booking_ref TEXT UNIQUE, price NUMERIC, promo_code TEXT,
message TEXT, createdAt TEXT
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
Seeded keys: `hero_tagline`, `hero_copy`, `faq_advance_booking`, `faq_group_size`, `faq_cancellation`, `contact_phone`, `contact_address`.

**promo_codes**
```
id TEXT PK, code TEXT UNIQUE, kind TEXT (percent|flat), value NUMERIC,
active BOOL, valid_from TEXT, valid_to TEXT, max_uses INT, used_count INT,
sport_slug TEXT (NULL=all sports), createdAt TEXT
```

**admin_users**
```
id TEXT PK, username TEXT UNIQUE, password_hash TEXT,
role TEXT (admin|manager), active BOOL
```
Superadmin from env vars (`ADMIN_USERNAME`, `ADMIN_PASSWORD`). Managers stored here.

**enquiries**
```
id TEXT PK, name TEXT, contact TEXT, message TEXT, sport TEXT,
handled BOOL, createdAt TEXT
```

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
| GET | `/slots?sport=&date=` | Available slots for sport + date. Returns `SlotDto[]`. |
| POST | `/bookings` | Create booking. Body: `BookingCreate`. Returns `BookingResponse`. |
| GET | `/promos/validate?code=&sport=&amount=` | Validate promo code. Returns discount info. |
| GET | `/gallery` | Approved gallery items. |
| GET | `/testimonials` | Approved testimonials. |
| GET | `/cms` | All CMS key-value entries. |
| POST | `/enquiries` | Submit general enquiry. |
| POST | `/admin/login` | Returns JWT. Body: `{username, password}`. |

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
| PATCH | `/admin/bookings/{id}/status` | Update status. Body: `{status}`. |
| DELETE | `/admin/bookings/{id}` | Hard delete booking. |

**Content**
| Method | Path | Description |
|---|---|---|
| GET/POST | `/admin/gallery` | List / create gallery item. |
| PATCH/DELETE | `/admin/gallery/{id}` | Update / delete gallery item. |
| POST | `/admin/gallery/upload` | Upload image file → returns `{imageUrl}`. |
| GET/POST | `/admin/testimonials` | List / create testimonial. |
| PATCH/DELETE | `/admin/testimonials/{id}` | Update / delete testimonial. |
| GET | `/admin/cms` | List all CMS entries. |
| PUT | `/admin/cms/{key}` | Update CMS value. |

**Promos**
| Method | Path | Description |
|---|---|---|
| GET/POST | `/admin/promos` | List / create promo code. |
| PATCH/DELETE | `/admin/promos/{id}` | Update / delete promo code. |

**Users (superadmin only)**
| Method | Path | Description |
|---|---|---|
| GET/POST | `/admin/users` | List / create manager accounts. |
| PATCH/DELETE | `/admin/users/{id}` | Update / delete manager. |

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
```

---

## Frontend — Web App (`:5173`)

**Pages / sections (single-page, scroll-nav):**
- `Home` — hero, sports highlights, gallery carousel, testimonials
- `Book` — full booking flow
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
6. Confirm → success screen with booking ref

**State reset:** switching sport, date, or court clears selected slots.

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
| `/` | Login | Username + password → JWT |
| `/bookings` | Bookings | Table + filter (sport, date, status). Confirm/cancel/complete/no-show actions. |
| `/schedule` | Schedule | Court selector, weekly block editor, per-day accordion, date exceptions |
| `/courts` | Courts | Add/edit/deactivate courts grouped by sport |
| `/gallery` | Gallery | Image grid with add (URL or file upload) / edit / delete / approve/reject |
| `/testimonials` | Testimonials | List with add / edit / delete / approve/reject |
| `/cms` | CMS | Edit key-value content entries inline |
| `/promos` | Promos | Promo code CRUD with kind/value/sport/dates |
| `/users` | Users | Manager account CRUD (superadmin only) |

**Schedule page detail:**
- Court dropdown to select which court to configure
- Weekly editor: table of Mon–Sun with open/close/price per block; "Make continuous", "Copy to all days"
- Advanced section (collapsible): per-day override rows — add/remove time blocks
- Date exceptions panel: add closed dates or special-hours overrides; "Apply to all courts" toggle (default on = venue-wide holiday)

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
| Promo codes | `percent` (e.g. 10% off) or `flat` (e.g. ₹100 off). Can be sport-specific. Applied at booking. |
| Cancelled bookings | Do NOT block slot. Availability re-derived excluding `cancelled`/`no_show`. |
| Double-booking guard | Unique constraint on `(court_id, date, start_time)` where status not cancelled/no_show → 409 on race. |
| Auth roles | `admin` (env-var superadmin) = full access. `manager` (DB) = all except user management. |
| JWT | HS256, 8h expiry, `JWT_SECRET` env var. Login rate-limited (5 attempts). |
| Media | Images as URL strings or local `/media/gallery/` files. Served via FastAPI StaticFiles at `/media`. |
| Seeded data | 3 courts, 63 schedule rules (3 blocks × 7 days × 3 courts), gallery, testimonials, CMS entries, 2 promos (WELCOME10, FLAT100) |

---

## Environment Variables

```
DAZY_DB_URL=sqlite:///./dazy.db        # swap to postgres://... for prod
ADMIN_USERNAME=admin
ADMIN_PASSWORD=admin
JWT_SECRET=changeme
```

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
```

**Run tests:**
```bash
cd apps/api
.venv/Scripts/python.exe -m pytest tests -q
# 278 tests, all pass
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
    availability_service.py  Slot generation from rules + exceptions
    booking_service.py       Booking creation + concurrency guard
  repositories/
    court_repo.py            Court CRUD + clear()
    schedule_repo.py         Rules + exceptions CRUD + clear()
    booking_repo.py          Booking CRUD
    gallery_repo.py          Gallery CRUD + image cleanup
    testimonial_repo.py      Testimonial CRUD
    cms_repo.py              CMS CRUD
    promo_repo.py            Promo CRUD + validation
    customer_repo.py         Customer upsert-by-contact
    user_repo.py             Manager account CRUD
  routes/
    slots.py                 GET /slots
    bookings.py              POST /bookings, GET /promos/validate
    gallery.py               GET /gallery (public, approved only, DB-driven)
    testimonials.py          GET /testimonials (approved only)
    cms.py                   GET /cms
    enquiries.py             POST /enquiries
    admin/
      auth.py                POST /admin/login, rate limiter
      courts.py              Courts CRUD
      schedule.py            Rules + exceptions CRUD
      bookings.py            Admin booking management
      gallery.py             Gallery CRUD + upload
      testimonials.py        Testimonial CRUD
      cms.py                 CMS update
      promos.py              Promo CRUD + validate
      users.py               Manager CRUD
  alembic/
    versions/                Migration scripts (chained)
  tests/
    conftest.py              autouse fixture resets all repos + re-seeds each test
    test_positive.py         Happy-path slot/booking/promo/auth tests
    test_schedule.py         Schedule rules/exceptions tests
    test_admin_courts.py     Courts CRUD tests (24 tests)
    test_edge_cases.py       Boundary/error tests
    test_bookings.py         Booking lifecycle tests
    (+ more test files)

apps/web/src/
  pages/Book.tsx             Full booking flow (sport→date→court→slot→form→confirm)
  pages/Home.tsx             Landing page with gallery carousel
  lib/api.ts                 All API calls (getSlots, createBooking, validatePromo, etc.)
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
  pages/Users.tsx            Manager account CRUD
  components/Sidebar.tsx     Nav with all page links
  lib/api.ts                 Admin API client (get/post/patch/delete/upload)

packages/shared/src/index.ts  Slot, BookingRequest types + SPORT_LABELS

e2e/
  web/booking.spec.ts        Web booking flow E2E
  web/pricing.spec.ts        Promo code E2E
  admin/bookings.spec.ts     Admin booking management E2E
  admin/schedule.spec.ts     Schedule management E2E
  admin/courts.spec.ts       Courts admin E2E
  admin/gallery.spec.ts      Gallery admin E2E
```
