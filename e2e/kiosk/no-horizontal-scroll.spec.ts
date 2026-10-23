import { test, expect, devices, APIRequestContext, Page } from "@playwright/test";

// Same guard as the admin one, for the kiosk: no page wider than the phone, and the menu screen stacks so the
// category chips, the items and the order are all reachable.

const API = "http://localhost:8000/api/v1";
const CASHIER = { username: `e2e_wide_${Date.now().toString().slice(-6)}`, pin: "7391" };
const { defaultBrowserType: _ignored, ...iphone } = devices["iPhone 15"];

async function adminToken(request: APIRequestContext): Promise<string> {
  const r = await request.post(`${API}/admin/login`, { data: { username: "admin", password: "admin" } });
  return (await r.json()).access_token;
}

async function signIn(page: Page) {
  await page.goto("/login");
  await page.locator(".login-input").fill(CASHIER.username);
  await page.locator(".login-card h1").click();
  for (const d of CASHIER.pin) await page.locator(".pin-btn").filter({ hasText: new RegExp(`^${d}$`) }).click();
  await expect(page).toHaveURL(/\/menu/, { timeout: 10_000 });
}

test.describe("Kiosk — fits the screen", () => {
  let cashierId: string;

  test.beforeAll(async ({ request }) => {
    const tok = await adminToken(request);
    const r = await request.post(`${API}/admin/users`, {
      headers: { Authorization: `Bearer ${tok}` },
      data: { username: CASHIER.username, password: CASHIER.pin, role: "cashier" },
    });
    expect(r.status()).toBe(201);
    cashierId = (await r.json()).id;
  });

  test.afterAll(async ({ request }) => {
    const tok = await adminToken(request);
    await request.delete(`${API}/admin/users/${cashierId}`, { headers: { Authorization: `Bearer ${tok}` } });
  });

  for (const width of [393, 360, 320]) {
    test.describe(`phone ${width}px`, () => {
      test.use({ ...iphone, viewport: { width, height: 800 } });

      test("no kiosk page is wider than the screen", async ({ page }) => {
        await signIn(page);
        const wide: string[] = [];
        for (const path of ["/menu", "/orders", "/tables", "/kds"]) {
          await page.goto(path);
          await page.waitForLoadState("networkidle");
          const m = await page.evaluate(() => ({ iw: window.innerWidth, sw: document.documentElement.scrollWidth }));
          if (m.iw !== width || m.sw > width) wide.push(`${path} (layout ${m.iw}px, content ${m.sw}px)`);
        }
        expect(wide, `pages wider than a ${width}px screen`).toEqual([]);
      });

      test("the menu screen stacks: category chips on top, the order below the items", async ({ page }) => {
        await signIn(page);
        const rail = (await page.locator(".category-rail").boundingBox())!;
        const cart = (await page.locator(".cart-panel").boundingBox())!;
        expect(rail.width).toBeGreaterThan(width - 4);  // full width chip row, not a 160px side rail
        expect(cart.width).toBeGreaterThan(width - 4);  // full width order panel, not a 280px side column
        expect(cart.y).toBeGreaterThan(rail.y);          // below the chips
        const mainBox = (await page.locator("main.item-grid, .item-grid").first().boundingBox())!;
        expect(mainBox.width).toBeGreaterThan(width - 4); // the items get the whole width
      });
    });
  }

  test.describe("tablet and desktop keep the side-by-side POS layout", () => {
    test.use({ viewport: { width: 1024, height: 700 } });

    test("category rail on the left, order panel on the right", async ({ page }) => {
      await signIn(page);
      const rail = (await page.locator(".category-rail").boundingBox())!;
      const cart = (await page.locator(".cart-panel").boundingBox())!;
      expect(rail.width).toBeLessThan(200);
      expect(cart.width).toBeLessThan(400);
      expect(cart.x).toBeGreaterThan(rail.x + rail.width);
    });
  });
});
