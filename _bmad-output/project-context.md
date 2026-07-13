---
project_name: 'dazy_club_pilot'
user_name: 'Sahn'
date: '2026-07-03'
sections_completed: ['technology_stack', 'language_rules', 'framework_rules', 'testing_rules', 'quality_rules', 'workflow_rules', 'anti_patterns', 'scope_boundaries', 'frontend_divergence', 'infra_rules']
status: 'complete'
rule_count: 95
optimized_for_llm: true
---

# Project Context for AI Agents

_Critical rules and patterns AI agents must follow when implementing code in dazy_club_pilot. Focused on unobvious details — not things obvious from reading any single file._

---

## Technology Stack & Versions

**Backend** (`apps/api/`)
- FastAPI, Python ≥3.12, Pydantic v2 (≥2.9), SQLAlchemy 2.0 — **sync**, not asyncio
- Alembic migrations, uv package manager (`apps/api/uv.lock`)
- Auth: pyjwt (HS256), bcrypt ≥4.0
- DB: SQLite (pilot) via `DAZY_DB_URL` — swap to Postgres is meant to be zero-code-change (repo pattern); concurrent-booking pressure under SQLite is the trigger point most likely to force this swap
- Testing: pytest ≥8.3, httpx, pytest-asyncio (`asyncio_mode = "auto"`)

**Frontends** (`apps/web`, `apps/admin`, `apps/kiosk`)
- React 19, Vite 6, TypeScript 5.7, react-router-dom v7
- Plain CSS + CSS variables — **no Tailwind, no CSS-in-JS**
- No Redux/Zustand/Context store — `useState`/`useEffect` only
- pnpm workspaces (plain, **no Turborepo** — `pnpm -r <script>` only, no build cache/pipeline graph), pinned `packageManager: pnpm@11.5.3`
- `@dazy/shared` and `@dazy/ui` linked via `workspace:*` — see **Frontend App Divergence** below, they are not uniformly used

**E2E**: Playwright (`e2e/web`, `e2e/admin`, `e2e/kiosk`)

**Version constraints:**
- SQLAlchemy is sync — never introduce `async def` DB session code
- No Tailwind — don't add utility classes, extend the existing CSS-variable system
- No shared OpenAPI-generated client — frontend interfaces are hand-written per endpoint

---

## Product Scope Boundaries — Built vs Not-Yet-Built

**Read this before adding any feature that "should obviously exist."** Several tables/endpoints are documented as design intent (in `docs/Cafe-POS-Plan.md`, `docs/Decision-Log.md`, `docs/Detailed-Roadmap.md`) but are **not implemented** — verify against actual schema/routes, don't assume:

- **NOT built**: inventory system (`suppliers`, `purchases`, `stock_movements`, `stock_counts` tables), discounts/comps enforcement (schema field `discountAmount` exists but is never set), dine-in table loop (move-table/merge/split), credit notes, e-invoicing (IRN/QR), offline mode, SMS notifications (only console/email adapters exist), wallet (`customer_wallets`/`wallet_ledger`), full reports/CSV export (only dashboard + Z-report exist), WhatsApp/reminders/marketing, subscriptions/autopay/split-payments, self-service reschedule (admin does it manually), full UnitOfWork refactor (only invoice issuance got the injected-session treatment)
- **Café is counter/takeaway-only for launch** — `orderType=dine_in` and table fields exist in schema but the dine-in flow is not wired up; don't build on top of it assuming it works
- **Superseded decision**: pay-at-venue is NOT the default — bookings take **online prepay from day one** (Razorpay). Some older docs/comments may still reference pay-at-venue; the online-prepay flow is current.
- **Booking lifecycle**: `POST /bookings` creates `pending` (slot reserved via unique index) *before* payment completes. The Razorpay **webhook is the source of truth**, not the client-side callback. A timeout sweep releases stale `pending` bookings. Never treat `pending` as a confirmed/final state.
- **Unresolved business decisions** (don't hardcode as if settled): GSTIN entity, café GST composition-scheme eligibility, tax-inclusive-vs-on-top pricing, invoice series format, Postgres migration timeline, SMS/email provider selection, Razorpay KYC.
- Migration chain head is `e1f2a3b4c5d6` — new migrations must chain after it, must round-trip (upgrade→downgrade→upgrade), and must not touch turf/booking code paths unless a phase explicitly calls for it.

---

## Critical Implementation Rules

### Language-Specific Rules

**Python / FastAPI**
- Repos are **module-level singletons** in `apps/api/deps.py` (e.g. `booking_repo = SqliteBookingRepository()`), imported directly into routes (`from deps import booking_repo`). There is **no `Depends()`-based DI** for repos.
- Every repo method opens its **own** `with _session() as s:` block (`apps/api/db.py`) — commits/rollbacks/closes per call. **There is no request-scoped transaction.** A route calling 3 repo methods = 3 separate commits, not one atomic transaction. Don't assume multi-step flows are rollback-safe as a unit.
- The one exception: `invoice_repo.next_number()` / `.create()` take an **optional injected `session=`** so the sequence-bump and the insert share one transaction (DEC-025/DEC-032). This pattern exists only for invoice issuance — don't assume other repos support it.
- `db.py` loads `.env` before anything else specifically so `deps.py` factories see env vars at import time — import order matters, don't reorder.
- **Error handling split by layer**: services raise domain exceptions (e.g. `PromoError` in `pricing_service.py`); routes catch and translate to `HTTPException`. Never raise `HTTPException` from inside a service module.
- `apps/api/repositories/base.py` is largely decorative — concrete repos (`SqliteBookingPaymentRepository`, `SqliteOrderRepository`, etc.) are duck-typed, not guaranteed to inherit a shared CRUD interface. Don't assume all repos expose the same method set.
- Every repo must expose a **`.clear()`** method — tests rely on it for state reset (see Testing Rules). Adding a new repo without `.clear()` will leak state across tests.
- Day-boundary ("today") calculations (dashboard, Z-report, any date-bucketing) **must** use the venue's IANA timezone via `services/venue_tz.py` (Asia/Kolkata) — never server/browser local time; this was a documented bug fix.

**TypeScript / React**
- Files: `PascalCase.tsx` components/pages, `camelCase.ts` libs
- State modeled as **string-literal union**, not booleans: `useState<"idle" | "loading" | "found" | "error">("idle")` — follow this idiom for any new async flow, not separate `loading`/`error` flags.
- No custom hooks extracted for reusable logic (e.g. debounced promo validation is inlined in `Book.tsx`'s `useEffect`, not a `useDebouncedPromo()` hook) — match existing inline style rather than introducing new hook abstractions.
- Page-specific business logic (validators, overlap checks) is colocated in the page file (e.g. `Schedule.tsx`'s `draftToPayload`/`overlapError`), not extracted to a shared lib — match this, don't "clean up" into new modules uninvited.

### Framework-Specific Rules

**FastAPI routes**
- Canonical shape (see `apps/api/routes/bookings.py`): resolve/validate via services → build record objects → repo writes wrapped in `try/except IntegrityError` for unique-constraint races → call `notification_service.notify_*` (never blocks/raises) → return hand-built dict (not always identical to `response_model`).
- Double-booking guard: unique constraint on `(court_id, date, start_time)` excluding cancelled/no_show → catch `IntegrityError` → 409.
- Public-but-unguessable pattern: `GET /cafe/invoices/{id}/print` is intentionally unauthenticated — security relies on UUID unguessability, not auth. Don't assume other `/cafe/*` routes follow this; they don't.
- `get_current_cashier` (café auth guard) intentionally accepts cashier, kitchen, manager, AND admin — broader than the name implies. Don't restrict new café routes to "cashier only."
- Party-size caps are sport-specific server-side validated constants (Cricket 11, Pickleball 6, Badminton 4) — never treat as one generic max.

**Pydantic models** (`apps/api/models.py`)
- No global alias generator / no camelCase↔snake_case config. Field names ARE the wire format, **chosen per-model, inconsistently**: most fields are camelCase (`sportSlug`, `bookingRef`), but some models mix in snake_case (`court_id`, `party_size` on `PromoCodeDto`). **When adding a field, copy casing from sibling fields in the same model** — don't infer a global rule.
- Naming suffixes: `*Dto` (read models to clients), `*Create`/`*Update` (admin mutation payloads), `*Request` (public POST bodies), `*Record` (internal service/repo transfer objects), `*Result` (computed responses).
- `model_config = {"from_attributes": True}` on Dtos built via `Model.model_validate(row)`.
- `model_config = {"frozen": False}` is an explicit tell that the object is mutated in place after construction (e.g. `result.checkout = json.loads(...)`) — not accidental, don't "fix" it.
- Contact validation (phone-or-email) is centralized in `_validate_contact()` (`models.py`) — reuse via `@field_validator`, don't reimplement the regex on new request models.

**Notifications** (`apps/api/services/notification_service.py`)
- Adapter pattern: `NotificationProvider` ABC, `factory.py` picks `console` (dev) or `email` (SMTP) via `DAZY_NOTIFY_PROVIDER`.
- **SMS is documented-not-built** — the email provider explicitly *skips* (not fails) phone-number recipients. Phone-only contacts currently get no notification.
- `send_and_log` and both public `notify_*` functions **never raise** — a notification failure must never fail the calling booking/payment flow. Preserve this if touching notification code.
- No dedup/idempotency logic in the notification layer itself — correctness relies on the caller only invoking `notify_*` once per state transition (e.g. early-return on already-`paid` status before re-notifying).
- Templates are plain functions returning `(subject, body)` tuples — no Jinja/templating engine.

**Cafe POS — Order / KOT state machine** (`pos_service.py`, `order_repo.py`, `kot_repo.py`)
- **Order numbers are timestamp-derived and can collide**: `f"ORD-{ts_ms % 100000:05d}"` cycles every 100s wall-clock; DB has a unique constraint but nothing catches the resulting `IntegrityError` — this will surface as a raw 500. KOT numbers use the same pattern with **no unique constraint at all**, so silent duplicates are possible.
- **Round-off is always to the nearest whole rupee**, computed independently in `order_repo._recalc_totals` and `invoice_repo.create` — both must stay in sync if either changes. Tax must be computed **per-line, summed, then rounded** — never a single flat rate on the order total (mixed 5%/18% items).
- **Item "pending for KOT" = `not voided and kot_id is None`.** Once an item has any `kot_id` it's excluded from future `fire_kot` calls permanently — there's no re-fire/amend path. Adding more of the same menu item creates a new line, not a merged quantity.
- **`fire_kot` is not transactionally safe** — reads items, then menu items, then writes `kot_id` across three separate sessions. Concurrent fire calls on the same order can produce duplicate KOTs.
- **`void_item` has zero state guards** — an item can be voided after KOT-fire, after `preparing`/`ready`/`served`, or after the order is `paid`/`billed`. No check exists. Same for `PATCH /cafe/orders/{id}` status — any status jump (`paid → open`) is accepted with no guard.
- **KOT status transitions are unconstrained** (`preparing|ready|served` regex only) — jumping straight to `served` or going backwards is accepted.

**Cafe POS — Payments & Invoices** (`payment_repo.py`, `invoice_repo.py`)
- **No cap on payment vs remaining balance** — `add_payment` accepts amounts that overshoot the total; only `total_paid >= order.total` flips status to `paid`. Overpayment has no refund/change tracking. Payments can be added to a `cancelled`/`void` order — no guard.
- `PaymentRow.invoice_id` exists in schema but is **never populated anywhere** — payments and invoices are not actually linked in data.
- **Invoice numbering is atomic ONLY when `next_number()`/`create()` share a session** (`session=s` passed through) — any new caller that invokes `next_number()` without passing `session=` opens its own transaction and will burn a number if the subsequent insert fails. This is the one place the shared-session pattern is load-bearing.
- Sequence key is `"{series}-{financialYear}"` (Apr–Mar Indian FY, e.g. `"2526"`). Invoice type/series (`tax_invoice`/INV vs `bill_of_supply`/BOS) is read from **live** `CafeSettingsRow` at issue time, not a per-order snapshot — historical invoices aren't affected if settings change later, but two similar orders issued on different days can differ in type.
- **CGST/SGST is always an even 50/50 split** — no IGST path; intra-state-only assumption baked in.
- Invoices can be issued on an order in **any** status, including unpaid — no check that `order.status == "paid"`. `cancel()` just flips status; there's no auto-replacement/credit-note flow (credit notes aren't built yet).
- GST hard rules from `docs/Cafe-POS-Plan.md`: invoice numbers sequential/gap-free/≤16 chars/`[A-Za-z0-9/-]`; voids never delete a number (cancel or credit-note, not delete); no edits to issued invoices; GST rates/HSN-SAC must come from CA-confirmed config, never hardcoded; Rule-46 mandatory fields (GSTIN/address/state if invoice > ₹50,000, place of supply, HSN/SAC per line) are easy to omit silently.

**Booking-Payment linkage** (`booking_payment_repo.py`, `routes/bookings.py`, `routes/preorders.py`)
- **`booking_payments` keys off `bookingRef`** (shared across all slot rows of a multi-slot booking), not a single booking id. `get_by_ref`/`mark_refunded` take the **latest row by `createdAt`** — if a booking is retried and a second payment row is created for the same ref, the earlier row is silently ignored.
- **`checkoutJson` exists so `/bookings/lookup` can resume the SAME Razorpay order** — any new payment-creation path must reuse `booking_payment_repo.get_by_ref(...).checkoutJson` instead of calling `payment_provider.create_order` again, or customers get orphaned duplicate Razorpay orders.
- `verify_booking_payment` is intentionally idempotent (short-circuits if already `paid`) because both the client callback and the webhook can hit it.
- `orders.booking_id` is a **soft FK with no referential integrity** — deleting a booking doesn't cascade/null the link.
- Public booking-linked endpoints (lookup, payment-verify, preorders) share a trust model: **case-insensitive, trimmed contact compare, generic 404 either way** (no distinguishing "wrong ref" from "wrong contact") — follow this for any new public endpoint keyed by ref+contact.
- Pre-orders require `booking.status == "confirmed"`, always create `order_type="takeaway"` with `table_id=None` regardless of dine-in intent, and must reuse `pos_service.create_order` rather than duplicating pricing/tax logic.

**Rate limiting** (`apps/api/rate_limit.py`)
- **Fully in-memory, per-process** — restarting the API resets all limiter state; will not work correctly across multiple worker processes (each gets an independent counter).
- Sliding window is pruned lazily only when the same key is re-checked — an abandoned key leaks memory forever (no TTL sweep).
- Keyed by client IP with fallback to literal `"unknown"` if `req.client` is `None` — behind a reverse proxy without `X-Forwarded-For` handling, all traffic can collapse onto one bucket.
- Three named limiters (`admin_login_limiter`, `cashier_login_limiter`, `booking_lookup_limiter`) are independent counters, no global cross-endpoint throttle. `.clear()` is test-only — never call it in production code paths.

**Frontend API client** (`apps/web/src/lib/api.ts` — admin/kiosk diverge, see below)
- Every call is a plain `async function` wrapping `fetch` — no axios/class client.
- Base URL: `VITE_API_BASE_URL` env var, default `http://localhost:8000/api/v1`.
- **Error convention** (must copy for new calls): check `!r.ok` → `err = await r.json().catch(() => ({detail: "<fallback>"}))` → `throw new Error(errorMessage(err, fallback))`. `errorMessage()` exists because FastAPI 422 errors return `detail` as an array of `{loc,msg,type}`, not a string — stringifying directly renders `"[object Object]"`.
- TS interfaces are hand-written per endpoint, co-located above the function, and **mirror Python field names verbatim** including the inconsistent snake_case ones — there is no serialization boundary translating casing.

**Frontend components**
- Errors shown via inline `<p className="form-message error" data-testid="...">`, not toasts — always paired with a `data-testid` used by e2e assertions.
- Loading state disables the button and swaps its label text (`"Confirming…"`) — no spinners/skeletons.
- `PaymentPanel`'s dev-mode `checkout.provider === "noop"` branch renders `data-testid="simulate-payment-success"` / `"simulate-payment-failure"` buttons — e2e payment tests depend on these; preserve them in any checkout UI change.
- Admin destructive actions **must** use `useConfirm()`/`ConfirmDialog` — zero `window.confirm`/`alert` calls exist anywhere in the codebase, fully migrated (9 admin pages use it). `confirm(opts|string)` returns `Promise<boolean>`; `danger` defaults `true`.

### Frontend App Divergence (web / admin / kiosk are NOT uniform)

- **Auth is hand-rolled per app, no shared abstraction**: web has none (public); admin stores JWT under localStorage key `"dazy_admin_token"`; kiosk under `"dazy_kiosk_token"`. Both admin/kiosk inject `Authorization: Bearer <token>` only if present, and both hard-`window.location.href = "/login"` on any 401 outside their own login endpoint (not React Router nav). Copy the pattern from the app you're in — don't try to unify them mid-task.
- Admin's `api.ts` has a bespoke `upload()` (multipart, skips `Content-Type`) and full CRUD (`get/post/patch/put/delete/upload`). **Kiosk's `api.ts` has no `delete` method** — add it first if a kiosk delete call is needed. Kiosk also inlines all its domain types directly in `api.ts` rather than a separate types module.
- **`ConfirmDialog`/`useConfirm` is admin-only** — kiosk has zero references to it; kiosk uses its own plain custom-modal idiom (`onClose`/overlay-click, guards against closing while `loading`, see `PaymentModal.tsx`). Don't port `useConfirm` into kiosk assuming it's the global standard.
- **`@dazy/ui` is effectively dead code** — zero source imports anywhere in the repo despite being a workspace package; only `apps/web/package.json` even lists it as a dependency. Admin/kiosk theme via raw CSS custom properties (`var(--gold)`, etc.) defined in their own stylesheets — that's the real color-token source of truth, not `@dazy/ui.tokens`.
- **`@dazy/shared` is actively used only by `apps/web`** (Slot, BRAND, gallery/testimonials data, launchSports). Admin imports only `BRAND` in one place. **Kiosk depends on it in package.json but has zero imports** — kiosk hardcodes brand strings like `"Dazy.club"` literally; don't assume kiosk copy comes from the shared package.
- Confirmed polling intervals (all `useEffect` + `useCallback` + `setInterval`/`clearInterval` shape): Kiosk Orders 15s, Kiosk Tables 30s, Kiosk KDS 10s. Admin has no polling pages (Schedule.tsx is manual save/refresh).

### Testing Rules

**Backend (pytest)**
- `apps/api/tests/conftest.py` sets `DAZY_DB_URL` to a temp SQLite file **before** importing `deps`/`main` (import order matters — the engine is built at import time), and force-overrides `DAZY_PAYMENT_PROVIDER=noop` / `DAZY_NOTIFY_PROVIDER=console` so a dev's real `.env` creds never leak into tests.
- DB reset: `init_db()` runs Alembic once at collection; an **autouse** fixture calls `.clear()` on every singleton repo then `seed_if_empty()` before **every** test. New repos must be wired into this reset or they'll leak state across tests. Rate limiters (`clear_login_attempts()`, etc.) are reset the same way — new rate limiters need the same wiring or tests will intermittently 429.
- **Two competing TestClient idioms coexist** — `conftest.py`'s fixture uses `with TestClient(app) as c: yield c` (triggers lifespan); some files (`test_notifications.py`, `test_booking_lookup.py`) instead do module-level `client = TestClient(app)` with hand-rolled `ADMIN_HEADERS`. Match whichever idiom the file you're extending already uses — don't mix.
- **Mocking gotcha**: `notification_service.py` does `from deps import notification_provider`, creating its own independent binding. Tests must monkeypatch `notification_service.notification_provider` directly — patching `deps.notification_provider` will NOT affect an already-imported `notification_service`.
- Test naming: `test_<behavior_in_snake_case>` describing outcome, not `test_should_...`. Files grouped by feature (`test_bookings.py`), not by layer.

**E2E (Playwright)**
- No Page Object Model, no shared helpers file — `token()`/`deleteBooking()`/`findAvailableSlot()`-style helpers are re-pasted per spec file, not imported from a common module.
- Interact via role/placeholder/label text (`getByRole`, `getByPlaceholder`); assert final state via `data-testid` (`getByTestId("lookup-status")`).
- Tests create real data via `request.post` against a live API (no per-test DB isolation like the Python suite) — **always clean up in `try/finally`** using an admin-login-then-delete helper.
- Mix real API calls (need a *specific* deterministic state) with `page.route()` mocking (UI-only assertions) depending on what the test needs. When a mocked-slots test then submits a real booking, it must `page.unroute("**/api/v1/slots**")` first or the mock slot IDs will hit the real API and fail.
- Use `waitForResponse` to sync on network completion before asserting DOM — not arbitrary waits/sleeps. The one intentional exception: asserting an API call did *not* fire (debounce tests) uses a request-listener flag + `waitForTimeout`.
- Tests depending on seeded (not test-created) fixture data (e.g. promo codes) should self-heal via a `beforeEach` repair helper (`ensureSeededPromos()` pattern) rather than assuming seed data survived prior runs.
- **No shared auth fixture/storageState** — every admin/kiosk spec re-authenticates via full UI login inside each test; this is the accepted norm, not something to "fix" by adding a global setup.
- **Kiosk PIN-pad quirk**: after typing the username, you must click away (blur) before pressing PIN digits, or digits land in the text field instead of the PIN handler — repeated in every kiosk spec.
- `zz-*.spec.ts` files (per app) are documentation-screenshot generators, named to run last; they hardcode an absolute Windows path for output — not portable to other machines/CI as-is.
- `playwright.config.ts`: 3 Desktop-Chrome-only projects (web/admin/kiosk), `fullyParallel: false`, `retries: 1`, `webServer` auto-starts all 4 services with `reuseExistingServer: true` (a stale manually-running dev server is preferred over a fresh spawn — can leak state between runs). The API `webServer` command hardcodes `.venv/Scripts/python -m uvicorn` (Windows venv path) — will not work as-is on macOS/Linux. Root `package.json` has **no `e2e:kiosk` script** — run `playwright test --project=kiosk` directly.

### Code Quality & Style Rules

- **No ESLint/Prettier configured anywhere** in the repo (no `.eslintrc*`/`.prettierrc*`). `lint`/`format` npm scripts in web/admin are literal stub echoes; kiosk doesn't even have the script entries. Only `typecheck` (`tsc --noEmit`) is real. **Do not assume or invent lint rules** — match neighboring file style.
- **No ruff/black/mypy configured** in `apps/api/pyproject.toml` — only `[project]` deps and `[tool.pytest.ini_options]`. Same rule applies: match neighboring style, no tool will catch drift.
- Naming (from `docs/Naming-Standards.md`): Python files `snake_case.py`, classes `PascalCase`, DB columns `camelCase` (deliberate mismatch vs Python convention — matches existing schema); TS components/pages `PascalCase.tsx`, libs `camelCase.ts`, CSS classes `kebab-case`; API endpoints `kebab-case`, query params `snake_case`, JSON response keys mostly `camelCase` (see field-casing caveat above).
- Slot/ID formats are fixed conventions, don't invent new ones: `slot-{court.id}-{date}-{HHMM}`, `court-{sport}`, `venue-dazy`.
- Root `package.json`: `dev` only starts api+web+admin, **not kiosk** (start separately via `pnpm dev:kiosk`); `dev:api`/`api:dev` are literal duplicate scripts (edit both if changing one); `setup` deliberately uses `pnpm install --ignore-scripts` then a separate `uv sync` — postinstall steps (esbuild native binary linking) are skipped locally, unlike the Docker build which explicitly runs `pnpm rebuild --pending` to compensate.

### Development Workflow Rules

- Git commits are **loosely Conventional Commits, not enforced** — mix of `feat:`, `feat(scope):`, `fix:`, `docs:` and plain sentence-case messages (`"added bmad"`, `"updated 1"`). No commitlint/husky hook. Treat Conventional Commits as a soft preference, not a lint-checked rule.
- **Alembic migrations**: filename `<revision_id>_<snake_case_description>.py`. Recent revision IDs follow a hand-authored, visually-incrementing hex chain (not Alembic's random hash) — continue that pattern for new migrations, or at minimum set `revision`/`down_revision` deliberately. Chain head is `e1f2a3b4c5d6`.
- Every migration has a docstring with plain-English description, `Revision ID:`/`Revises:`/`Create Date:` (a real calendar date), and a paragraph on *why* (referencing roadmap phase/decision).
- **SQLite ALTER TABLE gotcha**: any column add/drop must be wrapped in `with op.batch_alter_table("<table>") as batch_op:` — SQLite doesn't support most `ALTER TABLE` ops directly. `create_index`/`drop_index` go outside the batch block. Never call a bare `op.add_column`/`op.drop_column` on an existing table. Some migrations need `recreate="always"` in the batch call (e.g. adding a column alongside constraint changes).
- `upgrade()`/`downgrade()` are always both implemented and symmetric — no bare `pass`.
- Architecture/business decisions live in `docs/Decision-Log.md` as numbered `DEC-###` entries with rationale — check it before assuming a design choice is arbitrary; several entries explicitly **supersede** earlier ones (e.g. DEC-027 supersedes pay-at-venue-as-default).

---

## Deployment & Infra

- **Two distinct Caddy configs, don't confuse them**: root `Caddyfile` is the edge reverse-proxy (used only by the `caddy` service in `docker-compose.yml`), routing 4 env-driven hostnames to internal container ports. `Caddyfile.spa` is baked into each frontend image separately to serve the SPA build with `try_files {path} /index.html` fallback.
- **`VITE_API_BASE_URL` is a Docker build arg, not a runtime env var** — baked into the static bundle at image-build time (Vite env vars are compile-time). Changing the API domain requires rebuilding all 3 frontend images, not a container/env restart.
- `DAZY_CORS_ORIGINS` is auto-derived from the 3 frontend domain env vars as a single computed CSV string at compose time — don't add it as 3 separate vars.
- DNS for all 4 hostnames must already be propagated before first `docker compose up` — Caddy requests Let's Encrypt certs on boot and will fail/retry otherwise.
- No default admin DB row — superadmin login is entirely env-var controlled (`ADMIN_USERNAME`/`ADMIN_PASSWORD`); "removing the demo admin" means changing env vars, not deleting a row. Rotating `JWT_SECRET` invalidates all issued tokens (expected, not a bug).
- Single named volume `api_data` holds both the SQLite DB and uploaded media — flagged as needing regular backup.
- `Dockerfile.frontend` is one parameterized file for all 3 SPAs (`--build-arg APP=web|admin|kiosk`); it forces `pnpm rebuild --pending` before building because `onlyBuiltDependencies` (esbuild) isn't always honored on a from-scratch install.

---

## Critical Don't-Miss Rules

- **No shared transaction across multi-step flows.** Each repo call is its own commit (except invoice issuance's injected-session exception above). A route that calls customer upsert → N booking creates → payment create is NOT atomic — a failure partway through leaves partial state.
- **Field casing is per-model, not global.** Never guess camelCase vs snake_case for a new Pydantic field — check sibling fields in that exact model.
- **Notifications must never raise.** Any change to `notification_service.py` must preserve the "swallow all exceptions" contract.
- **SMS contacts silently get no notification today** — the email-only provider skips them.
- **Test mocking must target the binding actually used** (`notification_service.notification_provider`, not `deps.notification_provider`).
- **Cancelled/no_show bookings don't block slots** — availability is re-derived excluding those statuses.
- **`court_id = NULL` in `schedule_exceptions` = venue-wide closure** — don't treat NULL as "no exception"/a bug.
- **Slots are never stored** — generated dynamically from `ScheduleRule` rows per request. Don't add a slots table.
- **Invoice numbering is atomic per financial-year sequence only when `session=` is passed through** — a caller that skips it can burn a number on failure.
- **SQLAlchemy is sync only** — introducing `async def` route handlers that `await` a repo call will break.
- **Order/KOT numbers can collide** (timestamp-derived, ~100s cycle) — order numbers have a DB unique constraint with no `IntegrityError` handling (raw 500 on collision); KOT numbers have no constraint at all (silent duplicates).
- **`void_item` and order status `PATCH` have zero state-machine guards** — voiding a served/paid item, or jumping `paid → open`, is currently accepted without error. Don't assume any lifecycle validation exists here unless you add it.
- **Payments can overshoot the order total or land on a cancelled order** — no cap, no status guard. `PaymentRow.invoice_id` is schema-present but never populated — don't rely on it to join payments to invoices.
- **`booking_payments` resolves to the newest row by `bookingRef`** — a retried booking with two payment rows silently orphans the older one. Reuse `checkoutJson` to resume the same Razorpay order rather than creating a new one.
- **Rate limiters are in-memory and per-process** — don't assume they survive a restart or work correctly behind multiple worker processes.
- **`@dazy/ui` and (for kiosk) `@dazy/shared` are dead dependencies** — don't route new code through them assuming they're the design-token/type source of truth for every app; check per-app CSS variables and per-app hardcoded types instead.
- **Don't build against not-yet-built surfaces** — see **Product Scope Boundaries** above before assuming inventory, dine-in, credit notes, wallet, SMS, or full reporting exist.

---

## Usage Guidelines

**For AI Agents:**
- Read this file before implementing any code
- Follow ALL rules exactly as documented
- When in doubt, prefer the more restrictive option
- Update this file if new patterns emerge

**For Humans:**
- Keep this file lean and focused on agent needs
- Update when technology stack changes
- Review quarterly for outdated rules
- Remove rules that become obvious over time

Last Updated: 2026-07-03
