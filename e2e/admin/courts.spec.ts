import { test, expect, Page, APIRequestContext } from "@playwright/test";

const API = "http://localhost:8000/api/v1";

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

async function deactivateCourt(request: APIRequestContext, courtId: string): Promise<void> {
  const tok = await token(request);
  await request.delete(`${API}/admin/courts/${courtId}`, { headers: { Authorization: `Bearer ${tok}` } });
}

async function deleteCourt(request: APIRequestContext, courtId: string): Promise<void> {
  // Hard delete not exposed — deactivate is the closest cleanup.
  await deactivateCourt(request, courtId);
}

/** Navigate to /courts and wait for the page to load. */
async function gotoCourts(page: Page) {
  await page.goto("/courts");
  await expect(page.getByRole("heading", { name: /courts/i }).first()).toBeVisible({ timeout: 8_000 });
}

test.describe("Admin — courts management", () => {
  test("courts page loads and shows seeded courts grouped by sport", async ({ page }) => {
    await login(page);
    await gotoCourts(page);

    // Three sport headings visible.
    await expect(page.getByText(/cricket/i).first()).toBeVisible();
    await expect(page.getByText(/badminton/i).first()).toBeVisible();
    await expect(page.getByText(/pickleball/i).first()).toBeVisible();

    // Seeded courts show.
    await expect(page.getByText("Court 1").first()).toBeVisible();
  });

  test("courts page reachable from sidebar", async ({ page }) => {
    await login(page);
    await page.goto("/");
    await page.locator(".sidebar a", { hasText: /courts/i }).click();
    await expect(page.url()).toContain("/courts");
    await expect(page.getByText("Court 1").first()).toBeVisible({ timeout: 8_000 });
  });

  test("add new court appears in table", async ({ page, request }) => {
    await login(page);
    await gotoCourts(page);

    const courtName = "E2E Court " + String(Date.now()).slice(-5);

    // Fill create form — sport stays "cricket" (default).
    await page.locator("input[placeholder='e.g. Court 2']").fill(courtName);

    const post = page.waitForResponse(
      (r) => r.url().endsWith("/admin/courts") && r.request().method() === "POST"
    );
    await page.getByRole("button", { name: /add court/i }).click();
    const res = await post;
    expect(res.status()).toBe(201);

    const createdId = (await res.json()).id;

    // New court visible under Cricket section.
    await expect(page.locator("td", { hasText: courtName }).first()).toBeVisible({ timeout: 5_000 });

    // Cleanup.
    await deleteCourt(request, createdId);
  });

  test("edit court name persists after reload", async ({ page, request }) => {
    // Create a throwaway court.
    const tok = await token(request);
    const createRes = await request.post(`${API}/admin/courts`, {
      headers: { Authorization: `Bearer ${tok}` },
      data: { venue_id: "venue-dazy", sport: "badminton", name: "Edit Test Court", capacity: 1 },
    });
    const { id: courtId } = await createRes.json();

    try {
      await login(page);
      await gotoCourts(page);

      const row = page.locator("tr", { hasText: "Edit Test Court" });
      await expect(row).toBeVisible({ timeout: 6_000 });

      // Click Edit.
      await row.getByRole("button", { name: /edit/i }).click();

      // Inline name input appears — update it.
      const nameInput = row.locator("input").first();
      await nameInput.fill("Renamed Court");

      const patch = page.waitForResponse(
        (r) => r.url().includes("/admin/courts/") && r.request().method() === "PATCH"
      );
      await row.getByRole("button", { name: /save/i }).click();
      expect((await patch).status()).toBe(200);

      // After reload the new name persists.
      await page.reload();
      await expect(page.locator("td", { hasText: "Renamed Court" }).first()).toBeVisible({ timeout: 6_000 });
    } finally {
      await deleteCourt(request, courtId);
    }
  });

  test("deactivate court shows inactive status", async ({ page, request }) => {
    const tok = await token(request);
    const createRes = await request.post(`${API}/admin/courts`, {
      headers: { Authorization: `Bearer ${tok}` },
      data: { venue_id: "venue-dazy", sport: "pickleball", name: "Deactivate Test", capacity: 1 },
    });
    const { id: courtId } = await createRes.json();

    try {
      await login(page);
      await gotoCourts(page);

      const row = page.locator("tr", { hasText: "Deactivate Test" });
      await expect(row).toBeVisible({ timeout: 6_000 });

      const del = page.waitForResponse(
        (r) => r.url().includes(`/admin/courts/${courtId}`) && r.request().method() === "DELETE"
      );
      await row.getByRole("button", { name: /deactivate/i }).click();
      expect((await del).status()).toBe(204);

      // Row still visible but now shows Inactive status.
      await expect(row.getByText(/inactive/i)).toBeVisible({ timeout: 5_000 });
    } finally {
      // Already deactivated — nothing extra to clean up.
    }
  });

  test("reactivate court toggles back to active", async ({ page, request }) => {
    // Ensure court-cricket is deactivated first via API, then reactivate via UI.
    const tok = await token(request);
    await request.delete(`${API}/admin/courts/court-cricket`, { headers: { Authorization: `Bearer ${tok}` } });

    try {
      await login(page);
      await gotoCourts(page);

      const row = page.locator("tr", { hasText: "Court 1" }).filter({ hasText: /inactive/i });
      await expect(row).toBeVisible({ timeout: 6_000 });

      const patch = page.waitForResponse(
        (r) => r.url().includes("/admin/courts/court-cricket") && r.request().method() === "PATCH"
      );
      await row.getByRole("button", { name: /reactivate/i }).click();
      expect((await patch).status()).toBe(200);

      await expect(row.getByText(/active/i)).toBeVisible({ timeout: 5_000 });
    } finally {
      // Restore — reactivate if somehow still inactive.
      const tok2 = await token(request);
      await request.patch(`${API}/admin/courts/court-cricket`, {
        headers: { Authorization: `Bearer ${tok2}` },
        data: { active: true },
      });
    }
  });

  test("empty court name shows validation error", async ({ page }) => {
    await login(page);
    await gotoCourts(page);

    // Submit with blank name.
    await page.getByRole("button", { name: /add court/i }).click();
    await expect(page.getByText(/name is required/i)).toBeVisible({ timeout: 3_000 });
  });
});
