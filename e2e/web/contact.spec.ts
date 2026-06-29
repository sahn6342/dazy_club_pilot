import { test, expect } from "@playwright/test";

test.describe("Contact page — tabs", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/contact");
  });

  test("shows both tab options", async ({ page }) => {
    await expect(page.getByRole("tab", { name: /general enquiry/i })).toBeVisible();
    await expect(page.getByRole("tab", { name: /corporate/i })).toBeVisible();
  });

  test("corporate tab switch shows company field", async ({ page }) => {
    await page.getByRole("tab", { name: /corporate/i }).click();
    await expect(page.getByPlaceholder("Company name")).toBeVisible();
    await expect(page.getByPlaceholder("Your name")).toBeVisible();
  });
});

test.describe("Contact form — validation", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/contact");
  });

  test("empty submit shows name and contact errors", async ({ page }) => {
    await page.getByRole("button", { name: /send message/i }).click();
    await expect(page.getByText("Name is required.")).toBeVisible();
    await expect(page.getByText("Phone or email is required.")).toBeVisible();
  });

  test("valid email accepted as contact", async ({ page }) => {
    await page.getByPlaceholder("Your name").fill("Ananya S");
    await page.getByPlaceholder("10-digit mobile or email").fill("ananya@example.com");
    await page.getByPlaceholder("10-digit mobile or email").blur();
    await expect(page.getByText(/phone or email is required/i)).not.toBeVisible();
    await expect(page.getByText(/valid 10-digit/i)).not.toBeVisible();
  });
});

test.describe("Contact form — submission", () => {
  test("general enquiry submits successfully", async ({ page }) => {
    await page.goto("/contact");
    await page.getByPlaceholder("Your name").fill("Test User");
    await page.getByPlaceholder("10-digit mobile or email").fill("9123456789");
    await page.getByRole("button", { name: /send message/i }).click();
    await expect(page.getByText(/we'll be in touch/i)).toBeVisible({ timeout: 10_000 });
  });

  test("corporate enquiry submits successfully", async ({ page }) => {
    await page.goto("/contact");
    await page.getByRole("tab", { name: /corporate/i }).click();
    await page.getByPlaceholder("Your name").fill("Corporate Contact");
    await page.getByPlaceholder("Company name").fill("Acme Sports Ltd");
    await page.getByPlaceholder("10-digit mobile or email").fill("9988776655");
    // group size default is 1 — valid
    await page.getByRole("button", { name: /submit enquiry/i }).click();
    await expect(page.getByText(/we'll be in touch/i)).toBeVisible({ timeout: 10_000 });
  });
});
