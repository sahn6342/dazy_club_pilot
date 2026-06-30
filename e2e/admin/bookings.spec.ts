import { test, expect, APIRequestContext } from "@playwright/test";

const ADMIN_CREDS = { username: "admin", password: "admin" };
const API_BASE = "http://localhost:8000/api/v1";

async function login(page: import("@playwright/test").Page) {
  await page.goto("/");
  await page.locator("input[name=username]").fill(ADMIN_CREDS.username);
  await page.locator("input[name=password]").fill(ADMIN_CREDS.password);
  await page.getByRole("button", { name: /sign in/i }).click();
  await expect(page.locator(".admin-layout")).toBeVisible({ timeout: 10_000 });
}

async function token(request: APIRequestContext): Promise<string> {
  const r = await request.post(`${API_BASE}/admin/login`, { data: ADMIN_CREDS });
  return (await r.json()).access_token;
}

async function deleteBooking(request: APIRequestContext, id: string): Promise<void> {
  const tok = await token(request);
  await request.delete(`${API_BASE}/admin/bookings/${id}`, {
    headers: { Authorization: `Bearer ${tok}` },
  });
}

/**
 * Create a booking via the API directly.
 * Tries all sports across the next 6 days until a 2xx response is received.
 * Returns the unique phone and booking id.
 */
async function createBookingViaAPI(request: APIRequestContext): Promise<{ phone: string; id: string }> {
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
      if (bookRes.ok()) {
        const body = await bookRes.json();
        return { phone, id: body.id };
      }
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
    const { phone, id } = await createBookingViaAPI(request);
    try {
      await login(page);
      await page.goto("/bookings");
      await expect(page.locator("tr", { hasText: phone }).first()).toBeVisible({ timeout: 8_000 });
      await expect(page.locator("tr", { hasText: phone }).first()).toContainText("E2E Admin Tester");
    } finally {
      await deleteBooking(request, id);
    }
  });

  test("pending booking can be confirmed via admin", async ({ page, request }) => {
    const { phone, id } = await createBookingViaAPI(request);
    try {
      await login(page);
      await page.goto("/bookings");

      const row = page.locator("tr", { hasText: phone }).first();
      await expect(row).toBeVisible({ timeout: 8_000 });

      const confirmBtn = row.getByRole("button", { name: /^confirm$/i });
      await expect(confirmBtn).toBeVisible({ timeout: 5_000 });
      await confirmBtn.click();

      await expect(row.getByRole("button", { name: /complete/i })).toBeVisible({ timeout: 8_000 });
      await expect(row.getByRole("button", { name: /no.?show/i })).toBeVisible();
      await expect(row.getByRole("button", { name: /^confirm$/i })).toHaveCount(0);
    } finally {
      await deleteBooking(request, id);
    }
  });

  test("pending booking can be cancelled via admin", async ({ page, request }) => {
    const { phone, id } = await createBookingViaAPI(request);
    try {
      await login(page);
      await page.goto("/bookings");

      const row = page.locator("tr", { hasText: phone }).first();
      await expect(row).toBeVisible({ timeout: 8_000 });

      const cancelBtn = row.getByRole("button", { name: /^cancel$/i });
      await expect(cancelBtn).toBeVisible({ timeout: 5_000 });
      await cancelBtn.click();

      await expect(row.getByRole("button", { name: /^confirm$/i })).toHaveCount(0, { timeout: 8_000 });
      await expect(row.getByRole("button", { name: /^cancel$/i })).toHaveCount(0);
      await expect(row.getByRole("button", { name: /^complete$/i })).toHaveCount(0);
    } finally {
      await deleteBooking(request, id);
    }
  });

  test("sport filter narrows booking list", async ({ page, request }) => {
    const { id } = await createBookingViaAPI(request);
    try {
      await login(page);
      await page.goto("/bookings");
      await expect(page.locator("table tbody tr").first()).toBeVisible({ timeout: 8_000 });
      const totalRows = await page.locator("tbody tr").count();

      await page.locator(".filter-bar select").first().selectOption("pickleball");
      await page.waitForTimeout(600);
      const filteredCount = await page.locator("tbody tr").count();
      expect(filteredCount).toBeLessThan(totalRows);

      await page.locator(".filter-bar select").first().selectOption("");
      await page.waitForTimeout(600);
      await expect(page.locator("tbody tr")).toHaveCount(totalRows);
    } finally {
      await deleteBooking(request, id);
    }
  });
});
