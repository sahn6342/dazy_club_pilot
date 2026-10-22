import { test, expect, Page } from "@playwright/test";

// Home → "Choose your court energy": the sport cards are a swipeable strip that shows 3 / 2 / 1 cards by width,
// has prev/next arrows that wrap, and advances on its own (pausing on hover).

const SIZES = [
  { name: "desktop", width: 1280, height: 900, perView: 3 },
  { name: "tablet", width: 800, height: 900, perView: 2 },
  { name: "mobile", width: 375, height: 800, perView: 1 },
];

const track = (page: Page) => page.getByTestId("sport-strip-track");
const scrollLeft = (page: Page) => track(page).evaluate((el) => Math.round(el.scrollLeft));

/** Wait until the smooth scroll has stopped moving. */
async function settled(page: Page): Promise<number> {
  let prev = -1;
  for (let i = 0; i < 20; i++) {
    const now = await scrollLeft(page);
    if (now === prev) return now;
    prev = now;
    await page.waitForTimeout(150);
  }
  return prev;
}

/** Cards whose box lies fully inside the visible part of the strip. */
async function fullyVisibleCards(page: Page): Promise<number> {
  return track(page).evaluate((el) => {
    const box = el.getBoundingClientRect();
    return Array.from(el.children).filter((c) => {
      const r = (c as HTMLElement).getBoundingClientRect();
      return r.left >= box.left - 1 && r.right <= box.right + 1;
    }).length;
  });
}

for (const size of SIZES) {
  test.describe(`Home sport strip — ${size.name} (${size.width}px)`, () => {
    test.use({ viewport: { width: size.width, height: size.height } });

    test(`shows ${size.perView} card(s) per screen with all four sports in the strip`, async ({ page }) => {
      await page.goto("/");
      await expect(track(page).locator(".sport-card")).toHaveCount(4);
      await expect(track(page).locator(".sport-card").first()).toBeVisible();
      expect(await fullyVisibleCards(page)).toBe(size.perView);
    });

    test("next arrow scrolls forward and wraps back to the start", async ({ page }) => {
      await page.goto("/");
      await expect(page.getByTestId("strip-next")).toBeVisible();
      expect(await scrollLeft(page)).toBe(0);
      await page.getByTestId("strip-next").click();
      await expect.poll(() => scrollLeft(page)).toBeGreaterThan(0);

      // keep stepping until the end stops moving it forward, then once more: back to the start
      let last = await settled(page);
      for (let i = 0; i < 5; i++) {
        await page.getByTestId("strip-next").click();
        const now = await settled(page);
        if (now < last) break; // wrapped
        last = now;
      }
      expect(await settled(page)).toBeLessThan(5);
    });

    test("prev arrow from the start jumps to the end", async ({ page }) => {
      await page.goto("/");
      await page.getByTestId("strip-prev").click();
      await expect.poll(() => scrollLeft(page), { timeout: 5_000 }).toBeGreaterThan(0);
    });
  });
}

test.describe("Home sport strip — behaviour", () => {
  test.use({ viewport: { width: 1280, height: 900 } });

  test("advances on its own", async ({ page }) => {
    await page.goto("/");
    await expect(track(page).locator(".sport-card").first()).toBeVisible();
    expect(await scrollLeft(page)).toBe(0);
    await expect.poll(() => scrollLeft(page), { timeout: 9_000, intervals: [500] }).toBeGreaterThan(0);
  });

  test("pauses while hovered", async ({ page }) => {
    await page.goto("/");
    await track(page).hover();
    await page.waitForTimeout(6_500); // longer than one auto-advance interval
    expect(await scrollLeft(page)).toBe(0);
  });

  test("does not auto-scroll when the visitor prefers reduced motion", async ({ browser }) => {
    const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 }, reducedMotion: "reduce" });
    const page = await ctx.newPage();
    await page.goto("http://localhost:5173/");
    await expect(track(page).locator(".sport-card").first()).toBeVisible();
    await page.waitForTimeout(6_500);
    expect(await scrollLeft(page)).toBe(0);
    await ctx.close();
  });

  test("Book links still point to the right sport", async ({ page }) => {
    await page.goto("/");
    await expect(track(page).getByRole("link", { name: "Book Football" })).toHaveAttribute("href", "/book?sport=football");
  });
});
