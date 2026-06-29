import { test, expect, APIRequestContext } from "@playwright/test";

const ADMIN_CREDS = { username: "admin", password: "dazy-admin-2024" };
const API_BASE = "http://localhost:8000/api/v1";

async function login(page: import("@playwright/test").Page) {
  await page.goto("/");
  await page.locator("input[name=username]").fill(ADMIN_CREDS.username);
  await page.locator("input[name=password]").fill(ADMIN_CREDS.password);
  await page.getByRole("button", { name: /sign in/i }).click();
  await expect(page.locator(".admin-layout")).toBeVisible({ timeout: 10_000 });
}

/**
 * Create a booking via the API directly.
 * Tries all sports across the next 6 days until a 2xx response is received.
 * Returns the unique phone used so the test can locate its row.
 */
async function createBookingViaAPI(request: APIRequestContext): Promise<string> {
  const phone = "9" + String(Date.now()).slice(-9);

  for (let daysAhead = 1; daysAhead <= 6; daysAhead++) {
    const d = new Date();
    d.setDate(d.getDate() + daysAhead);
    const dateStr = d.toISOString().slice(0, 10);

    for (const sport of ["cricket", "badminton", "pickleball"]) {
      const slotsRes = await request.get(`${API_BASE}/slots?sport=${sport}&date=${dateStr}`);
      if (!slotsRes.ok()) continue;
      const slots: any[] = await slotsRes.json();
      const slot = slots.find((s) => s.available);
      if (!slot) continue;

      const bookRes = await request.post(`${API_BASE}/bookings`, {
        data: {
          name: "E2E Admin Tester",
          contact: phone,
          slotId: slot.id,
          sportSlug: slot.sportSlug,
          date: slot.date,
          startTime: slot.startTime,
          players: 1,
        },
      });
      if (bookRes.ok()) return phone;
    }
  }
  throw new Error("No available slot found across 6 days × 3 sports");
}

test.describe("Admin — bookings management", () => {
  test("admin bookings page loads", async ({ page }) => {
    await login(page);
    await page.goto("/bookings");
    await expect(page.locator(".admin-layout")).toBeVisible();
  });

  test("booking created via API appears in admin list", async ({ page, request }) => {
    const phone = await createBookingViaAPI(request);
    await login(page);
    await page.goto("/bookings");
    // Row identified by its unique phone number
    await expect(page.locator("tr", { hasText: phone }).first()).toBeVisible({ timeout: 8_000 });
    await expect(page.locator("tr", { hasText: phone }).first()).toContainText("E2E Admin Tester");
  });

  test("pending booking can be confirmed via admin", async ({ page, request }) => {
    const phone = await createBookingViaAPI(request);
    await login(page);
    await page.goto("/bookings");

    // Row uniquely identified by phone — not shared with other test workers
    const row = page.locator("tr", { hasText: phone }).first();
    await expect(row).toBeVisible({ timeout: 8_000 });

    const confirmBtn = row.getByRole("button", { name: /^confirm$/i });
    await expect(confirmBtn).toBeVisible({ timeout: 5_000 });
    await confirmBtn.click();

    // After confirm: Complete + No-show appear; Confirm disappears
    await expect(row.getByRole("button", { name: /complete/i })).toBeVisible({ timeout: 8_000 });
    await expect(row.getByRole("button", { name: /no.?show/i })).toBeVisible();
    await expect(row.getByRole("button", { name: /^confirm$/i })).toHaveCount(0);
  });

  test("pending booking can be cancelled via admin", async ({ page, request }) => {
    const phone = await createBookingViaAPI(request);
    await login(page);
    await page.goto("/bookings");

    const row = page.locator("tr", { hasText: phone }).first();
    await expect(row).toBeVisible({ timeout: 8_000 });

    const cancelBtn = row.getByRole("button", { name: /^cancel$/i });
    await expect(cancelBtn).toBeVisible({ timeout: 5_000 });
    await cancelBtn.click();

    // After cancel: no action buttons remain in this row
    await expect(row.getByRole("button", { name: /^confirm$/i })).toHaveCount(0, { timeout: 8_000 });
    await expect(row.getByRole("button", { name: /^cancel$/i })).toHaveCount(0);
    await expect(row.getByRole("button", { name: /^complete$/i })).toHaveCount(0);
  });

  test("sport filter narrows booking list", async ({ page, request }) => {
    await createBookingViaAPI(request); // creates a cricket booking
    await login(page);
    await page.goto("/bookings");
    await expect(page.locator("table tbody tr").first()).toBeVisible({ timeout: 8_000 });
    const totalRows = await page.locator("tbody tr").count();

    // Filter to pickleball — cricket booking should not appear
    await page.locator(".filter-bar select").first().selectOption("pickleball");
    await page.waitForTimeout(600);
    const filteredCount = await page.locator("tbody tr").count();
    expect(filteredCount).toBeLessThan(totalRows);

    // Reset
    await page.locator(".filter-bar select").first().selectOption("");
    await page.waitForTimeout(600);
    await expect(page.locator("tbody tr")).toHaveCount(totalRows);
  });
});
