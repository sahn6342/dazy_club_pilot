import { test, expect, Page } from "@playwright/test";

// Counter bills: add rows (item, rate incl. GST, GST %), live totals, save with a number, print on A4, find and reprint old
// bills, void. Bills are never deleted (that is the point), so these specs leave their bills behind and look
// them up by a unique customer name.

const CREDS = { username: "admin", password: "admin" };

async function uiLogin(page: Page) {
  await page.goto("/");
  await page.locator("input[name=username]").fill(CREDS.username);
  await page.locator("input[name=password]").fill(CREDS.password);
  await page.getByRole("button", { name: /sign in/i }).click();
  await expect(page.locator(".admin-layout")).toBeVisible({ timeout: 10_000 });
}

/** Stop the print dialog from blocking the run, and count how often it was asked for. */
async function stubPrint(page: Page) {
  await page.addInitScript(() => {
    (window as any).__prints = 0;
    window.print = () => { (window as any).__prints++; };
  });
}

async function fillRow(page: Page, i: number, desc: string, qty: string, rate: string, gst: string) {
  await page.getByTestId(`line-desc-${i}`).fill(desc);
  await page.getByTestId(`line-qty-${i}`).fill(qty);
  await page.getByTestId(`line-rate-${i}`).fill(rate);
  await page.getByTestId(`line-gst-${i}`).fill(gst);
}

test.describe("Admin — bills", () => {
  test("rows add up live, the bill is saved with a number and printed on A4", async ({ page }) => {
    await stubPrint(page);
    await uiLogin(page);
    await page.goto("/bills");
    const name = "E2E Bill " + Date.now();

    await fillRow(page, 0, "Court hire", "2", "100.50", "18");
    await page.getByTestId("add-row").click();
    await fillRow(page, 1, "Tea", "1", "50", "5");
    await page.getByTestId("add-row").click();
    await fillRow(page, 2, "Water", "3", "33.33", "12");

    // The rate includes GST: a row is qty x rate, and the tax is taken out of it.
    await expect(page.getByTestId("line-total-0")).toHaveText("₹201.00");
    await expect(page.getByTestId("sum-taxable")).toHaveText("₹307.25");
    await expect(page.getByTestId("sum-cgst")).toHaveText("₹21.87");
    await expect(page.getByTestId("sum-sgst")).toHaveText("₹21.87");
    await expect(page.getByTestId("sum-total")).toHaveText("₹350.99"); // not rounded to the rupee

    await page.getByTestId("line-remove-1").click(); // drop Tea
    await expect(page.getByTestId("line-desc-1")).toHaveValue("Water");
    await page.getByTestId("add-row").click();
    await page.getByTestId("line-remove-2").click();

    await page.getByTestId("bill-name").fill(name);
    await page.getByTestId("bill-phone").fill("9" + String(Date.now()).slice(-9));
    await page.getByTestId("save-print").click();

    await expect(page).toHaveURL(/\/bills\/[^/]+\/print\?auto=1$/);
    const sheet = page.getByTestId("bill-sheet");
    await expect(sheet).toBeVisible();
    await expect(page.getByTestId("print-billno")).toHaveText(/^\d{4}-\d{2}\/\d{4}$/);
    await expect(sheet).toContainText(name);
    await expect(sheet).toContainText("Court hire");
    await expect(sheet).toContainText("Water");
    await expect(page.getByTestId("print-total")).toHaveText("₹300.99"); // 201.00 + 99.99, exactly
    await expect.poll(() => page.evaluate(() => (window as any).__prints), { timeout: 5_000 }).toBeGreaterThan(0);

    // The sheet is A4 wide and, when printed, nothing else is on the page.
    const box = await sheet.boundingBox();
    expect(Math.round((box!.width / 96) * 25.4)).toBe(210);
    await page.emulateMedia({ media: "print" });
    await expect(page.locator(".bill-toolbar")).toBeHidden();
    const pdf = await page.pdf({ preferCSSPageSize: true });
    expect(pdf.subarray(0, 4).toString()).toBe("%PDF");
    expect((pdf.toString("latin1").match(/\/Type\s*\/Page[^s]/g) ?? []).length).toBe(1);
    expect(pdf.toString("latin1")).toMatch(/\/MediaBox\s*\[\s*0\s+0\s+59[45](\.\d+)?\s+84[12](\.\d+)?\s*\]/); // A4 in points
  });

  test("an old bill can be found, reprinted and voided; its number is kept", async ({ page }) => {
    await stubPrint(page);
    await uiLogin(page);
    await page.goto("/bills");
    const name = "E2E Reprint " + Date.now();
    await fillRow(page, 0, "Coaching", "1", "500", "18");
    await page.getByTestId("bill-name").fill(name);
    await page.getByTestId("save-print").click();
    await expect(page.getByTestId("print-billno")).toBeVisible();
    const billNo = (await page.getByTestId("print-billno").textContent())!;

    await page.goto("/bills");
    await page.getByTestId("tab-past").click();
    await page.getByTestId("bill-search").fill(name);
    const row = page.getByTestId(`bill-row-${billNo}`);
    await expect(row).toBeVisible({ timeout: 8_000 });
    await expect(row).toContainText("₹500.00");

    await page.getByTestId(`reprint-${billNo}`).click();
    await expect(page.getByTestId("print-billno")).toHaveText(billNo);
    await expect(page.getByTestId("print-total")).toHaveText("₹500.00");
    await expect.poll(() => page.evaluate(() => (window as any).__prints)).toBeGreaterThan(0);
    await expect(page.getByTestId("void-mark")).toHaveCount(0);

    await page.getByRole("link", { name: /bills/i }).first().click();
    await page.getByTestId("tab-past").click();
    await page.getByTestId("bill-search").fill(billNo);
    await page.getByTestId(`void-${billNo}`).click();
    await expect(page.getByTestId("void-confirm")).toBeDisabled(); // a reason is required
    await page.getByTestId("void-reason").fill("Entered wrong item");
    await page.getByTestId("void-confirm").click();
    await expect(page.getByTestId(`bill-row-${billNo}`)).toContainText("Void");
    await expect(page.getByTestId(`void-${billNo}`)).toHaveCount(0);

    await page.getByTestId(`reprint-${billNo}`).click();
    await expect(page.getByTestId("void-mark")).toBeVisible();
    await expect(page.getByTestId("print-billno")).toHaveText(billNo);
  });

  test("letterhead can be left off and top space added for pre-printed paper", async ({ page }) => {
    await stubPrint(page);
    await uiLogin(page);
    await page.goto("/bills");
    await fillRow(page, 0, "Hire", "1", "100", "0");
    await page.getByTestId("save-print").click();
    const sheet = page.getByTestId("bill-sheet");
    await expect(sheet.locator(".bill-head")).toBeVisible();
    await page.getByTestId("print-header").uncheck();
    await expect(sheet.locator(".bill-head")).toHaveCount(0);
    await page.getByTestId("print-top").fill("40");
    const padTop = await sheet.evaluate((el) => parseFloat(getComputedStyle(el).paddingTop));
    expect(Math.round((padTop / 96) * 25.4)).toBe(40);
    await page.getByTestId("print-header").check();
    await page.getByTestId("print-top").fill("0");
  });

  test("the tax percentage is a typed box: decimals work, out of range is refused", async ({ page }) => {
    await uiLogin(page);
    await page.goto("/bills");
    await expect(page.getByTestId("line-gst-0")).toHaveValue("18"); // default
    await fillRow(page, 0, "Hire", "1", "1000", "2.5");
    await expect(page.getByTestId("sum-cgst")).toHaveText("₹12.19");
    await expect(page.getByTestId("sum-taxable")).toHaveText("₹975.62");
    await expect(page.getByTestId("sum-total")).toHaveText("₹1,000.00");
    await page.getByTestId("line-gst-0").fill("40");
    await page.getByTestId("save-print").click();
    await expect(page.getByText("0–28")).toBeVisible();
    await expect(page).toHaveURL(/\/bills$/);
  });

  test("the printed bill says the rate includes GST", async ({ page, request }) => {
    await stubPrint(page);
    const tok = (await (await request.post("http://localhost:8000/api/v1/admin/login", { data: CREDS })).json()).access_token;
    const bill = await (await request.post("http://localhost:8000/api/v1/admin/bills", {
      headers: { Authorization: `Bearer ${tok}` },
      data: { customerName: "E2E New " + Date.now(), lines: [{ description: "Hire", qty: 1, rate: 118, gstRatePercent: 18 }] },
    })).json();
    expect(bill.pricesIncludeTax).toBe(true);
    await uiLogin(page);
    await page.goto(`/bills/${bill.id}/print`);
    await expect(page.getByTestId("bill-sheet")).toContainText("Rate (incl. GST)");
    await expect(page.getByTestId("print-total")).toHaveText("₹118.00");
  });

  test("an incomplete bill is not saved", async ({ page }) => {
    await uiLogin(page);
    await page.goto("/bills");
    await page.getByTestId("save-print").click();
    await expect(page.getByText("Item needed")).toBeVisible();
    await expect(page.getByText("Rate needed")).toBeVisible();
    await expect(page).toHaveURL(/\/bills$/);
  });
});
