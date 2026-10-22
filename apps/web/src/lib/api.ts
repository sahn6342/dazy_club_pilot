import type { Slot } from "@dazy/shared";

const API = (import.meta as any).env?.VITE_API_BASE_URL ?? "http://localhost:8000/api/v1";

// API origin without /api/v1 — resolves relative /media image paths to absolute URLs.
// Cloudflare Turnstile PUBLIC site key (build-time). Unset in local dev => widget hidden, API skips the check.
export const TURNSTILE_SITE_KEY: string = (import.meta as any).env?.VITE_TURNSTILE_SITE_KEY ?? "";

export const API_ORIGIN = API.replace(/\/api\/v1\/?$/, "");

export function resolveImg(url: string | null | undefined): string {
  if (!url) return "";
  return /^https?:\/\//.test(url) ? url : `${API_ORIGIN}${url}`;
}

// FastAPI's `detail` is a string for app-raised HTTPExceptions, but a list of
// {loc, msg, type} objects for Pydantic 422 validation errors — stringifying
// that list directly renders "[object Object]". Always reduce to one string.
function errorMessage(body: any, fallback: string): string {
  const detail = body?.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) return detail.map((d) => d?.msg ?? JSON.stringify(d)).join("; ") || fallback;
  return fallback;
}

export interface GalleryItem {
  id: string;
  title: string;
  sportSlug: string;
  tone: string;
  imageUrl?: string | null;
}

export async function getVenueInfo(): Promise<Record<string, string>> {
  const r = await fetch(`${API}/venue`);
  if (!r.ok) throw new Error("Failed to load venue info");
  const entries: { key: string; value: string }[] = await r.json();
  return Object.fromEntries(entries.map((e) => [e.key, e.value]));
}

export async function getGallery(): Promise<GalleryItem[]> {
  const r = await fetch(`${API}/gallery`);
  if (!r.ok) throw new Error("Failed to load gallery");
  return r.json();
}

export async function getSlots(sport: string, date: string): Promise<Slot[]> {
  const r = await fetch(`${API}/slots?sport=${sport}&date=${date}`);
  if (!r.ok) throw new Error("Failed to load slots");
  return r.json();
}

export interface BookingPayload {
  name: string;
  contact: string;
  slotIds: string[];      // one or more consecutive slot IDs
  slotId?: string;        // kept for backward compat — derived from slotIds[0] by API
  sportSlug: string;
  date: string;
  startTime: string;
  players: number;
  promoCode?: string;
  message?: string;
  email?: string;
  turnstileToken?: string;
}

export interface CheckoutConfig {
  provider: string;         // "noop" | "razorpay"
  providerOrderId: string;
  amount: number;
  currency: string;
  // razorpay-only:
  key?: string;
  order_id?: string;
}

export interface BookingResult {
  status: string;           // "pending" (payment required) | "confirmed" (free booking)
  bookingRef: string;
  name: string;
  sport: string;
  date: string;
  startTime: string;
  endTime: string;
  time: string;
  slotCount: number;
  price?: number | null;
  basePrice?: number | null;
  discountPercent?: number | null;
  promoCode?: string | null;
  paymentRequired: boolean;
  checkout?: CheckoutConfig;
  gstRatePercent?: number | null;
  taxableAmount?: number | null;
  gstAmount?: number | null;
}

export interface PaymentVerifyPayload {
  providerOrderId: string;
  providerPaymentId: string;
  signature?: string | null;
}

export interface PromoValidationResult {
  valid: boolean;
  code: string;
  kind?: string;
  value?: number;
  discountedAmount?: number | null;
  savedAmount?: number | null;
  error?: string;
}

export async function validatePromo(
  code: string,
  sport: string,
  amount?: number | null
): Promise<PromoValidationResult> {
  const params = new URLSearchParams({ code, sport });
  if (amount != null) params.set("amount", String(amount));
  const r = await fetch(`${API}/promos/validate?${params}`);
  if (!r.ok) throw new Error("Validation failed");
  return r.json();
}

export async function createBooking(payload: BookingPayload): Promise<BookingResult> {
  const r = await fetch(`${API}/bookings`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!r.ok) {
    const err = await r.json().catch(() => ({ detail: "Booking failed" }));
    throw new Error(errorMessage(err, "Booking failed"));
  }
  return r.json();
}

export async function verifyBookingPayment(
  bookingRef: string,
  payload: PaymentVerifyPayload
): Promise<{ status: string; paymentStatus: string }> {
  const r = await fetch(`${API}/bookings/${bookingRef}/payment/verify`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!r.ok) {
    const err = await r.json().catch(() => ({ detail: "Payment verification failed" }));
    throw new Error(errorMessage(err, "Payment verification failed"));
  }
  return r.json();
}

export interface BookingLookupResult {
  bookingRef: string;
  name: string;
  status: string;
  sport: string;
  date: string;
  startTime: string;
  endTime: string;
  slotCount: number;
  price: number | null;
  paymentRequired: boolean;
  checkout: CheckoutConfig | null;
  gstRatePercent?: number | null;
  taxableAmount?: number | null;
  gstAmount?: number | null;
}

export async function lookupBooking(ref: string, contact?: string): Promise<BookingLookupResult> {
  const params = new URLSearchParams({ ref });
  if (contact) params.set("contact", contact);
  const r = await fetch(`${API}/bookings/lookup?${params}`);
  if (!r.ok) {
    const err = await r.json().catch(() => ({ detail: "Booking not found." }));
    throw new Error(errorMessage(err, "Booking not found."));
  }
  return r.json();
}

export class OtpRequiredError extends Error {
  constructor() { super("otp_required"); }
}

export type PublicConfig = { otpRequired: boolean };

let publicConfigPromise: Promise<PublicConfig> | null = null;

/** Flags the API exposes for choosing a flow up front. Fetched once per page load; any failure falls back to the
 *  safe default (OTP required) instead of guessing that it is off. */
export function getPublicConfig(): Promise<PublicConfig> {
  if (!publicConfigPromise) {
    publicConfigPromise = fetch(`${API}/public-config`)
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(String(r.status)))))
      .then((c) => ({ otpRequired: c?.otpRequired !== false }))
      .catch(() => ({ otpRequired: true }));
  }
  return publicConfigPromise;
}

/** `otpToken` is optional: the API only demands it when OTP is enabled (it answers 401 otp_required otherwise). */
export async function searchBookingsByContact(contact: string, otpToken?: string): Promise<BookingLookupResult[]> {
  const params = new URLSearchParams({ contact });
  const r = await fetch(`${API}/bookings/search?${params}`, { headers: otpToken ? { "X-OTP-Token": otpToken } : {} });
  if (r.status === 401 || r.status === 403) throw new OtpRequiredError();
  if (!r.ok) {
    const err = await r.json().catch(() => ({ detail: "No bookings found." }));
    throw new Error(errorMessage(err, "No bookings found."));
  }
  return r.json();
}

/** Step 1: ask the API to send a one-time code (email, or WhatsApp for a phone number). */
export async function requestOtp(contact: string, turnstileToken?: string): Promise<{ channel: "email" | "whatsapp" }> {
  const r = await fetch(`${API}/otp/request`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ contact, turnstileToken }),
  });
  if (!r.ok) {
    const err = await r.json().catch(() => ({ detail: "Could not send a code." }));
    throw new Error(errorMessage(err, "Could not send a code."));
  }
  return r.json();
}

/** Step 2: exchange the code for a short-lived token that unlocks booking search for that contact. */
export async function verifyOtp(contact: string, code: string): Promise<string> {
  const r = await fetch(`${API}/otp/verify`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ contact, code }),
  });
  if (!r.ok) {
    const err = await r.json().catch(() => ({ detail: "That code is incorrect or has expired." }));
    throw new Error(errorMessage(err, "That code is incorrect or has expired."));
  }
  return (await r.json()).otpToken;
}

export interface ContactPayload {
  name: string;
  contact: string;
  interestedSport?: string;
  message?: string;
  turnstileToken?: string;
}

export async function submitContactEnquiry(payload: ContactPayload) {
  const r = await fetch(`${API}/contact-enquiries`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!r.ok) throw new Error("Enquiry failed");
  return r.json();
}

export interface CorporatePayload {
  contactName: string;
  company: string;
  contact: string;
  estimatedGroupSize: number;
  eventType?: string;
  preferredDate?: string;
  preferredSport?: string;
  message?: string;
  turnstileToken?: string;
}

export async function submitCorporateEnquiry(payload: CorporatePayload) {
  const r = await fetch(`${API}/corporate-enquiries`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!r.ok) throw new Error("Enquiry failed");
  return r.json();
}

export interface PublicMenuCategory {
  id: string;
  name: string;
  kind: string;
  vegType?: string | null;
  sortOrder: number;
  active: boolean;
}

export interface PublicMenuItem {
  id: string;
  category_id: string;
  name: string;
  description?: string | null;
  price: number;
  vegType?: string | null;
  available: boolean;
}

export interface PublicMenu {
  categories: PublicMenuCategory[];
  items: PublicMenuItem[];
}

export async function getPublicMenu(): Promise<PublicMenu> {
  const r = await fetch(`${API}/menu`);
  if (!r.ok) throw new Error("Failed to load menu");
  return r.json();
}

export interface PreOrderLine {
  name: string;
  qty: number;
  lineTotal: number;
}

export interface PreOrderResult {
  orderNo: string;
  total: number;
  items: PreOrderLine[];
}

export async function createPreorder(
  bookingRef: string,
  contact: string,
  items: { menu_item_id: string; qty: number }[]
): Promise<PreOrderResult> {
  const r = await fetch(`${API}/bookings/${bookingRef}/preorder`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ contact, items }),
  });
  if (!r.ok) {
    const err = await r.json().catch(() => ({ detail: "Pre-order failed" }));
    throw new Error(errorMessage(err, "Pre-order failed"));
  }
  return r.json();
}

export const SPORT_LABELS: Record<string, string> = {
  cricket: "Cricket",
  football: "Football",
  badminton: "Badminton",
  pickleball: "Pickleball",
};

export function getNext7Days(): { iso: string; label: string; short: string }[] {
  return Array.from({ length: 7 }, (_, i) => {
    const d = new Date();
    d.setDate(d.getDate() + i);
    // Use local year/month/day — toISOString() returns UTC and diverges from
    // toLocaleDateString() for users in UTC+ zones before 00:00 UTC (e.g. IST 00:00–05:30).
    const iso = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
    const label = d.toLocaleDateString("en-IN", { weekday: "short", day: "numeric", month: "short" });
    const short = d.toLocaleDateString("en-IN", { weekday: "short", day: "numeric" });
    return { iso, label, short };
  });
}

export function todayIso(): string {
  return new Date().toISOString().split("T")[0];
}
