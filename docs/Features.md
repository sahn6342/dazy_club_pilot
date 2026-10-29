# Dazy Club — Feature Catalog

Complete reference of every feature across the four apps, with screenshots. For the REST API and data model, see [API-Reference.md](API-Reference.md).

- [🌐 Web — Public Website](#-web--public-website)
- [🛠️ Admin — Back-Office](#-admin--back-office)
- [🍽️ Kiosk — Cafe POS & KDS](#-kiosk--cafe-pos--kds)
- [⚙️ Backend — Cross-Cutting](#-backend--cross-cutting)

---

## 🌐 Web — Public Website

Customer-facing site at **:5173**. Dark, gold-accent theme; fully responsive (desktop + mobile).

### Home

The landing page: hero with CMS-driven tagline/copy, the four sports, an "In action" video strip, a live gallery and testimonials.

![Web home](screenshots/web-home.png)

- **Hero** — tagline + body copy pulled from CMS (`hero_tagline`, `hero_copy`); call-to-action into booking.
- **Sports** — Cricket, Football, Badminton, Pickleball cards in a swipeable strip (3 / 2 / 1 per screen by width, auto-advancing, looping without a rewind; pauses on hover/touch).
- **In action** — four short muted looping clips (`apps/web/public/videos/*.mp4` with posters), shown in the same kind of strip; only clips in view play, and none autoplay with reduced motion. The full-size originals live in the git-ignored `media/` folder.
- **Gallery** — driven live from the API (`GET /gallery`, approved items only), images render from uploaded/managed `imageUrl`.
- **Testimonials** — real Google reviews (first name + initial, placeholder avatars) in a carousel with a fixed card height.
- **Search-engine files** — the tab/search icon is served as `favicon.ico` plus 48px and 192px PNGs (Google only shows a favicon that is a square multiple of 48px; the old 32px one was ignored), the page has a canonical URL, absolute social-preview image URLs and `WebSite`/`Organization` structured data, and `robots.txt` + `sitemap.xml` list the public pages. After changing the logo, request re-indexing in Google Search Console; Google updates the icon in results on its own schedule.
- **Header menu** — on screens 720px wide or less the header is a single row (logo + menu button) and the links (Home, Book, My Bookings, Contact) open as a dropdown panel with large touch targets; it closes when a link is chosen, on Escape, on a tap outside, or when the screen grows. Wider screens show the links in the header row.
- **Footer (every page)** — logo, tagline and the venue's contact details from the CMS (Admin → Contact Details): address (links to Google Maps), phone, email, hours and social links; fields left empty in the admin are not shown. The Contact page no longer has its own venue strip. The WhatsApp button uses the admin's WhatsApp number, or the venue phone when none is set.

**Mobile:**

![Web home mobile](screenshots/web-home-mobile.png)

### Book

The booking flow: choose a sport, choose a date, see **live availability slots**, and book one or more slots.

![Web book](screenshots/web-book.png)

- **Sport selector** — Cricket / Football / Badminton / Pickleball.
- **Date picker** — bookable window (7 days ahead).
- **Live slots** — fetched from `GET /slots`; availability is computed from schedule rules, exceptions (holidays/special hours), capacity, and existing bookings. Closed days / blocked dates show no slots.
- **Multi-slot booking** — select consecutive slots; one is flagged primary.
- **Party size & price** — party size limited per slot (Cricket 25, Football 25, Badminton 4, Pickleball 4); price derives from per-sport base price.
- **Promo codes** — validated via `GET /promos/validate` before submission.
- **Booking submission** — `POST /bookings` returns a booking reference immediately; customer record is created/linked. A priced slot goes to `pending` and opens the **payment panel** (dev-simulate buttons or real Razorpay checkout, depending on `DAZY_PAYMENT_PROVIDER`); a free slot (e.g. a 100%-off promo) confirms immediately.
- **Advance or full payment** — when the booking total is more than the advance (default ₹500, set in Admin → Contact Details, `0` switches it off), the form shows "Pay in full ₹X" (preselected) or "Pay ₹500 advance now, ₹X−500 at the venue" next to the price. The advance is **non-refundable** and one flat amount per booking; paying only the advance still **confirms** the booking, and the confirmation card, My Bookings and the confirmation message show what was paid and the balance due at the venue. The option follows the promo-discounted total and disappears when that is not more than the advance; the API enforces it (`paymentOption`, 422 `advance_not_available`) and the page reads the amount from `GET /public-config` (`advanceAmount`).
- **After booking** — the page is never locked. A confirmed booking becomes a compact card above the slot picker (booking ID with a Copy button, a "take a screenshot or note down this booking ID" reminder, the amount and a link to My Bookings) and stays there while the customer books more. Tapping another slot, sport or date while a payment is pending leaves the payment step (also possible with "Choose a different slot"): a banner says the slot is held for 15 minutes and can be resumed from My Bookings with the ID.
- **No food & drinks ordering on the website** — the Book page and My Bookings do not offer a café pre-order (the `POST /bookings/{ref}/preorder` API and the kiosk's pre-order badge still exist).

**Mobile:**

![Web book mobile](screenshots/web-book-mobile.png)

### My Bookings

Self-service booking lookup at `/my-bookings` — no login. Enter the booking ref (pre-filled if arriving from a payment-reminder link) + the phone/email used at booking time.

- **Pending booking** — resumes payment with the *original* checkout order (never a second gateway charge for one booking).
- **Confirmed booking** — shows the details and the paid amount; an advance booking also shows the balance to pay at the venue.
- Wrong contact or unknown ref → generic "not found" (no enumeration); rate-limited per IP.
- Exists because a closed tab or reload had no other way back to a pending payment (there's no customer login/profile system).

### Contact

General enquiry and corporate/event enquiry, each its own form.

| General | Corporate |
|---------|-----------|
| ![Contact general](screenshots/web-contact-general.png) | ![Contact corporate](screenshots/web-contact-corporate.png) |

- **General enquiry** — `POST /contact-enquiries`; name, contact, message.
- **Corporate/event enquiry** — `POST /corporate-enquiries`; captures event details for the team to follow up.
- **Venue details** — address, phone, email, hours from CMS (`venue_*` keys).
- Client-side validation with inline field errors; FastAPI 422 validation errors are surfaced legibly (array `detail` joined into a readable message).

---

## 🛠️ Admin — Back-Office

Staff console at **:5174**. JWT login (`admin`/`admin` in dev). Left sidebar groups **Venue/Booking**, **Content**, and **Cafe** sections. Destructive actions use an in-app confirm dialog (no native `window.confirm`).

### Login

![Admin login](screenshots/admin-login.png)

Username + password → JWT stored client-side. Wrong credentials show an inline error. Logout clears the session.

### Dashboard

![Admin dashboard](screenshots/admin-dashboard.png)

Real venue KPIs, computed in the venue's timezone (not browser/server local):
- **Bookings today** — count + revenue (confirmed, priced bookings only).
- **Café revenue today** — sum of issued invoices.
- **Occupancy today** — booked slots ÷ bookable slots.
- **Pending bookings** / **New enquiries** — quick-glance counts, unchanged from before.
- **Day-close (Z-report)** — a date-pickable table of café payment totals by mode (cash/UPI/card), for reconciling the till.

### Navigation on small screens

At 760px wide or less the sidebar becomes a sticky bar (logo + menu button) and all links, including the Café POS group, open as a scrollable dropdown panel; it closes on choosing a link, Escape, a tap outside, or when the screen grows. Wider screens keep the sidebar. Pages never scroll sideways on a phone: the content column is `minmax(0, 1fr)`, so a wide table scrolls inside its own box instead of stretching the page (guarded by `e2e/admin/no-horizontal-scroll.spec.ts`, which checks the layout width of all 18 pages in real mobile emulation).

### Footer

Every admin page ends with the website's footer (logo, tagline, address linking to Google Maps, phone, email, hours, socials) from the public `GET /venue`, so Admin → Contact Details drives all three apps. Empty fields are not shown; if the details cannot be loaded only the logo and tagline remain. The login page has none.

### Bookings

![Admin bookings](screenshots/admin-bookings.png)

- List all bookings (`GET /admin/bookings`).
- Update booking status (`PATCH /admin/bookings/{id}`) through the status lifecycle.
- Cancel/delete a booking (`DELETE`, confirm dialog).
- **Advance bookings** — the Price cell shows the advance and the balance; **Collect balance** (`POST /admin/bookings/{id}/collect-balance`, admin only) records cash / UPI / card taken at the venue (partial amounts allowed, never more than the balance) and is audited. The advance is never refundable: the refund dialog says so, nothing is refundable, and cancelling only frees the slot. The CSV export adds Payment Option, Amount Paid and Balance Due.
- **Walk-in booking** — **+ Walk-in booking** opens `/bookings/new`: pick sport, day (today to +6), court and consecutive slots (the hour in progress is allowed), enter the customer's name and phone, choose **Cash** or **UPI** (optional reference) and confirm. The booking is confirmed and paid at once with no online payment (`POST /admin/bookings/walkin`, audited as `booking.walkin_create`). The list marks it "Counter · Cash/UPI"; it has no Refund button (no gateway payment), and the CSV export adds Source and Payment Mode.

![Admin walk-in booking](screenshots/admin-walkin-booking.png)

### Bills

![Admin bills](screenshots/admin-bills.png)

- **New bill** — add rows (item, qty, rate **including GST**, GST % typed in a box, default 18, 0–28 with decimals); the amount of a row is qty × rate, the tax is taken out of it, and the totals (taxable value, CGST, SGST, total) update as you type. The total is the sum of the rows, not rounded. The server recomputes every figure on save. **Save & print** gives the bill its number (`2026-27/0001`: financial year, then a running number that restarts each 1 April) and opens the A4 print view. Bills issued before this change took the rate without GST and still print that way ("Rate (excl. GST)").
- **Print view** (`/bills/{id}/print`) — A4 sheet with logo, business name, address, phone, GSTIN, bill number and date, items with GST split, amount in words and a signature line. For paper that already has a printed letterhead, untick **Print letterhead** and set **Top space (mm)**; both are remembered on this browser.
- **Past bills** — search by bill number, customer name or phone, filter by date and status, **Reprint** or **View** any old bill.
- **Void** — a bill can never be edited or deleted. A mistake is voided with a reason; the bill prints with a VOID mark and its number is not reused.
- The header (name, address, phone, email on separate lines, GSTIN) comes from Admin → Contact Details, including its **GSTIN** field; Café Settings are not used. With no GSTIN the sheet says "Bill" instead of "Tax Invoice". GST is intra-state only (CGST + SGST).

### Schedule

Data-driven availability. Two views: **weekly rules** and **advanced** (date exceptions).

| Weekly rules | Advanced / exceptions |
|--------------|------------------------|
| ![Schedule](screenshots/admin-schedule.png) | ![Schedule advanced](screenshots/admin-schedule-advanced.png) |

- **Weekly rules** — per-weekday open/close time blocks per court (`/admin/schedule/rules` CRUD). Helpers: "Make continuous", "Add block", "Copy to all days" (readable secondary-button styling).
- **Date exceptions** — close a day or set special hours for a specific date (`/admin/schedule/exceptions`). **"Apply to all courts" (holiday)** toggle, default on → a venue-wide exception (`court_id = null`) closes every sport that day; per-court exceptions are also supported. Venue-wide rows show "All courts".
- **Validation** — empty date is blocked with an inline "Date is required." error before submit.

### Courts

![Admin courts](screenshots/admin-courts.png)

CRUD for courts (`/admin/courts`) — one court per sport seeded by default; capacity and active flags editable.

### Promos

![Admin promos](screenshots/admin-promos.png)

Promo-code CRUD (`/admin/promos`) — create/edit/remove discount codes used by the booking flow.

### Enquiries

![Admin enquiries](screenshots/admin-enquiries.png)

Triage general + corporate enquiries (`GET /admin/enquiries`); update status (`PATCH`).

### Gallery

![Admin gallery](screenshots/admin-gallery.png)

- Full CRUD (`/admin/gallery`) with **image upload** (`POST /admin/gallery/upload` → stored under `/media/gallery/...`) or pasted URL.
- Approve/reject controls; only approved items appear on the public site (realtime — public gallery reads the DB).
- Edit title/sport/tone; delete (confirm dialog) best-effort removes the local image file.

### Testimonials

![Admin testimonials](screenshots/admin-testimonials.png)

Full CRUD (`/admin/testimonials`) — add/edit/delete plus approve/reject. Approved items show on the public Home.

### CMS

![Admin CMS](screenshots/admin-cms.png)

Key/label/value content store (`/admin/cms`). Create new keys (409 on duplicate), edit label + value, delete. Drives hero copy, FAQs, footer, and venue contact details on the web site.

### Users

![Admin users](screenshots/admin-users.png)

User/role management (`/admin/users`) — create admin/manager/cashier/kitchen users; cashier/kitchen accounts use a 4-digit PIN for kiosk login. Remove users (confirm dialog with the username).

### Contact Details

![Admin contact details](screenshots/admin-contact-details.png)

Edit the venue contact block (address, phone, email, hours, socials) shown in the website footer, the slot booking GST rate and the **advance payment amount** (₹, non-refundable, `0` = customers must pay in full; validated by the API).

### Cafe — Menu Categories

![Cafe categories](screenshots/admin-cafe-categories.png)

CRUD for menu categories (`/admin/cafe/categories`) — name, kind (food/beverage), veg type, sort order, active. Delete via confirm dialog.

### Cafe — Menu Items

![Cafe items](screenshots/admin-cafe-items.png)

CRUD for menu items (`/admin/cafe/items`) — name, description, price, GST tax rate %, veg type, **station (kitchen/bar)** for KOT routing, packaged flag, availability, image, sort order.

### Cafe — Tables

![Cafe tables](screenshots/admin-cafe-tables.png)

CRUD for dine-in tables (`/admin/cafe/tables`) — label, area, capacity, sort order, active, and **status (free/occupied/reserved)** editable from the edit form.

### Cafe — Settings

![Cafe settings](screenshots/admin-cafe-settings.png)

Cafe/GST configuration (`/admin/cafe/settings`) — business name, GSTIN, address, tax mode, invoice series, etc. — feeds the GST invoice generator.

### Cafe — Orders (read-only)

![Cafe orders](screenshots/admin-cafe-orders.png)

Back-office view of all POS orders (`/cafe/orders`). Filter tabs (All / Open / Paid / Cancelled) with counts; status badges; expand a row to see items + payments.

---

## 🍽️ Kiosk — Cafe POS & KDS

Touch-first POS at **:5175**. Cashier logs in with staff name + 4-digit PIN. Top nav: **Menu · Orders · Tables · KDS**. On screens 720px wide or less the nav buttons and Logout sit behind a menu button in the header (one shared `KioskHeader` component on every page). Every page ends with a slim strip of the venue's address, phone and hours (from `GET /venue`; hidden if it cannot be loaded). On phones the menu screen stacks (category chips, items, then the order) and no page scrolls sideways. Auth token in `localStorage` (`dazy_kiosk_token`).

### Login

![Kiosk login](screenshots/kiosk-login.png)

- Staff name + 4-digit PIN pad (digits, backspace, confirm). Keyboard entry also supported.
- Errors: invalid PIN, fewer than 4 digits, missing staff name.
- Already-authenticated cashiers are redirected straight to Menu; unauthenticated access to any page bounces to login.

### Menu (order building)

![Kiosk menu](screenshots/kiosk-menu.png)

- **Category rail** + item grid; veg/non-veg/egg dots; price per item.
- **Cart panel** — add/remove with qty steppers; live **Subtotal / Tax / Total** (GST-inclusive math, 2-decimal amounts).
- **Place Order** → `POST /cafe/orders` (quick or dine-in) → opens the **Payment modal**.

**Payment flow (modal):**
- Mode: **Cash / UPI / Card**; UPI/Card show a reference field (correctly labelled per mode).
- **Round-off disclosure** — when server total differs from subtotal+tax, the round-off line is shown so the cashier sees the exact charge.
- `POST /cafe/orders/{id}/payments` records payment (auto-marks order paid when fully settled), then `POST /cafe/orders/{id}/invoice` issues a **GST invoice**.
- **Print Receipt** opens the 80mm thermal invoice (`GET /cafe/invoices/{id}/print`, public HTML that auto-triggers `window.print()`).
- Overlay click is blocked while a payment is processing.

### Orders (history & in-process)

![Kiosk orders](screenshots/kiosk-orders.png)

- **Open** tab — open/in-kitchen/served orders, each with a **Pay** action (guarded: only payable, non-zero, item-bearing orders).
- **History** tab — paid/cancelled orders, marked "✓ Settled".
- Orders created by a customer's web pre-order (linked to a turf booking) show a **"🎫 Pre-order"** badge, so staff know to have it ready for the customer's slot time.
- Auto-refreshes every 15s; manual refresh button.

### Tables

![Kiosk tables](screenshots/kiosk-tables.png)

Floor view of tables with status; auto-refreshes every 30s. Logout clears the token.

### KDS — Kitchen Display System

![Kiosk KDS](screenshots/kiosk-kds.png)

- Polls pending KOTs for a station (`GET /cafe/kots?station=kitchen&status=pending`) every 10s.
- Each KOT card shows its number, the source order number, and line items with quantities.
- **Mark Preparing** / **Mark Ready** (`PATCH /cafe/kots/{id}/status`); ready tickets drop off the board.

---

## ⚙️ Backend — Cross-Cutting

FastAPI at **:8000** (`/api/v1` prefix). Full endpoint list, data model, and migrations in [API-Reference.md](API-Reference.md). Highlights:

- **Auth & roles** — JWT. `get_current_admin` (password login) guards admin routes; `get_current_cashier` (accepts cashier/kitchen/manager/admin) guards cafe routes. Cashier PINs are 4-digit, bcrypt-hashed.
- **Scheduling engine** — availability computed from weekly **rules** + date **exceptions** (venue-wide or per-court), capacity, and existing bookings. Race-safe via a capacity-aware unique index.
- **GST billing** — invoices split CGST/SGST, number per **financial year** (e.g. `2526`) via an atomic sequence table, render **amount in words** (Indian numbering, no external deps), and print as 80mm thermal HTML.
- **KOT routing** — on "fire KOT", pending order items are grouped by **station** into one KOT per station.
- **Persistence** — SQLAlchemy 2.0 (sync) over SQLite; one `with _session()` context per repo op (auto commit/rollback). Swappable to PostgreSQL via `DAZY_DB_URL`. Schema managed by Alembic (auto-upgrades to head on boot); demo data seeded into empty tables.
- **Content** — gallery/testimonials/CMS are DB-driven and surface to the public site in realtime; uploaded images served from `/media`.
