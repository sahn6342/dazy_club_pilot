import { test, expect, Page, APIRequestContext } from "@playwright/test";

const API = "http://localhost:8000/api/v1";
const uid = () => `e2e_${Date.now().toString().slice(-7)}`;

async function adminToken(request: APIRequestContext): Promise<string> {
  const r = await request.post(`${API}/admin/login`, {
    data: { username: "admin", password: "admin" },
  });
  return (await r.json()).access_token;
}

async function login(page: Page) {
  await page.goto("/");
  await page.locator("input[name=username]").fill("admin");
  await page.locator("input[name=password]").fill("admin");
  await page.getByRole("button", { name: /sign in/i }).click();
  await expect(page.locator(".admin-layout")).toBeVisible({ timeout: 10_000 });
}

async function goUsers(page: Page) {
  await page.goto("/users");
  await expect(page.locator(".users-split")).toBeVisible({ timeout: 8_000 });
}

test.describe("Admin — Users CRUD", () => {
  test("users page renders tabs and form", async ({ page }) => {
    await login(page);
    await goUsers(page);
    await expect(page.getByRole("button", { name: /all/i })).toBeVisible();
    await expect(page.getByRole("button", { name: /managers/i })).toBeVisible();
    await expect(page.getByRole("button", { name: /kiosk staff/i })).toBeVisible();
    await expect(page.locator(".user-form")).toBeVisible();
  });

  test("create cashier → appears in list → delete", async ({ page }) => {
    await login(page);
    await goUsers(page);

    const username = uid();

    // Select cashier role
    await page.locator(".role-option").filter({ hasText: "Cashier" }).click();
    await page.locator('[data-testid="user-username"]').fill(username);
    await page.locator('[data-testid="user-password"]').fill("5678");

    const post = page.waitForResponse(
      (r) => r.url().endsWith("/admin/users") && r.request().method() === "POST"
    );
    await page.getByRole("button", { name: /add cashier/i }).click();
    expect((await post).status()).toBe(201);

    // Should appear in list
    await expect(page.locator(".enquiry-card").filter({ hasText: username })).toBeVisible();

    // Switch to Kiosk Staff tab — should still be visible
    await page.getByRole("button", { name: /kiosk staff/i }).click();
    const card = page.locator(".enquiry-card").filter({ hasText: username });
    await expect(card).toBeVisible();

    // Delete — the in-app ConfirmDialog (not a native window.confirm) gates this.
    await card.getByRole("button", { name: /remove/i }).click();
    await page.locator(".confirm-dialog").getByRole("button", { name: "Remove" }).click();
    await expect(page.locator(".enquiry-card").filter({ hasText: username })).toHaveCount(0);
  });

  test("create manager → appears in list → delete", async ({ page }) => {
    await login(page);
    await goUsers(page);

    const username = uid();

    // Manager is default role
    await page.locator('[data-testid="user-username"]').fill(username);
    await page.locator('[data-testid="user-password"]').fill("securepass1");

    const post = page.waitForResponse(
      (r) => r.url().endsWith("/admin/users") && r.request().method() === "POST"
    );
    await page.getByRole("button", { name: /add manager/i }).click();
    expect((await post).status()).toBe(201);

    await expect(page.locator(".enquiry-card").filter({ hasText: username })).toBeVisible();

    // Managers tab
    await page.getByRole("button", { name: /managers/i }).click();
    const card = page.locator(".enquiry-card").filter({ hasText: username });
    await expect(card).toBeVisible();

    await card.getByRole("button", { name: /remove/i }).click();
    await page.locator(".confirm-dialog").getByRole("button", { name: "Remove" }).click();
    await expect(page.locator(".enquiry-card").filter({ hasText: username })).toHaveCount(0);
  });

  test("edit user role via click then save", async ({ page, request }) => {
    // Create via API so we own the lifecycle
    const tok = await adminToken(request);
    const username = uid();
    const create = await request.post(`${API}/admin/users`, {
      headers: { Authorization: `Bearer ${tok}` },
      data: { username, password: "1234", role: "cashier" },
    });
    expect(create.status()).toBe(201);
    const { id } = await create.json();

    try {
      await login(page);
      await goUsers(page);

      // Click the card to enter edit mode
      await page.locator(".enquiry-card").filter({ hasText: username }).click();
      await expect(page.locator(".section-heading")).toContainText(username);

      // Change role to kitchen
      await page.locator(".role-option").filter({ hasText: "Kitchen" }).click();

      const patch = page.waitForResponse(
        (r) => r.url().includes("/admin/users/") && r.request().method() === "PATCH"
      );
      await page.getByRole("button", { name: /save changes/i }).click();
      expect((await patch).status()).toBe(200);

      // Verify via API
      const tok2 = await adminToken(request);
      const check = await request.get(`${API}/admin/users`, {
        headers: { Authorization: `Bearer ${tok2}` },
      });
      const users = await check.json();
      const updated = users.find((u: any) => u.id === id);
      expect(updated?.role).toBe("kitchen");
    } finally {
      const tok3 = await adminToken(request);
      await request.delete(`${API}/admin/users/${id}`, {
        headers: { Authorization: `Bearer ${tok3}` },
      });
    }
  });

  test("weak manager password shows validation error", async ({ page }) => {
    await login(page);
    await goUsers(page);

    // Manager role (default)
    await page.locator('[data-testid="user-username"]').fill(uid());
    await page.locator('[data-testid="user-password"]').fill("short");
    await page.locator('[data-testid="user-password"]').blur();

    await expect(page.locator(".field-error")).toContainText(/8 char/i);
  });

  test("invalid cashier PIN shows validation error", async ({ page }) => {
    await login(page);
    await goUsers(page);

    await page.locator(".role-option").filter({ hasText: "Cashier" }).click();
    await page.locator('[data-testid="user-username"]').fill(uid());
    await page.locator('[data-testid="user-password"]').fill("abc");
    await page.locator('[data-testid="user-password"]').blur();

    await expect(page.locator(".field-error")).toContainText(/4 digit/i);
  });
});
