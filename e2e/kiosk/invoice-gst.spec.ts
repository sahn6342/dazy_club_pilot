import { test, expect, APIRequestContext } from "@playwright/test";

const API = "http://localhost:8000/api/v1";
const uid = () => `${Date.now().toString().slice(-7)}`;

async function adminToken(request: APIRequestContext): Promise<string> {
  const r = await request.post(`${API}/admin/login`, {
    data: { username: "admin", password: "admin" },
  });
  return (await r.json()).access_token;
}

async function createCashier(request: APIRequestContext, tok: string) {
  const username = `e2e_gst_${uid()}`;
  const r = await request.post(`${API}/admin/users`, {
    headers: { Authorization: `Bearer ${tok}` },
    data: { username, password: "9182", role: "cashier" },
  });
  expect(r.status()).toBe(201);
  const { id } = await r.json();
  const login = await request.post(`${API}/cafe/login`, { data: { username, pin: "9182" } });
  expect(login.status()).toBe(200);
  const { access_token } = await login.json();
  return { id, token: access_token };
}

async function createCategory(request: APIRequestContext, tok: string) {
  const r = await request.post(`${API}/admin/cafe/categories`, {
    headers: { Authorization: `Bearer ${tok}` },
    data: { name: `E2E-GST-${uid()}`, kind: "food" },
  });
  expect(r.status()).toBe(201);
  return (await r.json()).id;
}

async function createItem(request: APIRequestContext, tok: string, categoryId: string, name: string, price: number, taxRatePercent: number) {
  const r = await request.post(`${API}/admin/cafe/items`, {
    headers: { Authorization: `Bearer ${tok}` },
    data: { category_id: categoryId, name, price, taxRatePercent },
  });
  expect(r.status()).toBe(201);
  return r.json();
}

test.describe("Kiosk — order to GST-correct invoice print (Phase 2)", () => {
  test("mixed-rate order → pay → printed receipt shows rate-wise GST summary and Tax Invoice title", async ({ page, request, context }) => {
    const admin = await adminToken(request);

    // Set real GSTIN/FSSAI so the invoice issues as a Tax Invoice (not Bill of Supply).
    const settingsBefore = await (await request.get(`${API}/admin/cafe/settings`, {
      headers: { Authorization: `Bearer ${admin}` },
    })).json();
    await request.put(`${API}/admin/cafe/settings`, {
      headers: { Authorization: `Bearer ${admin}` },
      data: { legalName: "Dazy Café E2E", gstin: "29ABCDE1234F1Z5", fssaiNumber: "10023456789012", scheme: "regular" },
    });

    const category = await createCategory(request, admin);
    const item5 = await createItem(request, admin, category, "E2E Snack 5pct", 100, 5);
    const item18 = await createItem(request, admin, category, "E2E Drink 18pct", 200, 18);
    const cashier = await createCashier(request, admin);

    try {
      // Log in as the cashier without re-testing the PIN pad UI (covered by login.spec.ts).
      await page.goto("/login");
      await page.evaluate((token) => localStorage.setItem("dazy_kiosk_token", token), cashier.token);
      await page.goto("/menu");
      await expect(page.locator(".item-grid")).toBeVisible({ timeout: 8_000 });

      // Add both mixed-rate items to the cart.
      await page.locator(".item-card").filter({ hasText: "E2E Snack 5pct" }).getByRole("button", { name: "+ Add" }).click();
      await page.locator(".item-card").filter({ hasText: "E2E Drink 18pct" }).getByRole("button", { name: "+ Add" }).click();
      await expect(page.locator(".cart-line")).toHaveCount(2);

      // Place the order.
      const createOrderResp = page.waitForResponse((r) => r.url().endsWith("/cafe/orders") && r.request().method() === "POST");
      await page.getByRole("button", { name: /Place Order/ }).click();
      expect((await createOrderResp).status()).toBe(201);
      await expect(page.locator(".modal-title")).toHaveText("Payment");

      // Pay by cash (default mode) for the full amount.
      const paymentResp = page.waitForResponse((r) => r.url().includes("/payments") && r.request().method() === "POST");
      const invoiceResp = page.waitForResponse((r) => r.url().includes("/invoice") && r.request().method() === "POST");
      await page.getByRole("button", { name: "Record Payment" }).click();
      expect((await paymentResp).status()).toBe(201);
      expect((await invoiceResp).status()).toBe(201);
      await expect(page.locator(".modal-success")).toBeVisible();

      // Print Receipt opens the invoice HTML in a new tab.
      const popupPromise = context.waitForEvent("page");
      await page.getByRole("button", { name: "Print Receipt" }).click();
      const popup = await popupPromise;
      await popup.waitForLoadState("domcontentloaded");
      const html = await popup.content();

      expect(html).toContain("FSSAI: 10023456789012");
      expect(html).toContain("TAX INVOICE");
      expect(html).toContain("GST 5%");
      expect(html).toContain("GST 18%");
      // Per-line GST split: 5% of 100 = 5 tax -> 2.50 CGST + 2.50 SGST; 18% of 200 = 36 tax -> 18.00 CGST + 18.00 SGST.
      expect(html).toContain("2.50");
      expect(html).toContain("18.00");
    } finally {
      await request.delete(`${API}/admin/users/${cashier.id}`, { headers: { Authorization: `Bearer ${admin}` } });
      await request.put(`${API}/admin/cafe/settings`, {
        headers: { Authorization: `Bearer ${admin}` },
        data: { scheme: settingsBefore.scheme ?? "regular" },
      });
    }
  });
});
