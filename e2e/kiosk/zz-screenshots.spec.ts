import { test, expect, Page, APIRequestContext } from "@playwright/test";

// Documentation screenshots for the cashier kiosk (Vite :5175).
// Output: docs/screenshots/kiosk-*.png. Re-runnable to regenerate docs.

const DIR = "C:/Users/shaparashar/Documents/extra personal/code/dazy_club_pilot/docs/screenshots";
const API = "http://localhost:8000/api/v1";
const DESKTOP = { width: 1440, height: 900 };

// Reuse the standing demo cashier (seeded out-of-band). Fall back to creating one.
const CASHIER = { username: "cashier1", pin: "1234" };

async function ensureCashier(request: APIRequestContext) {
  const lr = await request.post(`${API}/cafe/login`, { data: { username: CASHIER.username, pin: CASHIER.pin } });
  if (lr.ok()) return;
  // Create it if the standing cashier is missing.
  const tr = await request.post(`${API}/admin/login`, { data: { username: "admin", password: "admin" } });
  const tok = (await tr.json()).access_token;
  await request.post(`${API}/admin/users`, {
    headers: { Authorization: `Bearer ${tok}` },
    data: { username: CASHIER.username, password: CASHIER.pin, role: "cashier" },
  });
}

async function login(page: Page) {
  await page.goto("/login");
  await expect(page.locator(".login-card")).toBeVisible({ timeout: 10_000 });
  await page.locator(".login-input").fill(CASHIER.username);
  // Click away to release input focus so digit presses hit the PIN handler.
  await page.locator(".login-card h1").click();
  for (const d of CASHIER.pin) {
    await page.locator(".pin-btn").filter({ hasText: new RegExp(`^${d}$`) }).click();
  }
  await expect(page).toHaveURL(/\/menu/, { timeout: 10_000 });
}

test.describe("Kiosk screenshots", () => {
  test.use({ viewport: DESKTOP });

  test.beforeAll(async ({ request }) => {
    await ensureCashier(request);
  });

  test("kiosk-login (PIN pad)", async ({ page }) => {
    await page.goto("/login");
    await expect(page.locator(".pin-pad")).toBeVisible({ timeout: 10_000 });
    await page.locator(".login-input").fill(CASHIER.username);
    await page.waitForTimeout(200);
    await page.screenshot({ path: `${DIR}/kiosk-login.png`, fullPage: false });
  });

  test("kiosk-menu (with cart)", async ({ page }) => {
    await login(page);
    await expect(page.locator(".item-grid")).toBeVisible({ timeout: 10_000 });
    await page.waitForLoadState("networkidle");
    await expect(page.locator(".item-card").first()).toBeVisible({ timeout: 10_000 });
    // Add a few items to populate the cart panel with lines + totals.
    const addButtons = page.locator(".item-add");
    const count = await addButtons.count();
    const toAdd = Math.min(3, count);
    for (let i = 0; i < toAdd; i++) {
      // The locator list shrinks as buttons turn into qty rows; always click the first remaining.
      await page.locator(".item-add").first().click();
      await page.waitForTimeout(150);
    }
    await expect(page.locator(".cart-panel.has-items")).toBeVisible({ timeout: 8_000 });
    await expect(page.locator(".cart-line").first()).toBeVisible();
    await page.waitForTimeout(300);
    await page.screenshot({ path: `${DIR}/kiosk-menu.png`, fullPage: false });
  });

  test("kiosk-orders (open tab)", async ({ page }) => {
    await login(page);
    await page.goto("/orders");
    await page.waitForLoadState("networkidle");
    // Open tab is the default. Wait for either an order card or the empty msg.
    await page.waitForTimeout(800);
    await page.screenshot({ path: `${DIR}/kiosk-orders.png`, fullPage: false });
  });

  test("kiosk-tables", async ({ page }) => {
    await login(page);
    await page.goto("/tables");
    await page.waitForLoadState("networkidle");
    await expect(page.locator(".table-btn").first()).toBeVisible({ timeout: 10_000 });
    await page.waitForTimeout(300);
    await page.screenshot({ path: `${DIR}/kiosk-tables.png`, fullPage: false });
  });

  test("kiosk-kds (pending KOT)", async ({ page }) => {
    await login(page);
    await page.goto("/kds");
    await page.waitForLoadState("networkidle");
    // Wait for a KOT card or the "kitchen is clear" message.
    await page.locator(".kot-card").first().waitFor({ state: "visible", timeout: 8_000 }).catch(() => {});
    await page.waitForTimeout(300);
    await page.screenshot({ path: `${DIR}/kiosk-kds.png`, fullPage: false });
  });
});
