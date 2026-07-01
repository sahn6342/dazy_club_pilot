import { test, expect, Page } from "@playwright/test";

// Documentation screenshots for the admin console (Vite :5174).
// Output: docs/screenshots/admin-*.png. Re-runnable to regenerate docs.

const DIR = "C:/Users/shaparashar/Documents/extra personal/code/dazy_club_pilot/docs/screenshots";
const DESKTOP = { width: 1440, height: 900 };
const CREDS = { username: "admin", password: "admin" };

async function login(page: Page) {
  await page.goto("/");
  await page.locator("input[name=username]").fill(CREDS.username);
  await page.locator("input[name=password]").fill(CREDS.password);
  await page.getByRole("button", { name: /sign in/i }).click();
  await expect(page.locator(".admin-layout")).toBeVisible({ timeout: 10_000 });
}

async function shoot(page: Page, route: string, name: string) {
  await page.goto(route);
  await expect(page.locator(".admin-layout")).toBeVisible({ timeout: 10_000 });
  await page.waitForLoadState("networkidle");
  await page.waitForTimeout(400);
  await page.screenshot({ path: `${DIR}/${name}.png`, fullPage: true });
}

test.describe("Admin screenshots", () => {
  test.use({ viewport: DESKTOP });

  test("admin-login (unauthenticated)", async ({ page }) => {
    await page.goto("/login");
    await expect(page.locator(".login-card")).toBeVisible({ timeout: 10_000 });
    await page.waitForTimeout(300);
    await page.screenshot({ path: `${DIR}/admin-login.png`, fullPage: false });
  });

  test("all authenticated pages", async ({ page }) => {
    await login(page);

    await shoot(page, "/", "admin-dashboard");
    await shoot(page, "/bookings", "admin-bookings");

    // Schedule — default weekly view.
    await shoot(page, "/schedule", "admin-schedule");
    // Schedule — advanced per-day panel expanded.
    await page.goto("/schedule");
    await expect(page.locator(".admin-layout")).toBeVisible({ timeout: 10_000 });
    await page.waitForLoadState("networkidle");
    const advToggle = page.getByTestId("advanced-toggle");
    if (await advToggle.count()) {
      await advToggle.first().click();
      await expect(page.getByTestId("advanced-panel")).toBeVisible({ timeout: 8_000 }).catch(() => {});
      await page.waitForTimeout(400);
      await page.screenshot({ path: `${DIR}/admin-schedule-advanced.png`, fullPage: true });
    }

    await shoot(page, "/promos", "admin-promos");
    await shoot(page, "/enquiries", "admin-enquiries");
    await shoot(page, "/gallery", "admin-gallery");
    await shoot(page, "/testimonials", "admin-testimonials");
    await shoot(page, "/cms", "admin-cms");
    await shoot(page, "/courts", "admin-courts");
    await shoot(page, "/contact-details", "admin-contact-details");
    await shoot(page, "/users", "admin-users");
    await shoot(page, "/cafe/categories", "admin-cafe-categories");
    await shoot(page, "/cafe/items", "admin-cafe-items");
    await shoot(page, "/cafe/tables", "admin-cafe-tables");
    await shoot(page, "/cafe/settings", "admin-cafe-settings");
    await shoot(page, "/cafe/orders", "admin-cafe-orders");
  });
});
