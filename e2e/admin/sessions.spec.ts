import { test, expect } from "@playwright/test";

const API = "http://localhost:8000/api/v1";

async function login(page: import("@playwright/test").Page) {
  await page.goto("/");
  await page.locator("input[name=username]").fill("admin");
  await page.locator("input[name=password]").fill("admin");
  await page.getByRole("button", { name: /sign in/i }).click();
  await expect(page.locator(".admin-layout")).toBeVisible({ timeout: 10_000 });
}

test.describe("Admin — cookie session", () => {
  test("session is an httpOnly cookie, never a script-readable token", async ({ page, context }) => {
    await login(page);

    const cookie = (await context.cookies()).find((c) => c.name === "dazy_admin");
    expect(cookie, "API should have set the dazy_admin cookie").toBeTruthy();
    expect(cookie!.httpOnly).toBe(true);
    expect(cookie!.sameSite).toBe("Lax");

    // Nothing a script could steal: the cookie is invisible to document.cookie and no JWT is in storage.
    const visible = await page.evaluate(() => ({
      cookies: document.cookie,
      storage: JSON.stringify({ ...localStorage }),
    }));
    expect(visible.cookies).not.toContain("dazy_admin");
    expect(visible.storage).not.toMatch(/eyJ[A-Za-z0-9_-]+\./);
  });

  test("session survives a reload and talks to the API with the cookie alone", async ({ page }) => {
    await login(page);
    await page.goto("/bookings");
    await expect(page.locator(".admin-layout")).toBeVisible({ timeout: 10_000 });
    const me = await page.request.get(`${API}/admin/me`);
    expect(me.status()).toBe(200);
    expect((await me.json()).role).toBe("admin");
  });

  test("logout revokes the session server-side, even for a copied token", async ({ page, context, playwright }) => {
    await login(page);
    const stolen = (await context.cookies()).find((c) => c.name === "dazy_admin")!.value;

    await page.getByRole("button", { name: /logout/i }).click();
    await expect(page.locator(".login-card")).toBeVisible({ timeout: 8_000 });

    // The browser's cookie is gone (the logout request is fire-and-forget, so poll briefly) ...
    await expect
      .poll(async () => (await context.cookies()).find((c) => c.name === "dazy_admin"), { timeout: 5_000 })
      .toBeUndefined();
    expect((await page.request.get(`${API}/admin/me`)).status()).toBe(401);

    // ... and the token itself no longer works anywhere.
    const bare = await playwright.request.newContext();
    const r = await bare.get(`${API}/admin/me`, { headers: { Authorization: `Bearer ${stolen}` } });
    expect(r.status()).toBe(401);
    await bare.dispose();
  });

  test("protected page without a session bounces to login", async ({ page }) => {
    await page.goto("/bookings");
    await expect(page.locator(".login-card")).toBeVisible({ timeout: 8_000 });
  });
});
