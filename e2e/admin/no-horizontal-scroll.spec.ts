import { test, expect, devices, Page, Route } from "@playwright/test";

// A page wider than the phone makes the browser widen the layout, so the menu button, top bar and content spill off
// the right edge. In real mobile emulation that shows up as innerWidth > the device width. Every admin page must
// fit, with wide tables scrolling inside their own box.

const { defaultBrowserType: _ignored, ...iphone } = devices["iPhone 15"];

const ROUTES = [
  "/", "/bookings", "/schedule", "/promos", "/enquiries", "/gallery", "/testimonials", "/cms", "/courts",
  "/contact-details", "/users", "/audit", "/notifications", "/cafe/categories", "/cafe/items", "/cafe/tables",
  "/cafe/settings", "/cafe/orders",
];

const BOOKING = {
  id: "b1", bookingRef: "WIDE0001", name: "A Customer With A Fairly Long Name", contact: "customer.with.a.long.address@example.com",
  sportSlug: "cricket", date: "2099-01-01", startTime: "06:00", endTime: "07:00", party_size: 4, price: 1200,
  promo_code: "WELCOME10", gst_rate_percent: 18, status: "confirmed", paymentStatus: "paid", createdAt: "2099-01-01T00:00:00Z",
  depositAmount: 500, balance_collected: 0,
};

/** The bookings table only exists with rows, and it is the widest table: answer the list request with one row. */
function bookingsWithOneRow(route: Route) {
  const origin = route.request().headers()["origin"] ?? "*";
  return route.fulfill({
    status: 200, contentType: "application/json",
    headers: { "access-control-allow-origin": origin, "access-control-allow-credentials": "true" },
    body: JSON.stringify({ items: [BOOKING], total: 1 }),
  });
}

/** The café orders page asks a kiosk-only endpoint that an admin browser session (cookie) is not accepted by, so the
 *  page bounces to the login screen; answer it with an empty list so the page itself is what gets measured. */
async function stubCafeOrders(page: Page) {
  await page.route("**/api/v1/cafe/orders**", (route) => {
    const origin = route.request().headers()["origin"] ?? "*";
    return route.fulfill({
      status: 200, contentType: "application/json",
      headers: { "access-control-allow-origin": origin, "access-control-allow-credentials": "true" },
      body: "[]",
    });
  });
}

async function login(page: Page) {
  await page.goto("/");
  await page.locator("input[name=username]").fill("admin");
  await page.locator("input[name=password]").fill("admin");
  await page.getByRole("button", { name: /sign in/i }).click();
  await expect(page.locator(".admin-layout")).toBeVisible({ timeout: 10_000 });
}

for (const width of [393, 360, 320]) {
  test.describe(`phone ${width}px`, () => {
    test.use({ ...iphone, viewport: { width, height: 800 } });

    test("no admin page is wider than the screen", async ({ page }) => {
      await stubCafeOrders(page);
      await page.route("**/api/v1/admin/bookings?**", (route) =>
        bookingsWithOneRow(route));
      await login(page);
      const wide: string[] = [];
      for (const path of ROUTES) {
        await page.goto(path);
        await page.waitForLoadState("networkidle");
        const m = await page.evaluate(() => ({ iw: window.innerWidth, sw: document.documentElement.scrollWidth }));
        if (m.iw !== width || m.sw > width) wide.push(`${path} (layout ${m.iw}px, content ${m.sw}px)`);
      }
      expect(wide, `pages wider than a ${width}px screen`).toEqual([]);
    });

    test("the menu button stays on screen on the widest page", async ({ page }) => {
      await page.route("**/api/v1/admin/bookings?**", (route) =>
        bookingsWithOneRow(route));
      await login(page);
      await page.goto("/bookings");
      await expect(page.locator(".table-wrap table")).toBeVisible();
      const box = (await page.getByTestId("nav-toggle").boundingBox())!;
      expect(box.x + box.width).toBeLessThanOrEqual(width);
      // the table is wider than the screen and scrolls inside its own box
      const scrolls = await page.locator(".table-wrap").first().evaluate((el) => el.scrollWidth > el.clientWidth);
      expect(scrolls).toBe(true);
    });
  });
}

test.describe("desktop", () => {
  test.use({ viewport: { width: 1280, height: 800 } });

  test("the sidebar keeps its width and wide tables still scroll inside their box", async ({ page }) => {
    await page.route("**/api/v1/admin/bookings?**", (route) =>
      bookingsWithOneRow(route));
    await login(page);
    await page.goto("/bookings");
    await expect(page.locator(".table-wrap table")).toBeVisible();
    expect((await page.locator(".sidebar").boundingBox())!.width).toBeCloseTo(220, 0);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  });
});
