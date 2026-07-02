import { test, expect, APIRequestContext, Page } from "@playwright/test";

const API = "http://localhost:8000/api/v1";
const COURT = "court-cricket";
const WD = 2; // Wednesday — kept away from the day-1 slots the web booking specs use

async function login(page: Page) {
  await page.goto("/");
  await page.locator("input[name=username]").fill("admin");
  await page.locator("input[name=password]").fill("admin");
  await page.getByRole("button", { name: /sign in/i }).click();
  await expect(page.locator(".admin-layout")).toBeVisible({ timeout: 10_000 });
}

async function token(request: APIRequestContext): Promise<string> {
  const r = await request.post(`${API}/admin/login`, { data: { username: "admin", password: "admin" } });
  return (await r.json()).access_token;
}

type Rule = { id: string; weekday: number; open_time: string; close_time: string; slot_minutes: number; price: number | null; discount_percent: number | null };

async function rulesFor(request: APIRequestContext, tok: string, weekday: number): Promise<Rule[]> {
  const r = await request.get(`${API}/admin/schedule/rules?court_id=${COURT}`, { headers: { Authorization: `Bearer ${tok}` } });
  return (await r.json()).filter((x: Rule) => x.weekday === weekday);
}

async function allRules(request: APIRequestContext, tok: string): Promise<Rule[]> {
  const r = await request.get(`${API}/admin/schedule/rules?court_id=${COURT}`, { headers: { Authorization: `Bearer ${tok}` } });
  return await r.json();
}

/** Snapshot ALL weekdays' rules, run fn, then restore exactly. Used by the weekly-editor test. */
async function withFullRestore(request: APIRequestContext, fn: () => Promise<void>) {
  const tok = await token(request);
  const snapshot = await allRules(request, tok);
  try {
    await fn();
  } finally {
    const tok2 = await token(request);
    const current = await allRules(request, tok2);
    for (const r of current) {
      await request.delete(`${API}/admin/schedule/rules/${r.id}`, { headers: { Authorization: `Bearer ${tok2}` } });
    }
    for (const r of snapshot) {
      await request.post(`${API}/admin/schedule/rules`, {
        headers: { Authorization: `Bearer ${tok2}` },
        data: { court_id: COURT, weekday: r.weekday, open_time: r.open_time, close_time: r.close_time, slot_minutes: r.slot_minutes, price: r.price, discount_percent: r.discount_percent },
      });
    }
  }
}

/** Snapshot a weekday's rules, run fn, then restore exactly (delete current, recreate snapshot). */
async function withRestore(request: APIRequestContext, fn: () => Promise<void>) {
  const tok = await token(request);
  const snapshot = await rulesFor(request, tok, WD);
  try {
    await fn();
  } finally {
    const tok2 = await token(request);
    const current = await rulesFor(request, tok2, WD);
    for (const r of current) {
      await request.delete(`${API}/admin/schedule/rules/${r.id}`, { headers: { Authorization: `Bearer ${tok2}` } });
    }
    for (const r of snapshot) {
      await request.post(`${API}/admin/schedule/rules`, {
        headers: { Authorization: `Bearer ${tok2}` },
        data: { court_id: COURT, weekday: WD, open_time: r.open_time, close_time: r.close_time, slot_minutes: r.slot_minutes, price: r.price, discount_percent: r.discount_percent },
      });
    }
  }
}

const section = (page: Page) => page.locator(`.weekday-section[data-weekday="${WD}"]`);

/** Open the collapsible "Customize individual days" panel and wait for it to render. */
async function expandAdvanced(page: Page) {
  await page.locator('[data-testid="advanced-toggle"]').click();
  await expect(page.locator('[data-testid="advanced-panel"]')).toBeVisible();
}

/** Wait until courts + rules have loaded (weekly editor populated → courtId is set). */
async function waitLoaded(page: Page) {
  await expect(page.locator(".weekly-block-row").first()).toBeVisible({ timeout: 10_000 });
}

test.describe("Admin — schedule management", () => {
  test("weekly editor renders and per-day sections are hidden until expanded", async ({ page }) => {
    await login(page);
    await page.goto("/schedule");
    await expect(page.locator('[data-testid="weekly-editor"]')).toBeVisible();
    await expect(page.locator('[data-testid="court-select"]')).toBeVisible();
    // Per-day sections collapsed by default.
    await expect(page.locator(".weekday-section")).toHaveCount(0);
    await expandAdvanced(page);
    await expect(page.locator(".weekday-section")).toHaveCount(7);
    await expect(section(page).locator(".block-row")).toHaveCount(3); // 06-12, 14-17, 18-21
  });

  test("weekly editor saves one schedule to all 7 days + shows success toast", async ({ page, request }) => {
    await withFullRestore(request, async () => {
      await login(page);
      await page.goto("/schedule");
      await waitLoaded(page);

      // Collapse to a single continuous block, set a distinctive price, save.
      await page.locator('[data-testid="weekly-continuous"]').click();
      const row = page.locator(".weekly-block-row").first();
      await expect(row).toBeVisible();
      await row.locator("input").nth(3).fill("999"); // price column

      await page.locator('[data-testid="weekly-save"]').click();
      // Success toast appears.
      await expect(page.locator('[data-testid="toast"]')).toContainText(/saved/i, { timeout: 8_000 });

      // Every weekday now has exactly one 06:00–21:00 @ 999 block.
      const tok = await token(request);
      const rules = await allRules(request, tok);
      for (let wd = 0; wd < 7; wd++) {
        const dayRules = rules.filter((r) => r.weekday === wd);
        expect(dayRules.length).toBe(1);
        expect(dayRules[0].open_time).toBe("06:00");
        expect(dayRules[0].close_time).toBe("21:00");
        expect(dayRules[0].price).toBe(999);
      }
    });
  });

  test("edit block price and discount persists", async ({ page, request }) => {
    await withRestore(request, async () => {
      await login(page);
      await page.goto("/schedule");
      await waitLoaded(page);
      await expandAdvanced(page);
      const row = section(page).locator(".block-row").first();
      await row.locator("input").nth(3).fill("800");        // price
      await row.locator("input").nth(4).fill("20");         // discount %
      const patch = page.waitForResponse((r) => r.url().includes("/admin/schedule/rules/") && r.request().method() === "PATCH");
      await row.locator('[data-testid="save-block"]').click();
      expect((await patch).status()).toBe(200);

      await page.reload();
      await expandAdvanced(page);
      const row2 = section(page).locator(".block-row").first();
      await expect(row2.locator("input").nth(3)).toHaveValue("800");
      await expect(row2.locator("input").nth(4)).toHaveValue("20");
    });
  });

  test("add block increases row count", async ({ page, request }) => {
    await withRestore(request, async () => {
      await login(page);
      await page.goto("/schedule");
      await waitLoaded(page);
      await expandAdvanced(page);
      await expect(section(page).locator(".block-row").first()).toBeVisible();
      const before = await section(page).locator(".block-row").count();
      const add = section(page).locator(`[data-testid="add-block-${WD}"]`);
      const addRow = add.locator("xpath=ancestor::tr");
      await addRow.locator("input").nth(0).fill("12:00");
      await addRow.locator("input").nth(1).fill("14:00");
      const post = page.waitForResponse((r) => r.url().endsWith("/admin/schedule/rules") && r.request().method() === "POST");
      await add.click();
      expect((await post).status()).toBe(201);
      await page.reload();
      await expandAdvanced(page);
      await expect(section(page).locator(".block-row")).toHaveCount(before + 1);
    });
  });

  test("close day removes all blocks", async ({ page, request }) => {
    await withRestore(request, async () => {
      await login(page);
      await page.goto("/schedule");
      await waitLoaded(page);
      await expandAdvanced(page);
      await expect(section(page).locator(".block-row").first()).toBeVisible();
      // gated by the in-app ConfirmDialog, not a native window.confirm
      await section(page).getByRole("button", { name: /close day/i }).click();
      await page.locator(".confirm-dialog").getByRole("button", { name: "Close Day" }).click();
      await expect(section(page).getByText(/closed — add hours/i)).toBeVisible({ timeout: 10_000 });
    });
  });

  test("make continuous collapses to one block", async ({ page, request }) => {
    await withRestore(request, async () => {
      await login(page);
      await page.goto("/schedule");
      await waitLoaded(page);
      await expandAdvanced(page);
      await expect(section(page).locator(".block-row").first()).toBeVisible();
      await section(page).getByRole("button", { name: /make continuous/i }).click();
      await expect(section(page).locator(".block-row")).toHaveCount(1, { timeout: 10_000 });
      await expect(section(page).locator(".block-row").first().locator("input").nth(0)).toHaveValue("06:00");
      await expect(section(page).locator(".block-row").first().locator("input").nth(1)).toHaveValue("21:00");
    });
  });

  test("add and delete a date exception", async ({ page }) => {
    await login(page);
    await page.goto("/schedule");
    await waitLoaded(page);
    const d = new Date();
    d.setDate(d.getDate() + 20);
    const day = d.toISOString().slice(0, 10);
    await page.locator('input[type="date"]').first().fill(day);
    const post = page.waitForResponse((r) => r.url().endsWith("/admin/schedule/exceptions") && r.request().method() === "POST");
    await page.locator('[data-testid="exception-add"]').click();
    expect((await post).status()).toBe(201);
    const exRow = page.locator("tr", { hasText: day });
    await expect(exRow).toBeVisible();
    // cleanup
    // gated by the in-app ConfirmDialog, not a native window.confirm
    await exRow.getByRole("button", { name: /delete/i }).click();
    await page.locator(".confirm-dialog").getByRole("button", { name: "Delete" }).click();
    await expect(page.locator("tr", { hasText: day })).toHaveCount(0);
  });

  test("all-courts holiday closes every sport that day", async ({ page, request }) => {
    await login(page);
    await page.goto("/schedule");
    await waitLoaded(page);
    const d = new Date();
    d.setDate(d.getDate() + 22);
    const day = d.toISOString().slice(0, 10);

    // "Apply to all courts" defaults ON -> posts court_id: null.
    await expect(page.locator('[data-testid="exception-all-courts"]')).toBeChecked();
    await page.locator('input[type="date"]').first().fill(day);
    const post = page.waitForResponse((r) => r.url().endsWith("/admin/schedule/exceptions") && r.request().method() === "POST");
    await page.locator('[data-testid="exception-add"]').click();
    expect((await post).status()).toBe(201);

    // Row shows "All courts".
    const exRow = page.locator("tr", { hasText: day });
    await expect(exRow).toContainText(/all courts/i);

    // Every sport has zero slots that day (via the public API).
    for (const sport of ["cricket", "badminton", "pickleball"]) {
      const res = await request.get(`${API}/slots?sport=${sport}&date=${day}`);
      expect((await res.json()).length).toBe(0);
    }

    // cleanup
    // gated by the in-app ConfirmDialog, not a native window.confirm
    await exRow.getByRole("button", { name: /delete/i }).click();
    await page.locator(".confirm-dialog").getByRole("button", { name: "Delete" }).click();
    await expect(page.locator("tr", { hasText: day })).toHaveCount(0);
  });
});
