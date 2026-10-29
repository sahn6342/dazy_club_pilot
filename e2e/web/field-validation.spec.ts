import { test, expect, Page } from "@playwright/test";

// The booking form checks each field as soon as the visitor leaves it, so a problem is shown next to the field and
// not as a failure after pressing Confirm. Slots are mocked: no real booking is made.

function synthetic(url: string) {
  const date = url.match(/date=([^&]+)/)?.[1] ?? "2099-01-01";
  const sport = url.match(/sport=([^&]+)/)?.[1] ?? "cricket";
  return Array.from({ length: 3 }, (_, i) => ({
    id: `mock-slot-${i}`, courtId: `court-${sport}`, sportSlug: sport, date,
    startTime: `0${6 + i}:00`, endTime: `0${7 + i}:00`, available: true, maxPlayers: 10,
    price: 1000, discountPercent: null, finalPrice: 1000,
  }));
}

async function openForm(page: Page) {
  await page.route("**/api/v1/slots**", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(synthetic(route.request().url())) }));
  await page.goto("/book");
  await page.locator(".date-pill").nth(1).click();
  await expect(page.locator(".slot-chip").first()).toBeVisible();
  await page.locator(".slot-chip").first().click();
}

const field = (page: Page, name: string) => page.locator(`[data-field="${name}"]`);
const errorOf = (page: Page, name: string) => field(page, name).locator("xpath=ancestor::div[contains(@class,'field-group')][1]").locator(".field-error");

test.describe("Booking form — field by field", () => {
  test("nothing is flagged before the visitor has been to a field", async ({ page }) => {
    await openForm(page);
    await expect(page.locator(".form-card .field-error")).toHaveCount(0);
  });

  test("each field shows its problem as soon as it is left, and clears when fixed", async ({ page }) => {
    await openForm(page);

    await field(page, "name").focus();
    await field(page, "contact").focus(); // leaves name empty
    await expect(errorOf(page, "name")).toHaveText("Name is required.");

    await field(page, "contact").fill("12345");
    await field(page, "email").focus(); // leaves contact
    await expect(errorOf(page, "contact")).toContainText("10-digit mobile number or email");

    await field(page, "email").fill("not-an-email");
    await field(page, "players").focus(); // leaves email
    await expect(errorOf(page, "email")).toContainText("valid email address");

    await field(page, "players").fill("99");
    await field(page, "message").focus(); // leaves players
    await expect(errorOf(page, "players")).toContainText("Maximum 10 players");

    // fixing a field removes its message right away
    await field(page, "name").fill("Asha Rao");
    await expect(errorOf(page, "name")).toHaveCount(0);
    await field(page, "contact").fill("9876543210");
    await expect(errorOf(page, "contact")).toHaveCount(0);
    await field(page, "email").fill("asha@example.com");
    await expect(errorOf(page, "email")).toHaveCount(0);
    await field(page, "players").fill("4");
    await expect(errorOf(page, "players")).toHaveCount(0);
  });

  test("an empty optional email is fine; an over-long message is caught on leaving it", async ({ page }) => {
    await openForm(page);
    await field(page, "email").focus();
    await field(page, "message").focus();
    await expect(errorOf(page, "email")).toHaveCount(0);
    await field(page, "message").fill("x".repeat(2001));
    await field(page, "name").focus();
    await expect(errorOf(page, "message")).toContainText("1 characters too long");
  });

  test("a name longer than the limit cannot be typed", async ({ page }) => {
    await openForm(page);
    await field(page, "name").fill("N".repeat(120));
    await expect(field(page, "name")).toHaveValue("N".repeat(80));
  });

  test("pressing Confirm with problems sends nothing, shows them all and focuses the first", async ({ page }) => {
    let posts = 0;
    await page.route("**/api/v1/bookings", (route) => { posts++; return route.abort(); });
    await openForm(page);
    await field(page, "email").fill("bad");
    await page.getByRole("button", { name: /confirm booking/i }).click();
    await expect(errorOf(page, "name")).toBeVisible();
    await expect(errorOf(page, "contact")).toBeVisible();
    await expect(errorOf(page, "email")).toBeVisible();
    await expect(field(page, "name")).toBeFocused();
    expect(posts).toBe(0);
  });
});
