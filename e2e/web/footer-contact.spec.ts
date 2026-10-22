import { test, expect, Page } from "@playwright/test";

// Venue contact details live in the footer of every page (from the CMS via GET /venue), not on the Contact page.

const ADDRESS = "J29M+RP5 D1, Chamari Chak Rd, Ram Krishna Puram, Balaji Nagar, New Tarachak, Danapur, Patna, Bihar 801503";

const VENUE = [
  { key: "venue_address", value: ADDRESS },
  { key: "venue_phone", value: "+91 93153 06294" },
  { key: "venue_email", value: "dazyclub1223@gmail.com" },
  { key: "venue_hours", value: "Open 24 hours" },
  { key: "social_instagram", value: "" },
  { key: "social_facebook", value: "" },
  { key: "whatsapp_phone", value: "919315306294" },
  { key: "whatsapp_message", value: "Hello!" },
];

async function mockVenue(page: Page, entries = VENUE) {
  let calls = 0;
  await page.route("**/api/v1/venue", (route) => {
    calls++;
    return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(entries) });
  });
  return { calls: () => calls };
}

const footer = (page: Page) => page.locator("footer.footer");

for (const path of ["/", "/book", "/my-bookings", "/contact"]) {
  test(`footer on ${path} shows address, phone, email and hours`, async ({ page }) => {
    await mockVenue(page);
    await page.goto(path);
    const f = footer(page);
    await expect(f.getByTestId("footer-address")).toContainText(ADDRESS);
    await expect(f.getByTestId("footer-phone").getByRole("link")).toHaveAttribute("href", "tel:+919315306294");
    await expect(f.getByTestId("footer-phone")).toContainText("+91 93153 06294");
    await expect(f.getByTestId("footer-email").getByRole("link")).toHaveAttribute("href", "mailto:dazyclub1223@gmail.com");
    await expect(f.getByTestId("footer-hours")).toHaveText(/Open 24 hours/);
  });
}

test("the address links to a Google Maps search for it", async ({ page }) => {
  await mockVenue(page);
  await page.goto("/");
  const href = await footer(page).getByTestId("footer-address").getByRole("link").getAttribute("href");
  expect(href).toContain("https://www.google.com/maps/search/?api=1&query=");
  expect(decodeURIComponent(href!.split("query=")[1])).toBe(ADDRESS);
});

test("social links appear only when they are set", async ({ page }) => {
  await mockVenue(page);
  await page.goto("/");
  await expect(footer(page).getByTestId("footer-social")).toHaveCount(0);

  const withSocial = VENUE.map((e) => e.key === "social_instagram" ? { ...e, value: "https://instagram.com/dazyclub" } : e);
  await page.unroute("**/api/v1/venue");
  await mockVenue(page, withSocial);
  await page.goto("/");
  await expect(footer(page).getByTestId("footer-social").getByRole("link", { name: "Instagram" })).toHaveAttribute("href", "https://instagram.com/dazyclub");
});

test("fields that are empty in the admin portal are not shown", async ({ page }) => {
  await mockVenue(page, VENUE.map((e) => (e.key === "venue_hours" || e.key === "venue_email" ? { ...e, value: "" } : e)));
  await page.goto("/");
  await expect(footer(page).getByTestId("footer-address")).toBeVisible();
  await expect(footer(page).getByTestId("footer-hours")).toHaveCount(0);
  await expect(footer(page).getByTestId("footer-email")).toHaveCount(0);
});

test("the footer and the WhatsApp button share a single venue request", async ({ page }) => {
  const venue = await mockVenue(page);
  await page.goto("/");
  await expect(footer(page).getByTestId("footer-address")).toBeVisible();
  await expect(page.locator("a.whatsapp-fab")).toBeVisible();
  expect(venue.calls()).toBe(1);
});

test("the Contact page no longer has its own venue strip", async ({ page }) => {
  await mockVenue(page);
  await page.goto("/contact");
  await expect(page.getByRole("heading", { name: /questions or planning an event/i })).toBeVisible();
  await expect(page.locator(".venue-info-band")).toHaveCount(0);
  // the address is shown once, in the footer only
  await expect(page.getByText(ADDRESS)).toHaveCount(1);
  await expect(footer(page).getByText(ADDRESS)).toHaveCount(1);
});

test.describe("WhatsApp button number", () => {
  test("uses the WhatsApp number from the admin portal", async ({ page }) => {
    await mockVenue(page, VENUE.map((e) => (e.key === "whatsapp_phone" ? { ...e, value: "919000000001" } : e)));
    await page.goto("/");
    await expect(page.locator("a.whatsapp-fab")).toHaveAttribute("href", /^https:\/\/wa\.me\/919000000001\?/);
  });

  test("falls back to the venue phone when no WhatsApp number is set", async ({ page }) => {
    await mockVenue(page, VENUE.map((e) => (e.key === "whatsapp_phone" ? { ...e, value: "" } : e)));
    await page.goto("/");
    await expect(page.locator("a.whatsapp-fab")).toHaveAttribute("href", /^https:\/\/wa\.me\/919315306294\?/);
  });
});

test("a failing venue request leaves a normal footer without contact details", async ({ page }) => {
  await page.route("**/api/v1/venue", (route) => route.fulfill({ status: 500, contentType: "application/json", body: "{}" }));
  await page.goto("/");
  await expect(footer(page)).toBeVisible();
  await expect(footer(page).getByTestId("footer-contact")).toHaveCount(0);
});

test("a database seeded with the defaults shows the real venue details (no mocks)", async ({ page }) => {
  await page.goto("/");
  const f = footer(page);
  await expect(f.getByTestId("footer-address")).toContainText("Danapur, Patna, Bihar 801503");
  await expect(f.getByTestId("footer-phone")).toContainText("93153 06294");
  await expect(f.getByTestId("footer-hours")).toContainText("Open 24 hours");
});
