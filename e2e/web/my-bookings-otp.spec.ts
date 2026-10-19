import { test, expect } from "@playwright/test";

// Contact-only search is gated by a one-time code. The code itself is only delivered by
// email/WhatsApp (printed to the API log in dev), so this spec covers the UI gate and the
// rejection path; the full request -> verify -> search flow is covered by the pytest suite.

test.describe("My bookings — contact search needs a one-time code", () => {
  test("contact-only search asks for a code instead of listing bookings", async ({ page }) => {
    await page.goto("/my-bookings");
    await page.getByPlaceholder(/10-digit mobile or email/i).fill("9" + String(Date.now()).slice(-9));
    await page.getByRole("button", { name: /send me a code/i }).click();

    await expect(page.getByTestId("otp-step")).toBeVisible({ timeout: 8_000 });
    await expect(page.getByTestId("otp-code")).toBeVisible();
    // No booking list is shown before verification.
    await expect(page.locator(".lookup-result")).toHaveCount(0);
  });

  test("a wrong code is rejected and no bookings are revealed", async ({ page }) => {
    await page.goto("/my-bookings");
    await page.getByPlaceholder(/10-digit mobile or email/i).fill("9" + String(Date.now()).slice(-9));
    await page.getByRole("button", { name: /send me a code/i }).click();
    await expect(page.getByTestId("otp-step")).toBeVisible({ timeout: 8_000 });

    await page.getByTestId("otp-code").fill("000000");
    await page.getByTestId("otp-verify").click();
    await expect(page.getByTestId("lookup-error")).toContainText(/incorrect or has expired/i);
    await expect(page.locator(".lookup-result")).toHaveCount(0);
  });

  test("ref + contact lookup still works without a code", async ({ page }) => {
    await page.goto("/my-bookings");
    await page.getByPlaceholder(/e\.g\. A1B2C3D4/i).fill("NOSUCHREF");
    await page.getByPlaceholder(/10-digit mobile or email/i).fill("9123456780");
    await page.getByRole("button", { name: /find my booking/i }).click();
    await expect(page.getByTestId("lookup-error")).toBeVisible();
    await expect(page.getByTestId("otp-step")).toHaveCount(0);
  });
});
