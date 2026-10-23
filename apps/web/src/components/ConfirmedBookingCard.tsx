import { useState } from "react";
import { Link } from "react-router-dom";

/** Everything the confirmation card shows. Kept by the Book page for the rest of the visit. */
export interface ConfirmedBooking {
  ref: string;
  sportLabel: string;
  dateLabel: string;
  start: string;
  end: string;
  slotCount: number;
  price: number | null;
  promo: string | null;
  gstRate: number | null;
  gstAmount: number | null;
  /** What was paid online. Differs from `price` (the total) when only the advance was paid. */
  amountPaid: number | null;
  /** Still to pay at the venue after an advance payment; 0 when paid in full. */
  balanceDue: number;
  /** The non-refundable advance, when the advance option was chosen. */
  advance: number | null;
  contact: string;
}

async function copyText(text: string): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    // Clipboard API unavailable (insecure origin, old browser): fall back to a temporary selection.
    try {
      const ta = document.createElement("textarea");
      ta.value = text;
      ta.setAttribute("readonly", "");
      ta.style.position = "fixed";
      ta.style.opacity = "0";
      document.body.appendChild(ta);
      ta.select();
      const ok = document.execCommand("copy");
      document.body.removeChild(ta);
      return ok;
    } catch {
      return false;
    }
  }
}

/** Compact confirmation that stays above the slot picker, so the visitor can keep booking while keeping the ref. */
export function ConfirmedBookingCard({ booking }: { booking: ConfirmedBooking }) {
  const [copied, setCopied] = useState<"idle" | "yes" | "no">("idle");

  async function copy() {
    setCopied((await copyText(booking.ref)) ? "yes" : "no");
    window.setTimeout(() => setCopied("idle"), 2500);
  }

  return (
    <div className="booking-confirmed confirmed-card" data-testid="confirmed-card">
      <p className="eyebrow">Booking confirmed</p>
      <h3>You're booked in!</h3>

      <div className="ref-box">
        <span className="ref-label">Your booking ID</span>
        <strong className="ref-value" data-testid="booking-ref">{booking.ref}</strong>
        <button type="button" className="button secondary small" data-testid="copy-ref" onClick={copy}>
          {copied === "yes" ? "Copied ✓" : copied === "no" ? "Press and hold to copy" : "Copy"}
        </button>
      </div>

      <p className="screenshot-note" data-testid="screenshot-note" role="note">
        📸 Take a screenshot or note down this booking ID now. You'll need it to look up your booking.
      </p>

      <p>
        {booking.sportLabel}, {booking.dateLabel}, {booking.start}–{booking.end}
        {booking.slotCount > 1 && <span className="muted"> &nbsp;({booking.slotCount} slots)</span>}
      </p>
      {booking.price != null && (
        <p className="summary-total" data-testid="confirmed-amount">
          Amount paid: ₹{booking.amountPaid ?? booking.price}
          {booking.promo && <span className="muted"> — promo {booking.promo}</span>}
        </p>
      )}
      {booking.balanceDue > 0 && (
        <p className="balance-note" data-testid="confirmed-balance" role="note">
          Balance to pay at the venue: <strong>₹{booking.balanceDue}</strong> (total ₹{booking.price}).
          {booking.advance != null && <> The ₹{booking.advance} advance is non-refundable.</>}
        </p>
      )}
      {booking.gstAmount != null && booking.gstRate != null && (
        <p className="gst-note muted" style={{ fontSize: "0.85em" }}>
          {booking.balanceDue > 0 ? `The total of ₹${booking.price} includes` : "Includes"} GST ({booking.gstRate}%): ₹{booking.gstAmount.toFixed(2)}
        </p>
      )}
      <p className="muted" style={{ fontSize: "0.85em" }}>
        Look it up any time in <Link to="/my-bookings">My Bookings</Link> with this ID and your phone or email.
      </p>
    </div>
  );
}
