import { test, expect, APIRequestContext, Page } from "@playwright/test";

// The kiosk header: a hamburger menu on small screens (720px and below), the usual button row above that.

const API = "http://localhost:8000/api/v1";
const CASHIER = { username: `e2e_nav_${Date.now().toString().slice(-6)}`, pin: "7391" };

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

const toggle = (page: Page) => page.getByTestId("nav-toggle");
const nav = (page: Page) => page.getByRole("navigation", { name: "Kiosk navigation" });
const btn = (page: Page, name: string) => nav(page).getByRole("button", { name, exact: true });
const logout = (page: Page) => page.locator(".kiosk-logout");

test.describe("Kiosk — header menu", () => {
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

  test.describe("small screens", () => {
    test.use({ viewport: { width: 375, height: 700 } });

    test("the buttons and Logout are behind a menu button", async ({ page }) => {
      await signIn(page);
      await expect(toggle(page)).toBeVisible();
      await expect(toggle(page)).toHaveAttribute("aria-expanded", "false");
      await expect(toggle(page)).toHaveAccessibleName("Open menu");
      for (const name of ["Menu", "Orders", "Tables", "KDS"]) await expect(btn(page, name)).toBeHidden();
      await expect(logout(page)).toBeHidden();
      expect((await page.locator(".kiosk-header").boundingBox())!.height).toBeLessThanOrEqual(58);
    });

    test("opening shows every page and Logout, with the current page marked", async ({ page }) => {
      await signIn(page);
      await toggle(page).click();
      await expect(toggle(page)).toHaveAttribute("aria-expanded", "true");
      for (const name of ["Menu", "Orders", "Tables", "KDS"]) {
        await expect(btn(page, name)).toBeVisible();
        expect((await btn(page, name).boundingBox())!.height).toBeGreaterThanOrEqual(44);
      }
      await expect(logout(page)).toBeVisible();
      await expect(btn(page, "Menu")).toHaveClass(/active/);
      await expect(btn(page, "Menu")).toHaveAttribute("aria-current", "page");
      await expect(btn(page, "Orders")).not.toHaveClass(/active/);
    });

    test("choosing a page goes there and the menu starts closed on the new page", async ({ page }) => {
      await signIn(page);
      for (const [name, url] of [["Orders", /\/orders$/], ["Tables", /\/tables$/], ["KDS", /\/kds$/], ["Menu", /\/menu$/]] as const) {
        await toggle(page).click();
        await btn(page, name).click();
        await expect(page).toHaveURL(url);
        await expect(toggle(page)).toHaveAttribute("aria-expanded", "false");
        await toggle(page).click();
        await expect(btn(page, name)).toHaveClass(/active/); // the new page is the marked one
        await page.keyboard.press("Escape");
      }
    });

    test("Escape closes it and returns focus; a tap outside closes it too", async ({ page }) => {
      await signIn(page);
      await toggle(page).click();
      await page.keyboard.press("Escape");
      await expect(toggle(page)).toHaveAttribute("aria-expanded", "false");
      await expect(toggle(page)).toBeFocused();
      await toggle(page).click();
      await page.mouse.click(200, 690); // the bottom of the screen, below the open panel
      await expect(toggle(page)).toHaveAttribute("aria-expanded", "false");
    });

    test("Logout from the menu returns to the login screen", async ({ page }) => {
      await signIn(page);
      await toggle(page).click();
      await logout(page).click();
      await expect(page).toHaveURL(/\/login/);
      await expect(page.locator(".login-card")).toBeVisible();
    });

    test("growing to tablet width closes an open menu and shows the normal row", async ({ page }) => {
      await signIn(page);
      await toggle(page).click();
      await page.setViewportSize({ width: 1024, height: 700 });
      await expect(toggle(page)).toBeHidden();
      for (const name of ["Menu", "Orders", "Tables", "KDS"]) await expect(btn(page, name)).toBeVisible();
      await expect(logout(page)).toBeVisible();
      await page.setViewportSize({ width: 375, height: 700 });
      await expect(btn(page, "Orders")).toBeHidden(); // closed again on mobile
    });
  });

  test.describe("wide screens", () => {
    test.use({ viewport: { width: 1024, height: 700 } });

    test("tablet width keeps the full header row and no menu button", async ({ page }) => {
      await signIn(page);
      await expect(toggle(page)).toBeHidden();
      for (const name of ["Menu", "Orders", "Tables", "KDS"]) await expect(btn(page, name)).toBeVisible();
      await expect(logout(page)).toBeVisible();
      await expect(btn(page, "Menu")).toHaveClass(/active/);
      expect((await page.locator(".kiosk-header").boundingBox())!.height).toBeLessThanOrEqual(58);
    });

    test("720px uses the menu, 721px shows the row", async ({ page }) => {
      await page.setViewportSize({ width: 720, height: 700 });
      await signIn(page);
      await expect(toggle(page)).toBeVisible();
      await page.setViewportSize({ width: 721, height: 700 });
      await expect(toggle(page)).toBeHidden();
      await expect(btn(page, "Orders")).toBeVisible();
    });
  });
});
