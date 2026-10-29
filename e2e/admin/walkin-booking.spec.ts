import { test, expect, APIRequestContext, Page } from "@playwright/test";

// Counter (walk-in) bookings: staff book a slot and take cash or UPI, confirmed at once, no online payment.

const API = "http://localhost:8000/api/v1";
const CREDS = { username: "admin", password: "admin" };

// One API login for the whole file: the login endpoint allows 10 a minute, and every test also logs in through the page.
let cachedToken: string | undefined;
async function adminToken(request: APIRequestContext): Promise<string> {
  if (!cachedToken) {
    const r = await request.post(`${API}/admin/login`, { data: CREDS });
    cachedToken = (await r.json()).access_token;
  }
  return cachedToken!;
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

// ── part payment (advance) ──────────────────────────────────────────────────

const rupees = (text: string | null) => Number((text ?? "").replace(/[^\d.]/g, ""));

/** Open the walk-in form on the first bookable PRICED slot (tomorrow, badminton); returns the total shown. */
async function openPricedSlot(page: Page): Promise<number> {
  await page.goto("/bookings/new");
  await page.getByTestId("walkin-sport").selectOption("badminton");
  await page.getByTestId("walkin-date").selectOption({ index: 1 });
  const slot = page.locator('[data-testid^="walkin-slot-"]:not([disabled])').filter({ hasText: "₹" }).first();
  await expect(slot).toBeVisible({ timeout: 8_000 });
  await slot.click();
  await expect(page.getByTestId("walkin-form")).toBeVisible();
  return rupees(await page.getByTestId("walkin-total").textContent());
}

async function bookPart(page: Page, phone: string, paid: number) {
  const total = await openPricedSlot(page);
  await page.getByTestId("walkin-name").fill("E2E Part Payer");
  await page.getByTestId("walkin-contact").fill(phone);
  await page.getByTestId("walkin-pay-part").check();
  await page.getByTestId("walkin-paid").fill(String(paid));
  await page.getByTestId("walkin-mode-upi").check();
  await page.getByTestId("walkin-submit").click();
  await expect(page.getByTestId("walkin-done")).toBeVisible({ timeout: 8_000 });
  const ref = (await page.getByTestId("walkin-ref").textContent())!;
  return { ref, total };
}

async function bookingsOwing(page: Page) {
  await page.goto("/bookings");
  await page.getByTestId("balance-filter").selectOption("due");
}

test.describe("Admin — walk-in part payment", () => {
  test("full payment is the default; part payment asks for an amount and checks it field by field", async ({ page }) => {
    await uiLogin(page);
    const total = await openPricedSlot(page);
    await expect(page.getByTestId("walkin-pay-full")).toBeChecked();
    await expect(page.getByTestId("walkin-paid")).toHaveCount(0);

    await page.getByTestId("walkin-pay-part").check();
    await expect(page.getByTestId("walkin-paid")).toBeVisible();
    await page.getByTestId("walkin-paid").focus();
    await page.getByTestId("walkin-name").focus(); // leave it empty
    await expect(page.getByTestId("walkin-paid-error")).toHaveText("Enter the amount paid now.");
    await page.getByTestId("walkin-paid").fill("0");
    await page.getByTestId("walkin-name").focus();
    await expect(page.getByTestId("walkin-paid-error")).toContainText("more than 0");
    await page.getByTestId("walkin-paid").fill(String(total));
    await page.getByTestId("walkin-name").focus();
    await expect(page.getByTestId("walkin-paid-error")).toContainText("less than the total");
    await page.getByTestId("walkin-paid").fill("100");
    await expect(page.getByTestId("walkin-paid-error")).toHaveCount(0);
    await expect(page.getByTestId("walkin-balance")).toContainText(`₹${(total - 100).toLocaleString("en-IN")}`);
    await expect(page.getByTestId("walkin-submit")).toContainText("₹100 now");
    await page.getByTestId("walkin-pay-full").check(); // back to full: no amount needed
    await expect(page.getByTestId("walkin-paid")).toHaveCount(0);
  });

  test("an advance shows its balance and the balance filter; Complete collects it", async ({ page, request }) => {
    const phone = "9" + String(Date.now()).slice(-9);
    await uiLogin(page);
    const { ref, total } = await bookPart(page, phone, 100);
    try {
      await expect(page.getByTestId("walkin-done-paid")).toHaveText("₹100");
      await expect(page.getByTestId("walkin-done-balance")).toContainText(`₹${(total - 100).toLocaleString("en-IN")}`);

      await bookingsOwing(page);
      await expect(page.getByTestId(`balance-${ref}`)).toHaveText(`Balance ₹${total - 100} due`, { timeout: 8_000 });
      await expect(page.getByTestId(`counter-${ref}`)).toHaveText("Counter · UPI");

      await page.getByTestId(`complete-${ref}`).click(); // a balance is due: offers to collect it
      await expect(page.getByTestId("collect-dialog")).toContainText("Complete booking");
      await expect(page.getByTestId("collect-amount")).toHaveValue(String(total - 100));
      await page.getByTestId("collect-submit").click();
      await expect(page.getByTestId(`balance-${ref}`)).toHaveCount(0, { timeout: 8_000 }); // settled: left the filter
      await page.getByTestId("balance-filter").selectOption("");
      await expect(page.locator("tr", { hasText: phone }).first()).toContainText(/completed/i);
      await expect(page.getByTestId(`advance-${ref}`)).toContainText("balance collected");
    } finally {
      await cleanup(request, ref);
    }
  });

  test("Complete without collecting leaves the balance due, and it can still be collected", async ({ page, request }) => {
    const phone = "9" + String(Date.now()).slice(-9);
    await uiLogin(page);
    const { ref, total } = await bookPart(page, phone, 100);
    try {
      await bookingsOwing(page);
      await page.getByTestId(`complete-${ref}`).click();
      await page.getByTestId("collect-skip").click();
      await expect(page.locator("tr", { hasText: phone }).first()).toContainText(/completed/i, { timeout: 8_000 });
      await expect(page.getByTestId(`balance-${ref}`)).toHaveText(`Balance ₹${total - 100} due`); // still owed, still in the filter

      await page.getByTestId(`collect-${ref}`).click();
      await page.getByTestId("collect-submit").click();
      await expect(page.getByTestId(`balance-${ref}`)).toHaveCount(0, { timeout: 8_000 });
    } finally {
      await cleanup(request, ref);
    }
  });

  test("a fully paid booking is completed straight away, with no dialog", async ({ page, request }) => {
    const phone = "9" + String(Date.now()).slice(-9);
    await uiLogin(page);
    const { ref } = await bookViaUi(page, phone, "cash");
    try {
      await page.goto("/bookings");
      const d = new Date(); d.setDate(d.getDate() + 1);
      const tomorrow = new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 10);
      await page.getByTitle("From date").fill(tomorrow);
      await page.getByTitle("To date").fill(tomorrow);
      await page.getByTestId(`complete-${ref}`).click();
      await expect(page.getByTestId("collect-dialog")).toHaveCount(0);
      await expect(page.locator("tr", { hasText: phone }).first()).toContainText(/completed/i, { timeout: 8_000 });
    } finally {
      await cleanup(request, ref);
    }
  });
});

