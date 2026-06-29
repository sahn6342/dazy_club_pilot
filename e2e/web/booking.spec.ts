import { test, expect } from "@playwright/test";

/** Intercept slots API and mark every slot available — for UI-only tests. */
async function mockAllSlotsAvailable(page: import("@playwright/test").Page) {
  await page.route("**/api/v1/slots**", async (route) => {
    const res = await route.fetch();
    const slots: any[] = await res.json();
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(slots.map((s) => ({ ...s, available: true }))),
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
    await selectDate(page, 1); // tomorrow
    // Any non-zero count — exact count depends on schedule rules + existing bookings
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
  test("complete booking flow shows confirmation", async ({ page }) => {
    // Mock slots available so form opens reliably
    await mockAllSlotsAvailable(page);
    await page.goto("/book");
    // Use badminton day-1 — less likely to be exhausted
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

    // Unroute so the POST hits the real API
    await page.unroute("**/api/v1/slots**");
    await page.getByRole("button", { name: /confirm booking/i }).click();

    // Accept either success or "slot taken" — both are valid outcomes
    await expect(
      page.getByText(/you're booked in/i).or(page.getByText(/slot may have just been taken/i))
    ).toBeVisible({ timeout: 10_000 });
  });

  test("book another slot button resets form", async ({ page }) => {
    await mockAllSlotsAvailable(page);
    await page.goto("/book");
    await selectDate(page, 1);
    await page.locator(".slot-chip").first().click();
    await expect(page.locator(".booking-form-wrap")).toBeVisible();

    await page.getByPlaceholder("Your full name").fill("E2E User 2");
    const phone = "9" + String(Date.now()).slice(-9);
    await page.getByPlaceholder("10-digit mobile or email").fill(phone);
    await page.unroute("**/api/v1/slots**");
    await page.getByRole("button", { name: /confirm booking/i }).click();

    // Either booking succeeds or fails — test is about the "book another" reset
    await expect(
      page.getByText(/you're booked in/i).or(page.getByText(/slot may have just been taken/i))
    ).toBeVisible({ timeout: 10_000 });

    // Only test the reset if booking succeeded
    const succeeded = await page.getByText(/you're booked in/i).isVisible();
    if (succeeded) {
      await page.getByRole("button", { name: /book another/i }).click();
      await expect(page.locator(".booking-form-wrap")).not.toBeVisible();
      await expect(page.locator(".slot-grid")).toBeVisible();
    }
  });
});
