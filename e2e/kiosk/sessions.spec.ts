import { test, expect, APIRequestContext } from "@playwright/test";

const API = "http://localhost:8000/api/v1";
const CASHIER = { username: `e2e_sess_${Date.now().toString().slice(-6)}`, pin: "5827" };

async function adminToken(request: APIRequestContext): Promise<string> {
  const r = await request.post(`${API}/admin/login`, { data: { username: "admin", password: "admin" } });
  return (await r.json()).access_token;
}

test.describe("Kiosk — cookie session", () => {
  let cashierId: string;

  test.beforeAll(async ({ request }) => {
    const tok = await adminToken(request);
    const r = await request.post(`${API}/admin/users`, {
      headers: { Authorization: `Bearer ${tok}` },
      data: { username: CASHIER.username, password: CASHIER.pin, role: "cashier" },
    });
    expect(r.status()).toBe(201);
    cashierId = (await r.json()).id;
  });

  test.afterAll(async ({ request }) => {
    const tok = await adminToken(request);
    await request.delete(`${API}/admin/users/${cashierId}`, { headers: { Authorization: `Bearer ${tok}` } });
  });

  test("PIN login sets an httpOnly cookie and logout revokes it", async ({ page, context }) => {
    await page.goto("/login");
    await page.locator(".login-input").fill(CASHIER.username);
    await page.keyboard.press("Tab");
    for (const d of CASHIER.pin) await page.keyboard.press(d);
    await expect(page).toHaveURL(/\/menu/, { timeout: 10_000 });

    const cookie = (await context.cookies()).find((c) => c.name === "dazy_kiosk");
    expect(cookie).toBeTruthy();
    expect(cookie!.httpOnly).toBe(true);
    const storage = await page.evaluate(() => JSON.stringify({ ...localStorage }));
    expect(storage).not.toMatch(/eyJ[A-Za-z0-9_-]+\./);
    expect((await page.request.get(`${API}/cafe/me`)).status()).toBe(200);
    // A kiosk session is not a back-office session.
    expect((await page.request.get(`${API}/admin/me`)).status()).toBe(401);

    await page.getByRole("button", { name: /logout/i }).click();
    await expect(page).toHaveURL(/\/login/, { timeout: 8_000 });
    await expect
      .poll(async () => (await context.cookies()).find((c) => c.name === "dazy_kiosk"), { timeout: 5_000 })
      .toBeUndefined();
    expect((await page.request.get(`${API}/cafe/me`)).status()).toBe(401);
  });
});
