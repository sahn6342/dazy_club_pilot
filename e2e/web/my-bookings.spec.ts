import { test, expect, APIRequestContext } from "@playwright/test";

const API = "http://localhost:8000/api/v1";

async function token(request: APIRequestContext): Promise<string> {
  const r = await request.post(`${API}/admin/login`, { data: { username: "admin", password: "admin" } });
  return (await r.json()).access_token;
}

async function deleteBooking(request: APIRequestContext, id: string): Promise<void> {
  const tok = await token(request);
  await request.delete(`${API}/admin/bookings/${id}`, { headers: { Authorization: `Bearer ${tok}` } });
}

async function findAvailableSlot(request: APIRequestContext, sport: string) {
  for (let i = 0; i <= 6; i++) {
    const d = new Date();
    d.setDate(d.getDate() + i);
    const dateStr = d.toISOString().slice(0, 10);
    const slots = await (await request.get(`${API}/slots?sport=${sport}&date=${dateStr}`)).json();
    const slot = slots.find((s: any) => s.available && s.finalPrice);
    if (slot) return slot;
  }
  throw new Error(`No available priced ${sport} slot found in the next 7 days.`);
}

test.describe("Book page — self-service booking lookup", () => {
  test("resumes a pending booking's payment with the same checkout order", async ({ page, request }) => {
    const slot = await findAvailableSlot(request, "cricket");
    const contact = "9" + String(Date.now()).slice(-9);
    const created = await (await request.post(`${API}/bookings`, {
      data: {
        name: "Lookup E2E User", contact, sportSlug: slot.sportSlug,
        date: slot.date, startTime: slot.startTime, slotIds: [slot.id], players: 1,
      },
    })).json();
    expect(created.paymentRequired).toBe(true);

    try {
      await page.goto("/my-bookings");
      await page.getByPlaceholder(/e.g. A1B2C3D4/i).fill(created.bookingRef);
      await page.getByPlaceholder(/10-digit mobile or email/i).fill(contact);
      await page.getByRole("button", { name: /find my booking/i }).click();

      await expect(page.getByTestId("lookup-status")).toContainText(/payment pending/i);
      await expect(page.locator(".payment-panel")).toBeVisible();
      await expect(page.getByTestId("payment-amount")).toContainText(String(created.price));
    } finally {
      const tok = await token(request);
      const list = await (await request.get(`${API}/admin/bookings`, { headers: { Authorization: `Bearer ${tok}` } })).json();
      const booking = list.find((b: any) => b.bookingRef === created.bookingRef);
      if (booking) await deleteBooking(request, booking.id);
    }
  });

  test("wrong contact shows a not-found error, not the booking", async ({ page, request }) => {
    const slot = await findAvailableSlot(request, "badminton");
    const contact = "9" + String(Date.now()).slice(-9);
    const created = await (await request.post(`${API}/bookings`, {
      data: {
        name: "Lookup Wrong Contact", contact, sportSlug: slot.sportSlug,
        date: slot.date, startTime: slot.startTime, slotIds: [slot.id], players: 1,
      },
    })).json();

    try {
      await page.goto("/my-bookings");
      await page.getByPlaceholder(/e.g. A1B2C3D4/i).fill(created.bookingRef);
      await page.getByPlaceholder(/10-digit mobile or email/i).fill("0000000000");
      await page.getByRole("button", { name: /find my booking/i }).click();

      await expect(page.getByTestId("lookup-error")).toBeVisible();
      await expect(page.locator(".payment-panel")).not.toBeVisible();
    } finally {
      const tok = await token(request);
      const list = await (await request.get(`${API}/admin/bookings`, { headers: { Authorization: `Bearer ${tok}` } })).json();
      const booking = list.find((b: any) => b.bookingRef === created.bookingRef);
      if (booking) await deleteBooking(request, booking.id);
    }
  });

  test("unknown ref shows a not-found error", async ({ page }) => {
    await page.goto("/my-bookings");
    await page.getByPlaceholder(/e.g. A1B2C3D4/i).fill("NOSUCHREF");
    await page.getByPlaceholder(/10-digit mobile or email/i).fill("9812345670");
    await page.getByRole("button", { name: /find my booking/i }).click();
    await expect(page.getByTestId("lookup-error")).toBeVisible();
  });

  test("ref pre-fills from the ?ref= query param", async ({ page }) => {
    await page.goto("/my-bookings?ref=ABCD1234");
    await expect(page.getByPlaceholder(/e.g. A1B2C3D4/i)).toHaveValue("ABCD1234");
  });
});
