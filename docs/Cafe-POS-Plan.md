# Dazy.club — Café POS, Inventory & GST Billing — Integration Plan

> Build plan for adding a café (food & beverage) operation alongside the existing turf-booking platform.
> Designed to slot into the current FastAPI + SQLAlchemy + React monorepo with the same patterns.
>
> **Status: Phases 0–1 IMPLEMENTED** (Alembic `d0e1f2a3b4c5` foundations + `e1f2a3b4c5d6` POS). Shipped: the `apps/kiosk` POS app, menu categories/items, tables, orders, KOT station routing, payments (cash/UPI/card), and GST invoices (CGST/SGST, financial-year numbering, amount-in-words, 80mm thermal print), plus admin cafe screens. See [Features.md](Features.md) (Kiosk POS & KDS) and [API-Reference.md](API-Reference.md).
> Phases 2–4 remain future work (inventory logic, discounts/comps, dine-in table loop, credit notes, e-invoicing, offline) — tracked in [Roadmap.md](Roadmap.md). GST mode is configurable (see §3).

---

## 1. Scope & locked decisions

We are adding three new capabilities to the existing app: **menu/catalog**, **inventory (product-level)**, and **sales + GST billing** via a new touch **kiosk** app, plus back-office screens in the existing admin portal.

| Decision | Choice | Notes |
|---|---|---|
| Service model | **Hybrid** | Counter "Quick Bill" + table service (waiter → KOT → settle later) |
| Inventory depth | **Product-level only** | Track sellable/packaged goods 1:1. No recipe/BOM layer (seam left for later) |
| GST mode | **Config-driven, default = Regular / Tax Invoice** | Bill of Supply + plain-receipt modes behind one settings toggle |
| Kiosk frontend | **New `apps/kiosk` app (:5175)** | Separate from admin; reuses `@dazy/shared` + existing theme |
| Payments | **Cash + UPI + "mark paid" for pilot** | No gateway yet; adapter later (consistent with DEC-007) |
| Database | **SQLite for pilot; Postgres at real traffic** | Swap via `DAZY_DB_URL`, zero route changes (DEC-006/014) |
| Customers | **Reuse existing `customers` table** | One CRM across turf + café; enables loyalty later |
| Printing | **Browser thermal print + server-side PDF** | Direct ESC/POS optional later |
| Staff auth | **Extend JWT roles + PIN login for counter** | Adds `cashier` (and optional `kitchen`) roles |

### Assumptions flagged as defaults (change any before build)
- Menu prices stored as **tax-inclusive** unless told otherwise (common for café walk-ins); engine back-calculates the taxable value.
- **One counter/terminal** at launch (multiple concurrent counters strengthens the case for Postgres-now).
- Modifiers/variants (e.g., "Large", "extra shot") are supported in the schema but treated as a Phase-1+ polish item.
- KOT routing has at least two stations: `kitchen` and `bar`; configurable per item.

---

## 2. How it fits the existing architecture

No change to the existing stack or turf code. The café is a set of **new bounded modules** following the current patterns:

- **Layering:** `routes → services → repositories → db_models`, singleton repos registered in `deps.py`, Pydantic `Dto`/`Create`/`Update` models — identical to `booking_service.py` etc.
- **Naming (per Naming-Standards.md):** `snake_case` plural tables, `PascalCase…Row` ORM classes, `camelCase` JSON keys, `kebab-case` endpoints. New API namespaces: `/api/v1/cafe/...` (kiosk/public-auth) and `/api/v1/admin/cafe/...` (back-office).
- **Auth:** extend the role enum (`admin`/`manager`) with `cashier` and optional `kitchen`. Add a **PIN login** endpoint issuing a short-lived JWT for fast counter handover.
- **Migrations:** all new tables ship as chained Alembic migrations (consistent with the "Alembic over create_all" decision).
- **Media/theme:** kiosk reuses the dark theme + gold accent (`#d8b456`) and the `@dazy/shared` types package.

### New monorepo additions
```
apps/
  kiosk/        React 18 + Vite + TS — counter/table POS (:5175)   [NEW]
apps/api/
  routes/cafe/        kiosk + admin café routes                    [NEW]
  services/           pos_service, billing_service, inventory_service, kot_service [NEW]
  repositories/       menu_repo, order_repo, invoice_repo, stock_repo, supplier_repo, table_repo [NEW]
docs/cafe/      this plan + future café docs                       [NEW]
```

---

## 3. GST / compliance model (configurable)

A single `cafe_settings` row controls compliance behaviour so the legal call can be made later without code changes.

- **`scheme = regular`** → issues a **Tax Invoice**, charges GST (CGST + SGST for intra-state). Default.
- **`scheme = composition`** → issues a **Bill of Supply**, shows **no GST**, prints the composition declaration.
- **`scheme = unregistered`** → issues a plain **Receipt**, no GST, no GSTIN.

### Hard rules the engine enforces
- **Per-line tax rate** (prepared food 5%, packaged goods possibly 5%/18%) → bills can mix rates and must print a **rate-wise tax summary**.
- **Tax computed per line, then summed**, then round-off (not on the grand total).
- **Sequential, gap-free invoice numbers**, unique per **Indian financial year** (Apr–Mar), ≤16 chars, charset `[A-Za-z0-9/-]`. Backed by `invoice_sequences` with a concurrency-safe increment (transaction + retry on SQLite; `SELECT … FOR UPDATE` on Postgres). Voids never delete a number — cancel the invoice or raise a credit note.
- **No edits to issued invoices** — corrections/refunds go through **credit notes**.
- **FSSAI license number** prints on every receipt (legal requirement for food businesses, separate from GST).
- **E-invoicing (IRN/QR)** only applies above ₹5 cr turnover → not built now; an adapter seam is reserved (mirrors the deferred payment/OTP adapters).

### Mandatory Tax-Invoice fields (Rule 46) baked into the template
Supplier legal name + address + GSTIN · "Tax Invoice" / "Bill of Supply" title · invoice no + date (+ time for F&B) · customer name + GSTIN (and address/state if value > ₹50,000) · place of supply + state code · per line: description, HSN/SAC, qty, unit, rate, taxable value, GST rate, CGST/SGST · rate-wise tax summary · round-off · grand total · amount in words · FSSAI number · payment mode · declaration/footer.

> ⚠️ Rates and HSN/SAC are configurable, not hard-coded. Confirm the exact values with a CA — wrong invoices carry penalties. See the go-live checklist in §10.

---

## 4. Data model (new tables)

All follow existing conventions: `PascalCase…Row` ORM classes, text UUID/slug PKs, `camelCase` columns.

### Config
**cafe_settings** — single row
```
id TEXT PK, legalName TEXT, gstin TEXT NULL, fssaiNumber TEXT,
addressLine TEXT, city TEXT, stateName TEXT, stateCode TEXT,
scheme TEXT (regular|composition|unregistered),
priceIncludesTax BOOL, defaultTaxRate NUMERIC,
invoiceSeriesPrefix TEXT, billOfSupplySeriesPrefix TEXT,
logoUrl TEXT, declaration TEXT, footerNote TEXT,
roundingEnabled BOOL, createdAt TEXT, updatedAt TEXT
```

### Catalog
**menu_categories**
```
id TEXT PK, name TEXT, kind TEXT (food|beverage|packaged|combo),
vegType TEXT NULL (veg|nonveg|egg|na), sortOrder INT, active BOOL, createdAt TEXT
```
**menu_items** — inventory fields live here (product-level)
```
id TEXT PK, category_id FK→menu_categories, name TEXT, description TEXT,
price NUMERIC, taxRatePercent NUMERIC, hsnSac TEXT, vegType TEXT,
isPackaged BOOL, station TEXT (kitchen|bar|none), available BOOL,
trackInventory BOOL, currentQty NUMERIC NULL, reorderLevel NUMERIC NULL,
unit TEXT NULL, purchaseCost NUMERIC NULL, barcode TEXT NULL,
imageUrl TEXT, sortOrder INT, createdAt TEXT
```
**item_variants** *(optional)* — `id, item_id FK, name, priceDelta, sortOrder`
**modifier_groups / modifiers** *(optional, later)* — selectable add-ons with price deltas

### Inventory (product-level)
**suppliers** — `id, name, gstin NULL, phone, email, addressLine, active, createdAt`
**purchases** (GRN header)
```
id TEXT PK, supplier_id FK NULL, supplierInvoiceNo TEXT, purchaseDate TEXT,
totalAmount NUMERIC, taxAmount NUMERIC NULL, notes TEXT,
status TEXT (draft|received), createdBy TEXT, createdAt TEXT
```
**purchase_items**
```
id TEXT PK, purchase_id FK, menu_item_id FK, description TEXT,
qty NUMERIC, unit TEXT, unitCost NUMERIC, taxRatePercent NUMERIC NULL,
packSize NUMERIC NULL, batchNo TEXT NULL, expiry TEXT NULL
```
**stock_movements** — immutable ledger; single source of truth (currentQty is a cache)
```
id TEXT PK, menu_item_id FK, type TEXT (opening|purchase|sale|wastage|adjustment|transfer),
qtyDelta NUMERIC, unitCostAtMovement NUMERIC NULL,
refType TEXT NULL (purchase|order|count|manual), refId TEXT NULL,
reason TEXT NULL, createdBy TEXT, createdAt TEXT
```
**stock_counts** — `id, countDate, status (open|finalized), notes, createdBy, createdAt`
**stock_count_items** — `id, count_id FK, menu_item_id FK, systemQty, countedQty, varianceQty`
(Finalizing a count writes `adjustment` rows to `stock_movements`.)

### Sales / POS (hybrid)
**cafe_tables**
```
id TEXT PK, label TEXT, area TEXT NULL, capacity INT,
status TEXT (free|occupied|reserved), active BOOL, sortOrder INT
```
**orders**
```
id TEXT PK, orderNo TEXT, orderType TEXT (quick|dine_in|takeaway),
table_id FK NULL, customer_id FK NULL→customers,
status TEXT (open|in_kitchen|served|billed|paid|cancelled|void),
subtotal NUMERIC, discountType TEXT (none|percent|flat), discountValue NUMERIC,
discountAmount NUMERIC, taxAmount NUMERIC, roundOff NUMERIC, total NUMERIC,
notes TEXT, createdBy TEXT, createdAt TEXT, updatedAt TEXT
```
**order_items** — snapshots so historical bills never change
```
id TEXT PK, order_id FK, menu_item_id FK, kot_id FK NULL,
nameSnapshot TEXT, variantSnapshot TEXT NULL, modifiersSnapshot TEXT NULL,
qty NUMERIC, unitPrice NUMERIC, taxRatePercent NUMERIC, hsnSacSnapshot TEXT,
lineSubtotal NUMERIC, lineTax NUMERIC, lineTotal NUMERIC,
kotStatus TEXT NULL (pending|sent|preparing|ready|served),
voided BOOL, voidReason TEXT NULL, createdAt TEXT
```
**kots** — Kitchen Order Tickets (routing + status)
```
id TEXT PK, kotNo TEXT, order_id FK, station TEXT,
status TEXT (pending|preparing|ready|served), printedAt TEXT NULL, createdAt TEXT
```
**payments** — multiple rows per order = split payment
```
id TEXT PK, order_id FK, invoice_id FK NULL,
mode TEXT (cash|card|upi|wallet|other), amount NUMERIC,
reference TEXT NULL, createdBy TEXT, createdAt TEXT
```

### Billing
**invoices**
```
id TEXT PK, invoiceNo TEXT, invoiceType TEXT (tax_invoice|bill_of_supply|receipt),
series TEXT, financialYear TEXT, order_id FK,
customer_id FK NULL, customerName TEXT NULL, customerGstin TEXT NULL,
placeOfSupply TEXT, stateCode TEXT,
taxableValue NUMERIC, cgst NUMERIC, sgst NUMERIC, igst NUMERIC,
roundOff NUMERIC, total NUMERIC, amountInWords TEXT,
status TEXT (issued|cancelled), issuedBy TEXT, issuedAt TEXT
```
**invoice_lines**
```
id TEXT PK, invoice_id FK, description TEXT, hsnSac TEXT, qty NUMERIC, unit TEXT,
rate NUMERIC, taxableValue NUMERIC, gstRatePercent NUMERIC,
cgst NUMERIC, sgst NUMERIC, igst NUMERIC, lineTotal NUMERIC
```
**invoice_sequences** — gap-free counter
```
id TEXT PK (series-financialYear), series TEXT, financialYear TEXT, lastNumber INT
```
**credit_notes** + **credit_note_lines** — refunds/corrections, referencing the original invoice.

---

## 5. API endpoints (representative)

### Kiosk / POS (auth: `cashier`+)
```
POST   /cafe/login                      PIN → short-lived JWT
GET    /cafe/menu                       categories + available items
GET    /cafe/tables                     table map + status
POST   /cafe/orders                     create order (quick | dine_in | takeaway)
GET    /cafe/orders?status=&table_id=   open orders
GET    /cafe/orders/{id}
PATCH  /cafe/orders/{id}                discount / notes / status
POST   /cafe/orders/{id}/items          add line(s)
DELETE /cafe/orders/{id}/items/{lineId} void line (reason required)
POST   /cafe/orders/{id}/kot            fire KOT(s) to station(s)
POST   /cafe/orders/{id}/payments       record payment (supports split)
POST   /cafe/orders/{id}/invoice        issue invoice (mode per settings)
GET    /cafe/invoices/{id}/print?format=thermal|pdf
POST   /cafe/orders/{id}/move-table | /merge | /split
GET    /cafe/kots?station=&status=      KDS feed
PATCH  /cafe/kots/{id}/status           preparing → ready → served
```

### Admin / back-office (auth: `manager`/`admin`)
```
GET/PUT     /admin/cafe/settings
CRUD        /admin/cafe/categories, /admin/cafe/items, /admin/cafe/tables
CRUD        /admin/cafe/suppliers, /admin/cafe/purchases (+ /receive)
GET         /admin/cafe/stock                       current levels + low-stock
POST        /admin/cafe/stock/adjust                wastage/manual adjustment
GET         /admin/cafe/stock/movements             ledger
CRUD        /admin/cafe/stock-counts (+ /finalize)
GET         /admin/cafe/invoices                     list/search
POST        /admin/cafe/invoices/{id}/cancel
POST        /admin/cafe/credit-notes
GET         /admin/cafe/reports/{sales|gst-summary|item-sales|variance|day-end}
```

---

## 6. The kiosk app (`apps/kiosk`)

Touch-first, fast, runs all day on a tablet/touchscreen. Two primary modes:

- **Quick Bill (counter):** pick items → cart → discount (if allowed) → take payment → issue bill → print. Order + payment in one step. Best for QSR-style walk-ups.
- **Tables (dine-in):** floor view of tables (free/occupied/reserved) → open a tab → add items over time → **fire KOTs** to kitchen/bar → **merge/split** → settle and print at the end.

Supporting screens: **KDS** (kitchen display — live ticket queue per station, tap to mark ready/served) and a lightweight **PIN switch** for staff handover. Tech: same React 18 + Vite + TS + plain CSS as the other apps, `useState` + direct API calls (no Redux), reusing `@dazy/shared`.

---

## 7. Billing engine & bill template

- **`billing_service.issue_invoice(order)`** — snapshots all lines, computes per-line CGST/SGST, applies round-off, reserves the next gap-free number for the current FY/series, persists `invoices` + `invoice_lines`, returns a print payload.
- **Two render targets:**
  - **Thermal (80mm/58mm):** HTML template printed straight from the kiosk browser — works with virtually any printer, no driver work for the pilot.
  - **PDF (A4/A5):** generated server-side in FastAPI for email/WhatsApp or B2B customers.
- **Custom template, config-driven:** business header/logo/GSTIN/FSSAI/declaration pulled from `cafe_settings`; all Rule-46 fields (§3) baked in; a couple of preset layouts to choose from. Switches between "Tax Invoice", "Bill of Supply", and "Receipt" automatically based on `scheme`.
- **Corrections:** credit notes for post-issue refunds/returns; voids before issue simply cancel the order line with a logged reason.

---

## 8. Reports

Query-driven (no new tables): **daily/shift sales summary**, **rate-wise GST summary** mapping to GSTR-1/GSTR-3B for the CA, **item-wise sales**, **sold-vs-counted variance**, **wastage**, and a **day-end "Z" report** with payment-mode breakdown for cash reconciliation. Export to Excel/CSV for the accountant.

---

## 9. Roles & auth

Extend the existing JWT role model:
- `admin` / `manager` — unchanged, gain café back-office access.
- `cashier` — kiosk Quick Bill + Tables + issue bills; no settings/reports.
- `kitchen` *(optional)* — KDS only.
- **PIN login** at the counter issues a short-lived JWT for quick handover; every void/discount is logged with the staff ID (anti-theft, reviewable in admin).

---

## 10. Phased roadmap

| Phase | Delivers | Outcome |
|---|---|---|
| **0 — Foundations** | `cafe_settings`, categories/items (tax + HSN), tables setup, `cashier` role, kiosk skeleton | You can model the menu |
| **1 — POS + GST billing (MVP)** | Quick Bill + Tables flows, KOT firing, payments (cash/UPI/mark-paid), invoicing engine + thermal receipt + PDF | Take an order, hand a compliant bill |
| **2 — Inventory (product-level)** | Suppliers, purchases/GRN, stock ledger, adjustments/wastage, low-stock alerts, stock count + variance | You know what you have |
| **3 — Back-office polish** | Credit notes/refunds, reports + GSTR export, discounts/promo reuse, KDS refinement, loyalty on shared customers | Control & compliance |
| **4 — When needed** | Postgres swap, offline mode, e-invoice adapter (>₹5 cr), Swiggy/Zomato/ONDC, recipe-level upgrade | Scale |

Each phase is independently shippable and adds tables/routes without touching existing turf code.

---

## 11. Go-live checklist (resolve before charging customers)

- [ ] Confirm whether the turf entity already holds a **GSTIN**.
- [ ] Decide **same PAN/entity** vs **separate company** for the café (with CA).
- [ ] Confirm café **output rate** (5% expected) and correct **HSN/SAC** per item type (prepared vs packaged).
- [ ] Confirm whether **composition** is available given turf service income (likely not).
- [ ] Decide **tax-inclusive** vs **tax-on-top** menu pricing.
- [ ] Obtain **FSSAI license number** for the receipt.
- [ ] Confirm **invoice series format** and starting number with CA.
- [ ] Decide **number of counters** (affects SQLite-vs-Postgres timing).
- [ ] Choose **printer/hardware** (thermal size; cash drawer; barcode scanner for packaged goods).

---

## 12. Open / future items

- **Recipe-level inventory** — the schema leaves a clean seam (introduce `stock_items` + `recipe_components`) if you later want ingredient-level depletion and true food-cost.
- **Offline mode** — counters with flaky internet; deferrable for a single online counter.
- **E-invoicing adapter** — only if turnover crosses ₹5 cr.
- **Aggregators (Swiggy/Zomato/ONDC)** — note Section 9(5): the aggregator collects GST on delivery orders.
- **Payment gateway** — slots into the same adapter as the deferred turf payment provider.
