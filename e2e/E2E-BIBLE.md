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
  await page.locator("input[name=password]").fill("dazy-admin-2024");
  await page.getByRole("button", { name: /sign in/i }).click();
  await expect(page.locator(".admin-layout")).toBeVisible({ timeout: 10_000 });
}
```

### 3.2 API token (for direct API calls inside a test)

```ts
async function token(request: APIRequestContext): Promise<string> {
  const r = await request.post(`${API}/admin/login`, {
    data: { username: "admin", password: "dazy-admin-2024" }
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
| Save block button | `save-block` |
| Add block button | `add-block-{weekday}` |
| Add exception button | `exception-add` |
| Promo submit | `promo-submit` |
| Promo code input (admin) | `promo-code` |
| Promo kind select | `promo-kind` |
| Promo value input | `promo-value` |

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

### Dialog acceptance

Register handler **before** the action that triggers the dialog:

```ts
page.on("dialog", (d) => d.accept());
await button.click(); // triggers confirm()
```

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
| Dialog not handled | Handler registered after trigger | Register `page.on("dialog")` before the click |
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
