import { test, expect, Page } from "@playwright/test";

// Home → "In action": four short muted clips in the same kind of looping strip as the sport cards
// (3 / 2 / 1 per screen), only the visible clips play, no third-party GIFs.

const CAPTIONS = ["Match day in the nets", "Fast feet at dusk", "Friendly rallies, big smiles", "Doubles on the court"];
const CLIPS = ["cricket", "football", "badminton", "pickleball"];

const SIZES = [
  { name: "desktop", width: 1280, height: 900, perView: 3 },
  { name: "tablet", width: 800, height: 900, perView: 2 },
  { name: "mobile", width: 375, height: 800, perView: 1 },
];

const track = (page: Page) => page.getByTestId("action-strip-track");
const scrollLeft = (page: Page) => track(page).evaluate((el) => Math.round(el.scrollLeft));

async function openSection(page: Page) {
  await page.goto("/");
  await page.locator("#action").scrollIntoViewIfNeeded();
  await expect(track(page).locator(".action-tile").first()).toBeVisible();
}

/** Captions of the tiles that lie fully inside the strip, left to right. */
async function visibleCaptions(page: Page): Promise<string[]> {
  return track(page).evaluate((el) => {
    const box = el.getBoundingClientRect();
    return Array.from(el.children)
      .filter((c) => {
        const r = (c as HTMLElement).getBoundingClientRect();
        return r.left >= box.left - 2 && r.right <= box.right + 2;
      })
      .map((c) => (c.querySelector("figcaption")?.textContent ?? "").trim());
  });
}

const expected = (i: number, perView: number) =>
  Array.from({ length: perView }, (_, k) => CAPTIONS[(((i + k) % CAPTIONS.length) + CAPTIONS.length) % CAPTIONS.length]);

async function clickAndSettle(page: Page, which: "next" | "prev"): Promise<number[]> {
  await page.getByTestId(`action-strip-${which}`).click();
  const samples: number[] = [];
  let same = 0;
  for (let i = 0; i < 60 && same < 3; i++) {
    const now = await scrollLeft(page);
    same = samples.length && samples[samples.length - 1] === now ? same + 1 : 0;
    samples.push(now);
    await page.waitForTimeout(40);
  }
  await page.waitForTimeout(450); // let the invisible swap back into the middle set run
  return samples;
}

for (const size of SIZES) {
  test.describe(`In action strip — ${size.name} (${size.width}px)`, () => {
    test.use({ viewport: { width: size.width, height: size.height } });

    test(`shows ${size.perView} tile(s) per screen, all the same height`, async ({ page }) => {
      await openSection(page);
      await expect(track(page).locator(".action-tile:not([data-clone])")).toHaveCount(4);
      expect(await visibleCaptions(page)).toEqual(expected(0, size.perView));
      const heights = await track(page).locator(".action-tile").evaluateAll((els) => els.map((e) => Math.round(e.getBoundingClientRect().height)));
      expect(new Set(heights).size).toBe(1);
    });

    test("next arrow loops through all four clips and continues past the last one", async ({ page }) => {
      await openSection(page);
      let last = await scrollLeft(page);
      for (let i = 1; i <= 5; i++) {
        const samples = await clickAndSettle(page, "next");
        expect(Math.max(...samples)).toBeGreaterThanOrEqual(last); // never sweeps back to the start
        last = await scrollLeft(page);
        expect(await visibleCaptions(page)).toEqual(expected(i, size.perView));
      }
    });
  });
}

test.describe("In action strip — clips", () => {
  test.use({ viewport: { width: 1280, height: 900 } });

  test("tiles are the four clips, captioned, with no GIFs on the page", async ({ page }) => {
    const gifs: string[] = [];
    page.on("request", (r) => { if (/\.gif(\?|$)/i.test(r.url())) gifs.push(r.url()); });
    await openSection(page);
    const real = track(page).locator(".action-tile:not([data-clone])");
    await expect(real.locator("figcaption")).toHaveText(CAPTIONS);
    const srcs = await real.locator("video").evaluateAll((els) => els.map((e) => (e as HTMLVideoElement).getAttribute("src")));
    expect(srcs).toEqual(CLIPS.map((c) => `/videos/${c}.mp4`));
    await page.waitForTimeout(500);
    expect(gifs).toEqual([]);
  });

  test("every clip and poster file is served and reasonably small", async ({ page }) => {
    for (const c of CLIPS) {
      const v = await page.request.get(`/videos/${c}.mp4`);
      expect(v.status()).toBe(200);
      expect((await v.body()).length).toBeLessThan(4_000_000); // optimised copies, not the 4K originals
      expect((await page.request.get(`/videos/posters/${c}.jpg`)).status()).toBe(200);
    }
  });

  test("only the clips in view play, and they actually advance", async ({ page }) => {
    await openSection(page);
    const real = track(page).locator(".action-tile:not([data-clone]) video");
    await expect.poll(async () => real.nth(0).evaluate((v) => !(v as HTMLVideoElement).paused), { timeout: 8_000 }).toBe(true);
    const t0 = await real.nth(0).evaluate((v) => (v as HTMLVideoElement).currentTime);
    await page.waitForTimeout(1_200);
    expect(await real.nth(0).evaluate((v) => (v as HTMLVideoElement).currentTime)).toBeGreaterThan(t0);
    // the fourth clip (Pickleball) is outside the strip at this width, so it is not playing
    expect(await real.nth(3).evaluate((v) => (v as HTMLVideoElement).paused)).toBe(true);
  });

  test("clones for the endless loop are hidden from assistive tech and keyboard", async ({ page }) => {
    await openSection(page);
    const clones = track(page).locator(".action-tile[data-clone]");
    await expect(clones).toHaveCount(8);
    for (const attr of ["aria-hidden", "inert"]) {
      expect(await clones.evaluateAll((els, a) => els.every((e) => e.hasAttribute(a)), attr)).toBe(true);
    }
  });

  test("no autoplay when the visitor prefers reduced motion", async ({ browser }) => {
    const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 }, reducedMotion: "reduce" });
    const page = await ctx.newPage();
    await page.goto("http://localhost:5173/");
    await page.locator("#action").scrollIntoViewIfNeeded();
    await page.waitForTimeout(1_500);
    const playing = await page.locator("#action video").evaluateAll((els) => els.filter((v) => !(v as HTMLVideoElement).paused).length);
    expect(playing).toBe(0);
    await ctx.close();
  });
});
