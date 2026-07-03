# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: web\pricing.spec.ts >> Web — promo at booking >> mocked invalid promo shows inline error on submit
- Location: e2e\web\pricing.spec.ts:305:7

# Error details

```
Error: expect(locator).toContainText(expected) failed

Locator: locator('[data-testid="promo-error"]')
Expected pattern: /promo/i
Timeout: 8000ms
Error: element(s) not found

Call log:
  - Expect "toContainText" with timeout 8000ms
  - waiting for locator('[data-testid="promo-error"]')

```

```yaml
- main:
  - link "Dazy.club":
    - /url: /
  - navigation "Primary navigation":
    - link "Home":
      - /url: /
    - link "Book":
      - /url: /book
    - link "My Bookings":
      - /url: /my-bookings
    - link "Contact":
      - /url: /contact
  - paragraph: Book a court
  - heading "Pick your sport, date, and slot." [level=2]
  - paragraph: Select one or more consecutive slots and confirm your booking.
  - tablist:
    - tab "Cricket"
    - tab "Badminton"
    - tab "Pickleball"
  - group "Select date":
    - button "Fri 3"
    - button "Sat 4"
    - button "Sun 5"
    - button "Mon 6"
    - button "Tue 7"
    - button "Wed 8"
    - button "Thu 9"
  - paragraph: Cricket — Sat, 4 Jul 06:00–07:00
  - paragraph: Tap the next adjacent slot to book multiple hours, or fill in the form below.
  - button "06:00 ₹1200"
  - button "07:00 ₹1200"
  - button "08:00 ₹1200"
  - text: Selected slot
  - strong: Cricket · Sat, 4 Jul · 06:00–07:00
  - text: "Up to 10 players Total: ₹1200 Name"
  - textbox "Name":
    - /placeholder: Your full name
    - text: E2E Bad Promo
  - text: Phone or email
  - textbox "Phone or email":
    - /placeholder: 10-digit mobile or email
    - text: "9123456789"
  - text: Number of players
  - spinbutton "Number of players": "1"
  - text: Promo code (optional)
  - textbox "Promo code (optional)":
    - /placeholder: e.g. WELCOME10
    - text: NOPECODE
  - paragraph:
    - text: ✓ NOPECODE applied — ₹1200 →
    - strong: ₹1000
    - text: (save ₹200)
  - text: Message (optional)
  - textbox "Message (optional)"
  - button "Confirm booking"
  - strong: Dazy.club
  - text: Premium sports experience. Cricket, Badminton & Pickleball.
```

# Test source

```ts
  224 |     await expect(page.locator('[data-testid="promo-valid"]')).toBeVisible({ timeout: 3_000 });
  225 | 
  226 |     // Slot 0 is selected above; clicking slot 1 would be contiguous with it (same court,
  227 |     // back-to-back time) and correctly *extends* the range-select instead of replacing it —
  228 |     // promo stays valid there by design. Click the last chip instead: with 3+ synthetic slots
  229 |     // it's never adjacent to slot 0, so it starts a fresh single-slot selection and must reset the promo.
  230 |     const chips = page.locator(".slot-chip:not(.unavailable)");
  231 |     if (await chips.count() > 2) {
  232 |       await chips.last().click();
  233 |       await expect(page.locator('[data-testid="promo-input"]')).toHaveValue("");
  234 |       await expect(page.locator('[data-testid="promo-valid"]')).not.toBeVisible();
  235 |     }
  236 |   });
  237 | 
  238 |   test("flat promo shows correct saving amount", async ({ page }) => {
  239 |     await mockSlots(page, () => ({ price: 700, discountPercent: null, finalPrice: 700 }));
  240 |     await page.goto("/book");
  241 |     await page.getByRole("tab", { name: /pickleball/i }).click();
  242 |     await selectDate(page, 1, "pickleball");
  243 |     await page.locator(".slot-chip").first().click();
  244 |     await expect(page.locator(".booking-form-wrap")).toBeVisible();
  245 | 
  246 |     const done = waitForPromoValidate(page, "FLAT100");
  247 |     await page.locator('[data-testid="promo-input"]').fill("FLAT100");
  248 |     await done;
  249 | 
  250 |     await expect(page.locator('[data-testid="promo-valid"]')).toBeVisible({ timeout: 3_000 });
  251 |     await expect(page.locator('[data-testid="promo-discounted-price"]')).toContainText("₹600");
  252 |     await expect(page.locator('[data-testid="promo-valid"]')).toContainText("save ₹100");
  253 |   });
  254 | });
  255 | 
  256 | // ── promo at booking submission ────────────────────────────────────────────────
  257 | 
  258 | test.describe("Web — promo at booking", () => {
  259 |   test.beforeEach(async ({ request }) => { await ensureSeededPromos(request); });
  260 | 
  261 |   test("applying promo shows discounted amount on confirmation", async ({ page, request }) => {
  262 |     await mockSlots(page, () => ({ price: 500, discountPercent: null, finalPrice: 500 }));
  263 |     await page.goto("/book");
  264 |     await page.getByRole("tab", { name: /badminton/i }).click();
  265 |     await selectDate(page, 1, "badminton");
  266 |     await page.locator(".slot-chip").first().click();
  267 |     await expect(page.locator(".booking-form-wrap")).toBeVisible();
  268 | 
  269 |     await page.getByPlaceholder("Your full name").fill("E2E Pricing User");
  270 |     const phone = "9" + String(Date.now()).slice(-9);
  271 |     await page.getByPlaceholder("10-digit mobile or email").fill(phone);
  272 | 
  273 |     const done = waitForPromoValidate(page, "WELCOME10");
  274 |     await page.locator('[data-testid="promo-input"]').fill("WELCOME10");
  275 |     await done;
  276 |     await expect(page.locator('[data-testid="promo-valid"]')).toBeVisible({ timeout: 3_000 });
  277 | 
  278 |     let createdBookingId: string | null = null;
  279 |     page.on("response", async (res) => {
  280 |       if (res.url().includes("/api/v1/bookings") && res.request().method() === "POST" && res.status() === 201) {
  281 |         try { const b = await res.json(); createdBookingId = b.id; } catch { /* ignore */ }
  282 |       }
  283 |     });
  284 | 
  285 |     try {
  286 |       await page.unroute("**/api/v1/slots**");
  287 |       await page.getByRole("button", { name: /confirm booking/i }).click();
  288 | 
  289 |       const confirmed = page.locator('[data-testid="confirmed-amount"]');
  290 |       const payment = page.locator('[data-testid="payment-amount"]');
  291 |       const taken = page.getByText(/slots may have just been taken/i);
  292 |       await expect(confirmed.or(payment).or(taken)).toBeVisible({ timeout: 10_000 });
  293 |       if (await payment.isVisible()) {
  294 |         await page.locator('[data-testid="simulate-payment-success"]').click();
  295 |         await expect(confirmed).toBeVisible({ timeout: 5_000 });
  296 |       }
  297 |       if (await confirmed.isVisible()) {
  298 |         await expect(confirmed).toContainText("WELCOME10");
  299 |       }
  300 |     } finally {
  301 |       if (createdBookingId) await deleteBooking(request, createdBookingId);
  302 |     }
  303 |   });
  304 | 
  305 |   test("mocked invalid promo shows inline error on submit", async ({ page }) => {
  306 |     await mockSlots(page, () => ({ price: 1200, discountPercent: null, finalPrice: 1200 }));
  307 |     await page.route("**/api/v1/bookings", async (route) => {
  308 |       await route.fulfill({ status: 400, contentType: "application/json", body: JSON.stringify({ detail: "Invalid promo code." }) });
  309 |     });
  310 |     await page.route("**/api/v1/promos/validate**", async (route) => {
  311 |       await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ valid: true, code: "NOPECODE", discountedAmount: 1000, savedAmount: 200, kind: "percent", value: 10 }) });
  312 |     });
  313 |     await page.goto("/book");
  314 |     await selectDate(page, 1);
  315 |     await page.locator(".slot-chip").first().click();
  316 |     await expect(page.locator(".booking-form-wrap")).toBeVisible();
  317 | 
  318 |     await page.getByPlaceholder("Your full name").fill("E2E Bad Promo");
  319 |     await page.getByPlaceholder("10-digit mobile or email").fill("9123456789");
  320 |     await page.locator('[data-testid="promo-input"]').fill("NOPECODE");
  321 |     await page.getByRole("button", { name: /confirm booking/i }).click();
  322 | 
  323 |     await expect(page.locator('[data-testid="promo-error"]')).toBeVisible();
> 324 |     await expect(page.locator('[data-testid="promo-error"]')).toContainText(/promo/i);
      |                                                               ^ Error: expect(locator).toContainText(expected) failed
  325 |   });
  326 | });
  327 | 
```