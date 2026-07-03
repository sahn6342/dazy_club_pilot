import type { Slot } from "@dazy/shared";

const API = (import.meta as any).env?.VITE_API_BASE_URL ?? "http://localhost:8000/api/v1";

// API origin without /api/v1 — resolves relative /media image paths to absolute URLs.
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
}

export async function lookupBooking(ref: string, contact: string): Promise<BookingLookupResult> {
  const params = new URLSearchParams({ ref, contact });
  const r = await fetch(`${API}/bookings/lookup?${params}`);
  if (!r.ok) {
    const err = await r.json().catch(() => ({ detail: "Booking not found." }));
    throw new Error(errorMessage(err, "Booking not found."));
  }
  return r.json();
}

export interface ContactPayload {
  name: string;
  contact: string;
  interestedSport?: string;
  message?: string;
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
  badminton: "Badminton",
  pickleball: "Pickleball",
};

export function getNext7Days(): { iso: string; label: string; short: string }[] {
  return Array.from({ length: 7 }, (_, i) => {
    const d = new Date();
    d.setDate(d.getDate() + i);
    const iso = d.toISOString().split("T")[0];
    const label = d.toLocaleDateString("en-IN", { weekday: "short", day: "numeric", month: "short" });
    const short = d.toLocaleDateString("en-IN", { weekday: "short", day: "numeric" });
    return { iso, label, short };
  });
}

export function todayIso(): string {
  return new Date().toISOString().split("T")[0];
}
