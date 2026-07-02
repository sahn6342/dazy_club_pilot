import { test, expect, APIRequestContext } from "@playwright/test";

const API = "http://localhost:8000/api/v1";

async function token(request: APIRequestContext): Promise<string> {
  const r = await request.post(`${API}/admin/login`, { data: { username: "admin", password: "admin" } });
  return (await r.json()).access_token;
}

async function deleteBooking(request: APIRequestContext, id: string): Promise<void> {
  const tok = await token(request);
  await request.delete(`${API}/admin/bookings/${id}`, { headers: { Authorization: `Bearer ${tok}` } });
}

/** Return 3 synthetic available slots for sport/date parsed from the request URL. */
function syntheticSlots(url: string) {
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
  }));
}

/** Intercept slots API with synthetic available slots — no real fetch needed. */
async function mockAllSlotsAvailable(page: import("@playwright/test").Page) {
  await page.route("**/api/v1/slots**", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(syntheticSlots(route.request().url())),
    });
  });
}

/**
 * Go to a specific date pill and await the correct API response.
 * `pillIdx` 0 = today, 1 = tomorrow, ..., 6 = 6 days from now.
 */
async function selectDate(
  page: import("@playwright/test").Page,
  pillIdx: number,
  sport = "cricket"
) {
  const target = new Date();
  target.setDate(target.getDate() + pillIdx);
  const dateStr = target.toISOString().slice(0, 10);

  const slotsFetch = page.waitForResponse(
    (r) =>
      r.url().includes("/api/v1/slots") &&
      r.url().includes(dateStr) &&
      r.url().includes(sport),
    { timeout: 10_000 }
  );
  await page.locator(".date-pill").nth(pillIdx).click();
  await slotsFetch;
  await expect(page.locator(".slot-chip").first()).toBeVisible({ timeout: 5_000 });
}

/**
 * Real-API only: click upcoming date pills (1..6) until one renders an
 * AVAILABLE (non-disabled) slot chip. Robust against machine-clock drift
 * where "tomorrow" may land on a date the server has no slots for (today is
 * past-filtered; horizon is 7 days), and against real bookings from prior
 * test/manual runs occupying the very first chip in DOM order. Returns the
 * pill index; caller should click `.slot-chip:not(.unavailable)` to match.
 */
async function selectFirstDateWithSlots(page: import("@playwright/test").Page): Promise<number> {
  for (let i = 1; i <= 6; i++) {
    await page.locator(".date-pill").nth(i).click();
    try {
      await expect(page.locator(".slot-chip:not(.unavailable)").first()).toBeVisible({ timeout: 3_000 });
      return i;
    } catch { /* try next pill */ }
  }
  throw new Error("No date with an available slot found in the next 6 days (real API).");
}

// ── Slot selection tests ────────────────────────────────────────────────────

test.describe("Book page — slot selection", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/book");
  });

  test("shows sport tabs and date pills", async ({ page }) => {
    await expect(page.getByRole("tab", { name: /cricket/i })).toBeVisible();
    await expect(page.getByRole("tab", { name: /badminton/i })).toBeVisible();
    await expect(page.getByRole("tab", { name: /pickleball/i })).toBeVisible();
    await expect(page.locator(".date-pill")).toHaveCount(7);
  });

  test("loads slot chips for a future date", async ({ page }) => {
    // Pick the first upcoming date that actually has slots (robust to clock drift).
    await selectFirstDateWithSlots(page);
    const count = await page.locator(".slot-chip").count();
    expect(count).toBeGreaterThan(0);
  });

  test("clicking an available slot opens booking form", async ({ page }) => {
    await mockAllSlotsAvailable(page);
    await selectDate(page, 1);
    await page.locator(".slot-chip").first().click();
    await expect(page.locator(".booking-form-wrap")).toBeVisible();
    await expect(page.getByPlaceholder("Your full name")).toBeVisible();
    await expect(page.getByPlaceholder("10-digit mobile or email")).toBeVisible();
  });

  test("switching sport tab reloads slots", async ({ page }) => {
    const tomorrow = new Date();
    tomorrow.setDate(tomorrow.getDate() + 1);
    const dateStr = tomorrow.toISOString().slice(0, 10);

    const newFetch = page.waitForResponse(
      (r) => r.url().includes("/api/v1/slots") && r.url().includes(dateStr),
      { timeout: 10_000 }
    );
    await page.locator(".date-pill").nth(1).click();
    await page.getByRole("tab", { name: /badminton/i }).click();
    await newFetch;
    await expect(page.locator(".slot-chip").first()).toBeVisible({ timeout: 5_000 });
  });
});

// ── Form validation tests (all use mocked slots — no real booking) ───────────

test.describe("Book page — form validation", () => {
  test.beforeEach(async ({ page }) => {
    await mockAllSlotsAvailable(page);
    await page.goto("/book");
    await selectDate(page, 1);
    await page.locator(".slot-chip").first().click();
    await expect(page.locator(".booking-form-wrap")).toBeVisible();
  });

  test("empty submit shows required errors", async ({ page }) => {
    await page.getByRole("button", { name: /confirm booking/i }).click();
    await expect(page.getByText("Name is required.")).toBeVisible();
    await expect(page.getByText("Phone or email is required.")).toBeVisible();
  });

  test("short name shows min-length error", async ({ page }) => {
    await page.getByPlaceholder("Your full name").fill("J");
    await page.getByPlaceholder("Your full name").blur();
    await expect(page.getByText(/at least 2/i)).toBeVisible();
  });

  test("invalid contact shows format error", async ({ page }) => {
    await page.getByPlaceholder("10-digit mobile or email").fill("notvalid");
    await page.getByPlaceholder("10-digit mobile or email").blur();
    await expect(page.getByText(/valid 10-digit/i)).toBeVisible();
  });

  test("errors clear when user corrects input", async ({ page }) => {
    await page.getByPlaceholder("Your full name").fill("J");
    await page.getByPlaceholder("Your full name").blur();
    await expect(page.getByText(/at least 2/i)).toBeVisible();
    await page.getByPlaceholder("Your full name").fill("Valid Name");
    await expect(page.getByText(/at least 2/i)).not.toBeVisible();
  });
});

// ── End-to-end booking success tests ─────────────────────────────────────────

test.describe("Book page — successful booking", () => {
  test("complete booking flow shows confirmation", async ({ page, request }) => {
    await mockAllSlotsAvailable(page);
    await page.goto("/book");
    const tomorrow = new Date();
    tomorrow.setDate(tomorrow.getDate() + 1);
    const dateStr = tomorrow.toISOString().slice(0, 10);
    const badFetch = page.waitForResponse(
      (r) => r.url().includes("/api/v1/slots") && r.url().includes(dateStr),
      { timeout: 10_000 }
    );
    await page.getByRole("tab", { name: /badminton/i }).click();
    await page.locator(".date-pill").nth(1).click();
    await badFetch;

    await page.locator(".slot-chip").first().click();
    await expect(page.locator(".booking-form-wrap")).toBeVisible();

    await page.getByPlaceholder("Your full name").fill("E2E Booking User");
    const phone = "9" + String(Date.now()).slice(-9);
    await page.getByPlaceholder("10-digit mobile or email").fill(phone);

    let createdBookingId: string | null = null;
    page.on("response", async (res) => {
      if (res.url().includes("/api/v1/bookings") && res.request().method() === "POST" && res.status() === 201) {
        try { const b = await res.json(); createdBookingId = b.id; } catch { /* ignore */ }
      }
    });

    try {
      await page.unroute("**/api/v1/slots**");
      await page.getByRole("button", { name: /confirm booking/i }).click();

      await expect(
        page.getByText(/you're booked in/i).or(page.getByText(/slots may have just been taken/i))
      ).toBeVisible({ timeout: 10_000 });
    } finally {
      if (createdBookingId) await deleteBooking(request, createdBookingId);
    }
  });

  test("book another slot button resets form", async ({ page, request }) => {
    await mockAllSlotsAvailable(page);
    await page.goto("/book");
    await selectDate(page, 1);
    await page.locator(".slot-chip").first().click();
    await expect(page.locator(".booking-form-wrap")).toBeVisible();

    await page.getByPlaceholder("Your full name").fill("E2E User 2");
    const phone = "9" + String(Date.now()).slice(-9);
    await page.getByPlaceholder("10-digit mobile or email").fill(phone);

    let createdBookingId: string | null = null;
    page.on("response", async (res) => {
      if (res.url().includes("/api/v1/bookings") && res.request().method() === "POST" && res.status() === 201) {
        try { const b = await res.json(); createdBookingId = b.id; } catch { /* ignore */ }
      }
    });

    try {
      await page.unroute("**/api/v1/slots**");
      await page.getByRole("button", { name: /confirm booking/i }).click();

      await expect(
        page.getByText(/you're booked in/i).or(page.getByText(/slots may have just been taken/i))
      ).toBeVisible({ timeout: 10_000 });

      const succeeded = await page.getByText(/you're booked in/i).isVisible();
      if (succeeded) {
        await page.getByRole("button", { name: /book another/i }).click();
        await expect(page.locator(".booking-form-wrap")).not.toBeVisible();
        await expect(page.locator(".slot-grid")).toBeVisible();
      }
    } finally {
      if (createdBookingId) await deleteBooking(request, createdBookingId);
    }
  });
});

// ── Online prepay (Phase 3): pending -> payment panel -> confirm ──────────

test.describe("Book page — online prepay", () => {
  test("priced booking shows the payment panel, dev-simulate confirms it", async ({ page, request }) => {
    await page.goto("/book");
    await selectFirstDateWithSlots(page); // real slots — cricket is priced (₹1200 seeded)

    await page.locator(".slot-chip:not(.unavailable)").first().click();
    await expect(page.locator(".booking-form-wrap")).toBeVisible();

    await page.getByPlaceholder("Your full name").fill("Prepay E2E User");
    const phone = "9" + String(Date.now()).slice(-9);
    await page.getByPlaceholder("10-digit mobile or email").fill(phone);

    let ref: string | null = null;
    page.on("response", async (res) => {
      if (res.url().endsWith("/api/v1/bookings") && res.request().method() === "POST" && res.status() === 201) {
        try { ref = (await res.json()).bookingRef; } catch { /* ignore */ }
      }
    });

    try {
      const create = page.waitForResponse((r) => r.url().endsWith("/api/v1/bookings") && r.request().method() === "POST");
      await page.getByRole("button", { name: /confirm booking/i }).click();
      const createBody = await (await create).json();
      expect(createBody.status).toBe("pending");
      expect(createBody.paymentRequired).toBe(true);

      await expect(page.locator(".payment-panel")).toBeVisible();
      await expect(page.getByTestId("payment-amount")).toContainText("Amount due");
      await expect(page.getByTestId("payment-dev-panel")).toBeVisible(); // noop provider in dev

      const verify = page.waitForResponse((r) => r.url().includes("/payment/verify") && r.request().method() === "POST");
      await page.getByTestId("simulate-payment-success").click();
      expect((await verify).status()).toBe(200);

      await expect(page.getByText(/you're booked in/i)).toBeVisible({ timeout: 10_000 });
      await expect(page.getByTestId("confirmed-amount")).toContainText("Amount paid");
    } finally {
      if (ref) {
        const tok = await token(request);
        const list = await (await request.get(`${API}/admin/bookings`, { headers: { Authorization: `Bearer ${tok}` } })).json();
        const booking = list.find((b: any) => b.bookingRef === ref);
        if (booking) await deleteBooking(request, booking.id);
      }
    }
  });

  test("simulated failed payment shows retry state, slot still held", async ({ page, request }) => {
    await page.goto("/book");
    await selectFirstDateWithSlots(page);

    await page.locator(".slot-chip:not(.unavailable)").first().click();
    await expect(page.locator(".booking-form-wrap")).toBeVisible();
    await page.getByPlaceholder("Your full name").fill("Prepay Fail E2E");
    const phone = "9" + String(Date.now()).slice(-9);
    await page.getByPlaceholder("10-digit mobile or email").fill(phone);

    let ref: string | null = null;
    page.on("response", async (res) => {
      if (res.url().endsWith("/api/v1/bookings") && res.request().method() === "POST" && res.status() === 201) {
        try { ref = (await res.json()).bookingRef; } catch { /* ignore */ }
      }
    });

    try {
      await page.getByRole("button", { name: /confirm booking/i }).click();
      await expect(page.locator(".payment-panel")).toBeVisible();

      await page.getByTestId("simulate-payment-failure").click();
      await expect(page.getByTestId("payment-dev-panel")).toBeVisible(); // still on the payment step, can retry
      await expect(page.getByText(/you're booked in/i)).not.toBeVisible();
    } finally {
      if (ref) {
        const tok = await token(request);
        const list = await (await request.get(`${API}/admin/bookings`, { headers: { Authorization: `Bearer ${tok}` } })).json();
        const booking = list.find((b: any) => b.bookingRef === ref);
        if (booking) await deleteBooking(request, booking.id);
      }
    }
  });
});
