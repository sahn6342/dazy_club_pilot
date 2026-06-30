import { test, expect, Page, APIRequestContext } from "@playwright/test";

const API = "http://localhost:8000/api/v1";

async function token(request: APIRequestContext): Promise<string> {
  const r = await request.post(`${API}/admin/login`, { data: { username: "admin", password: "admin" } });
  return (await r.json()).access_token;
}

async function deleteBooking(request: APIRequestContext, id: string): Promise<void> {
  const tok = await token(request);
  await request.delete(`${API}/admin/bookings/${id}`, { headers: { Authorization: `Bearer ${tok}` } });
}

/**
 * Ensure the seeded promos this spec relies on exist and are active.
 * Self-healing: a prior run (or manual poking) can delete/deactivate WELCOME10/FLAT100,
 * which would make every valid-promo assertion fail. Idempotent — no-op if already good.
 */
async function ensureSeededPromos(request: APIRequestContext): Promise<void> {
  const tok = await token(request);
  const headers = { Authorization: `Bearer ${tok}` };
  const existing: any[] = await (await request.get(`${API}/admin/promos`, { headers })).json();
  const want = [
    { code: "WELCOME10", kind: "percent", value: 10 },
    { code: "FLAT100", kind: "flat", value: 100 },
  ];
  for (const w of want) {
    const found = existing.find((p) => p.code === w.code);
    if (!found) {
      await request.post(`${API}/admin/promos`, {
        headers,
        data: { code: w.code, kind: w.kind, value: w.value, active: true, valid_from: null, valid_to: null, max_uses: null, sport_slug: null },
      });
    } else if (!found.active) {
      await request.patch(`${API}/admin/promos/${found.id}`, { headers, data: { active: true } });
    }
  }
}

/** Return synthetic slot objects for a given sport/date from the request URL. */
function syntheticSlots(url: string, overrides: Record<string, any> = {}) {
  const dateMatch = url.match(/date=([^&]+)/);
  const date = dateMatch?.[1] ?? "2099-01-01";
  const sportMatch = url.match(/sport=([^&]+)/);
  const sport = sportMatch?.[1] ?? "cricket";
  return Array.from({ length: 3 }, (_, i) => ({
    id: `mock-slot-${i}`,
    courtId: `court-${sport}`,
    sportSlug: sport,
    date,
    startTime: `0${6 + i}:00`,
    endTime: `0${7 + i}:00`,
    available: true,
    maxPlayers: 10,
    price: 1000,
    discountPercent: null,
    finalPrice: 1000,
    ...overrides,
  }));
}

/**
 * Intercept slots API — returns synthetic slots (no real fetch) so tests are fully
 * independent of the live API. The transform callback can override any field.
 */
async function mockSlots(page: Page, transform: (s: any) => any) {
  await page.route("**/api/v1/slots**", async (route) => {
    const slots = syntheticSlots(route.request().url());
    // Merge the synthetic base with the transform's overrides — transform returns
    // only the fields it wants to change (price/discount/etc), not a whole slot.
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(slots.map((s) => ({ ...s, ...transform(s) }))),
    });
  });
}

/** Click date pill and wait for the slots response + first chip to render. */
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

/**
 * Real-API only: click upcoming date pills (1..6) until one renders slot chips.
 * Robust against machine-clock drift where "tomorrow" may land on a date the server
 * has no slots for (today is past-filtered; horizon is 7 days). Returns the pill index.
 */
async function selectFirstDateWithSlots(page: Page): Promise<number> {
  for (let i = 1; i <= 6; i++) {
    await page.locator(".date-pill").nth(i).click();
    try {
      await expect(page.locator(".slot-chip").first()).toBeVisible({ timeout: 3_000 });
      return i;
    } catch { /* try next pill */ }
  }
  throw new Error("No date with slots found in the next 6 days (real API).");
}

/** Wait for the promo-validate API response matching a given code. */
async function waitForPromoValidate(page: Page, code: string) {
  return page.waitForResponse(
    (r) => r.url().includes("/api/v1/promos/validate") && r.url().includes(code),
    { timeout: 5_000 }
  );
}

// ── slot price display ─────────────────────────────────────────────────────────

test.describe("Web — pricing display", () => {
  test("slot chips show a price", async ({ page }) => {
    await page.goto("/book");
    await selectFirstDateWithSlots(page);
    const price = page.locator('[data-testid="slot-price"]').first();
    await expect(price).toBeVisible();
    await expect(price).toContainText("₹");
  });

  test("discounted slot shows struck base price and badge", async ({ page }) => {
    await mockSlots(page, () => ({ price: 800, discountPercent: 20, finalPrice: 640 }));
    await page.goto("/book");
    await selectDate(page, 1);
    const price = page.locator('[data-testid="slot-price"]').first();
    await expect(price.locator(".slot-price-strike")).toContainText("₹800");
    await expect(price).toContainText("₹640");
    await expect(price.locator(".slot-discount-badge")).toContainText("-20%");
  });
});

// ── live promo validation ──────────────────────────────────────────────────────

test.describe("Web — live promo validation", () => {
  test.beforeEach(async ({ request }) => { await ensureSeededPromos(request); });

  test("valid promo shows green feedback and discounted price after 3 chars", async ({ page }) => {
    await mockSlots(page, () => ({ price: 1200, discountPercent: null, finalPrice: 1200 }));
    await page.goto("/book");
    await selectDate(page, 1);
    await page.locator(".slot-chip").first().click();
    await expect(page.locator(".booking-form-wrap")).toBeVisible();

    const validateDone = waitForPromoValidate(page, "WELCOME10");
    await page.locator('[data-testid="promo-input"]').fill("WELCOME10");
    await validateDone;

    await expect(page.locator('[data-testid="promo-valid"]')).toBeVisible({ timeout: 3_000 });
    await expect(page.locator('[data-testid="promo-valid"]')).toContainText("WELCOME10");
    await expect(page.locator('[data-testid="promo-discounted-price"]')).toContainText("₹1080");
    await expect(page.locator('[data-testid="promo-input"]')).toHaveClass(/input-valid/);
  });

  test("validates only after 3 chars — no call on 2 chars", async ({ page }) => {
    await mockSlots(page, () => ({ price: 1200, discountPercent: null, finalPrice: 1200 }));
    await page.goto("/book");
    await selectDate(page, 1);
    await page.locator(".slot-chip").first().click();
    await expect(page.locator(".booking-form-wrap")).toBeVisible();

    let called = false;
    page.on("request", (req) => {
      if (req.url().includes("/promos/validate")) called = true;
    });
    await page.locator('[data-testid="promo-input"]').fill("WE");
    await page.waitForTimeout(800);
    expect(called).toBe(false);
    await expect(page.locator('[data-testid="promo-valid"]')).not.toBeVisible();
    await expect(page.locator('[data-testid="promo-error"]')).not.toBeVisible();
  });

  test("invalid promo shows inline error after debounce", async ({ page }) => {
    await mockSlots(page, () => ({ price: 1200, discountPercent: null, finalPrice: 1200 }));
    await page.goto("/book");
    await selectDate(page, 1);
    await page.locator(".slot-chip").first().click();
    await expect(page.locator(".booking-form-wrap")).toBeVisible();

    const validateDone = waitForPromoValidate(page, "NOPECODE");
    await page.locator('[data-testid="promo-input"]').fill("NOPECODE");
    await validateDone;

    await expect(page.locator('[data-testid="promo-error"]')).toBeVisible({ timeout: 3_000 });
    await expect(page.locator('[data-testid="promo-error"]')).toContainText(/invalid/i);
    await expect(page.locator('[data-testid="promo-valid"]')).not.toBeVisible();
  });

  test("clearing promo resets all validation feedback", async ({ page }) => {
    await mockSlots(page, () => ({ price: 1200, discountPercent: null, finalPrice: 1200 }));
    await page.goto("/book");
    await selectDate(page, 1);
    await page.locator(".slot-chip").first().click();
    await expect(page.locator(".booking-form-wrap")).toBeVisible();

    const done = waitForPromoValidate(page, "WELCOME10");
    await page.locator('[data-testid="promo-input"]').fill("WELCOME10");
    await done;
    await expect(page.locator('[data-testid="promo-valid"]')).toBeVisible({ timeout: 3_000 });

    await page.locator('[data-testid="promo-input"]').fill("");
    await expect(page.locator('[data-testid="promo-valid"]')).not.toBeVisible();
    await expect(page.locator('[data-testid="promo-error"]')).not.toBeVisible();
    await expect(page.locator('[data-testid="promo-input"]')).not.toHaveClass(/input-valid/);
  });

  test("changing slot resets promo validation", async ({ page }) => {
    await mockSlots(page, () => ({ price: 1200, discountPercent: null, finalPrice: 1200 }));
    await page.goto("/book");
    await selectDate(page, 1);

    await page.locator(".slot-chip").first().click();
    await expect(page.locator(".booking-form-wrap")).toBeVisible();
    const done = waitForPromoValidate(page, "WELCOME10");
    await page.locator('[data-testid="promo-input"]').fill("WELCOME10");
    await done;
    await expect(page.locator('[data-testid="promo-valid"]')).toBeVisible({ timeout: 3_000 });

    const chips = page.locator(".slot-chip:not(.unavailable)");
    if (await chips.count() > 1) {
      await chips.nth(1).click();
      await expect(page.locator('[data-testid="promo-input"]')).toHaveValue("");
      await expect(page.locator('[data-testid="promo-valid"]')).not.toBeVisible();
    }
  });

  test("flat promo shows correct saving amount", async ({ page }) => {
    await mockSlots(page, () => ({ price: 700, discountPercent: null, finalPrice: 700 }));
    await page.goto("/book");
    await page.getByRole("tab", { name: /pickleball/i }).click();
    await selectDate(page, 1, "pickleball");
    await page.locator(".slot-chip").first().click();
    await expect(page.locator(".booking-form-wrap")).toBeVisible();

    const done = waitForPromoValidate(page, "FLAT100");
    await page.locator('[data-testid="promo-input"]').fill("FLAT100");
    await done;

    await expect(page.locator('[data-testid="promo-valid"]')).toBeVisible({ timeout: 3_000 });
    await expect(page.locator('[data-testid="promo-discounted-price"]')).toContainText("₹600");
    await expect(page.locator('[data-testid="promo-valid"]')).toContainText("save ₹100");
  });
});

// ── promo at booking submission ────────────────────────────────────────────────

test.describe("Web — promo at booking", () => {
  test.beforeEach(async ({ request }) => { await ensureSeededPromos(request); });

  test("applying promo shows discounted amount on confirmation", async ({ page, request }) => {
    await mockSlots(page, () => ({ price: 500, discountPercent: null, finalPrice: 500 }));
    await page.goto("/book");
    await page.getByRole("tab", { name: /badminton/i }).click();
    await selectDate(page, 1, "badminton");
    await page.locator(".slot-chip").first().click();
    await expect(page.locator(".booking-form-wrap")).toBeVisible();

    await page.getByPlaceholder("Your full name").fill("E2E Pricing User");
    const phone = "9" + String(Date.now()).slice(-9);
    await page.getByPlaceholder("10-digit mobile or email").fill(phone);

    const done = waitForPromoValidate(page, "WELCOME10");
    await page.locator('[data-testid="promo-input"]').fill("WELCOME10");
    await done;
    await expect(page.locator('[data-testid="promo-valid"]')).toBeVisible({ timeout: 3_000 });

    let createdBookingId: string | null = null;
    page.on("response", async (res) => {
      if (res.url().includes("/api/v1/bookings") && res.request().method() === "POST" && res.status() === 201) {
        try { const b = await res.json(); createdBookingId = b.id; } catch { /* ignore */ }
      }
    });

    try {
      await page.unroute("**/api/v1/slots**");
      await page.getByRole("button", { name: /confirm booking/i }).click();

      const confirmed = page.locator('[data-testid="confirmed-amount"]');
      const taken = page.getByText(/slot may have just been taken/i);
      await expect(confirmed.or(taken)).toBeVisible({ timeout: 10_000 });
      if (await confirmed.isVisible()) {
        await expect(confirmed).toContainText("WELCOME10");
      }
    } finally {
      if (createdBookingId) await deleteBooking(request, createdBookingId);
    }
  });

  test("mocked invalid promo shows inline error on submit", async ({ page }) => {
    await mockSlots(page, () => ({ price: 1200, discountPercent: null, finalPrice: 1200 }));
    await page.route("**/api/v1/bookings", async (route) => {
      await route.fulfill({ status: 400, contentType: "application/json", body: JSON.stringify({ detail: "Invalid promo code." }) });
    });
    await page.route("**/api/v1/promos/validate**", async (route) => {
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ valid: true, code: "NOPECODE", discountedAmount: 1000, savedAmount: 200, kind: "percent", value: 10 }) });
    });
    await page.goto("/book");
    await selectDate(page, 1);
    await page.locator(".slot-chip").first().click();
    await expect(page.locator(".booking-form-wrap")).toBeVisible();

    await page.getByPlaceholder("Your full name").fill("E2E Bad Promo");
    await page.getByPlaceholder("10-digit mobile or email").fill("9123456789");
    await page.locator('[data-testid="promo-input"]').fill("NOPECODE");
    await page.getByRole("button", { name: /confirm booking/i }).click();

    await expect(page.locator('[data-testid="promo-error"]')).toBeVisible();
    await expect(page.locator('[data-testid="promo-error"]')).toContainText(/promo/i);
  });
});
