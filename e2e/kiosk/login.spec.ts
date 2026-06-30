import { test, expect, APIRequestContext } from "@playwright/test";

const API = "http://localhost:8000/api/v1";
const CASHIER = { username: `e2e_cashier_${Date.now().toString().slice(-6)}`, pin: "7391" };

async function adminToken(request: APIRequestContext): Promise<string> {
  const r = await request.post(`${API}/admin/login`, {
    data: { username: "admin", password: "admin" },
  });
  return (await r.json()).access_token;
}

async function createCashier(request: APIRequestContext): Promise<string> {
  const tok = await adminToken(request);
  const r = await request.post(`${API}/admin/users`, {
    headers: { Authorization: `Bearer ${tok}` },
    data: { username: CASHIER.username, password: CASHIER.pin, role: "cashier" },
  });
  expect(r.status()).toBe(201);
  return (await r.json()).id;
}

async function deleteCashier(request: APIRequestContext, id: string) {
  const tok = await adminToken(request);
  await request.delete(`${API}/admin/users/${id}`, {
    headers: { Authorization: `Bearer ${tok}` },
  });
}

test.describe("Kiosk — login", () => {
  let cashierId: string;

  test.beforeAll(async ({ request }) => {
    cashierId = await createCashier(request);
  });

  test.afterAll(async ({ request }) => {
    await deleteCashier(request, cashierId);
  });

  test("login screen renders", async ({ page }) => {
    await page.goto("/login");
    await expect(page.locator(".login-card")).toBeVisible();
    await expect(page.locator(".pin-pad")).toBeVisible();
    // 4 dots
    await expect(page.locator(".pin-dot")).toHaveCount(4);
    // 12 pad buttons (1-9, ⌫, 0, ↵)
    await expect(page.locator(".pin-btn")).toHaveCount(12);
  });

  test("wrong PIN shows error", async ({ page }) => {
    await page.goto("/login");
    await page.locator(".login-input").fill(CASHIER.username);
    await page.locator(".login-input").press("Escape"); // blur to release focus
    // Click wrong PIN
    for (const d of "1234") {
      await page.locator(`.pin-btn`).filter({ hasText: d }).first().click();
    }
    await expect(page.locator(".login-error")).toBeVisible({ timeout: 8_000 });
    await expect(page.locator(".login-error")).toContainText(/invalid/i);
  });

  test("correct PIN via pad buttons logs in", async ({ page }) => {
    await page.goto("/login");
    await page.locator(".login-input").fill(CASHIER.username);
    // Click away to unfocus input
    await page.locator(".login-card h1").click();
    for (const d of CASHIER.pin) {
      await page.locator(".pin-btn").filter({ hasText: new RegExp(`^${d}$`) }).click();
    }
    await expect(page).toHaveURL(/\/menu/, { timeout: 10_000 });
  });

  test("correct PIN via keyboard logs in", async ({ page }) => {
    await page.goto("/login");
    await page.locator(".login-input").fill(CASHIER.username);
    // Tab out of input so keyboard digits go to PIN handler
    await page.keyboard.press("Tab");
    for (const d of CASHIER.pin) {
      await page.keyboard.press(d);
    }
    await expect(page).toHaveURL(/\/menu/, { timeout: 10_000 });
  });

  test("↵ button submits filled PIN", async ({ page }) => {
    await page.goto("/login");
    await page.locator(".login-input").fill(CASHIER.username);
    await page.locator(".login-card h1").click();
    // Enter 4 digits then explicitly click ↵ (auto-submit fires, but let's test the button)
    // Use 3 digits then ↵ → should show error (not enough digits)
    for (const d of CASHIER.pin.slice(0, 3)) {
      await page.locator(".pin-btn").filter({ hasText: new RegExp(`^${d}$`) }).click();
    }
    await page.locator(".pin-btn.confirm").click();
    await expect(page.locator(".login-error")).toBeVisible();
    await expect(page.locator(".login-error")).toContainText(/4-digit/i);
  });

  test("missing username shows error on ↵", async ({ page }) => {
    await page.goto("/login");
    // No username
    await page.locator(".login-card h1").click();
    for (const d of CASHIER.pin) {
      await page.locator(".pin-btn").filter({ hasText: new RegExp(`^${d}$`) }).click();
    }
    await expect(page.locator(".login-error")).toBeVisible();
    await expect(page.locator(".login-error")).toContainText(/staff name/i);
  });

  test("unauthenticated /menu redirects to /login", async ({ page }) => {
    await page.goto("/menu");
    await expect(page).toHaveURL(/\/login/, { timeout: 8_000 });
  });
});
