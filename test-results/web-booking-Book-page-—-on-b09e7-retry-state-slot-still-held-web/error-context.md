# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: web\booking.spec.ts >> Book page — online prepay >> simulated failed payment shows retry state, slot still held
- Location: e2e\web\booking.spec.ts:304:7

# Error details

```
TypeError: list.find is not a function
```

# Page snapshot

```yaml
- main [ref=e3]:
  - generic [ref=e4]:
    - link "Dazy.club" [ref=e5] [cursor=pointer]:
      - /url: /
    - navigation "Primary navigation" [ref=e6]:
      - link "Home" [ref=e7] [cursor=pointer]:
        - /url: /
      - link "Book" [ref=e8] [cursor=pointer]:
        - /url: /book
      - link "Contact" [ref=e9] [cursor=pointer]:
        - /url: /contact
  - generic [ref=e10]:
    - generic [ref=e11]:
      - paragraph [ref=e12]: Book a court
      - heading "Pick your sport, date, and slot." [level=2] [ref=e13]
      - paragraph [ref=e14]: Select one or more consecutive slots and confirm your booking.
    - tablist [ref=e15]:
      - tab "Cricket" [ref=e16] [cursor=pointer]
      - tab "Badminton" [ref=e17] [cursor=pointer]
      - tab "Pickleball" [ref=e18] [cursor=pointer]
    - group "Select date" [ref=e19]:
      - button "Thu 2" [ref=e20] [cursor=pointer]
      - button "Fri 3" [ref=e21] [cursor=pointer]
      - button "Sat 4" [ref=e22] [cursor=pointer]
      - button "Sun 5" [ref=e23] [cursor=pointer]
      - button "Mon 6" [ref=e24] [cursor=pointer]
      - button "Tue 7" [ref=e25] [cursor=pointer]
      - button "Wed 8" [ref=e26] [cursor=pointer]
    - group "Select court" [ref=e27]:
      - button "All courts" [ref=e28] [cursor=pointer]
      - button "Court 1" [ref=e29] [cursor=pointer]
      - button "court 2" [ref=e30] [cursor=pointer]
    - generic [ref=e31]:
      - paragraph [ref=e32]:
        - text: Cricket — Fri, 3 Jul
        - generic [ref=e33]: 15:00–16:00
      - paragraph [ref=e34]: Tap the next adjacent slot to book multiple hours, or fill in the form below.
      - generic [ref=e35]:
        - button "14:00 Court 1 ₹1200 Booked" [disabled] [ref=e36]:
          - text: 14:00
          - generic [ref=e37]: Court 1
          - generic [ref=e38]: ₹1200
          - generic [ref=e39]: Booked
        - button "15:00 Court 1 ₹1200" [ref=e40] [cursor=pointer]:
          - text: 15:00
          - generic [ref=e41]: Court 1
          - generic [ref=e42]: ₹1200
        - button "16:00 Court 1 ₹1200" [ref=e43] [cursor=pointer]:
          - text: 16:00
          - generic [ref=e44]: Court 1
          - generic [ref=e45]: ₹1200
        - button "18:00 Court 1 ₹1200" [ref=e46] [cursor=pointer]:
          - text: 18:00
          - generic [ref=e47]: Court 1
          - generic [ref=e48]: ₹1200
        - button "19:00 Court 1 ₹1200" [ref=e49] [cursor=pointer]:
          - text: 19:00
          - generic [ref=e50]: Court 1
          - generic [ref=e51]: ₹1200
        - button "20:00 Court 1 ₹1200" [ref=e52] [cursor=pointer]:
          - text: 20:00
          - generic [ref=e53]: Court 1
          - generic [ref=e54]: ₹1200
        - button "13:00 court 2 Free" [ref=e55] [cursor=pointer]:
          - text: 13:00
          - generic [ref=e56]: court 2
          - generic [ref=e57]: Free
        - button "14:00 court 2 Free" [ref=e58] [cursor=pointer]:
          - text: 14:00
          - generic [ref=e59]: court 2
          - generic [ref=e60]: Free
        - button "15:00 court 2 Free" [ref=e61] [cursor=pointer]:
          - text: 15:00
          - generic [ref=e62]: court 2
          - generic [ref=e63]: Free
        - button "16:00 court 2 Free" [ref=e64] [cursor=pointer]:
          - text: 16:00
          - generic [ref=e65]: court 2
          - generic [ref=e66]: Free
        - button "17:00 court 2 Free" [ref=e67] [cursor=pointer]:
          - text: 17:00
          - generic [ref=e68]: court 2
          - generic [ref=e69]: Free
        - button "18:00 court 2 Free" [ref=e70] [cursor=pointer]:
          - text: 18:00
          - generic [ref=e71]: court 2
          - generic [ref=e72]: Free
        - button "19:00 court 2 Free" [ref=e73] [cursor=pointer]:
          - text: 19:00
          - generic [ref=e74]: court 2
          - generic [ref=e75]: Free
        - button "20:00 court 2 Free" [ref=e76] [cursor=pointer]:
          - text: 20:00
          - generic [ref=e77]: court 2
          - generic [ref=e78]: Free
    - generic [ref=e79]:
      - paragraph [ref=e80]: Payment required
      - heading "Complete payment to confirm your booking" [level=3] [ref=e81]
      - paragraph [ref=e82]: "Amount due: ₹1200.00"
      - paragraph [ref=e83]: "Ref: 562B9AD0 — your slot is held for 15 minutes while you pay."
      - generic [ref=e84]:
        - paragraph [ref=e85]: Dev mode — no real payment gateway is configured.
        - generic [ref=e86]:
          - button "Simulate successful payment" [ref=e87] [cursor=pointer]
          - button "Simulate failed / cancelled payment" [active] [ref=e88] [cursor=pointer]
  - generic [ref=e89]:
    - strong [ref=e90]: Dazy.club
    - generic [ref=e91]: Premium sports experience. Cricket, Badminton & Pickleball.
```

# Test source

```ts
  232 |         try { const b = await res.json(); createdBookingId = b.id; } catch { /* ignore */ }
  233 |       }
  234 |     });
  235 | 
  236 |     try {
  237 |       await page.unroute("**/api/v1/slots**");
  238 |       await page.getByRole("button", { name: /confirm booking/i }).click();
  239 | 
  240 |       await expect(
  241 |         page.getByText(/you're booked in/i).or(page.getByText(/slots may have just been taken/i))
  242 |       ).toBeVisible({ timeout: 10_000 });
  243 | 
  244 |       const succeeded = await page.getByText(/you're booked in/i).isVisible();
  245 |       if (succeeded) {
  246 |         await page.getByRole("button", { name: /book another/i }).click();
  247 |         await expect(page.locator(".booking-form-wrap")).not.toBeVisible();
  248 |         await expect(page.locator(".slot-grid")).toBeVisible();
  249 |       }
  250 |     } finally {
  251 |       if (createdBookingId) await deleteBooking(request, createdBookingId);
  252 |     }
  253 |   });
  254 | });
  255 | 
  256 | // ── Online prepay (Phase 3): pending -> payment panel -> confirm ──────────
  257 | 
  258 | test.describe("Book page — online prepay", () => {
  259 |   test("priced booking shows the payment panel, dev-simulate confirms it", async ({ page, request }) => {
  260 |     await page.goto("/book");
  261 |     await selectFirstDateWithSlots(page); // real slots — cricket is priced (₹1200 seeded)
  262 | 
  263 |     await page.locator(".slot-chip:not(.unavailable)").first().click();
  264 |     await expect(page.locator(".booking-form-wrap")).toBeVisible();
  265 | 
  266 |     await page.getByPlaceholder("Your full name").fill("Prepay E2E User");
  267 |     const phone = "9" + String(Date.now()).slice(-9);
  268 |     await page.getByPlaceholder("10-digit mobile or email").fill(phone);
  269 | 
  270 |     let ref: string | null = null;
  271 |     page.on("response", async (res) => {
  272 |       if (res.url().endsWith("/api/v1/bookings") && res.request().method() === "POST" && res.status() === 201) {
  273 |         try { ref = (await res.json()).bookingRef; } catch { /* ignore */ }
  274 |       }
  275 |     });
  276 | 
  277 |     try {
  278 |       const create = page.waitForResponse((r) => r.url().endsWith("/api/v1/bookings") && r.request().method() === "POST");
  279 |       await page.getByRole("button", { name: /confirm booking/i }).click();
  280 |       const createBody = await (await create).json();
  281 |       expect(createBody.status).toBe("pending");
  282 |       expect(createBody.paymentRequired).toBe(true);
  283 | 
  284 |       await expect(page.locator(".payment-panel")).toBeVisible();
  285 |       await expect(page.getByTestId("payment-amount")).toContainText("Amount due");
  286 |       await expect(page.getByTestId("payment-dev-panel")).toBeVisible(); // noop provider in dev
  287 | 
  288 |       const verify = page.waitForResponse((r) => r.url().includes("/payment/verify") && r.request().method() === "POST");
  289 |       await page.getByTestId("simulate-payment-success").click();
  290 |       expect((await verify).status()).toBe(200);
  291 | 
  292 |       await expect(page.getByText(/you're booked in/i)).toBeVisible({ timeout: 10_000 });
  293 |       await expect(page.getByTestId("confirmed-amount")).toContainText("Amount paid");
  294 |     } finally {
  295 |       if (ref) {
  296 |         const tok = await token(request);
  297 |         const list = await (await request.get(`${API}/admin/bookings`, { headers: { Authorization: `Bearer ${tok}` } })).json();
  298 |         const booking = list.find((b: any) => b.bookingRef === ref);
  299 |         if (booking) await deleteBooking(request, booking.id);
  300 |       }
  301 |     }
  302 |   });
  303 | 
  304 |   test("simulated failed payment shows retry state, slot still held", async ({ page, request }) => {
  305 |     await page.goto("/book");
  306 |     await selectFirstDateWithSlots(page);
  307 | 
  308 |     await page.locator(".slot-chip:not(.unavailable)").first().click();
  309 |     await expect(page.locator(".booking-form-wrap")).toBeVisible();
  310 |     await page.getByPlaceholder("Your full name").fill("Prepay Fail E2E");
  311 |     const phone = "9" + String(Date.now()).slice(-9);
  312 |     await page.getByPlaceholder("10-digit mobile or email").fill(phone);
  313 | 
  314 |     let ref: string | null = null;
  315 |     page.on("response", async (res) => {
  316 |       if (res.url().endsWith("/api/v1/bookings") && res.request().method() === "POST" && res.status() === 201) {
  317 |         try { ref = (await res.json()).bookingRef; } catch { /* ignore */ }
  318 |       }
  319 |     });
  320 | 
  321 |     try {
  322 |       await page.getByRole("button", { name: /confirm booking/i }).click();
  323 |       await expect(page.locator(".payment-panel")).toBeVisible();
  324 | 
  325 |       await page.getByTestId("simulate-payment-failure").click();
  326 |       await expect(page.getByTestId("payment-dev-panel")).toBeVisible(); // still on the payment step, can retry
  327 |       await expect(page.getByText(/you're booked in/i)).not.toBeVisible();
  328 |     } finally {
  329 |       if (ref) {
  330 |         const tok = await token(request);
  331 |         const list = await (await request.get(`${API}/admin/bookings`, { headers: { Authorization: `Bearer ${tok}` } })).json();
> 332 |         const booking = list.find((b: any) => b.bookingRef === ref);
      |                              ^ TypeError: list.find is not a function
  333 |         if (booking) await deleteBooking(request, booking.id);
  334 |       }
  335 |     }
  336 |   });
  337 | });
  338 | 
```