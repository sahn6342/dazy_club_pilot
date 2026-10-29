import { test, expect } from "@playwright/test";

// A sleeping free-tier server answers late or not at all for the first request. The site must wait for it, repeat
// reads that got no answer, and tell the visitor what is going on.

test.describe("Web — sleeping API", () => {
  test("a read that gets 503 while the server starts is repeated and then succeeds", async ({ page }) => {
    let calls = 0;
    await page.route("**/api/v1/venue", (route) => {
      calls++;
      return calls === 1 ? route.fulfill({ status: 503, body: "starting" }) : route.continue();
    });
    await page.goto("/contact");
    await expect.poll(() => calls, { timeout: 15_000 }).toBeGreaterThanOrEqual(2);
    await expect(page.locator("footer")).toContainText(/Danapur|Patna|\+91/, { timeout: 15_000 });
  });

  test("a read that never connects the first time is repeated", async ({ page }) => {
    let calls = 0;
    await page.route("**/api/v1/venue", (route) => {
      calls++;
      return calls === 1 ? route.abort("connectionfailed") : route.continue();
    });
    await page.goto("/contact");
    await expect.poll(() => calls, { timeout: 15_000 }).toBeGreaterThanOrEqual(2);
  });

  test("a slow answer shows the waking-up notice, which goes away when it arrives", async ({ page }) => {
    await page.route("**/api/v1/venue", async (route) => {
      await new Promise((r) => setTimeout(r, 6_000));
      await route.continue();
    });
    await page.goto("/contact");
    await expect(page.getByTestId("api-waking")).toBeVisible({ timeout: 8_000 });
    await expect(page.getByTestId("api-waking")).toContainText("Waking up the server");
    await expect(page.getByTestId("api-waking")).toBeHidden({ timeout: 15_000 });
  });
});
