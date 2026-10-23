import { test, expect, Page } from "@playwright/test";

// The admin sidebar: a hamburger menu on small screens (760px and below), the normal sidebar above that.

const CREDS = { username: "admin", password: "admin" };

async function login(page: Page) {
  await page.goto("/");
  await page.locator("input[name=username]").fill(CREDS.username);
  await page.locator("input[name=password]").fill(CREDS.password);
  await page.getByRole("button", { name: /sign in/i }).click();
  await expect(page.locator(".admin-layout")).toBeVisible({ timeout: 10_000 });
}

const nav = (page: Page) => page.getByRole("navigation", { name: "Admin navigation" });
const toggle = (page: Page) => page.getByTestId("nav-toggle");
// each link starts with an emoji icon, so match the label at the end of the accessible name
const link = (page: Page, name: string) => nav(page).getByRole("link", { name: new RegExp(`${name}$`) });

test.describe("small screens", () => {
  test.use({ viewport: { width: 375, height: 640 } });

  test("the links are behind a menu button and the sidebar is one short row", async ({ page }) => {
    await login(page);
    await expect(toggle(page)).toBeVisible();
    await expect(toggle(page)).toHaveAttribute("aria-expanded", "false");
    await expect(toggle(page)).toHaveAccessibleName("Open menu");
    await expect(link(page, "Bookings")).toBeHidden();
    expect((await page.locator(".sidebar").boundingBox())!.height).toBeLessThan(80);
    await expect(page.locator(".topbar")).toBeVisible(); // the page content starts right below
  });

  test("the menu lists every link, including the café ones, and scrolls inside the screen", async ({ page }) => {
    await login(page);
    await toggle(page).click();
    await expect(toggle(page)).toHaveAttribute("aria-expanded", "true");
    for (const name of ["Dashboard", "Bookings", "Courts", "Contact Details", "Notifications", "Menu Items", "Orders"]) {
      await expect(link(page, name)).toBeAttached();
    }
    await expect(page.locator(".sidebar-section-label")).toHaveText("Café POS");
    const panel = nav(page);
    const box = (await panel.boundingBox())!;
    expect(box.y + box.height).toBeLessThanOrEqual(640 + 1); // never taller than the screen
    expect(await panel.evaluate((el) => el.scrollHeight > el.clientHeight)).toBe(true); // the rest is reachable by scrolling it
    await link(page, "Orders").scrollIntoViewIfNeeded();
    await expect(link(page, "Orders")).toBeInViewport();
    await expect(link(page, "Dashboard")).toHaveClass(/active/);
  });

  test("choosing a link opens that page with the menu closed", async ({ page }) => {
    await login(page);
    await toggle(page).click();
    await link(page, "Bookings").click();
    await expect(page).toHaveURL(/\/bookings$/);
    await expect(page.locator(".topbar h1")).toHaveText("Bookings");
    await expect(toggle(page)).toHaveAttribute("aria-expanded", "false");
    await expect(link(page, "Bookings")).toBeHidden();
    await toggle(page).click();
    await expect(link(page, "Bookings")).toHaveClass(/active/);
  });

  test("the button toggles it, Escape closes it and returns focus to the button", async ({ page }) => {
    await login(page);
    await toggle(page).click();
    await toggle(page).click();
    await expect(link(page, "Dashboard")).toBeHidden();
    await toggle(page).click();
    await page.keyboard.press("Escape");
    await expect(toggle(page)).toHaveAttribute("aria-expanded", "false");
    await expect(toggle(page)).toBeFocused();
  });

  test("a tap outside the sidebar closes it", async ({ page }) => {
    await login(page);
    await toggle(page).click();
    await expect(link(page, "Dashboard")).toBeVisible();
    // the open panel covers the page, so send the tap to the page body directly
    await page.evaluate(() => document.querySelector(".admin-main")!.dispatchEvent(new PointerEvent("pointerdown", { bubbles: true })));
    await expect(toggle(page)).toHaveAttribute("aria-expanded", "false");
  });

  test("the menu button stays reachable after scrolling a long page", async ({ page }) => {
    await login(page);
    await page.setViewportSize({ width: 375, height: 300 });
    await page.evaluate(() => window.scrollTo(0, 400));
    await expect(toggle(page)).toBeInViewport(); // the sidebar bar is sticky
  });

  test("growing to desktop width closes an open menu and shows the sidebar", async ({ page }) => {
    await login(page);
    await toggle(page).click();
    await page.setViewportSize({ width: 1100, height: 700 });
    await expect(toggle(page)).toBeHidden();
    await expect(link(page, "Bookings")).toBeVisible();
    await page.setViewportSize({ width: 375, height: 640 });
    await expect(link(page, "Bookings")).toBeHidden(); // closed again on mobile
  });

  test("the page does not scroll sideways", async ({ page }) => {
    await login(page);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  });
});

test.describe("breakpoint and desktop", () => {
  test("760px uses the menu, 761px shows the sidebar", async ({ page }) => {
    await page.setViewportSize({ width: 760, height: 800 });
    await login(page);
    await expect(toggle(page)).toBeVisible();
    await page.setViewportSize({ width: 761, height: 800 });
    await expect(toggle(page)).toBeHidden();
    await expect(link(page, "Bookings")).toBeVisible();
  });

  test.describe("wide", () => {
    test.use({ viewport: { width: 1280, height: 800 } });

    test("no menu button, the sidebar lists everything as before", async ({ page }) => {
      await login(page);
      await expect(toggle(page)).toBeHidden();
      for (const name of ["Dashboard", "Bookings", "Contact Details", "Orders"]) await expect(link(page, name)).toBeVisible();
      expect((await page.locator(".sidebar").boundingBox())!.width).toBeGreaterThan(200);
    });
  });
});
