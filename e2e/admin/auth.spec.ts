import { test, expect } from "@playwright/test";

const ADMIN_CREDS = { username: "admin", password: "admin" };

async function login(page: import("@playwright/test").Page) {
  await page.goto("/");
  await page.locator("input[name=username]").fill(ADMIN_CREDS.username);
  await page.locator("input[name=password]").fill(ADMIN_CREDS.password);
  await page.getByRole("button", { name: /sign in/i }).click();
  await expect(page.locator(".admin-layout")).toBeVisible({ timeout: 10_000 });
}

test.describe("Admin — login", () => {
  test("wrong credentials shows error", async ({ page }) => {
    await page.goto("/");
    await page.locator("input[name=username]").fill("wrong");
    await page.locator("input[name=password]").fill("wrongpass");
    await page.getByRole("button", { name: /sign in/i }).click();
    await expect(page.locator(".error-msg")).toBeVisible({ timeout: 8_000 });
  });

  test("correct credentials logs in", async ({ page }) => {
    await login(page);
    await expect(page.locator(".topbar")).toBeVisible();
  });

  test("logout clears session and redirects to login", async ({ page }) => {
    await login(page);
    await page.getByRole("button", { name: /logout/i }).click();
    await expect(page.locator(".login-card")).toBeVisible({ timeout: 8_000 });
  });
});
