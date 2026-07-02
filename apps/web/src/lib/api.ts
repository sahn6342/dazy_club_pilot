import type { Slot } from "@dazy/shared";

const API = (import.meta as any).env?.VITE_API_BASE_URL ?? "http://localhost:8000/api/v1";

// API origin without /api/v1 — resolves relative /media image paths to absolute URLs.
export const API_ORIGIN = API.replace(/\/api\/v1\/?$/, "");

export function resolveImg(url: string | null | undefined): string {
  if (!url) return "";
  return /^https?:\/\//.test(url) ? url : `${API_ORIGIN}${url}`;
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
    throw new Error(err.detail ?? "Booking failed");
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
    throw new Error(err.detail ?? "Payment verification failed");
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
