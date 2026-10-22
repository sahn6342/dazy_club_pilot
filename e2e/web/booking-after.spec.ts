import { test, expect, Page, Route } from "@playwright/test";

// What the Book page does after a booking: it stays usable, the confirmation stays as a card with the ref
// (and a screenshot reminder), and a pending payment can be left. Everything is mocked.

function synthetic(url: string) {
  const date = url.match(/date=([^&]+)/)?.[1] ?? "2099-01-01";
  const sport = url.match(/sport=([^&]+)/)?.[1] ?? "cricket";
  return Array.from({ length: 4 }, (_, i) => ({
    id: `mock-${sport}-${date}-${i}`, courtId: `court-${sport}`, sportSlug: sport, date,
    startTime: `0${6 + i}:00`, endTime: `0${7 + i}:00`, available: true, maxPlayers: 10,
    price: 1000, discountPercent: null, finalPrice: 1000,
  }));
}

async function mockSlots(page: Page) {
  await page.route("**/api/v1/slots**", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(synthetic(route.request().url())) }));
}

const json = (status: number, body: unknown) => (route: Route) =>
  route.fulfill({ status, contentType: "application/json", body: JSON.stringify(body) });

function booking(ref: string, opts: { paid: boolean }) {
  return {
    status: opts.paid ? "pending" : "confirmed", bookingRef: ref, name: "E2E", sport: "cricket", date: "2099-01-01",
    startTime: "06:00", endTime: "07:00", time: "06:00", slotCount: 1, price: 1000, paymentRequired: opts.paid,
    ...(opts.paid ? { checkout: { provider: "noop", providerOrderId: `order_${ref}`, amount: 1000, currency: "INR" } } : {}),
  };
}

async function pickSlotAndFill(page: Page, index: number) {
  await page.locator(".slot-chip").nth(index).click();
  await page.getByPlaceholder("Your full name").fill("E2E After User");
  await page.getByPlaceholder("10-digit mobile or email").fill("9876543210");
  await page.getByRole("button", { name: /confirm booking/i }).click();
}

async function open(page: Page) {
  await mockSlots(page);
  await page.goto("/book");
  await page.locator(".date-pill").nth(1).click();
  await expect(page.locator(".slot-chip").first()).toBeVisible();
}

test.describe("After a confirmed booking", () => {
  test("a ref card appears with Copy and the screenshot reminder, and nothing is locked", async ({ page }) => {
    await page.route("**/api/v1/bookings", json(201, booking("ABCD1234", { paid: false })));
    await open(page);
    await pickSlotAndFill(page, 0);

    const card = page.getByTestId("confirmed-card");
    await expect(card).toBeVisible();
    await expect(card.getByText("You're booked in!")).toBeVisible();
    await expect(card.getByTestId("booking-ref")).toHaveText("ABCD1234");
    await expect(card.getByTestId("copy-ref")).toBeVisible();
    await expect(card.getByTestId("screenshot-note")).toContainText(/screenshot or note down this booking ID/i);

    // the form is empty again and the picker is fully usable
    await expect(page.locator(".booking-form-wrap")).toHaveCount(0);
    await expect(page.locator(".slot-chip").first()).toBeEnabled();
    for (const tab of ["Football", "Badminton", "Pickleball", "Cricket"]) {
      await expect(page.getByRole("tab", { name: tab })).toBeEnabled();
    }
    await expect(page.locator(".date-pill").first()).toBeEnabled();
  });

  test("Copy puts the ref on the clipboard", async ({ page, context }) => {
    await context.grantPermissions(["clipboard-read", "clipboard-write"]);
    await page.route("**/api/v1/bookings", json(201, booking("COPY5678", { paid: false })));
    await open(page);
    await pickSlotAndFill(page, 0);
    await page.getByTestId("copy-ref").click();
    await expect(page.getByTestId("copy-ref")).toHaveText(/copied/i);
    expect(await page.evaluate(() => navigator.clipboard.readText())).toBe("COPY5678");
  });

  test("another slot can be booked straight away, and both cards stay (newest first)", async ({ page }) => {
    let n = 0;
    await page.route("**/api/v1/bookings", (route) => {
      n++;
      return json(201, booking(n === 1 ? "FIRST111" : "SECOND22", { paid: false }))(route);
    });
    await open(page);
    await pickSlotAndFill(page, 0);
    await expect(page.getByTestId("confirmed-card")).toHaveCount(1);

    await page.getByRole("tab", { name: "Football" }).click(); // switching sport is allowed too
    await expect(page.locator(".slot-chip").first()).toBeVisible();
    await pickSlotAndFill(page, 1);

    const cards = page.getByTestId("confirmed-card");
    await expect(cards).toHaveCount(2);
    await expect(cards.nth(0).getByTestId("booking-ref")).toHaveText("SECOND22");
    await expect(cards.nth(1).getByTestId("booking-ref")).toHaveText("FIRST111");
  });
});

test.describe("Pending payment", () => {
  test("another slot can be tapped; the payment step closes and a banner says where to resume", async ({ page }) => {
    await page.route("**/api/v1/bookings", json(201, booking("HELD0001", { paid: true })));
    await open(page);
    await pickSlotAndFill(page, 0);
    await expect(page.getByTestId("simulate-payment-success")).toBeVisible();

    await expect(page.locator(".slot-chip").nth(2)).toBeEnabled();
    await page.locator(".slot-chip").nth(2).click();

    await expect(page.getByTestId("simulate-payment-success")).toHaveCount(0);
    await expect(page.getByTestId("left-payment")).toContainText("HELD0001");
    await expect(page.getByTestId("left-payment")).toContainText("My Bookings");
    await expect(page.locator(".booking-form-wrap")).toBeVisible(); // the new slot is selected and the form is back
    await expect(page.locator(".slot-chip.selected")).toHaveCount(1);
  });

  test("the 'Choose a different slot' button leaves the payment step too", async ({ page }) => {
    await page.route("**/api/v1/bookings", json(201, booking("HELD0002", { paid: true })));
    await open(page);
    await pickSlotAndFill(page, 0);
    await page.getByTestId("choose-another-slot").click();
    await expect(page.getByTestId("simulate-payment-success")).toHaveCount(0);
    await expect(page.getByTestId("left-payment")).toContainText("HELD0002");
    await expect(page.locator(".slot-chip.selected")).toHaveCount(0);
  });

  test("changing the sport or date during payment also leaves it, with the banner", async ({ page }) => {
    await page.route("**/api/v1/bookings", json(201, booking("HELD0003", { paid: true })));
    await open(page);
    await pickSlotAndFill(page, 0);
    await page.locator(".date-pill").nth(2).click();
    await expect(page.getByTestId("simulate-payment-success")).toHaveCount(0);
    await expect(page.getByTestId("left-payment")).toContainText("HELD0003");
  });

  test("paying successfully turns the payment step into a ref card", async ({ page }) => {
    await page.route("**/api/v1/bookings", json(201, booking("PAID0001", { paid: true })));
    await page.route("**/api/v1/bookings/*/payment/verify", json(200, { status: "confirmed", paymentStatus: "paid" }));
    await open(page);
    await pickSlotAndFill(page, 0);
    await page.getByTestId("simulate-payment-success").click();
    await expect(page.getByTestId("confirmed-card").getByTestId("booking-ref")).toHaveText("PAID0001");
    await expect(page.getByTestId("left-payment")).toHaveCount(0);
    await expect(page.getByTestId("simulate-payment-success")).toHaveCount(0);
  });
});
