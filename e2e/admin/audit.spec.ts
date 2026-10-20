import { test, expect, APIRequestContext } from "@playwright/test";

const API = "http://localhost:8000/api/v1";
const CSRF = { "X-Requested-With": "dazy" };

async function adminToken(request: APIRequestContext): Promise<string> {
  const r = await request.post(`${API}/admin/login`, { data: { username: "admin", password: "admin" } });
  return (await r.json()).access_token;
}

async function uiLogin(page: import("@playwright/test").Page, username: string, password: string) {
  await page.goto("/");
  await page.locator("input[name=username]").fill(username);
  await page.locator("input[name=password]").fill(password);
  await page.getByRole("button", { name: /sign in/i }).click();
  await expect(page.locator(".admin-layout")).toBeVisible({ timeout: 10_000 });
}

test.describe("Admin — audit log", () => {
  test("superadmin sees logins and admin writes, and can filter them", async ({ page }) => {
    await uiLogin(page, "admin", "admin");

    // Do something auditable through the browser's own (cookie) session.
    const code = `AUD${Date.now().toString().slice(-6)}`;
    const created = await page.request.post(`${API}/admin/promos`, {
      headers: CSRF, data: { code, kind: "percent", value: 5, active: true },
    });
    expect(created.status()).toBe(201);
    const id = (await created.json()).id;
    expect((await page.request.delete(`${API}/admin/promos/${id}`, { headers: CSRF })).status()).toBe(204);

    await page.goto("/audit");
    const table = page.getByTestId("audit-table");
    await expect(table).toBeVisible({ timeout: 8_000 });
    await expect(table).toContainText("auth.login");
    await expect(table).toContainText("POST /admin/promos");
    await expect(table).toContainText("DELETE /admin/promos/{id}");

    await page.getByTestId("audit-action").fill("promos");
    await expect(table).not.toContainText("auth.login");
    await expect(table).toContainText("POST /admin/promos");
    await expect(page.getByTestId("audit-range")).toContainText(/1–\d+ of \d+/);

    await page.getByTestId("audit-action").fill("no-such-action-xyz");
    await expect(page.getByText("No audit entries match.")).toBeVisible();
  });

  test("a manager is told only the superadmin can read the log", async ({ page, request }) => {
    const tok = await adminToken(request);
    const username = `aud_mgr_${Date.now().toString().slice(-6)}`;
    const created = await request.post(`${API}/admin/users`, {
      headers: { Authorization: `Bearer ${tok}` }, data: { username, password: "manager-pass-1", role: "manager" },
    });
    expect(created.status()).toBe(201);
    try {
      await uiLogin(page, username, "manager-pass-1");
      await page.goto("/audit");
      await expect(page.getByTestId("audit-error")).toContainText(/only the superadmin/i, { timeout: 8_000 });
      await expect(page.getByTestId("audit-table")).toHaveCount(0);
    } finally {
      await request.delete(`${API}/admin/users/${(await created.json()).id}`, { headers: { Authorization: `Bearer ${tok}` } });
    }
  });
});
