import { test, expect, Page } from "@playwright/test";

// The website header: a hamburger menu on small screens (720px and below), the plain link row above that.

const LINKS = ["Home", "Book", "My Bookings", "Contact"];
const nav = (page: Page) => page.getByRole("navigation", { name: "Primary navigation" });
const toggle = (page: Page) => page.getByTestId("nav-toggle");

test.describe("small screens", () => {
  test.use({ viewport: { width: 375, height: 700 } });

  test("the links are behind a menu button, in a single-row header", async ({ page }) => {
    await page.goto("/contact");
    await expect(toggle(page)).toBeVisible();
    await expect(toggle(page)).toHaveAttribute("aria-expanded", "false");
    await expect(toggle(page)).toHaveAccessibleName("Open menu");
    for (const name of LINKS) await expect(nav(page).getByRole("link", { name, exact: true })).toBeHidden();
    const box = await page.locator(".site-header").boundingBox();
    expect(box!.height).toBeLessThan(90);
  });

  test("the button opens a list of all four links with the current page highlighted", async ({ page }) => {
    await page.goto("/contact");
    await toggle(page).click();
    await expect(toggle(page)).toHaveAttribute("aria-expanded", "true");
    await expect(toggle(page)).toHaveAccessibleName("Close menu");
    for (const name of LINKS) await expect(nav(page).getByRole("link", { name, exact: true })).toBeVisible();
    await expect(nav(page).getByRole("link", { name: "Contact", exact: true })).toHaveClass(/active/);
    await expect(nav(page).getByRole("link", { name: "Home", exact: true })).not.toHaveClass(/active/);
    // touch targets are comfortably tall
    for (const name of LINKS) {
      const h = (await nav(page).getByRole("link", { name, exact: true }).boundingBox())!.height;
      expect(h).toBeGreaterThanOrEqual(44);
    }
  });

  test("choosing a link goes there and closes the menu", async ({ page }) => {
    await page.goto("/");
    await toggle(page).click();
    await nav(page).getByRole("link", { name: "Book", exact: true }).click();
    await expect(page).toHaveURL(/\/book$/);
    await expect(toggle(page)).toHaveAttribute("aria-expanded", "false");
    await expect(nav(page).getByRole("link", { name: "Book", exact: true })).toBeHidden();
  });

  test("choosing the page you are already on also closes it", async ({ page }) => {
    await page.goto("/book");
    await toggle(page).click();
    await nav(page).getByRole("link", { name: "Book", exact: true }).click();
    await expect(toggle(page)).toHaveAttribute("aria-expanded", "false");
  });

  test("the button toggles it, Escape closes it and returns focus to the button", async ({ page }) => {
    await page.goto("/");
    await toggle(page).click();
    await toggle(page).click();
    await expect(nav(page).getByRole("link", { name: "Home", exact: true })).toBeHidden();
    await toggle(page).click();
    await page.keyboard.press("Escape");
    await expect(toggle(page)).toHaveAttribute("aria-expanded", "false");
    await expect(toggle(page)).toBeFocused();
  });

  test("tapping outside the header closes it", async ({ page }) => {
    await page.goto("/");
    await toggle(page).click();
    await expect(nav(page).getByRole("link", { name: "Home", exact: true })).toBeVisible();
    await page.mouse.click(200, 690); // the bottom of the screen, below the open panel
    await expect(toggle(page)).toHaveAttribute("aria-expanded", "false");
  });

  test("the menu is reachable from the keyboard", async ({ page }) => {
    await page.goto("/");
    await toggle(page).focus();
    await page.keyboard.press("Enter");
    await expect(nav(page).getByRole("link", { name: "Home", exact: true })).toBeVisible();
    await page.keyboard.press("Tab");
    await expect(nav(page).getByRole("link", { name: "Home", exact: true })).toBeFocused();
  });

  test("the first screen of the home page still fits under the header", async ({ page }) => {
    await page.goto("/");
    const header = (await page.locator(".site-header").boundingBox())!.height;
    const hero = (await page.locator(".hero").boundingBox())!;
    expect(Math.round(header + hero.height)).toBeLessThanOrEqual(700 + 2); // viewport height
  });

  test("growing to desktop width closes an open menu and shows the normal links", async ({ page }) => {
    await page.goto("/");
    await toggle(page).click();
    await page.setViewportSize({ width: 1100, height: 700 });
    await expect(toggle(page)).toBeHidden();
    for (const name of LINKS) await expect(nav(page).getByRole("link", { name, exact: true })).toBeVisible();
    await page.setViewportSize({ width: 375, height: 700 });
    await expect(nav(page).getByRole("link", { name: "Home", exact: true })).toBeHidden(); // still closed when back on mobile
  });
});

test.describe("breakpoint", () => {
  test("720px still uses the menu, 721px shows the links", async ({ page }) => {
    await page.setViewportSize({ width: 720, height: 800 });
    await page.goto("/");
    await expect(toggle(page)).toBeVisible();
    await page.setViewportSize({ width: 721, height: 800 });
    await expect(toggle(page)).toBeHidden();
    await expect(nav(page).getByRole("link", { name: "Contact", exact: true })).toBeVisible();
  });
});

test.describe("desktop", () => {
  test.use({ viewport: { width: 1280, height: 800 } });

  test("no menu button, all links in the header row", async ({ page }) => {
    await page.goto("/");
    await expect(toggle(page)).toBeHidden();
    for (const name of LINKS) await expect(nav(page).getByRole("link", { name, exact: true })).toBeVisible();
    await expect(nav(page).getByRole("link", { name: "Home", exact: true })).toHaveClass(/active/);
    const header = page.locator(".site-header");
    const links = await nav(page).boundingBox();
    const bar = await header.boundingBox();
    expect(links!.y + links!.height).toBeLessThanOrEqual(bar!.y + bar!.height); // the links sit inside the header row
  });
});
