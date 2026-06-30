import { test, expect, Page } from "@playwright/test";

async function login(page: Page) {
  await page.goto("/");
  await page.locator("input[name=username]").fill("admin");
  await page.locator("input[name=password]").fill("admin");
  await page.getByRole("button", { name: /sign in/i }).click();
  await expect(page.locator(".admin-layout")).toBeVisible({ timeout: 10_000 });
}

function uniqueCode(): string {
  return "E2E" + String(Date.now()).slice(-7);
}

async function fillPromo(page: Page, code: string, kind: "percent" | "flat", value: string) {
  await page.locator('[data-testid="promo-code"]').fill(code);
  await page.locator('[data-testid="promo-kind"]').selectOption(kind);
  await page.locator('[data-testid="promo-value"]').fill(value);
}

test.describe("Admin — promo codes", () => {
  test("create promo appears in list", async ({ page }) => {
    await login(page);
    await page.goto("/promos");
    const code = uniqueCode();
    await fillPromo(page, code, "percent", "15");
    const post = page.waitForResponse((r) => r.url().endsWith("/admin/promos") && r.request().method() === "POST");
    await page.locator('[data-testid="promo-submit"]').click();
    expect((await post).status()).toBe(201);
    const row = page.locator(`.promo-row[data-code="${code}"]`);
    await expect(row).toBeVisible();
    await expect(row).toContainText("15%");
    // cleanup
    page.on("dialog", (d) => d.accept());
    await row.getByRole("button", { name: /remove/i }).click();
  });

  test("duplicate code shows error", async ({ page }) => {
    await login(page);
    await page.goto("/promos");
    const code = uniqueCode();
    await fillPromo(page, code, "percent", "10");
    await page.locator('[data-testid="promo-submit"]').click();
    await expect(page.locator(`.promo-row[data-code="${code}"]`)).toBeVisible();

    await fillPromo(page, code, "percent", "10");
    await page.locator('[data-testid="promo-submit"]').click();
    await expect(page.locator(".error-msg")).toContainText(/already exists/i);
    // cleanup
    page.on("dialog", (d) => d.accept());
    await page.locator(`.promo-row[data-code="${code}"]`).getByRole("button", { name: /remove/i }).click();
  });

  test("toggle active then delete", async ({ page }) => {
    await login(page);
    await page.goto("/promos");
    const code = uniqueCode();
    await fillPromo(page, code, "flat", "50");
    await page.locator('[data-testid="promo-submit"]').click();
    const row = page.locator(`.promo-row[data-code="${code}"]`);
    await expect(row).toBeVisible();

    await row.getByRole("button", { name: /^active$/i }).click();
    await expect(row.getByRole("button", { name: /inactive/i })).toBeVisible();

    page.on("dialog", (d) => d.accept());
    await row.getByRole("button", { name: /remove/i }).click();
    await expect(page.locator(`.promo-row[data-code="${code}"]`)).toHaveCount(0);
  });

  test("validation blocks empty code and zero value", async ({ page }) => {
    await login(page);
    await page.goto("/promos");
    await page.locator('[data-testid="promo-value"]').fill("0");
    await page.locator('[data-testid="promo-submit"]').click();
    await expect(page.getByText(/code is required/i)).toBeVisible();
    await expect(page.getByText(/greater than 0/i)).toBeVisible();
    // No new promo row was created beyond the seeded two.
  });
});
