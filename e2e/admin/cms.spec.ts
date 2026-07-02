import { test, expect, Page, APIRequestContext } from "@playwright/test";

const API = "http://localhost:8000/api/v1";

async function token(request: APIRequestContext): Promise<string> {
  const r = await request.post(`${API}/admin/login`, { data: { username: "admin", password: "admin" } });
  return (await r.json()).access_token;
}

async function login(page: Page) {
  await page.goto("/");
  await page.locator("input[name=username]").fill("admin");
  await page.locator("input[name=password]").fill("admin");
  await page.getByRole("button", { name: /sign in/i }).click();
  await expect(page.locator(".admin-layout")).toBeVisible({ timeout: 10_000 });
}

const uniqueKey = () => "e2e_key_" + String(Date.now()).slice(-7);

test.describe("Admin — CMS CRUD", () => {
  test("create entry appears in list, then delete", async ({ page }) => {
    await login(page);
    await page.goto("/cms");
    const key = uniqueKey();

    await page.locator('[data-testid="cms-new-key"]').fill(key);
    await page.locator('[data-testid="cms-new-label"]').fill("E2E Label");
    await page.locator('[data-testid="cms-new-value"]').fill("E2E content value.");
    const post = page.waitForResponse((r) => r.url().endsWith("/admin/cms") && r.request().method() === "POST");
    await page.locator('[data-testid="cms-create"]').click();
    expect((await post).status()).toBe(201);

    const entry = page.locator(`.cms-entry[data-key="${key}"]`);
    await expect(entry).toBeVisible();

    // delete — gated by the in-app ConfirmDialog, not a native window.confirm
    await entry.locator('[data-testid="cms-delete"]').click();
    await page.locator(".confirm-dialog").getByRole("button", { name: "Delete" }).click();
    await expect(page.locator(`.cms-entry[data-key="${key}"]`)).toHaveCount(0);
  });

  test("duplicate key shows error", async ({ page }) => {
    await login(page);
    await page.goto("/cms");
    await page.locator('[data-testid="cms-new-key"]').fill("hero_tagline"); // seeded
    await page.locator('[data-testid="cms-new-label"]').fill("Dup");
    await page.locator('[data-testid="cms-new-value"]').fill("x");
    await page.locator('[data-testid="cms-create"]').click();
    await expect(page.locator(".error-msg")).toContainText(/already exists/i);
  });

  test("edit value and save", async ({ page, request }) => {
    // Capture original value so we can restore after the test.
    const tok = await token(request);
    const allEntries = await (await request.get(`${API}/admin/cms`, { headers: { Authorization: `Bearer ${tok}` } })).json();
    const original = allEntries.find((e: any) => e.key === "footer_tagline");
    const originalValue = original?.value ?? "";

    await login(page);
    await page.goto("/cms");
    const entry = page.locator('.cms-entry[data-key="footer_tagline"]');
    await expect(entry).toBeVisible();
    const newVal = "Footer updated " + String(Date.now()).slice(-5);
    await entry.locator("textarea").fill(newVal);
    const put = page.waitForResponse((r) => r.url().includes("/admin/cms/footer_tagline") && r.request().method() === "PUT");
    try {
      await entry.getByRole("button", { name: /^save$/i }).click();
      expect((await put).status()).toBe(200);
      await expect(entry.locator(".saved-msg")).toBeVisible();
    } finally {
      // Restore original value via API.
      const tok2 = await token(request);
      await request.put(`${API}/admin/cms/footer_tagline`, {
        headers: { Authorization: `Bearer ${tok2}` },
        data: { value: originalValue },
      });
    }
  });
});
