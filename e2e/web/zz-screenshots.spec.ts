import { test, expect, Page } from "@playwright/test";

// Documentation screenshots for the public web app (Vite :5173).
// Output: docs/screenshots/web-*.png. Re-runnable to regenerate docs.

const DIR = "C:/Users/shaparashar/Documents/extra personal/code/dazy_club_pilot/docs/screenshots";
const DESKTOP = { width: 1440, height: 900 };
const MOBILE = { width: 390, height: 844 };

async function gotoBookWithSlots(page: Page) {
  await page.goto("/book");
  await expect(page.locator(".sport-tabs .tab-btn").first()).toBeVisible();
  // Select a sport (Cricket) and the first available date so slots render.
  await page.locator(".sport-tabs .tab-btn").first().click();
  await page.locator(".date-pills .date-pill").first().click();
  await page.waitForLoadState("networkidle");
  // Wait for the slot section to resolve (slots, loading-done, or empty msg).
  await expect(page.locator(".slot-section")).toBeVisible();
  await page
    .locator(".slot-grid, .slot-loading")
    .first()
    .waitFor({ state: "visible", timeout: 8_000 })
    .catch(() => {});
}

test.describe("Web screenshots", () => {
  test("web-home (desktop + mobile)", async ({ page }) => {
    await page.setViewportSize(DESKTOP);
    await page.goto("/");
    await page.waitForLoadState("networkidle");
    await expect(page.locator("body")).toBeVisible();
    // Let hero/carousel settle.
    await page.waitForTimeout(800);
    await page.screenshot({ path: `${DIR}/web-home.png`, fullPage: true });

    await page.setViewportSize(MOBILE);
    await page.goto("/");
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(800);
    await page.screenshot({ path: `${DIR}/web-home-mobile.png`, fullPage: true });
  });

  test("web-book (desktop + mobile)", async ({ page }) => {
    await page.setViewportSize(DESKTOP);
    await gotoBookWithSlots(page);
    await page.screenshot({ path: `${DIR}/web-book.png`, fullPage: true });

    await page.setViewportSize(MOBILE);
    await gotoBookWithSlots(page);
    await page.screenshot({ path: `${DIR}/web-book-mobile.png`, fullPage: true });
  });

  test("web-contact (general + corporate)", async ({ page }) => {
    await page.setViewportSize(DESKTOP);
    await page.goto("/contact");
    await page.waitForLoadState("networkidle");
    await expect(page.locator(".sport-tabs .tab-btn", { hasText: /general/i })).toBeVisible();
    // General enquiry tab (default).
    await page.locator(".sport-tabs .tab-btn", { hasText: /general/i }).click();
    await expect(page.locator("form.form-card")).toBeVisible();
    await page.screenshot({ path: `${DIR}/web-contact-general.png`, fullPage: true });

    // Corporate event tab.
    await page.locator(".sport-tabs .tab-btn", { hasText: /corporate/i }).click();
    await expect(page.locator("input[name=eventType]")).toBeVisible();
    await page.screenshot({ path: `${DIR}/web-contact-corporate.png`, fullPage: true });
  });
});
