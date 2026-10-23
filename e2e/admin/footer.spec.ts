import { test, expect, Page, Route } from "@playwright/test";

// Every admin page shows the website's footer: logo, tagline and the venue details from the CMS (GET /venue).

const ADDRESS = "J29M+RP5 D1, Chamari Chak Rd, Ram Krishna Puram, Balaji Nagar, New Tarachak, Danapur, Patna, Bihar 801503";
const VENUE = [
  { key: "venue_address", value: ADDRESS },
  { key: "venue_phone", value: "+91 93153 06294" },
  { key: "venue_email", value: "dazyclub1223@gmail.com" },
  { key: "venue_hours", value: "Open 24 hours" },
  { key: "social_instagram", value: "" },
  { key: "social_facebook", value: "" },
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

/** The café orders page asks a kiosk-only endpoint that an admin browser session (cookie) is not accepted by, so the
 *  page bounces to the login screen; answer it with an empty list so this spec is about the footer, not that. */
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

const footer = (page: Page) => page.getByTestId("site-footer");

test("the footer shows the venue details on every admin page", async ({ page }) => {
  await page.route("**/api/v1/venue", venue());
  await stubCafeOrders(page);
  await login(page);
  for (const path of ["/", "/bookings", "/schedule", "/promos", "/enquiries", "/cms", "/courts", "/contact-details", "/audit", "/cafe/items", "/cafe/orders"]) {
    await page.goto(path);
    const f = footer(page);
    await expect(f, path).toBeVisible();
    await expect(f.getByTestId("footer-address"), path).toContainText(ADDRESS);
    await expect(f.getByTestId("footer-phone").getByRole("link"), path).toHaveAttribute("href", "tel:+919315306294");
    await expect(f.getByTestId("footer-email").getByRole("link"), path).toHaveAttribute("href", "mailto:dazyclub1223@gmail.com");
    await expect(f.getByTestId("footer-hours"), path).toContainText("Open 24 hours");
    await expect(f.locator(".brand-logo")).toBeVisible();
  }
});

test("the address links to Google Maps and empty fields are not shown", async ({ page }) => {
  await page.route("**/api/v1/venue", venue(VENUE.map((e) => (e.key === "venue_hours" || e.key === "venue_email" ? { ...e, value: "" } : e))));
  await login(page);
  const href = await footer(page).getByTestId("footer-address").getByRole("link").getAttribute("href");
  expect(decodeURIComponent(href!.split("query=")[1])).toBe(ADDRESS);
  await expect(footer(page).getByTestId("footer-hours")).toHaveCount(0);
  await expect(footer(page).getByTestId("footer-email")).toHaveCount(0);
  await expect(footer(page).getByTestId("footer-social")).toHaveCount(0);
});

test("if the venue details cannot be loaded the footer is just the logo and tagline", async ({ page }) => {
  await page.route("**/api/v1/venue", (route) => route.fulfill({ status: 500, contentType: "application/json", body: "{}" }));
  await login(page);
  await expect(footer(page)).toBeVisible();
  await expect(footer(page)).toContainText("Premium sports experience");
  await expect(footer(page).getByTestId("footer-contact")).toHaveCount(0);
});

test("the footer sits below the page content, inside the content column", async ({ page }) => {
  await page.route("**/api/v1/venue", venue());
  await login(page);
  const body = (await page.locator(".page-body").boundingBox())!;
  const foot = (await footer(page).boundingBox())!;
  const side = (await page.locator(".sidebar").boundingBox())!;
  expect(foot.y).toBeGreaterThanOrEqual(body.y + body.height - 1);
  expect(foot.x).toBeGreaterThanOrEqual(side.x + side.width - 1); // not under the sidebar
});

test("the login page has no footer", async ({ page }) => {
  await page.route("**/api/v1/venue", venue());
  await page.goto("/login");
  await expect(page.locator(".login-card")).toBeVisible();
  await expect(footer(page)).toHaveCount(0);
});

test.describe("phone", () => {
  test.use({ viewport: { width: 360, height: 800 } });

  test("the footer stacks and stays inside the screen", async ({ page }) => {
    await page.route("**/api/v1/venue", venue());
    await login(page);
    const box = (await footer(page).boundingBox())!;
    expect(box.x).toBeGreaterThanOrEqual(0);
    expect(box.x + box.width).toBeLessThanOrEqual(360);
    await expect(footer(page).getByTestId("footer-address")).toBeVisible();
  });
});
