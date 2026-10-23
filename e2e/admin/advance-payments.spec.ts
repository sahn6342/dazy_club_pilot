import { test, expect, APIRequestContext, Page } from "@playwright/test";

// Advance payments in the admin: the booking list shows advance and balance, "Collect balance" records the money
// taken at the venue, and the advance is never refundable. Needs the API on the noop payment provider.

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

/** A confirmed booking where only the advance was paid, on the first free slot priced above the advance. */
async function createAdvanceBooking(request: APIRequestContext) {
  const phone = "9" + String(Date.now()).slice(-9);
  const advance: number = (await (await request.get(`${API}/public-config`)).json()).advanceAmount;
  expect(advance, "the advance option must be switched on (Contact Details)").toBeGreaterThan(0);
  for (let ahead = 1; ahead <= 6; ahead++) {
    const d = new Date();
    d.setDate(d.getDate() + ahead);
    const dateStr = new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 10);
    for (const sport of ["cricket", "football", "badminton", "pickleball"]) {
      const slots: any[] = await (await request.get(`${API}/slots?sport=${sport}&date=${dateStr}`)).json();
      const slot = slots.find((s) => s.available && s.finalPrice && s.finalPrice > advance);
      if (!slot) continue;
      const res = await request.post(`${API}/bookings`, {
        data: { name: "E2E Advance Tester", contact: phone, slotIds: [slot.id], sportSlug: slot.sportSlug,
                date: slot.date, startTime: slot.startTime, players: 1, paymentOption: "advance" },
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
      return { phone, ref: b.bookingRef, id: row.id as string, price: b.price as number, advance, balance: b.price - advance };
    }
  }
  throw new Error("No free slot priced above the advance found in the next 6 days");
}

/** The advance is not refundable, so the booking stays "paid" and can only be removed by a superadmin purge (dev payments). */
async function cleanup(request: APIRequestContext, id: string) {
  const tok = await adminToken(request);
  await request.delete(`${API}/admin/bookings/${id}/purge`, { headers: { Authorization: `Bearer ${tok}` } });
}

const inr = (n: number) => `₹${n}`;

test.describe("Admin — advance bookings", () => {
  test("the list shows the advance and the balance, and Refund is not offered", async ({ page, request }) => {
    const b = await createAdvanceBooking(request);
    try {
      await uiLogin(page);
      await page.goto("/bookings");
      const row = page.locator("tr", { hasText: b.phone }).first();
      await expect(row).toBeVisible({ timeout: 8_000 });
      await expect(row).toContainText(inr(b.price));
      await expect(page.getByTestId(`advance-${b.ref}`)).toContainText(`Advance ${inr(b.advance)} · balance ${inr(b.balance)}`);
      await expect(page.getByTestId(`collect-${b.ref}`)).toBeVisible();
      await expect(page.getByTestId(`refund-${b.ref}`)).toHaveCount(0);
    } finally {
      await cleanup(request, b.id);
    }
  });

  test("collecting the balance in two parts, then it is settled", async ({ page, request }) => {
    const b = await createAdvanceBooking(request);
    try {
      await uiLogin(page);
      await page.goto("/bookings");
      await expect(page.locator("tr", { hasText: b.phone }).first()).toBeVisible({ timeout: 8_000 });

      await page.getByTestId(`collect-${b.ref}`).click();
      const dialog = page.getByTestId("collect-dialog");
      await expect(dialog).toBeVisible();
      await expect(page.getByTestId("collect-due")).toHaveText(inr(b.balance));
      await expect(page.getByTestId("collect-amount")).toHaveValue(String(b.balance)); // defaults to everything

      // more than the balance is refused in the dialog
      await page.getByTestId("collect-amount").fill(String(b.balance + 1));
      await expect(page.getByTestId("collect-submit")).toBeDisabled();

      await page.getByTestId("collect-mode").selectOption("upi");
      await page.getByTestId("collect-amount").fill("100");
      await page.getByTestId("collect-reference").fill("E2E UPI ref");
      await page.getByTestId("collect-submit").click();
      await expect(dialog).toHaveCount(0, { timeout: 8_000 });
      await expect(page.getByTestId(`advance-${b.ref}`)).toContainText(`balance ${inr(b.balance - 100)}`);

      await page.getByTestId(`collect-${b.ref}`).click();
      await expect(page.getByTestId("collect-amount")).toHaveValue(String(b.balance - 100));
      await page.getByTestId("collect-submit").click();
      await expect(dialog).toHaveCount(0, { timeout: 8_000 });
      await expect(page.getByTestId(`advance-${b.ref}`)).toContainText("balance collected");
      await expect(page.getByTestId(`collect-${b.ref}`)).toHaveCount(0);

      // the customer's own view agrees
      const look = await (await request.get(`${API}/bookings/lookup?ref=${b.ref}&contact=${b.phone}`)).json();
      expect(look.balanceDue).toBe(0);
      expect(look.amountPaid).toBe(b.price);
    } finally {
      await cleanup(request, b.id);
    }
  });

  test("cancelling keeps the advance: the dialog says nothing is refundable", async ({ page, request }) => {
    const b = await createAdvanceBooking(request);
    try {
      await uiLogin(page);
      await page.goto("/bookings");
      const row = page.locator("tr", { hasText: b.phone }).first();
      await expect(row).toBeVisible({ timeout: 8_000 });

      await page.getByTestId(`cancel-${b.ref}`).click();
      const dialog = page.getByTestId("refund-dialog");
      await expect(dialog).toBeVisible();
      await expect(page.getByTestId("refund-advance-note")).toContainText(`${inr(b.advance)} advance is non-refundable`);
      await expect(page.getByTestId("refund-summary")).toContainText("refundable ₹0");
      await expect(page.getByTestId("refund-amount")).toHaveValue("0");
      await expect(page.getByTestId("refund-submit")).toHaveText(/cancel booking, no refund/i);
      await page.getByTestId("refund-submit").click();

      await expect(dialog).toHaveCount(0, { timeout: 8_000 });
      await expect(row).toContainText(/cancelled/i);
      await expect(page.getByTestId(`pay-${b.ref}`)).toHaveText("Paid"); // the advance stays with the venue
      await expect(page.getByTestId(`collect-${b.ref}`)).toHaveCount(0); // nothing more is owed on a cancelled booking
    } finally {
      await cleanup(request, b.id);
    }
  });

  test("the advance amount is set in Contact Details and checked", async ({ page, request }) => {
    const tok = await adminToken(request);
    const before = (await (await request.get(`${API}/admin/cms`, { headers: { Authorization: `Bearer ${tok}` } })).json())
      .find((e: any) => e.key === "booking_advance_amount")?.value ?? "500";
    try {
      await uiLogin(page);
      await page.goto("/contact-details");
      const field = page.getByLabel(/advance payment/i);
      await expect(field).toBeVisible({ timeout: 8_000 });
      await field.fill("not a number");
      await page.getByRole("button", { name: /save changes/i }).click();
      await expect(page.locator(".error-msg")).toContainText(/must be a number/i);
      expect((await (await request.get(`${API}/public-config`)).json()).advanceAmount).toBe(Number(before));

      await field.fill("750");
      await page.getByRole("button", { name: /save changes/i }).click();
      await expect.poll(async () => (await (await request.get(`${API}/public-config`)).json()).advanceAmount).toBe(750);
    } finally {
      await request.put(`${API}/admin/cms/booking_advance_amount`, { data: { value: before }, headers: { Authorization: `Bearer ${tok}` } });
    }
  });
});
