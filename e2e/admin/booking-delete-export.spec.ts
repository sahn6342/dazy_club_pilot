import { test, expect, APIRequestContext } from "@playwright/test";

const API = "http://localhost:8000/api/v1";
const CREDS = { username: "admin", password: "admin" };

async function adminToken(request: APIRequestContext): Promise<string> {
  const r = await request.post(`${API}/admin/login`, { data: CREDS });
  return (await r.json()).access_token;
}

async function uiLogin(page: import("@playwright/test").Page) {
  await page.goto("/");
  await page.locator("input[name=username]").fill(CREDS.username);
  await page.locator("input[name=password]").fill(CREDS.password);
  await page.getByRole("button", { name: /sign in/i }).click();
  await expect(page.locator(".admin-layout")).toBeVisible({ timeout: 10_000 });
}

/** An unpaid booking on the first free slot in the next 6 days. Returns its ref, admin id and phone. */
async function createBooking(request: APIRequestContext): Promise<{ ref: string; id: string; phone: string }> {
  const phone = "9" + String(Date.now()).slice(-9);
  for (let ahead = 1; ahead <= 6; ahead++) {
    const d = new Date();
    d.setDate(d.getDate() + ahead);
    const dateStr = new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 10);
    for (const sport of ["cricket", "badminton", "pickleball"]) {
      const slots: any[] = await (await request.get(`${API}/slots?sport=${sport}&date=${dateStr}`)).json();
      const slot = slots.find((s) => s.available);
      if (!slot) continue;
      const res = await request.post(`${API}/bookings`, {
        data: { name: "E2E Delete Tester", contact: phone, slotIds: [slot.id], sportSlug: slot.sportSlug,
                date: slot.date, startTime: slot.startTime, players: 1 },
      });
      if (!res.ok()) continue;
      const b = await res.json();
      const tok = await adminToken(request);
      const list = (await (await request.get(`${API}/admin/bookings?limit=100&deleted=all`, { headers: { Authorization: `Bearer ${tok}` } })).json()).items;
      return { ref: b.bookingRef, id: list.find((x: any) => x.bookingRef === b.bookingRef).id, phone };
    }
  }
  throw new Error("No free slot found in the next 6 days");
}

async function purge(request: APIRequestContext, id: string) {
  const tok = await adminToken(request);
  await request.delete(`${API}/admin/bookings/${id}/purge`, { headers: { Authorization: `Bearer ${tok}` } });
}

test.describe("Admin — delete, restore and export bookings", () => {
  test("a cancelled booking can be deleted, found under Deleted only, and restored", async ({ page, request }) => {
    const b = await createBooking(request);
    try {
      await uiLogin(page);
      await page.goto("/bookings");
      const row = page.locator("tr", { hasText: b.phone }).first();
      await expect(row).toBeVisible({ timeout: 8_000 });

      await page.getByTestId(`cancel-${b.ref}`).click();               // unpaid: cancels straight away
      await expect(row).toContainText(/cancelled/i, { timeout: 8_000 });

      await page.getByTestId(`delete-${b.ref}`).click();
      await page.locator(".confirm-dialog").getByRole("button", { name: /^delete$/i }).click();   // confirm dialog
      await expect(page.locator("tr", { hasText: b.phone })).toHaveCount(0, { timeout: 8_000 });

      await page.getByTestId("deleted-filter").selectOption("only");
      const gone = page.locator("tr", { hasText: b.phone }).first();
      await expect(gone).toBeVisible({ timeout: 8_000 });
      await expect(page.getByTestId(`deleted-${b.ref}`)).toHaveText("Deleted");
      await expect(gone.getByRole("button", { name: /^cancel$/i })).toHaveCount(0);  // no actions except Restore

      await page.getByTestId(`restore-${b.ref}`).click();
      await expect(page.locator("tr", { hasText: b.phone })).toHaveCount(0, { timeout: 8_000 });  // leaves "Deleted only"
      await page.getByTestId("deleted-filter").selectOption("no");
      const back = page.locator("tr", { hasText: b.phone }).first();
      await expect(back).toBeVisible({ timeout: 8_000 });
      await expect(back).toContainText(/cancelled/i);                   // restored as cancelled, slot not re-booked
    } finally {
      await purge(request, b.id);
    }
  });

  test("a deleted booking is gone from the customer's lookup", async ({ page, request }) => {
    const b = await createBooking(request);
    try {
      await uiLogin(page);
      await page.goto("/bookings");
      await expect(page.locator("tr", { hasText: b.phone }).first()).toBeVisible({ timeout: 8_000 });
      await page.getByTestId(`cancel-${b.ref}`).click();
      await expect(page.getByTestId(`delete-${b.ref}`)).toBeVisible({ timeout: 8_000 });
      await page.getByTestId(`delete-${b.ref}`).click();
      await page.locator(".confirm-dialog").getByRole("button", { name: /^delete$/i }).click();
      await expect(page.locator("tr", { hasText: b.phone })).toHaveCount(0, { timeout: 8_000 });
      const lookup = await request.get(`${API}/bookings/lookup?ref=${b.ref}&contact=${b.phone}`);
      expect(lookup.status()).toBe(404);
    } finally {
      await purge(request, b.id);
    }
  });

  test("Export CSV downloads every matching booking as a file", async ({ page, request }) => {
    const b = await createBooking(request);
    try {
      await uiLogin(page);
      await page.goto("/bookings");
      await expect(page.locator("tr", { hasText: b.phone }).first()).toBeVisible({ timeout: 8_000 });

      const download = page.waitForEvent("download");
      await page.getByTestId("export-csv").click();
      const file = await download;
      expect(file.suggestedFilename()).toMatch(/^bookings-\d{4}-\d{2}-\d{2}\.csv$/);
      const path = await file.path();
      const text = (await import("node:fs")).readFileSync(path!, "utf8");
      expect(text.replace(/^﻿/, "").split("\n")[0]).toContain('"Ref","Name","Contact"');
      expect(text).toContain(`"${b.ref}"`);
      expect(text).toContain(`"${b.phone}"`);
    } finally {
      await purge(request, b.id);
    }
  });
});
