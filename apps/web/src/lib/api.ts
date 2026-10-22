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

// ── Errors ───────────────────────────────────────────────────────────────────
// Every call goes through request(). A failure becomes an ApiError that says WHAT happened (kind, HTTP status and
// the server's machine-readable `code`) next to a message that is safe to show. Callers decide by status/code,
// never by searching the message text.

export type ApiErrorKind = "http" | "network" | "timeout";

export class ApiError extends Error {
  readonly status: number;      // HTTP status, or 0 when there was no response (network / timeout)
  readonly code: string | null; // machine-readable code from the API (e.g. "slot_unavailable"), when it sent one
  readonly kind: ApiErrorKind;
  constructor(message: string, opts: { status?: number; code?: string | null; kind?: ApiErrorKind } = {}) {
    super(message);
    this.name = "ApiError";
    this.status = opts.status ?? 0;
    this.code = opts.code ?? null;
    this.kind = opts.kind ?? "http";
  }
  /** The service could not answer (no connection, timeout, or a 5xx): not the user's input and not a lost slot. */
  get isOutage(): boolean {
    return this.kind !== "http" || this.status >= 500;
  }
}

export const MESSAGES = {
  network: "Can't reach the server. Check your connection and try again.",
  timeout: "The server took too long to answer. Please try again.",
  server: "Something went wrong on our side. Please try again in a moment.",
};

const REQUEST_TIMEOUT_MS = 15_000;

/** Reduce FastAPI's `detail` (a string, or a list of {msg} objects for 422 validation errors) to one string. */
function detailText(body: any): string | null {
  const detail = body?.detail;
  if (typeof detail === "string") return detail || null;
  if (Array.isArray(detail)) {
    const msgs = detail.map((d) => String(d?.msg ?? "").replace(/^(Value|Assertion) error, /i, "")).filter(Boolean);
    return msgs.length ? msgs.join("; ") : null;
  }
  return null;
}

/** Back-compat for callers that only need the text. */
export function errorMessage(err: unknown, fallback: string): string {
  return err instanceof Error && err.message ? err.message : fallback;
}

async function request<T = any>(
  path: string,
  init: RequestInit & { fallback?: string; timeoutMs?: number } = {},
): Promise<T> {
  const { fallback = "Something went wrong. Please try again.", timeoutMs = REQUEST_TIMEOUT_MS, ...fetchInit } = init;
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  let r: Response;
  try {
    r = await fetch(`${API}${path}`, { ...fetchInit, signal: controller.signal });
  } catch (e: any) {
    if (e?.name === "AbortError") throw new ApiError(MESSAGES.timeout, { kind: "timeout" });
    throw new ApiError(MESSAGES.network, { kind: "network" });
  } finally {
    clearTimeout(timer);
  }
  if (!r.ok) {
    const body = await r.json().catch(() => null);
    const text = detailText(body);
    const code = typeof body?.code === "string" ? body.code : null;
    // 5xx: show the server's own words only when it chose them (e.g. 503 "Payment gateway unavailable");
    // the generic "Internal server error." is replaced, with the request id so support can find it.
    let message: string;
    if (r.status >= 500 && (!text || /^internal server error\.?$/i.test(text))) {
      const rid = typeof body?.requestId === "string" ? body.requestId.slice(0, 8) : "";
      message = rid ? `${MESSAGES.server} (ref ${rid})` : MESSAGES.server;
    } else {
      message = text ?? fallback;
    }
    throw new ApiError(message, { status: r.status, code, kind: "http" });
  }
  return r.json();
}

const jsonInit = (method: string, body: unknown, fallback: string, headers: Record<string, string> = {}) => ({
  method,
  headers: { "Content-Type": "application/json", ...headers },
  body: JSON.stringify(body),
  fallback,
});

export interface GalleryItem {
  id: string;
  title: string;
  sportSlug: string;
  tone: string;
  imageUrl?: string | null;
}

let venueInfoPromise: Promise<Record<string, string>> | null = null;

/** Venue details from the CMS. Cached for the page load so the footer and the WhatsApp button share one request. */
export function getVenueInfo(): Promise<Record<string, string>> {
  if (!venueInfoPromise) {
    venueInfoPromise = request<{ key: string; value: string }[]>("/venue", { fallback: "Failed to load venue info" })
      .then((entries) => Object.fromEntries(entries.map((e) => [e.key, e.value])))
      .catch((e) => { venueInfoPromise = null; throw e; }); // a failed load may be retried
  }
  return venueInfoPromise;
}

export async function getGallery(): Promise<GalleryItem[]> {
  return request("/gallery", { fallback: "Failed to load gallery" });
}

export async function getSlots(sport: string, date: string): Promise<Slot[]> {
  return request(`/slots?sport=${sport}&date=${date}`, { fallback: "Failed to load slots" });
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
  return request(`/promos/validate?${params}`, { fallback: "Validation failed" });
}

export async function createBooking(payload: BookingPayload): Promise<BookingResult> {
  return request("/bookings", jsonInit("POST", payload, "Booking failed"));
}

export async function verifyBookingPayment(
  bookingRef: string,
  payload: PaymentVerifyPayload
): Promise<{ status: string; paymentStatus: string }> {
  return request(`/bookings/${bookingRef}/payment/verify`, jsonInit("POST", payload, "Payment verification failed"));
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
  return request(`/bookings/lookup?${params}`, { fallback: "Booking not found." });
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
    publicConfigPromise = request("/public-config")
      .then((c) => ({ otpRequired: c?.otpRequired !== false }))
      .catch(() => ({ otpRequired: true }));
  }
  return publicConfigPromise;
}

/** `otpToken` is optional: the API only demands it when OTP is enabled (it answers 401 otp_required otherwise). */
export async function searchBookingsByContact(contact: string, otpToken?: string): Promise<BookingLookupResult[]> {
  const params = new URLSearchParams({ contact });
  try {
    return await request(`/bookings/search?${params}`, {
      headers: otpToken ? { "X-OTP-Token": otpToken } : {},
      fallback: "No bookings found.",
    });
  } catch (e) {
    if (e instanceof ApiError && (e.status === 401 || e.status === 403)) throw new OtpRequiredError();
    throw e;
  }
}

/** Step 1: ask the API to send a one-time code (email, or WhatsApp for a phone number). */
export async function requestOtp(contact: string, turnstileToken?: string): Promise<{ channel: "email" | "whatsapp" }> {
  return request("/otp/request", jsonInit("POST", { contact, turnstileToken }, "Could not send a code."));
}

/** Step 2: exchange the code for a short-lived token that unlocks booking search for that contact. */
export async function verifyOtp(contact: string, code: string): Promise<string> {
  const res = await request("/otp/verify", jsonInit("POST", { contact, code }, "That code is incorrect or has expired."));
  return res.otpToken;
}

export interface ContactPayload {
  name: string;
  contact: string;
  interestedSport?: string;
  message?: string;
  turnstileToken?: string;
}

export async function submitContactEnquiry(payload: ContactPayload) {
  return request("/contact-enquiries", jsonInit("POST", payload, "Enquiry failed. Please check the details and try again."));
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
  return request("/corporate-enquiries", jsonInit("POST", payload, "Enquiry failed. Please check the details and try again."));
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
