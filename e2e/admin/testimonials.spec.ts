import { test, expect, Page } from "@playwright/test";

async function login(page: Page) {
  await page.goto("/");
  await page.locator("input[name=username]").fill("admin");
  await page.locator("input[name=password]").fill("admin");
  await page.getByRole("button", { name: /sign in/i }).click();
  await expect(page.locator(".admin-layout")).toBeVisible({ timeout: 10_000 });
}

const uniqueName = () => "E2E Tester " + String(Date.now()).slice(-7);

test.describe("Admin — testimonials CRUD", () => {
  test("create, edit, delete a testimonial", async ({ page }) => {
    await login(page);
    await page.goto("/testimonials");
    const name = uniqueName();

    await page.locator('[data-testid="testimonial-name"]').fill(name);
    await page.locator('[data-testid="testimonial-context"]').fill("Weekend player");
    await page.locator('[data-testid="testimonial-quote"]').fill("Fantastic courts and vibe!");
    const post = page.waitForResponse((r) => r.url().endsWith("/admin/testimonials") && r.request().method() === "POST");
    await page.locator('[data-testid="testimonial-submit"]').click();
    expect((await post).status()).toBe(201);

    const card = page.locator(".enquiry-card", { hasText: name });
    await expect(card).toBeVisible();

    // edit — re-locate by data-id after edit mode opens (hasText no longer matches)
    const cardId = await card.getAttribute("data-id");
    await card.locator('[data-testid="testimonial-edit"]').click();
    const editingCard = page.locator(`.enquiry-card[data-id="${cardId}"]`);
    await editingCard.locator("textarea").fill("Updated quote text.");
    const put = page.waitForResponse((r) => r.url().includes("/admin/testimonials/") && r.request().method() === "PUT");
    await editingCard.locator('[data-testid="testimonial-edit-save"]').click();
    expect((await put).status()).toBe(200);
    await expect(page.locator(".enquiry-card", { hasText: name })).toContainText("Updated quote text.");

    // delete
    page.on("dialog", (d) => d.accept());
    await page.locator(".enquiry-card", { hasText: name }).getByRole("button", { name: /delete/i }).click();
    await expect(page.locator(".enquiry-card", { hasText: name })).toHaveCount(0);
  });

  test("approve/reject toggle still works", async ({ page }) => {
    await login(page);
    await page.goto("/testimonials");
    const name = uniqueName();
    await page.locator('[data-testid="testimonial-name"]').fill(name);
    await page.locator('[data-testid="testimonial-context"]').fill("ctx");
    await page.locator('[data-testid="testimonial-quote"]').fill("q");
    await page.locator('[data-testid="testimonial-submit"]').click();
    const card = page.locator(".enquiry-card", { hasText: name });
    await expect(card).toBeVisible();

    await card.getByRole("button", { name: /^reject$/i }).click();
    await expect(card.getByRole("button", { name: /^approve$/i })).toBeEnabled();

    // cleanup
    page.on("dialog", (d) => d.accept());
    await card.getByRole("button", { name: /delete/i }).click();
  });
});
