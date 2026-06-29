import { test, expect } from "@playwright/test";

test.describe("Home page", () => {
  test("loads and shows brand name", async ({ page }) => {
    await page.goto("/");
    await expect(page).toHaveTitle(/Dazy/i);
    await expect(page.locator("body")).toContainText("Dazy");
  });

  test("nav links are present", async ({ page }) => {
    await page.goto("/");
    for (const href of ["/book", "/contact"]) {
      await expect(page.locator(`a[href="${href}"]`).first()).toBeVisible();
    }
  });

  test("hero section visible", async ({ page }) => {
    await page.goto("/");
    const hero = page.locator("section, .hero, main").first();
    await expect(hero).toBeVisible();
  });
});
