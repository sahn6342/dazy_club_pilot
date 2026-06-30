import { test, expect } from "@playwright/test";

test.describe("Web — gallery from API", () => {
  test("renders images served by the API", async ({ page }) => {
    const items = [
      { id: "g1", title: "E2E Turf", sportSlug: "cricket", tone: "electric", imageUrl: "https://example.com/e2e-cricket.jpg" },
      { id: "g2", title: "E2E Rally", sportSlug: "badminton", tone: "focused", imageUrl: "/media/gallery/abc.png" },
    ];
    await page.route("**/api/v1/gallery", async (route) => {
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(items) });
    });

    await page.goto("/");
    const gallery = page.locator("#gallery");
    await gallery.scrollIntoViewIfNeeded();

    // Absolute URL passed through unchanged.
    await expect(gallery.locator('img[src="https://example.com/e2e-cricket.jpg"]')).toBeVisible();
    // Relative /media path resolved against the API origin.
    await expect(gallery.locator('img[src="http://localhost:8000/media/gallery/abc.png"]')).toHaveCount(1);
    await expect(gallery.getByText("E2E Turf")).toBeVisible();
  });

  test("falls back to static items if the API fails", async ({ page }) => {
    await page.route("**/api/v1/gallery", (route) => route.fulfill({ status: 500, body: "boom" }));
    await page.goto("/");
    const gallery = page.locator("#gallery");
    await gallery.scrollIntoViewIfNeeded();
    // Static fallback still renders figures with captions.
    await expect(gallery.locator("figure.gallery-item")).not.toHaveCount(0);
  });
});
