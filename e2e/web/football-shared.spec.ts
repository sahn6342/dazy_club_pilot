import { test, expect, APIRequestContext, Page } from "@playwright/test";

// Football and cricket share one turf: a slot booked under one sport shows as Booked under the other.

const API = "http://localhost:8000/api/v1";

function localDate(offset: number): string {
  const d = new Date();
  d.setDate(d.getDate() + offset);
  return new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 10);
}

async function adminToken(request: APIRequestContext): Promise<string> {
  const r = await request.post(`${API}/admin/login`, { data: { username: "admin", password: "admin" } });
  return (await r.json()).access_token;
}

async function slots(request: APIRequestContext, sport: string, date: string): Promise<any[]> {
  return (await request.get(`${API}/slots?sport=${sport}&date=${date}`)).json();
}

async function purge(request: APIRequestContext, ref: string) {
  const tok = await adminToken(request);
  const items = (await (await request.get(`${API}/admin/bookings?limit=100&deleted=all`, { headers: { Authorization: `Bearer ${tok}` } })).json()).items;
  const row = items.find((b: any) => b.bookingRef === ref);
  if (row) await request.delete(`${API}/admin/bookings/${row.id}/purge`, { headers: { Authorization: `Bearer ${tok}` } });
}

async function openSportOnDate(page: Page, sport: string, pillIdx: number, date: string) {
  await page.goto("/book");
  if (sport === "cricket") {
    await page.waitForLoadState("networkidle"); // cricket is the default tab: no fetch to wait for on click
  } else {
    const tabLoaded = page.waitForResponse((r) => r.url().includes("/api/v1/slots") && r.url().includes(`sport=${sport}`));
    await page.getByRole("tab", { name: new RegExp(sport, "i") }).click();
    await tabLoaded;
  }
  const loaded = page.waitForResponse((r) => r.url().includes("/api/v1/slots") && r.url().includes(date) && r.url().includes(`sport=${sport}`));
  await page.locator(".date-pill").nth(pillIdx).click();
  await loaded;
  await expect(page.locator(".slot-chip").first()).toBeVisible({ timeout: 8_000 });
}

test.describe("Football shares the cricket turf", () => {
  test("the same slots are offered for both sports", async ({ request }) => {
    const date = localDate(2);
    const [cricket, football] = [await slots(request, "cricket", date), await slots(request, "football", date)];
    expect(football.length).toBeGreaterThan(0);
    expect(football.map((s) => s.id)).toEqual(cricket.map((s) => s.id));
    expect(new Set(football.map((s) => s.sportSlug))).toEqual(new Set(["football"]));
  });

  test("a football booking shows as Booked on the cricket tab, and cricket cannot take it", async ({ page, request }) => {
    const date = localDate(2);
    const free = (await slots(request, "football", date)).find((s) => s.available && s.finalPrice);
    test.skip(!free, "no free priced slot two days ahead");
    const contact = `99${String(Date.now()).slice(-8)}`;
    const res = await request.post(`${API}/bookings`, {
      data: { name: "E2E Football", contact, slotIds: [free.id], sportSlug: "football", date, startTime: free.startTime, players: 12 },
    });
    expect(res.status()).toBe(201);
    const ref = (await res.json()).bookingRef;
    try {
      await openSportOnDate(page, "cricket", 2, date);
      const chip = page.locator(".slot-chip", { hasText: free.startTime }).first();
      await expect(chip).toBeDisabled();
      await expect(chip).toContainText("Booked");

      // The API refuses a cricket booking of the same slot.
      const clash = await request.post(`${API}/bookings`, {
        data: { name: "E2E Cricket", contact: "9111111111", slotIds: [free.id], sportSlug: "cricket", date, startTime: free.startTime, players: 1 },
      });
      expect(clash.status()).toBe(409);
    } finally {
      await purge(request, ref);
    }
  });

  test("football allows up to 25 players on the form", async ({ page, request }) => {
    const date = localDate(3);
    test.skip(!(await slots(request, "football", date)).some((s) => s.available), "no free slot three days ahead");
    await openSportOnDate(page, "football", 3, date);
    await page.locator(".slot-chip:not([disabled])").first().click();
    const players = page.getByLabel(/number of players/i);
    await players.fill("25");
    await expect(page.getByText(/maximum 25 players/i)).toHaveCount(0);
    await players.fill("26");
    await players.blur();
    await expect(page.getByText(/maximum 25 players/i)).toBeVisible();
  });
});
