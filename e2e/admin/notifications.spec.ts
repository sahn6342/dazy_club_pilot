import { test, expect, APIRequestContext } from "@playwright/test";

// Needs an API whose email provider cannot deliver, e.g. started with DAZY_NOTIFY_PROVIDER=email and no SMTP_*
// settings: every email then fails permanently ("SMTP ... not configured"), which is exactly the state this page
// exists for. With the default console provider there is nothing failed to look at, so the spec skips itself.

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

/** A priced booking whose contact is an email address, so exactly one notification (email) is attempted. */
async function bookWithEmail(request: APIRequestContext): Promise<{ email: string; ref: string }> {
  const email = `notif.${Date.now()}@example.com`;
  for (let ahead = 1; ahead <= 6; ahead++) {
    const d = new Date();
    d.setDate(d.getDate() + ahead);
    const dateStr = new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 10);
    const slots: any[] = await (await request.get(`${API}/slots?sport=cricket&date=${dateStr}`)).json();
    const slot = slots.find((s) => s.available && s.finalPrice);
    if (!slot) continue;
    const res = await request.post(`${API}/bookings`, {
      data: { name: "E2E Notify", contact: email, email, slotIds: [slot.id], sportSlug: "cricket", date: slot.date, startTime: slot.startTime, players: 1 },
    });
    if (res.ok()) return { email, ref: (await res.json()).bookingRef };
  }
  throw new Error("No free priced cricket slot in the next 6 days");
}

async function purge(request: APIRequestContext, ref: string) {
  const tok = await adminToken(request);
  const list = (await (await request.get(`${API}/admin/bookings?limit=100&deleted=all`, { headers: { Authorization: `Bearer ${tok}` } })).json()).items;
  const row = list.find((b: any) => b.bookingRef === ref);
  if (row) await request.delete(`${API}/admin/bookings/${row.id}/purge`, { headers: { Authorization: `Bearer ${tok}` } });
}

test.describe("Admin — notification log", () => {
  test("a failed email shows up, can be resent, and the result is reported", async ({ page, request }) => {
    const b = await bookWithEmail(request);
    try {
      const tok = await adminToken(request);
      const probe = (await (await request.get(`${API}/admin/notifications?channel=email&status=failed&limit=200`, { headers: { Authorization: `Bearer ${tok}` } })).json())
        .filter((n: any) => n.recipient === b.email);
      test.skip(probe.length === 0, "the API's email provider is delivering (or is the console stub), so there is no failed message to show");

      await uiLogin(page);
      await page.goto("/notifications");
      await page.getByTestId("tab-failed").click();
      const row = page.locator("tr", { hasText: b.email }).first();
      await expect(row).toBeVisible({ timeout: 8_000 });
      await expect(row.getByTestId("notification-status")).toHaveText("failed");
      await expect(row).toContainText(/SMTP/i);
      await expect(row).toContainText("Payment reminder");

      await row.getByRole("button", { name: /resend/i }).click();
      // The provider still cannot deliver, so the admin is told so, and the row records the second attempt.
      await expect(page.getByText(/not sent: .*smtp/i)).toBeVisible({ timeout: 8_000 });
      await expect(row).toContainText("attempt 2");
      await expect(row.getByTestId("notification-status")).toHaveText("failed");
    } finally {
      await purge(request, b.ref);
    }
  });

  test("filters narrow the list and the range label follows", async ({ page, request }) => {
    const b = await bookWithEmail(request);
    try {
      await uiLogin(page);
      await page.goto("/notifications");
      await expect(page.getByTestId("notifications-table")).toBeVisible({ timeout: 8_000 });
      await page.getByTestId("channel-filter").selectOption("sms");
      await expect(page.locator("tr", { hasText: b.email })).toHaveCount(0);  // this booking only used email
      await page.getByTestId("channel-filter").selectOption("email");
      await expect(page.locator("tr", { hasText: b.email }).first()).toBeVisible();
      await expect(page.getByTestId("notifications-range")).toContainText(/1–\d+ of \d+/);
    } finally {
      await purge(request, b.ref);
    }
  });
});
