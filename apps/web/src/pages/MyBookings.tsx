import { useState } from "react";
import { useSearchParams } from "react-router-dom";
import { lookupBooking, SPORT_LABELS, type BookingLookupResult } from "../lib/api";
import { PaymentPanel } from "../components/PaymentPanel";
import { PreOrderPanel } from "../components/PreOrderPanel";

const STATUS_LABEL: Record<string, string> = {
  pending: "Payment pending",
  confirmed: "Confirmed",
  cancelled: "Cancelled",
  completed: "Completed",
  no_show: "No-show",
};

export function MyBookings() {
  const [searchParams] = useSearchParams();
  const [ref, setRef] = useState(searchParams.get("ref") ?? "");
  const [contact, setContact] = useState("");
  const [status, setStatus] = useState<"idle" | "loading" | "found" | "error">("idle");
  const [error, setError] = useState("");
  const [result, setResult] = useState<BookingLookupResult | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!ref.trim() || !contact.trim()) return;
    setStatus("loading");
    setError("");
    try {
      const data = await lookupBooking(ref.trim().toUpperCase(), contact.trim());
      setResult(data);
      setStatus("found");
    } catch (err: any) {
      setStatus("error");
      setError(err?.message ?? "We couldn't find that booking.");
    }
  }

  return (
    <section id="my-bookings" className="section">
      <div className="section-heading">
        <p className="eyebrow">My bookings</p>
        <h2>Find your booking.</h2>
        <p>Enter your booking reference and the phone or email you booked with.</p>
      </div>

      <form className="lookup-form" onSubmit={submit}>
        <label>
          Booking ref
          <input value={ref} onChange={(e) => setRef(e.target.value)} placeholder="e.g. A1B2C3D4" required />
        </label>
        <label>
          Phone or email
          <input value={contact} onChange={(e) => setContact(e.target.value)} placeholder="10-digit mobile or email" required />
        </label>
        <button className="button primary" type="submit" disabled={status === "loading"}>
          {status === "loading" ? "Looking up…" : "Find my booking"}
        </button>
        {status === "error" && <p className="form-message error" data-testid="lookup-error">{error}</p>}
      </form>

      {status === "found" && result && (
        <div className="lookup-result">
          <p className="eyebrow">Ref: {result.bookingRef}</p>
          <h3>
            {SPORT_LABELS[result.sport] ?? result.sport} — {result.date}, {result.startTime}–{result.endTime}
            {result.slotCount > 1 && <span className="muted"> ({result.slotCount} slots)</span>}
          </h3>
          <p data-testid="lookup-status">Status: {STATUS_LABEL[result.status] ?? result.status}</p>

          {result.status === "pending" && result.paymentRequired && result.checkout && (
            <PaymentPanel
              bookingRef={result.bookingRef}
              checkout={result.checkout}
              amount={result.price ?? 0}
              customerName={result.name}
              customerContact={contact}
              onSuccess={() => setResult({ ...result, status: "confirmed", paymentRequired: false, checkout: null })}
            />
          )}

          {result.status === "confirmed" && (
            <>
              {result.price != null && (
                <p className="summary-total">Amount paid: ₹{result.price}</p>
              )}
              <PreOrderPanel bookingRef={result.bookingRef} contact={contact} />
            </>
          )}
        </div>
      )}
    </section>
  );
}
