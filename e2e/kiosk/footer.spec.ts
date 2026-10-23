import { test, expect, APIRequestContext, Page, Route } from "@playwright/test";

// Every kiosk page ends with a slim strip of the venue details from the CMS (GET /venue).

const API = "http://localhost:8000/api/v1";
const CASHIER = { username: `e2e_foot_${Date.now().toString().slice(-6)}`, pin: "7391" };
const ADDRESS = "J29M+RP5 D1, Chamari Chak Rd, Ram Krishna Puram, Balaji Nagar, New Tarachak, Danapur, Patna, Bihar 801503";
const VENUE = [
  { key: "venue_address", value: ADDRESS },
  { key: "venue_phone", value: "+91 93153 06294" },
  { key: "venue_email", value: "dazyclub1223@gmail.com" },
  { key: "venue_hours", value: "Open 24 hours" },
];

function venue(entries = VENUE) {
  return (route: Route) => {
    const origin = route.request().headers()["origin"] ?? "*";
    return route.fulfill({
      status: 200, contentType: "application/json",
      headers: { "access-control-allow-origin": origin, "access-control-allow-credentials": "true" },
      body: JSON.stringify(entries),
    });
  };
}

async function adminToken(request: APIRequestContext): Promise<string> {
  const r = await request.post(`${API}/admin/login`, { data: { username: "admin", password: "admin" } });
  return (await r.json()).access_token;
}

async function signIn(page: Page) {
  await page.goto("/login");
  await page.locator(".login-input").fill(CASHIER.username);
  await page.locator(".login-card h1").click();
  for (const d of CASHIER.pin) await page.locator(".pin-btn").filter({ hasText: new RegExp(`^${d}$`) }).click();
  await expect(page).toHaveURL(/\/menu/, { timeout: 10_000 });
}

const strip = (page: Page) => page.getByTestId("kiosk-footer");

test.describe("Kiosk — venue footer", () => {
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

  test("a slim strip with address, phone and hours ends every kiosk page", async ({ page }) => {
    await page.route("**/api/v1/venue", venue());
    await signIn(page);
    for (const path of ["/menu", "/orders", "/tables", "/kds"]) {
      await page.goto(path);
      const s = strip(page);
      await expect(s, path).toBeVisible();
      await expect(s.getByTestId("footer-address")).toContainText(ADDRESS);
      await expect(s.getByTestId("footer-phone")).toHaveAttribute("href", "tel:+919315306294");
      await expect(s.getByTestId("footer-hours")).toContainText("Open 24 hours");
      expect((await s.boundingBox())!.height).toBeLessThan(70); // slim: the POS keeps its height
      // it is the last thing on the page: nothing below it
      const viewport = page.viewportSize()!;
      const b = (await s.boundingBox())!;
      expect(Math.round(b.y + b.height)).toBeLessThanOrEqual(viewport.height + 2);
    }
  });

  test("the address links to Google Maps", async ({ page }) => {
    await page.route("**/api/v1/venue", venue());
    await signIn(page);
    const href = await strip(page).getByTestId("footer-address").getAttribute("href");
    expect(decodeURIComponent(href!.split("query=")[1])).toBe(ADDRESS);
  });

  test("empty fields are left out", async ({ page }) => {
    await page.route("**/api/v1/venue", venue(VENUE.map((e) => (e.key === "venue_hours" ? { ...e, value: "" } : e))));
    await signIn(page);
    await expect(strip(page).getByTestId("footer-address")).toBeVisible();
    await expect(strip(page).getByTestId("footer-hours")).toHaveCount(0);
  });

  test("no strip at all when the details cannot be loaded", async ({ page }) => {
    await page.route("**/api/v1/venue", (route) => route.fulfill({ status: 500, contentType: "application/json", body: "{}" }));
    await signIn(page);
    await expect(page.locator(".kiosk-body")).toBeVisible();
    await expect(strip(page)).toHaveCount(0);
  });

  test("the login screen has no footer", async ({ page }) => {
    await page.route("**/api/v1/venue", venue());
    await page.goto("/login");
    await expect(page.locator(".login-card")).toBeVisible();
    await expect(strip(page)).toHaveCount(0);
  });

  test.describe("phone", () => {
    test.use({ viewport: { width: 360, height: 760 } });

    test("the strip wraps and stays inside the screen", async ({ page }) => {
      await page.route("**/api/v1/venue", venue());
      await signIn(page);
      await page.locator(".kiosk-body").evaluate((el) => el.scrollTo(0, el.scrollHeight));
      const b = (await strip(page).boundingBox())!;
      expect(b.x).toBeGreaterThanOrEqual(0);
      expect(b.x + b.width).toBeLessThanOrEqual(360);
      await expect(strip(page).getByTestId("footer-address")).toBeVisible();
    });
  });
});
