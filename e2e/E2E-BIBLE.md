# E2E Bible — Dazy.club

Canonical reference for writing, maintaining, and extending Playwright E2E tests in this repo.
Living document — update when a new pattern is proven, a flaky fix is discovered, or the stack changes.

---

## 1. Stack & Ports

| Service | Port | Start command |
|---------|------|---------------|
| API (FastAPI) | 8000 | `uv run uvicorn main:app --reload` in `apps/api` |
| Web (Vite) | 5173 | `pnpm dev` in repo root |
| Admin (Vite) | 5174 | `pnpm dev` in repo root |

Playwright config defines two projects: `web` (baseURL 5173) and `admin` (baseURL 5174).  
Both share a live API on 8000 — tests run against the real backend unless explicitly mocked.

---

## 2. File Organisation

```
e2e/
  web/
    booking.spec.ts      # public booking flow
    pricing.spec.ts      # slot prices, discounts, live promo validation
    home.spec.ts         # landing page
    contact.spec.ts      # contact / corporate enquiry forms
  admin/
    auth.spec.ts         # login, session expiry
    bookings.spec.ts     # admin booking management
    schedule.spec.ts     # schedule rules + exceptions
    promos.spec.ts       # promo CRUD + toggle
  E2E-BIBLE.md           # this file
```

Rule: one spec per feature domain. Don't put web + admin tests in the same file.

---

## 3. Core Helpers — Copy These, Don't Reinvent

### 3.1 Admin login

```ts
async function login(page: Page) {
  await page.goto("/");
  await page.locator("input[name=username]").fill("admin");
  await page.locator("input[name=password]").fill("admin");
  await page.getByRole("button", { name: /sign in/i }).click();
  await expect(page.locator(".admin-layout")).toBeVisible({ timeout: 10_000 });
}
```

### 3.2 API token (for direct API calls inside a test)

```ts
async function token(request: APIRequestContext): Promise<string> {
  const r = await request.post(`${API}/admin/login`, {
    data: { username: "admin", password: "admin" }
  });
  return (await r.json()).access_token;
}
```

### 3.3 Select date + wait for slots

```ts
async function selectDate(page: Page, pillIdx: number, sport = "cricket") {
  const target = new Date();
  target.setDate(target.getDate() + pillIdx);
  const dateStr = target.toISOString().slice(0, 10);
  const fetchDone = page.waitForResponse(
    (r) => r.url().includes("/api/v1/slots") && r.url().includes(dateStr) && r.url().includes(sport),
    { timeout: 10_000 }
  );
  await page.locator(".date-pill").nth(pillIdx).click();
  await fetchDone;
  await expect(page.locator(".slot-chip").first()).toBeVisible({ timeout: 5_000 });
}
```

Always click a sport tab **before** calling `selectDate` when testing a non-default sport — the
response matcher must include the sport slug or it will match the wrong fetch.

### 3.4 Mock slots

```ts
async function mockSlots(page: Page, transform: (s: any) => any) {
  await page.route("**/api/v1/slots**", async (route) => {
    const res = await route.fetch();
    const slots: any[] = await res.json();
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(slots.map((s) => ({ ...s, available: true, ...transform(s) }))),
    });
  });
}
```

Call `await page.unroute("**/api/v1/slots**")` before a real POST booking so the booking
can hit the actual API.

### 3.5 Schedule restore (snapshot/restore)

Prevents schedule tests from permanently mutating `dazy.db`.

```ts
async function withRestore(request: APIRequestContext, fn: () => Promise<void>) {
  const tok = await token(request);
  const snapshot = await rulesFor(request, tok, WEEKDAY);
  try {
    await fn();
  } finally {
    const tok2 = await token(request);
    const current = await rulesFor(request, tok2, WEEKDAY);
    for (const r of current) {
      await request.delete(`${API}/admin/schedule/rules/${r.id}`, { headers: { Authorization: `Bearer ${tok2}` } });
    }
    for (const r of snapshot) {
      await request.post(`${API}/admin/schedule/rules`, {
        headers: { Authorization: `Bearer ${tok2}` },
        data: { court_id: COURT, weekday: WEEKDAY, open_time: r.open_time, close_time: r.close_time,
                slot_minutes: r.slot_minutes, price: r.price, discount_percent: r.discount_percent },
      });
    }
  }
}
```

Always use `withRestore` in schedule tests that create, edit, or delete rules.

### 3.6 Unique identifiers

```ts
function uniqueCode(): string {
  return "E2E" + String(Date.now()).slice(-7);
}

const phone = "9" + String(Date.now()).slice(-9); // unique 10-digit phone
```

Use timestamp-derived codes/phones — never hardcoded. Avoids cross-test contamination.

### 3.7 Wait for debounced network call

```ts
async function waitForPromoValidate(page: Page, code: string) {
  return page.waitForResponse(
    (r) => r.url().includes("/api/v1/promos/validate") && r.url().includes(code),
    { timeout: 5_000 }
  );
}

// Usage:
const done = waitForPromoValidate(page, "WELCOME10");
await page.locator('[data-testid="promo-input"]').fill("WELCOME10");
await done; // resolves when debounce fires and server responds
```

---

## 4. Selector Strategy (priority order)

| Priority | Pattern | When to use |
|----------|---------|-------------|
| 1 | `data-testid="..."` | Primary selector for all interactive elements |
| 2 | `getByRole("button", { name: /text/i })` | Buttons and links with text |
| 3 | `getByPlaceholder("...")` | Inputs without testid |
| 4 | `.css-class[data-attr="..."]` | Row-level selectors (e.g. `.promo-row[data-code="X"]`) |
| 5 | `.css-class` | Container guards (e.g. `.admin-layout`, `.booking-form-wrap`) |

**Never use:** `nth-child`, XPath unless absolutely no alternative, positional index without a guard.

### testid conventions

| Element | testid |
|---------|--------|
| Slot price display | `slot-price` |
| Promo input | `promo-input` |
| Promo checking state | `promo-checking` |
| Promo valid feedback | `promo-valid` |
| Promo discounted price | `promo-discounted-price` |
| Promo error | `promo-error` |
| Confirmed amount | `confirmed-amount` |
| Summary total | `summary-total` |
| Court selector | `court-select` |
| Weekly editor container | `weekly-editor` |
| Weekly: add block / make continuous / save | `weekly-add-block` / `weekly-continuous` / `weekly-save` |
| Weekly editor block row (class) | `.weekly-block-row` |
| Advanced per-day toggle / panel | `advanced-toggle` / `advanced-panel` |
| Save block button (per-day) | `save-block` |
| Add block button (per-day) | `add-block-{weekday}` |
| Add exception button | `exception-add` |
| Toast (success/error popup) | `toast` (container: `toast-container`) |
| Promo submit | `promo-submit` |
| Promo code input (admin) | `promo-code` |
| Promo kind select | `promo-kind` |
| Promo value input | `promo-value` |
| Exception "all courts" toggle | `exception-all-courts` |
| Gallery create: title/sport/tone | `gallery-title` / `gallery-sport` / `gallery-tone` |
| Gallery image URL / file picker | `gallery-image-url` / `gallery-image-file` |
| Gallery submit / edit / edit-save | `gallery-submit` / `gallery-edit` / `gallery-edit-save` |
| Testimonial create fields | `testimonial-name` / `testimonial-context` / `testimonial-quote` |
| Testimonial submit / edit / edit-save | `testimonial-submit` / `testimonial-edit` / `testimonial-edit-save` |
| CMS create fields | `cms-new-key` / `cms-new-label` / `cms-new-value` |
| CMS create / per-row delete | `cms-create` / `cms-delete` |

Row-level data attributes for selecting existing items:
- Gallery card: `.gallery-card[data-id="..."]`
- Testimonial card: `.enquiry-card[data-id="..."]`
- CMS entry: `.cms-entry[data-key="..."]`
- Exception row court: `tr[data-exc-court="all"]` (venue-wide) or the court id

---

## File upload (gallery)

Use `setInputFiles` on the file `<input>`; the upload returns a `/media/...` path that
becomes the item's `imageUrl`. For a deterministic test, prefer the **image URL** field
(`gallery-image-url`) over a real upload — assert the `<img src>` equals the URL.

```ts
// URL path (deterministic — no file needed)
await page.locator('[data-testid="gallery-image-url"]').fill("https://example.com/x.jpg");

// Real upload path (when exercising the upload endpoint)
await page.locator('[data-testid="gallery-image-file"]').setInputFiles({
  name: "shot.png", mimeType: "image/png", buffer: Buffer.from([0x89, 0x50, 0x4e, 0x47]),
});
```

`resolveImg`: an absolute `http(s)` URL is used as-is; a relative `/media/...` path is
prefixed with the API origin (`http://localhost:8000`). Assert the resolved `src`
accordingly in web tests.

---

## 5. Network Patterns

### Wait for a response, not a timeout

```ts
// GOOD — waits for the specific response
const resp = page.waitForResponse(
  (r) => r.url().includes("/admin/schedule/rules/") && r.request().method() === "PATCH",
);
await button.click();
expect((await resp).status()).toBe(200);

// BAD — arbitrary sleep, breaks on slow CI
await page.waitForTimeout(2000);
```

### Verify status codes

Always `await` the response and `expect(status).toBe(...)` — don't assume 2xx.

### Routing / mocking

```ts
// Mock a specific endpoint
await page.route("**/api/v1/bookings", async (route) => {
  await route.fulfill({ status: 400, contentType: "application/json",
    body: JSON.stringify({ detail: "Invalid promo code." }) });
});

// Unroute when done (so later real calls work)
await page.unroute("**/api/v1/bookings");
```

### Debounced inputs

Fill the full value at once, then `await` the expected response. Never type char-by-char
(slow, flaky) unless testing the debounce threshold itself.

---

## 6. State Isolation

### Between tests in a file

Tests share a live DB. Each test that creates data must clean up in a `finally` block or
use the `withRestore` pattern.

Clean-up patterns:
- **Promo**: create unique code → after assertions, `DELETE /admin/promos/{id}`.
- **Schedule**: wrap mutations in `withRestore`.
- **Bookings**: booking tests book unique phones — admin sees them but they don't conflict.

### Between spec files

Playwright runs specs in parallel (separate workers), so two specs can conflict if they
write the same shared resources (e.g., both modify the cricket Monday rule). Mitigate:
- Use different weekdays per spec (schedule.spec.ts uses Wednesday, `WD=2`).
- Use unique promo codes per test run.
- Never assume the DB is empty — assert relative changes, not absolute counts.

---

## 7. Async Patterns

### Load guards before counting

Always wait for content before counting rows:

```ts
// GOOD
await expect(section.locator(".block-row").first()).toBeVisible();
const before = await section.locator(".block-row").count();

// BAD — count returns 0 if rows haven't rendered yet
const before = await section.locator(".block-row").count();
```

### Confirm dialogs — in-app, not native

Admin destructive actions (delete/remove/close-day) go through an in-app `<ConfirmDialog>` (`useConfirm()`), **not** `window.confirm()` — GLOBAL-1 replaced every native confirm across the admin app so headless E2E can actually drive them (a real `window.confirm()` blocks Playwright entirely). Click the trigger, then click the dialog's own confirm button — scope to `.confirm-dialog` since the trigger button often shares the same label text:

```ts
await button.click();                                             // opens the ConfirmDialog
await page.locator(".confirm-dialog").getByRole("button", { name: "Delete" }).click();
```

The confirm button's label is whatever `confirmLabel` the page passed to `confirm({...})` — usually "Delete", but check the source (e.g. `confirmLabel: "Remove"` in Promos.tsx, `"Close Day"` in Schedule.tsx) rather than assuming.

`page.on("dialog", ...)` is now dead code for admin specs — it will never fire and the click will silently fail to dismiss anything. (Native `window.confirm`/`alert` may still appear elsewhere; if one genuinely does, register the handler before the triggering action as usual.)

### or() for ambiguous outcomes

When a test action has two valid results (success vs. slot-taken race):

```ts
const confirmed = page.locator('[data-testid="confirmed-amount"]');
const taken = page.getByText(/slot may have just been taken/i);
await expect(confirmed.or(taken)).toBeVisible({ timeout: 10_000 });
if (await confirmed.isVisible()) {
  // further assertions on confirmed state
}
```

---

## 8. Date Handling

### Always use future dates for slot-dependent tests

Today's slots are past-filtered in the evening — tests fail if run after 21:00.

```ts
// GOOD
const tomorrow = new Date();
tomorrow.setDate(tomorrow.getDate() + 1);
const dateStr = tomorrow.toISOString().slice(0, 10);

// BAD
const today = new Date().toISOString().slice(0, 10);
```

Slot-dependent E2E tests use `pillIdx = 1` (tomorrow) or higher.

### Exception tests use far-future dates

```ts
const d = new Date();
d.setDate(d.getDate() + 20); // far enough to avoid collisions with other tests
```

---

## 9. Flakiness Prevention

| Symptom | Root cause | Fix |
|---------|-----------|-----|
| Count wrong on first load | Counted before data rendered | Add `.first().toBeVisible()` guard |
| 422 on schedule form submit | `courtId` state not populated | Wait for `.block-row.first().toBeVisible()` before submitting |
| Promo test hits wrong date slot | Sport tab not clicked before `selectDate` | Click tab first |
| Confirm click doesn't delete anything | Used `page.on("dialog")` — admin confirms are in-app now, not native | Click `.confirm-dialog`'s own confirm button (see §"Confirm dialogs — in-app, not native") |
| Debounce test race | Filled slowly, then check before debounce fires | Use `waitForResponse`, not `waitForTimeout` |
| Schedule test leaves dirty state | No restore on failure | Always use `withRestore` wrapping |
| `input-valid` class not applied | Validation response returned after assertion | Await `waitForPromoValidate` before asserting class |

---

## 10. CI Considerations

- Specs run with `--workers=1` by default on CI to avoid port conflicts.
- API server started via `webServer` in `playwright.config.ts` — do not start it manually.
- E2E tests use the dev DB (`dazy.db`). Seed data (`WELCOME10`, `FLAT100`, default rules) must exist.
- Never delete seeded promos in a test — create new ones with `uniqueCode()`.

---

## 11. Adding a New E2E Test — Checklist

- [ ] File in `e2e/web/` or `e2e/admin/` matching the domain
- [ ] `data-testid` attributes on all new interactive elements
- [ ] Use `selectDate` / `login` / `withRestore` from helpers — don't reimplement
- [ ] Future dates only for slot-dependent assertions
- [ ] Unique phone/email per booking (`Date.now()` suffix)
- [ ] Unique promo code per test (`uniqueCode()`)
- [ ] Clean up created data (promo delete, `withRestore` for schedule)
- [ ] `waitForResponse` instead of `waitForTimeout`
- [ ] `or()` for booking success/slot-taken ambiguity
- [ ] Status code assertion on every API call made via `request` fixture
- [ ] Test name follows: `[thing] [action] [expected outcome]`

---

## 12. Known Limitations

- **Race at booking**: two tests booking the same slot concurrently can produce a 409 for one.
  Use unique slots (different sports or different date pills) or accept the `or(taken)` pattern.
- **Promo `used_count`**: seeded promos (`WELCOME10`, `FLAT100`) accumulate `used_count`
  across test runs. Tests must not assert an exact count — assert a relative increment.
- **Schedule horizon**: slots only exist 7 days ahead. Tests using `pillIdx > 6` will get 0 slots.
- **Late-night runs**: `pillIdx = 1` is safe at any time since it's tomorrow.
- **Venue-wide exceptions**: the "Apply to all courts" toggle defaults ON, so an added
  exception posts `court_id: null` and closes EVERY sport that day. It also shows on every
  court's exceptions table. Always delete the exception you create (cleanup) and use a
  far-future date (`+20`d or more) to avoid colliding with slot-dependent tests.
- **Public gallery**: now DB-driven (`/gallery`, `Cache-Control: max-age=10`), not static seed.
  It reflects admin create/approve/reject in near-real-time. Assert relative changes (item
  appears/disappears), not absolute counts — seeded items + other tests' items coexist.
- **Gallery uploads**: a real upload writes a file under `apps/api/media/gallery/` (gitignored).
  Prefer the image-URL field for deterministic assertions; reserve `setInputFiles` for
  exercising the upload endpoint itself.
- **Schedule UI (weekly + advanced)**: the page now leads with a single **Weekly hours**
  editor (`weekly-editor`) that writes the same blocks to all 7 weekdays on save (one
  POST/DELETE pass per day). Per-day editing lives behind the `advanced-toggle` — tests
  that touch `.weekday-section`/`.block-row`/`add-block-{wd}` must click it first
  (`expandAdvanced` helper) or the sections won't be in the DOM. Use `.weekly-block-row`
  (or `waitLoaded`) as the "rules loaded / courtId set" guard instead of `.block-row`.
  The weekly-save test mutates **every** weekday, so wrap it in a full-week snapshot/restore
  (`withFullRestore`), not the single-weekday `withRestore`.
- **Toasts**: every admin save/edit/delete fires a bottom-right auto-dismiss toast
  (`[data-testid="toast"]`, ~2.5s). Assert it with `toContainText(/saved|added|deleted|.../i)`
  **before** it fades. Toasts stack in `toast-container`; click to dismiss early. They are
  cosmetic — never use a toast as the sole proof an API call succeeded (assert the response
  status or resulting DOM/data too).
- **Slot mocks are synthetic**: `mockSlots`/`mockAllSlotsAvailable` in the web specs now
  fulfill `**/api/v1/slots**` with locally-built slot objects (parsed from the request's
  `sport`/`date`) instead of `route.fetch()`-ing the real API. This removes the
  "Response has been disposed" flake and makes slot-dependent UI tests independent of live
  schedule data. Real booking POSTs still hit the API after `page.unroute`.
- **Booking cleanup**: web booking/pricing tests that submit a real booking capture the
  created id from the `POST /bookings` 201 response (`page.on("response")`) and delete it via
  `DELETE /admin/bookings/{id}` in a `finally`. Admin booking tests get the id from
  `createBookingViaAPI` and do the same. Keeps `dazy.db` free of E2E booking rows.
