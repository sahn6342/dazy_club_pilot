import { test, expect, APIRequestContext } from "@playwright/test";

// Needs the API on the noop payment provider (like the other booking specs): the payment is
// "paid" through the dev verify endpoint and refunds succeed without a gateway.

const API = "http://localhost:8000/api/v1";
const CREDS = { username: "admin", password: "admin" };

async function adminToken(request: APIRequestContext): Promise<string> {
  const r = await request.post(`${API}/admin/login`, { data: CREDS });
  return (await r.json()).access_token;
}

async function uiLogin(page: import("@playwright/test").Page) {
  await page.goto("/");
  await page.locator("input[name=username]").fill(CREDS.username);
  await page.locator("input[name=password]").fill(CREDS.password);
  await page.getByRole("button", { name: /sign in/i }).click();
  await expect(page.locator(".admin-layout")).toBeVisible({ timeout: 10_000 });
}

/** A confirmed, paid booking on the first free priced slot in the next 6 days. */
async function createPaidBooking(request: APIRequestContext): Promise<{ phone: string; ref: string; id: string; price: number }> {
  const phone = "9" + String(Date.now()).slice(-9);
  for (let ahead = 1; ahead <= 6; ahead++) {
    const d = new Date();
    d.setDate(d.getDate() + ahead);
    const dateStr = new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 10);
    for (const sport of ["cricket", "badminton", "pickleball"]) {
      const slots: any[] = await (await request.get(`${API}/slots?sport=${sport}&date=${dateStr}`)).json();
      const slot = slots.find((s) => s.available && s.finalPrice);
      if (!slot) continue;
      const res = await request.post(`${API}/bookings`, {
        data: { name: "E2E Refund Tester", contact: phone, slotIds: [slot.id], sportSlug: slot.sportSlug,
                date: slot.date, startTime: slot.startTime, players: 1 },
      });
      if (!res.ok()) continue;
      const b = await res.json();
      const pay = await request.post(`${API}/bookings/${b.bookingRef}/payment/verify`, {
        data: { providerOrderId: b.checkout.providerOrderId, providerPaymentId: `noop_pay_${Date.now()}` },
      });
      expect(pay.ok()).toBe(true);
      const tok = await adminToken(request);
      const list = (await (await request.get(`${API}/admin/bookings?limit=100`, { headers: { Authorization: `Bearer ${tok}` } })).json()).items;
      const row = list.find((x: any) => x.bookingRef === b.bookingRef);
      return { phone, ref: b.bookingRef, id: row.id, price: b.price };
    }
  }
  throw new Error("No free priced slot found in the next 6 days");
}

async function cleanup(request: APIRequestContext, id: string) {
  const tok = await adminToken(request);
  await request.delete(`${API}/admin/bookings/${id}`, { headers: { Authorization: `Bearer ${tok}` } });
}

test.describe("Admin — cancel & refund", () => {
  test("cancelling a paid booking opens the refund dialog and refunds the policy amount", async ({ page, request }) => {
    const b = await createPaidBooking(request);
    try {
      await uiLogin(page);
      await page.goto("/bookings");
      const row = page.locator("tr", { hasText: b.phone }).first();
      await expect(row).toBeVisible({ timeout: 8_000 });
      await expect(page.getByTestId(`pay-${b.ref}`)).toHaveText("Paid");

      await page.getByTestId(`cancel-${b.ref}`).click();
      const dialog = page.getByTestId("refund-dialog");
      await expect(dialog).toBeVisible();
      await expect(page.getByTestId("refund-summary")).toContainText(`₹${b.price.toLocaleString("en-IN")}`);
      await expect(page.getByTestId("refund-policy-line")).toContainText(/policy refunds \d+%/);

      // Use the full balance so the outcome does not depend on what time of day the test runs.
      await dialog.getByRole("button", { name: /full balance/i }).click();
      await expect(page.getByTestId("refund-amount")).toHaveValue(String(b.price));
      await page.getByTestId("refund-reason").fill("E2E: customer asked");
      await page.getByTestId("refund-submit").click();

      await expect(dialog).toHaveCount(0, { timeout: 8_000 });
      await expect(page.getByTestId(`pay-${b.ref}`)).toHaveText("Refunded");
      await expect(row).toContainText(/cancelled/i);
      await expect(row.getByRole("button", { name: /^cancel$/i })).toHaveCount(0);
    } finally {
      await cleanup(request, b.id);
    }
  });

  test("a partial refund keeps the booking active and can be topped up", async ({ page, request }) => {
    const b = await createPaidBooking(request);
    try {
      await uiLogin(page);
      await page.goto("/bookings");
      const row = page.locator("tr", { hasText: b.phone }).first();
      await expect(row).toBeVisible({ timeout: 8_000 });

      await page.getByTestId(`refund-${b.ref}`).click();
      await page.getByTestId("refund-amount").fill("100");
      await page.getByTestId("refund-submit").click();
      await expect(page.getByTestId("refund-dialog")).toHaveCount(0, { timeout: 8_000 });
      await expect(page.getByTestId(`pay-${b.ref}`)).toHaveText("Partly refunded");
      await expect(row).not.toContainText(/cancelled/i);   // still a live booking

      await page.getByTestId(`refund-${b.ref}`).click();
      await expect(page.getByTestId("refund-summary")).toContainText("already refunded");
      await page.getByRole("button", { name: /full balance/i }).click();
      await page.getByTestId("refund-submit").click();
      await expect(page.getByTestId(`pay-${b.ref}`)).toHaveText("Refunded", { timeout: 8_000 });
      await expect(row).toContainText(/cancelled/i);        // balance reached zero, so it is cancelled
    } finally {
      await cleanup(request, b.id);
    }
  });

  test("the dialog refuses an amount above the refundable balance", async ({ page, request }) => {
    const b = await createPaidBooking(request);
    try {
      await uiLogin(page);
      await page.goto("/bookings");
      await expect(page.locator("tr", { hasText: b.phone }).first()).toBeVisible({ timeout: 8_000 });
      await page.getByTestId(`refund-${b.ref}`).click();
      await page.getByTestId("refund-amount").fill(String(b.price + 1));
      await expect(page.getByText(/cannot exceed the refundable balance/i)).toBeVisible();
      await expect(page.getByTestId("refund-submit")).toBeDisabled();
      await page.getByRole("button", { name: /keep booking/i }).click();
      await expect(page.getByTestId("refund-dialog")).toHaveCount(0);
      await expect(page.getByTestId(`pay-${b.ref}`)).toHaveText("Paid");
    } finally {
      await cleanup(request, b.id);
    }
  });

  test("cancelling an unpaid booking skips the dialog", async ({ page, request }) => {
    const phone = "9" + String(Date.now()).slice(-9);
    let created: any;
    for (let ahead = 1; ahead <= 6 && !created; ahead++) {
      const d = new Date();
      d.setDate(d.getDate() + ahead);
      const dateStr = new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 10);
      const slots: any[] = await (await request.get(`${API}/slots?sport=cricket&date=${dateStr}`)).json();
      const slot = slots.find((s) => s.available && s.finalPrice);
      if (!slot) continue;
      const res = await request.post(`${API}/bookings`, {
        data: { name: "E2E Unpaid", contact: phone, slotIds: [slot.id], sportSlug: "cricket", date: slot.date, startTime: slot.startTime, players: 1 },
      });
      if (res.ok()) created = await res.json();
    }
    expect(created, "needs a free cricket slot").toBeTruthy();
    const tok = await adminToken(request);
    const list = (await (await request.get(`${API}/admin/bookings?limit=100`, { headers: { Authorization: `Bearer ${tok}` } })).json()).items;
    const id = list.find((x: any) => x.bookingRef === created.bookingRef).id;
    try {
      await uiLogin(page);
      await page.goto("/bookings");
      const row = page.locator("tr", { hasText: phone }).first();
      await expect(row).toBeVisible({ timeout: 8_000 });
      await page.getByTestId(`cancel-${created.bookingRef}`).click();
      await expect(row).toContainText(/cancelled/i, { timeout: 8_000 });
      await expect(page.getByTestId("refund-dialog")).toHaveCount(0);
    } finally {
      await cleanup(request, id);
    }
  });
});
