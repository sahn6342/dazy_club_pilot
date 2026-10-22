import { test, expect, Page } from "@playwright/test";

// Home → "Choose your court energy": the sport cards are a swipeable strip that shows 3 / 2 / 1 cards by width,
// has prev/next arrows, advances on its own (pausing on hover) and loops seamlessly: after the last card the
// first one follows in the same direction instead of the strip rewinding.

const SPORTS = ["Cricket", "Football", "Badminton", "Pickleball"];

const SIZES = [
  { name: "desktop", width: 1280, height: 900, perView: 3 },
  { name: "tablet", width: 800, height: 900, perView: 2 },
  { name: "mobile", width: 375, height: 800, perView: 1 },
];

const track = (page: Page) => page.getByTestId("sport-strip-track");
const scrollLeft = (page: Page) => track(page).evaluate((el) => Math.round(el.scrollLeft));

/** Sport names of the cards that lie fully inside the strip, left to right. */
async function visibleSports(page: Page): Promise<string[]> {
  return track(page).evaluate((el) => {
    const box = el.getBoundingClientRect();
    return Array.from(el.children)
      .filter((c) => {
        const r = (c as HTMLElement).getBoundingClientRect();
        return r.left >= box.left - 2 && r.right <= box.right + 2;
      })
      .map((c) => (c.querySelector(".eyebrow")?.textContent ?? "").trim());
  });
}

/** What the strip should show when the card at logical position `i` is leftmost (the row wraps around). */
const expected = (i: number, perView: number) =>
  Array.from({ length: perView }, (_, k) => SPORTS[(((i + k) % SPORTS.length) + SPORTS.length) % SPORTS.length]);

/** Width of one full set of cards (the strip holds three: clones, real, clones). */
const setWidth = (page: Page) =>
  track(page).evaluate((el) => {
    const gap = parseFloat(getComputedStyle(el).columnGap || "0") || 0;
    return (el.scrollWidth + gap) / 3;
  });

/**
 * The strip may move smoothly in `dir`, and once it is idle it may jump by exactly one set width (the invisible
 * swap back into the middle set). A rewind sweep would instead show up as many small moves the wrong way.
 */
function expectNoRewind(samples: number[], dir: 1 | -1, jump: number) {
  for (let k = 1; k < samples.length; k++) {
    const delta = (samples[k] - samples[k - 1]) * dir; // > 0 = moving the intended way
    if (delta >= 0) continue;
    expect(Math.abs(delta)).toBeGreaterThan(jump - 4); // only the one-set instant swap may go the other way
  }
}

/**
 * Click an arrow and follow the smooth scroll until it stops, returning every scroll position seen on the way.
 * Then give the idle step (the invisible swap back into the middle set) time to run.
 */
async function clickAndSettle(page: Page, testId: "strip-next" | "strip-prev"): Promise<number[]> {
  await page.getByTestId(testId).click();
  const samples: number[] = [];
  let same = 0;
  for (let i = 0; i < 60 && same < 3; i++) {
    const now = await scrollLeft(page);
    same = samples.length && samples[samples.length - 1] === now ? same + 1 : 0;
    samples.push(now);
    await page.waitForTimeout(40);
  }
  await page.waitForTimeout(450);
  return samples;
}

for (const size of SIZES) {
  test.describe(`Home sport strip — ${size.name} (${size.width}px)`, () => {
    test.use({ viewport: { width: size.width, height: size.height } });

    test(`shows ${size.perView} card(s) per screen, starting at Cricket`, async ({ page }) => {
      await page.goto("/");
      await expect(track(page).locator(".sport-card:not([data-clone])")).toHaveCount(4);
      await expect(track(page).locator(".sport-card").first()).toBeVisible();
      expect(await visibleSports(page)).toEqual(expected(0, size.perView));
    });

    test("next arrow keeps going forward and the row continues past the last card", async ({ page }) => {
      await page.goto("/");
      await expect(page.getByTestId("strip-next")).toBeVisible();
      for (let i = 1; i <= 6; i++) {
        const samples = await clickAndSettle(page, "strip-next");
        // moving: never backwards (no rewind sweep), even when stepping past the last card
        expectNoRewind(samples, 1, await setWidth(page));
        // and the cards shown continue the cycle: ... Pickleball, Cricket, Football, ...
        expect(await visibleSports(page)).toEqual(expected(i, size.perView));
      }
    });

    test("prev arrow from the first card continues backwards to Pickleball", async ({ page }) => {
      await page.goto("/");
      const samples = await clickAndSettle(page, "strip-prev");
      expectNoRewind(samples, -1, await setWidth(page));
      expect(await visibleSports(page)).toEqual(expected(-1, size.perView));
    });
  });
}

test.describe("Home sport strip — behaviour", () => {
  test.use({ viewport: { width: 1280, height: 900 } });

  test("advances on its own", async ({ page }) => {
    await page.goto("/");
    await expect(track(page).locator(".sport-card").first()).toBeVisible();
    const start = await scrollLeft(page);
    await expect.poll(() => scrollLeft(page), { timeout: 9_000, intervals: [500] }).toBeGreaterThan(start);
  });

  test("pauses while hovered", async ({ page }) => {
    await page.goto("/");
    await expect(track(page).locator(".sport-card").first()).toBeVisible();
    const start = await scrollLeft(page);
    await track(page).hover();
    await page.waitForTimeout(6_500); // longer than one auto-advance interval
    expect(await scrollLeft(page)).toBe(start);
  });

  test("does not auto-scroll when the visitor prefers reduced motion", async ({ browser }) => {
    const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 }, reducedMotion: "reduce" });
    const page = await ctx.newPage();
    await page.goto("http://localhost:5173/");
    await expect(track(page).locator(".sport-card").first()).toBeVisible();
    const start = await scrollLeft(page);
    await page.waitForTimeout(6_500);
    expect(await scrollLeft(page)).toBe(start);
    await ctx.close();
  });

  test("clone cards are hidden from assistive tech and keyboard", async ({ page }) => {
    await page.goto("/");
    const clones = track(page).locator("[data-clone]");
    await expect(clones).toHaveCount(8);
    for (const attr of ["aria-hidden", "inert"]) {
      expect(await clones.evaluateAll((els, a) => els.every((e) => e.hasAttribute(a)), attr)).toBe(true);
    }
  });

  test("Book links still point to the right sport", async ({ page }) => {
    await page.goto("/");
    await expect(track(page).locator(":not([data-clone])").getByRole("link", { name: "Book Football" })).toHaveAttribute("href", "/book?sport=football");
  });
});
