import { test, expect, APIRequestContext, Page } from "@playwright/test";

// Counter (walk-in) bookings: staff book a slot and take cash or UPI, confirmed at once, no online payment.

const API = "http://localhost:8000/api/v1";
const CREDS = { username: "admin", password: "admin" };

async function adminToken(request: APIRequestContext): Promise<string> {
  const r = await request.post(`${API}/admin/login`, { data: CREDS });
  return (await r.json()).access_token;
}

async function uiLogin(page: Page) {
  await page.goto("/");
  await page.locator("input[name=username]").fill(CREDS.username);
  await page.locator("input[name=password]").fill(CREDS.password);
  await page.getByRole("button", { name: /sign in/i }).click();
  await expect(page.locator(".admin-layout")).toBeVisible({ timeout: 10_000 });
}

/** Remove the booking again (superadmin purge; a counter booking has no gateway payment so nothing blocks it). */
async function cleanup(request: APIRequestContext, ref: string) {
  const tok = await adminToken(request);
  const headers = { Authorization: `Bearer ${tok}` };
  const list = (await (await request.get(`${API}/admin/bookings?limit=100&date_from=2000-01-01`, { headers })).json()).items;
  const row = list.find((x: any) => x.bookingRef === ref);
  if (row) await request.delete(`${API}/admin/bookings/${row.id}/purge`, { headers });
}

async function bookViaUi(page: Page, phone: string, mode: "cash" | "upi", reference?: string) {
  await page.goto("/bookings");
  await page.getByTestId("new-walkin").click();
  await expect(page).toHaveURL(/\/bookings\/new$/);
  await page.getByTestId("walkin-date").selectOption({ index: 1 }); // tomorrow: every slot is still ahead
  const slot = page.locator('[data-testid^="walkin-slot-"]:not([disabled])').first();
  await expect(slot).toBeVisible({ timeout: 8_000 });
  const slotId = (await slot.getAttribute("data-testid"))!;
  await slot.click();
  await expect(page.getByTestId("walkin-form")).toBeVisible();
  await page.getByTestId("walkin-name").fill("E2E Walk-in");
  await page.getByTestId("walkin-contact").fill(phone);
  await page.getByTestId(`walkin-mode-${mode}`).check();
  if (reference) await page.getByTestId("walkin-reference").fill(reference);
  await page.getByTestId("walkin-submit").click();
  await expect(page.getByTestId("walkin-done")).toBeVisible({ timeout: 8_000 });
  return { ref: (await page.getByTestId("walkin-ref").textContent())!, slotId };
}

test.describe("Admin — walk-in booking", () => {
  test("a cash booking is confirmed at once and shows as a counter booking", async ({ page, request }) => {
    const phone = "9" + String(Date.now()).slice(-9);
    await uiLogin(page);
    const { ref, slotId } = await bookViaUi(page, phone, "cash");
    try {
      await expect(page.getByTestId("walkin-done")).toContainText("cash");
      await page.getByRole("link", { name: /view bookings/i }).click();
      const d = new Date();
      d.setDate(d.getDate() + 1);
      const tomorrow = new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 10);
      await page.getByTitle("From date").fill(tomorrow); // the list is newest-first: narrow it to the booking's day
      await page.getByTitle("To date").fill(tomorrow);
      const row = page.locator("tr", { hasText: phone }).first();
      await expect(row).toBeVisible({ timeout: 8_000 });
      await expect(page.getByTestId(`counter-${ref}`)).toHaveText("Counter · Cash");
      await expect(page.getByTestId(`refund-${ref}`)).toHaveCount(0); // no gateway payment to refund

      // The slot is taken: it shows as booked when booking again.
      await page.getByTestId("new-walkin").click();
      await page.getByTestId("walkin-date").selectOption({ index: 1 });
      await expect(page.getByTestId(slotId)).toBeDisabled({ timeout: 8_000 });
    } finally {
      await cleanup(request, ref);
    }
  });

  test("a UPI booking keeps its reference", async ({ page, request }) => {
    const phone = "9" + String(Date.now()).slice(-9);
    await uiLogin(page);
    const { ref } = await bookViaUi(page, phone, "upi", "UTR" + Date.now());
    try {
      await expect(page.getByTestId("walkin-done")).toContainText("UPI");
      const tok = await adminToken(request);
      const list = (await (await request.get(`${API}/admin/bookings?limit=100&date_from=2000-01-01`, { headers: { Authorization: `Bearer ${tok}` } })).json()).items;
      const row = list.find((x: any) => x.bookingRef === ref);
      expect(row.source).toBe("counter");
      expect(row.payment_mode).toBe("upi");
      expect(row.payment_reference).toMatch(/^UTR/);
      expect(row.status).toBe("confirmed");
      expect(row.paymentStatus).toBe("paid");
    } finally {
      await cleanup(request, ref);
    }
  });

  test("the form asks for a valid name and phone before booking", async ({ page }) => {
    await uiLogin(page);
    await page.goto("/bookings/new");
    await page.getByTestId("walkin-date").selectOption({ index: 1 });
    const slot = page.locator('[data-testid^="walkin-slot-"]:not([disabled])').first();
    await expect(slot).toBeVisible({ timeout: 8_000 });
    await slot.click();
    await page.getByTestId("walkin-contact").fill("123");
    await page.getByTestId("walkin-submit").click();
    await expect(page.getByText("Enter the customer's name.")).toBeVisible();
    await expect(page.getByText(/10-digit mobile number/)).toBeVisible();
    await expect(page.getByTestId("walkin-done")).toHaveCount(0);
  });
});
