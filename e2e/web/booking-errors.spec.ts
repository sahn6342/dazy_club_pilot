import { test, expect, Page, Route } from "@playwright/test";

// What the Book page shows when POST /bookings (or the payment check) fails. Everything is mocked, so no real
// booking is made and no payment gateway is needed.

function synthetic(url: string) {
  const date = url.match(/date=([^&]+)/)?.[1] ?? "2099-01-01";
  const sport = url.match(/sport=([^&]+)/)?.[1] ?? "cricket";
  return Array.from({ length: 3 }, (_, i) => ({
    id: `mock-slot-${i}`, courtId: `court-${sport}`, sportSlug: sport, date,
    startTime: `0${6 + i}:00`, endTime: `0${7 + i}:00`, available: true, maxPlayers: 10,
    price: 1000, discountPercent: null, finalPrice: 1000,
  }));
}

/** Mock the slot list and count how many times the page fetches it (a reload means "slots may have changed"). */
async function mockSlots(page: Page): Promise<{ count: () => number }> {
  let n = 0;
  await page.route("**/api/v1/slots**", async (route) => {
    n++;
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(synthetic(route.request().url())) });
  });
  return { count: () => n };
}

/** Fill the form and press Confirm. Returns how many times the slots had been fetched just before pressing it. */
async function fillAndSubmit(page: Page, slots?: { count: () => number }): Promise<number> {
  await page.goto("/book");
  await page.locator(".date-pill").nth(1).click();
  await expect(page.locator(".slot-chip").first()).toBeVisible();
  await page.locator(".slot-chip").first().click();
  await page.getByPlaceholder("Your full name").fill("E2E Error User");
  await page.getByPlaceholder("10-digit mobile or email").fill("9876543210");
  const before = slots?.count() ?? 0;
  await page.getByRole("button", { name: /confirm booking/i }).click();
  return before;
}

const json = (status: number, body: unknown) => (route: Route) =>
  route.fulfill({ status, contentType: "application/json", body: JSON.stringify(body) });

const bookingError = (page: Page) => page.getByTestId("booking-error");

test.describe("Booking page — error messages", () => {
  test("gateway outage (503) says so: not 'slots may have been taken', and the slots are not reloaded", async ({ page }) => {
    const slots = await mockSlots(page);
    await page.route("**/api/v1/bookings", json(503, { detail: "Payment gateway unavailable — please try again.", code: "payment_unavailable" }));
    const loadsBeforeClick = await fillAndSubmit(page, slots);
    await expect(bookingError(page)).toHaveText("Payment gateway unavailable — please try again.");
    await expect(page.getByText(/slots may have just been taken/i)).toHaveCount(0);
    await page.waitForTimeout(800);
    expect(slots.count()).toBe(loadsBeforeClick); // no reload because of the outage
    // the selection is still there, so the visitor can just press Confirm again
    await expect(page.locator(".slot-chip.selected")).toHaveCount(1);
    await expect(page.getByRole("button", { name: /confirm booking/i })).toBeEnabled();
  });

  test("the same 503 text without a code (an older server) still shows the gateway message", async ({ page }) => {
    await mockSlots(page);
    await page.route("**/api/v1/bookings", json(503, { detail: "Payment gateway unavailable — please try again." }));
    await fillAndSubmit(page);
    await expect(bookingError(page)).toHaveText("Payment gateway unavailable — please try again.");
  });

  test("a slot that was taken (409) shows the slot message and reloads the slots", async ({ page }) => {
    const slots = await mockSlots(page);
    await page.route("**/api/v1/bookings", json(409, { detail: "Slot 06:00 is unavailable (already booked or elapsed).", code: "slot_unavailable" }));
    const loadsBeforeClick = await fillAndSubmit(page, slots);
    await expect(bookingError(page)).toHaveText("Booking failed. One or more slots may have just been taken. Please choose again.");
    await expect.poll(() => slots.count()).toBeGreaterThan(loadsBeforeClick); // the grid is refreshed
  });

  test("a vanished slot (404) is treated as a taken slot", async ({ page }) => {
    await mockSlots(page);
    await page.route("**/api/v1/bookings", json(404, { detail: "Slot mock-slot-0 not found.", code: "slot_not_found" }));
    await fillAndSubmit(page);
    await expect(bookingError(page)).toContainText("slots may have just been taken");
  });

  test("rate limit (429) shows the server's own message", async ({ page }) => {
    await mockSlots(page);
    await page.route("**/api/v1/bookings", json(429, { detail: "Too many booking attempts. Please try again later.", code: "rate_limited" }));
    await fillAndSubmit(page);
    await expect(bookingError(page)).toHaveText("Too many booking attempts. Please try again later.");
  });

  test("the pending-booking cap (429) points the visitor at their waiting bookings", async ({ page }) => {
    await mockSlots(page);
    await page.route("**/api/v1/bookings", json(429, { detail: "You already have bookings waiting for payment. Complete or wait for them to expire (15 minutes) before booking more.", code: "pending_cap" }));
    await fillAndSubmit(page);
    await expect(bookingError(page)).toContainText("You already have bookings waiting for payment");
  });

  test("no connection shows a clear message instead of 'Failed to fetch'", async ({ page }) => {
    await mockSlots(page);
    await page.route("**/api/v1/bookings", (route) => route.abort("failed"));
    await fillAndSubmit(page);
    await expect(bookingError(page)).toHaveText("Can't reach the server. Check your connection and try again.");
    await expect(page.getByText(/failed to fetch/i)).toHaveCount(0);
  });

  test("an unexpected 500 shows a friendly message with the reference", async ({ page }) => {
    await mockSlots(page);
    await page.route("**/api/v1/bookings", json(500, { detail: "Internal server error.", requestId: "abcdef1234567890" }));
    await fillAndSubmit(page);
    await expect(bookingError(page)).toHaveText("Something went wrong on our side. Please try again in a moment. (ref abcdef12)");
  });

  test("a non-JSON gateway error page (502) is not shown as a slot problem", async ({ page }) => {
    await mockSlots(page);
    await page.route("**/api/v1/bookings", (route) => route.fulfill({ status: 502, contentType: "text/html", body: "<h1>Bad gateway</h1>" }));
    await fillAndSubmit(page);
    await expect(bookingError(page)).toHaveText("Something went wrong on our side. Please try again in a moment.");
  });

  test("a validation error (422) shows a readable message, not '[object Object]'", async ({ page }) => {
    await mockSlots(page);
    await page.route("**/api/v1/bookings", json(422, { detail: [{ loc: ["body", "name"], msg: "Value error, Name is too short.", type: "value_error" }] }));
    await fillAndSubmit(page);
    await expect(bookingError(page)).toHaveText("Name is too short.");
  });

  test("a promo problem lands on the promo field and leaves the form alone", async ({ page }) => {
    const slots = await mockSlots(page);
    await page.route("**/api/v1/bookings", json(400, { detail: "Promo code expired.", code: "promo_invalid" }));
    await fillAndSubmit(page);
    await expect(page.getByTestId("promo-error")).toHaveText("Promo code expired.");
    await expect(bookingError(page)).toHaveCount(0);
    expect(slots.count()).toBeGreaterThan(0);
  });
});

test.describe("Payment step — a failed check is retried, not paid twice", () => {
  const booked = {
    status: "pending", bookingRef: "ABCD1234", name: "E2E", sport: "cricket", date: "2099-01-01",
    startTime: "06:00", endTime: "07:00", time: "06:00", slotCount: 1, price: 1000, paymentRequired: true,
    checkout: { provider: "noop", providerOrderId: "order_x", amount: 1000, currency: "INR" },
  };

  test("network failure while checking the payment offers 'Check payment again' and re-sends the same payment", async ({ page }) => {
    await mockSlots(page);
    await page.route("**/api/v1/bookings", json(201, booked));
    const sent: string[] = [];
    let attempt = 0;
    await page.route("**/api/v1/bookings/*/payment/verify", async (route) => {
      attempt++;
      sent.push(route.request().postData() ?? "");
      if (attempt === 1) return route.abort("failed");
      return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ status: "confirmed", paymentStatus: "paid" }) });
    });
    await fillAndSubmit(page);
    await page.getByTestId("simulate-payment-success").click();

    await expect(page.getByTestId("payment-error")).toContainText("don't pay again");
    await expect(page.getByTestId("payment-recheck")).toBeVisible();
    await expect(page.getByTestId("simulate-payment-success")).toHaveCount(0); // no second payment is offered

    await page.getByTestId("payment-recheck").click();
    await expect(page.getByText(/you're booked in/i)).toBeVisible();
    expect(sent.length).toBe(2);
    expect(sent[1]).toBe(sent[0]); // the very same payment id was checked again
  });

  test("a definite failure (400) keeps the normal retry, with the server's message", async ({ page }) => {
    await mockSlots(page);
    await page.route("**/api/v1/bookings", json(201, booked));
    await page.route("**/api/v1/bookings/*/payment/verify", json(400, { detail: "Signature mismatch.", code: "payment_verification_failed" }));
    await fillAndSubmit(page);
    await page.getByTestId("simulate-payment-success").click();
    await expect(page.getByTestId("payment-error")).toHaveText("Signature mismatch.");
    await expect(page.getByTestId("payment-recheck")).toHaveCount(0);
    await expect(page.getByTestId("simulate-payment-success")).toBeVisible();
  });
});
