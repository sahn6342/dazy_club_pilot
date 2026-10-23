import { test, expect, Page, Route } from "@playwright/test";

// Advance (partial) payment on the Book and My Bookings pages. Everything is mocked, so it needs no particular
// price list or API settings: slots cost ₹1000 and the advance comes from the mocked /public-config.

function synthetic(url: string) {
  const date = url.match(/date=([^&]+)/)?.[1] ?? "2099-01-01";
  const sport = url.match(/sport=([^&]+)/)?.[1] ?? "cricket";
  return Array.from({ length: 4 }, (_, i) => ({
    id: `mock-${sport}-${date}-${i}`, courtId: `court-${sport}`, sportSlug: sport, date,
    startTime: `0${6 + i}:00`, endTime: `0${7 + i}:00`, available: true, maxPlayers: 10,
    price: 1000, discountPercent: null, finalPrice: 1000,
  }));
}

const json = (status: number, body: unknown) => (route: Route) =>
  route.fulfill({ status, contentType: "application/json", body: JSON.stringify(body) });

async function mockBase(page: Page, advanceAmount: number) {
  await page.route("**/api/v1/public-config", json(200, { otpRequired: true, advanceAmount }));
  await page.route("**/api/v1/slots**", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(synthetic(route.request().url())) }));
}

/** The API's answer to POST /bookings for a ₹1000 slot (price is the total; amountDue is what is paid now). */
function created(option: "full" | "advance", ref = "ADV00001") {
  const advance = option === "advance";
  return {
    status: "pending", bookingRef: ref, name: "E2E", sport: "cricket", date: "2099-01-01",
    startTime: "06:00", endTime: "07:00", time: "06:00", slotCount: 1, price: 1000, paymentRequired: true,
    paymentOption: option, advanceAmount: advance ? 500 : null, amountDue: advance ? 500 : 1000, balanceDue: advance ? 500 : 0,
    checkout: { provider: "noop", providerOrderId: `order_${ref}`, amount: advance ? 500 : 1000, currency: "INR" },
  };
}

async function open(page: Page, advanceAmount = 500) {
  await mockBase(page, advanceAmount);
  await page.goto("/book");
  await page.locator(".date-pill").nth(1).click();
  await expect(page.locator(".slot-chip").first()).toBeVisible();
  await page.locator(".slot-chip").first().click();
}

async function fillAndSubmit(page: Page) {
  await page.getByPlaceholder("Your full name").fill("E2E Advance User");
  await page.getByPlaceholder("10-digit mobile or email").fill("9876543210");
  await page.getByRole("button", { name: /confirm booking/i }).click();
}

test.describe("Choosing how to pay", () => {
  test("the advance is shown next to the price and the full payment is preselected", async ({ page }) => {
    await open(page);
    await expect(page.getByTestId("summary-total")).toContainText("₹1000");
    await expect(page.getByTestId("summary-advance")).toContainText("₹500");
    await expect(page.getByTestId("summary-advance")).toContainText(/non-refundable/i);

    const options = page.getByTestId("pay-options");
    await expect(options).toBeVisible();
    await expect(page.getByTestId("pay-option-full")).toBeChecked();
    await expect(page.getByTestId("pay-option-full-amount")).toHaveText("₹1000");
    await expect(page.getByTestId("pay-option-advance")).not.toBeChecked();
    await expect(options).toContainText("Pay ₹500 advance now");
    await expect(page.getByTestId("pay-option-advance-note")).toHaveText("₹500 at the venue");
    await expect(options).toContainText(/advance is non-refundable/i);
  });

  test("paying in full (the default) asks the API for the full payment", async ({ page }) => {
    let sent: any = null;
    await page.route("**/api/v1/bookings", (route) => { sent = route.request().postDataJSON(); return json(201, created("full"))(route); });
    await open(page);
    await fillAndSubmit(page);
    await expect(page.getByTestId("payment-amount")).toHaveText("Amount due: ₹1000.00");
    await expect(page.getByTestId("payment-balance")).toHaveCount(0);
    expect(sent.paymentOption).toBe("full");
  });

  test("choosing the advance: pay it, and the booking is confirmed with the balance shown", async ({ page }) => {
    let sent: any = null;
    await page.route("**/api/v1/bookings", (route) => { sent = route.request().postDataJSON(); return json(201, created("advance"))(route); });
    await page.route("**/payment/verify", json(200, { status: "confirmed", paymentStatus: "paid" }));
    await open(page);
    await page.getByTestId("pay-option-advance").check();
    await fillAndSubmit(page);
    expect(sent.paymentOption).toBe("advance");

    await expect(page.getByRole("heading", { name: /pay the advance/i })).toBeVisible();
    await expect(page.getByTestId("payment-amount")).toHaveText("Amount due: ₹500.00");
    await expect(page.getByTestId("payment-balance")).toContainText("non-refundable");
    await expect(page.getByTestId("payment-balance")).toContainText("₹500.00");

    await page.getByTestId("simulate-payment-success").click();
    const card = page.getByTestId("confirmed-card");
    await expect(card.getByText("You're booked in!")).toBeVisible();
    await expect(card.getByTestId("confirmed-amount")).toContainText("Amount paid: ₹500");
    await expect(card.getByTestId("confirmed-balance")).toContainText("₹500");
    await expect(card.getByTestId("confirmed-balance")).toContainText(/total ₹1000/);
    await expect(card.getByTestId("confirmed-balance")).toContainText(/advance is non-refundable/i);
  });

  test("a full payment confirmation shows no balance", async ({ page }) => {
    await page.route("**/api/v1/bookings", json(201, created("full")));
    await page.route("**/payment/verify", json(200, { status: "confirmed", paymentStatus: "paid" }));
    await open(page);
    await fillAndSubmit(page);
    await page.getByTestId("simulate-payment-success").click();
    await expect(page.getByTestId("confirmed-amount")).toContainText("Amount paid: ₹1000");
    await expect(page.getByTestId("confirmed-balance")).toHaveCount(0);
  });
});

test.describe("When the advance is not offered", () => {
  test("not at all when the advance is switched off (0)", async ({ page }) => {
    await open(page, 0);
    await expect(page.getByTestId("summary-total")).toBeVisible();
    await expect(page.getByTestId("pay-options")).toHaveCount(0);
    await expect(page.getByTestId("summary-advance")).toHaveCount(0);
  });

  test("not when the total is not more than the advance", async ({ page }) => {
    await open(page, 1000);
    await expect(page.getByTestId("summary-total")).toBeVisible();
    await expect(page.getByTestId("pay-options")).toHaveCount(0);
  });

  test("not when the config cannot be loaded", async ({ page }) => {
    await page.route("**/api/v1/slots**", (route) =>
      route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(synthetic(route.request().url())) }));
    await page.route("**/api/v1/public-config", json(500, {}));
    await page.goto("/book");
    await page.locator(".date-pill").nth(1).click();
    await page.locator(".slot-chip").first().click();
    await expect(page.getByTestId("summary-total")).toBeVisible();
    await expect(page.getByTestId("pay-options")).toHaveCount(0);
  });
});

test.describe("Promo codes", () => {
  const promo = (discountedAmount: number) =>
    json(200, { valid: true, code: "SAVE", kind: "percent", value: 10, discountedAmount, savedAmount: 1000 - discountedAmount });

  async function applyPromo(page: Page) {
    await page.getByTestId("promo-input").fill("SAVE");
    await expect(page.getByTestId("promo-valid")).toBeVisible();
  }

  test("the advance follows the discounted total", async ({ page }) => {
    await page.route("**/api/v1/promos/validate**", promo(600));
    await open(page);
    await applyPromo(page);
    await expect(page.getByTestId("pay-option-full-amount")).toHaveText("₹600");
    await expect(page.getByTestId("pay-option-advance-note")).toHaveText("₹100 at the venue");
  });

  test("a promo that brings the total down to the advance removes the option", async ({ page }) => {
    await page.route("**/api/v1/promos/validate**", promo(400));
    await open(page);
    await expect(page.getByTestId("pay-options")).toBeVisible();
    await page.getByTestId("pay-option-advance").check();
    await applyPromo(page);
    await expect(page.getByTestId("pay-options")).toHaveCount(0);
  });

  test("a promo that removes the option makes the booking go out as a full payment", async ({ page }) => {
    let sent: any = null;
    await page.route("**/api/v1/promos/validate**", promo(400));
    await page.route("**/api/v1/bookings", (route) => { sent = route.request().postDataJSON(); return json(201, { ...created("full"), price: 400, amountDue: 400, checkout: { ...created("full").checkout, amount: 400 } })(route); });
    await open(page);
    await page.getByTestId("pay-option-advance").check(); // chosen first...
    await applyPromo(page);                                // ...then the promo makes it unavailable
    await fillAndSubmit(page);
    await expect(page.getByTestId("payment-amount")).toHaveText("Amount due: ₹400.00");
    expect(sent.paymentOption).toBe("full");
  });
});

test.describe("API refuses the advance", () => {
  test("shows the reason and falls back to paying in full", async ({ page }) => {
    await page.route("**/api/v1/bookings", json(422, { detail: "Paying an advance is not available for this booking. Please pay the full amount.", code: "advance_not_available" }));
    await open(page);
    await page.getByTestId("pay-option-advance").check();
    await fillAndSubmit(page);
    await expect(page.getByTestId("booking-error")).toContainText("Paying an advance is not available");
    await expect(page.getByTestId("pay-option-full")).toBeChecked();
  });
});

test.describe("My Bookings", () => {
  const lookup = (over: Record<string, unknown>) => ({
    bookingRef: "ADV00002", name: "E2E", status: "confirmed", sport: "cricket", date: "2099-01-01", startTime: "06:00", endTime: "07:00",
    slotCount: 1, price: 1000, paymentRequired: false, checkout: null,
    paymentOption: "advance", advanceAmount: 500, amountDue: 500, amountPaid: 500, balanceDue: 500, ...over,
  });

  async function find(page: Page) {
    await page.goto("/my-bookings");
    await page.getByPlaceholder("e.g. A1B2C3D4").fill("ADV00002");
    await page.getByPlaceholder("10-digit mobile or email").fill("9876543210");
    await page.getByRole("button", { name: /find my booking/i }).click();
  }

  test("a confirmed advance booking shows what was paid and the balance", async ({ page }) => {
    await page.route("**/api/v1/bookings/lookup**", json(200, lookup({})));
    await find(page);
    await expect(page.getByTestId("lookup-amount-paid")).toHaveText("Amount paid: ₹500");
    await expect(page.getByTestId("lookup-balance")).toContainText("₹500");
    await expect(page.getByTestId("lookup-balance")).toContainText(/advance is non-refundable/i);
  });

  test("once the balance is collected nothing is owed", async ({ page }) => {
    await page.route("**/api/v1/bookings/lookup**", json(200, lookup({ amountPaid: 1000, balanceDue: 0 })));
    await find(page);
    await expect(page.getByTestId("lookup-amount-paid")).toHaveText("Amount paid: ₹1000");
    await expect(page.getByTestId("lookup-balance")).toHaveCount(0);
  });

  test("a pending advance booking resumes with the advance amount", async ({ page }) => {
    await page.route("**/api/v1/bookings/lookup**", json(200, lookup({
      status: "pending", paymentRequired: true, amountPaid: 0,
      checkout: { provider: "noop", providerOrderId: "order_ADV00002", amount: 500, currency: "INR" },
    })));
    await find(page);
    await expect(page.getByTestId("payment-amount")).toHaveText("Amount due: ₹500.00");
    await expect(page.getByTestId("payment-balance")).toContainText("₹500.00");
    await expect(page.getByTestId("lookup-balance")).toHaveCount(0); // only shown once confirmed
  });

  test("a paid-in-full booking is unchanged", async ({ page }) => {
    await page.route("**/api/v1/bookings/lookup**", json(200, lookup({ paymentOption: "full", advanceAmount: null, amountDue: 1000, amountPaid: 1000, balanceDue: 0 })));
    await find(page);
    await expect(page.getByTestId("lookup-amount-paid")).toHaveText("Amount paid: ₹1000");
    await expect(page.getByTestId("lookup-balance")).toHaveCount(0);
  });
});

test("the FAQ explains the advance", async ({ page }) => {
  await page.goto("/");
  const q = page.locator("details", { hasText: "Can I pay just an advance?" });
  await q.locator("summary").click();
  await expect(q).toContainText("non-refundable");
});
