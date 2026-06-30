import { test, expect, Page } from "@playwright/test";

async function login(page: Page) {
  await page.goto("/");
  await page.locator("input[name=username]").fill("admin");
  await page.locator("input[name=password]").fill("admin");
  await page.getByRole("button", { name: /sign in/i }).click();
  await expect(page.locator(".admin-layout")).toBeVisible({ timeout: 10_000 });
}

const uniqueTitle = () => "E2E Gallery " + String(Date.now()).slice(-7);

test.describe("Admin — gallery CRUD", () => {
  test("create item with image URL shows an img on its card", async ({ page }) => {
    await login(page);
    await page.goto("/gallery");
    const title = uniqueTitle();
    const url = "https://example.com/e2e-pic.jpg";
    await page.locator('[data-testid="gallery-title"]').fill(title);
    await page.locator('[data-testid="gallery-sport"]').selectOption("cricket");
    await page.locator('[data-testid="gallery-tone"]').fill("electric");
    await page.locator('[data-testid="gallery-image-url"]').fill(url);

    const post = page.waitForResponse((r) => r.url().endsWith("/admin/gallery") && r.request().method() === "POST");
    await page.locator('[data-testid="gallery-submit"]').click();
    expect((await post).status()).toBe(201);

    const card = page.locator(".gallery-card", { hasText: title });
    await expect(card).toBeVisible();
    await expect(card.locator("img.gallery-thumb")).toHaveAttribute("src", url);

    // cleanup
    page.on("dialog", (d) => d.accept());
    await card.getByRole("button", { name: /delete/i }).click();
    await expect(page.locator(".gallery-card", { hasText: title })).toHaveCount(0);
  });

  test("edit title persists", async ({ page }) => {
    await login(page);
    await page.goto("/gallery");
    const title = uniqueTitle();
    await page.locator('[data-testid="gallery-title"]').fill(title);
    await page.locator('[data-testid="gallery-tone"]').fill("focused");
    await page.locator('[data-testid="gallery-image-url"]').fill("https://example.com/x.jpg");
    await page.locator('[data-testid="gallery-submit"]').click();
    const card = page.locator(".gallery-card", { hasText: title });
    await expect(card).toBeVisible();

    const cardId = await card.getAttribute("data-id");
    await card.locator('[data-testid="gallery-edit"]').click();
    // hasText filter no longer matches after edit mode opens (title replaced by inputs); use data-id
    const editingCard = page.locator(`.gallery-card[data-id="${cardId}"]`);
    const edited = title + " EDITED";
    await editingCard.locator("input").first().fill(edited);
    const patch = page.waitForResponse((r) => r.url().includes("/admin/gallery/") && r.request().method() === "PATCH");
    await editingCard.locator('[data-testid="gallery-edit-save"]').click();
    expect((await patch).status()).toBe(200);
    await expect(page.locator(".gallery-card", { hasText: edited })).toBeVisible();

    // cleanup
    page.on("dialog", (d) => d.accept());
    await page.locator(".gallery-card", { hasText: edited }).getByRole("button", { name: /delete/i }).click();
  });
});
