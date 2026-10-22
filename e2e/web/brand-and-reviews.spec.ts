import { test, expect, Page } from "@playwright/test";

// Brand logo in every app + the real Google reviews in "What players say".

const ADMIN_URL = "http://localhost:5174";
const KIOSK_URL = "http://localhost:5175";

async function imageLoaded(page: Page, selector: string): Promise<boolean> {
  return page.locator(selector).first().evaluate((img) => (img as HTMLImageElement).complete && (img as HTMLImageElement).naturalWidth > 0);
}

test.describe("Brand logo", () => {
  test("web header and footer show the logo, and the tab icon is the logo", async ({ page }) => {
    await page.goto("/");
    const headerLogo = page.locator(".site-header .brand-logo");
    await expect(headerLogo).toBeVisible();
    expect(await imageLoaded(page, ".site-header .brand-logo")).toBe(true);
    await expect(page.locator(".site-header .brand")).toContainText("Dazy Club"); // name stays next to the logo
    await expect(page.locator(".footer .brand-logo")).toHaveCount(1);
    await expect(page.locator('link[rel="icon"]')).toHaveAttribute("href", "/favicon-32.png");
    await expect(page.locator('link[rel="apple-touch-icon"]')).toHaveAttribute("href", "/apple-touch-icon.png");
    const icon = await page.request.get("/favicon-32.png");
    expect(icon.status()).toBe(200);
  });

  test("admin login and kiosk login show the logo", async ({ page }) => {
    await page.goto(ADMIN_URL + "/");
    await expect(page.locator(".login-logo")).toBeVisible();
    expect(await imageLoaded(page, ".login-logo")).toBe(true);
    await expect(page.locator('link[rel="icon"]')).toHaveAttribute("href", "/favicon-32.png");

    await page.goto(KIOSK_URL + "/login");
    await expect(page.locator(".login-logo")).toBeVisible();
    expect(await imageLoaded(page, ".login-logo")).toBe(true);
    await expect(page.locator('link[rel="icon"]')).toHaveAttribute("href", "/favicon-32.png");
  });
});

test.describe("What players say", () => {
  test("shows the Google reviews (not the placeholders) with avatar images", async ({ page }) => {
    await page.goto("/");
    const cards = page.locator(".testimonial-card");
    await expect(cards.first()).toBeAttached();
    const text = await page.locator(".testimonial-carousel").innerText();
    // The carousel is paged, so read all pages from the DOM instead of only the visible one.
    const all = await page.locator(".testimonial-carousel .testimonial-card").evaluateAll((els) => els.map((e) => e.textContent ?? ""));
    const joined = all.join(" | ");
    for (const name of ["Sanraj S.", "Lucky R.", "Shivam S.", "Ashish P.", "Rudra S.", "Yash R.", "Ritik R.", "Kumar A."]) {
      expect(joined).toContain(name);
    }
    expect(joined).toContain("Google Local Guide");
    expect(joined).not.toContain("Priya R.");
    expect(joined).not.toContain("Arjun M.");
    expect(text.length).toBeGreaterThan(0);

    // every avatar is the male/female placeholder and actually loads
    const srcs = await page.locator(".testimonial-card .avatar").evaluateAll((els) => els.map((e) => (e as HTMLImageElement).getAttribute("src")));
    expect(srcs.length).toBeGreaterThan(0);
    for (const s of srcs) expect(s).toMatch(/\/images\/avatar-(male|female)\.svg$/);
    for (const s of new Set(srcs)) expect((await page.request.get(s!)).status()).toBe(200);
  });

  for (const width of [1280, 800, 375]) {
    test(`every review card has the same height (${width}px)`, async ({ page }) => {
      await page.setViewportSize({ width, height: 900 });
      await page.goto("/");
      await page.locator(".testimonial-carousel").scrollIntoViewIfNeeded();
      const heights = await page.locator(".testimonial-carousel .testimonial-card").evaluateAll((els) => els.map((e) => Math.round(e.getBoundingClientRect().height)));
      expect(heights.length).toBe(8);
      expect(new Set(heights).size).toBe(1); // fixed height: the carousel does not jump between pages
    });
  }
});
