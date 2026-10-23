import { test, expect, devices } from "@playwright/test";

// Same guard as the admin one: in real mobile emulation a page wider than the phone widens the layout
// (innerWidth > device width) and pushes the header menu button off the right edge.

const { defaultBrowserType: _ignored, ...iphone } = devices["iPhone 15"];

for (const width of [393, 375, 360, 320]) {
  test.describe(`phone ${width}px`, () => {
    test.use({ ...iphone, viewport: { width, height: 800 } });

    test("no website page is wider than the screen", async ({ page }) => {
      const wide: string[] = [];
      for (const path of ["/", "/book", "/my-bookings", "/contact"]) {
        await page.goto(path);
        await page.waitForLoadState("networkidle");
        // scroll down so lazily mounted sections exist before measuring
        const h = await page.evaluate(() => document.documentElement.scrollHeight);
        for (let y = 0; y <= h; y += 600) { await page.evaluate((yy) => window.scrollTo(0, yy), y); await page.waitForTimeout(120); }
        const m = await page.evaluate(() => ({ iw: window.innerWidth, sw: document.documentElement.scrollWidth }));
        if (m.iw !== width || m.sw > width) wide.push(`${path} (layout ${m.iw}px, content ${m.sw}px)`);
      }
      expect(wide, `pages wider than a ${width}px screen`).toEqual([]);
    });

    test("the menu button is fully on screen", async ({ page }) => {
      await page.goto("/");
      const box = (await page.getByTestId("nav-toggle").boundingBox())!;
      expect(box.x + box.width).toBeLessThanOrEqual(width);
      expect(box.x).toBeGreaterThanOrEqual(0);
    });
  });
}
