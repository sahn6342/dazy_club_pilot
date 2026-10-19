import { useState } from "react";
import { useSearchParams } from "react-router-dom";
import { lookupBooking, searchBookingsByContact, SPORT_LABELS, type BookingLookupResult } from "../lib/api";
import { validateContact } from "../lib/validate";
import { PaymentPanel } from "../components/PaymentPanel";
import { PreOrderPanel } from "../components/PreOrderPanel";

type PageStatus = "idle" | "loading" | "found" | "list" | "error";

const STATUS_LABEL: Record<string, string> = {
  pending: "Payment pending",
  confirmed: "Confirmed",
  cancelled: "Cancelled",
  completed: "Completed",
  no_show: "No-show",
};

const STATUS_CLASS: Record<string, string> = {
  pending: "status-pending",
  confirmed: "status-confirmed",
  cancelled: "status-cancelled",
  completed: "status-confirmed",
  no_show: "status-cancelled",
};

export function MyBookings() {
  const [searchParams] = useSearchParams();
  const [ref, setRef] = useState(searchParams.get("ref") ?? "");
  const [contact, setContact] = useState("");
  const [refError, setRefError] = useState("");
  const [contactError, setContactError] = useState("");
  const [status, setStatus] = useState<PageStatus>("idle");
  const [error, setError] = useState("");
  const [result, setResult] = useState<BookingLookupResult | null>(null);
  const [resultList, setResultList] = useState<BookingLookupResult[]>([]);

  function validate(): boolean {
    const hasRef = ref.trim().length > 0;
    const hasContact = contact.trim().length > 0;
    let ok = true;

    if (!hasRef && !hasContact) {
      setRefError("Enter at least one field.");
      setContactError("");
      return false;
    }
    setRefError("");

    if (hasContact) {
      const err = validateContact(contact.trim());
      if (err) { setContactError(err); ok = false; } else setContactError("");
    } else {
      setContactError("");
    }
    return ok;
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!validate()) return;

    const hasRef = ref.trim().length > 0;
    const hasContact = contact.trim().length > 0;

    setStatus("loading");
    setError("");
    setResult(null);
    setResultList([]);

    try {
      if (hasContact && !hasRef) {
        // Contact only → list all bookings for this phone/email.
        const list = await searchBookingsByContact(contact.trim());
        setResultList(list);
        setStatus("list");
      } else {
        // Ref only, or ref + contact → single booking.
        const data = await lookupBooking(
          ref.trim().toUpperCase(),
          hasContact ? contact.trim() : undefined,
        );
        setResult(data);
        setStatus("found");
      }
    } catch (err: any) {
      setStatus("error");
      setError(err?.message ?? "We couldn't find that booking.");
    }
  }

  function selectFromList(item: BookingLookupResult) {
    // Pre-fill ref and re-fetch with both fields so PaymentPanel is available.
    setRef(item.bookingRef);
    setStatus("loading");
    setError("");
    setResult(null);
    lookupBooking(item.bookingRef, contact.trim() || undefined)
      .then((data) => { setResult(data); setStatus("found"); })
      .catch((err: any) => { setStatus("error"); setError(err?.message ?? "Could not load booking."); });
  }

  return (
    <section id="my-bookings" className="section">
      <div className="section-heading">
        <p className="eyebrow">My bookings</p>
        <h2>Find your booking.</h2>
        <p>Enter your booking reference, phone number, or email — or any combination.</p>
      </div>

      <form className="lookup-form" onSubmit={submit} noValidate>
        <div className="field-group">
          <label>
            Booking reference <span className="muted" style={{ fontWeight: 400 }}>(optional)</span>
            <input
              value={ref}
              onChange={(e) => { setRef(e.target.value); setRefError(""); }}
              placeholder="e.g. A1B2C3D4"
              className={refError ? "input-error" : ""}
              autoCapitalize="characters"
            />
          </label>
          {refError && <p className="field-error">{refError}</p>}
        </div>

        <div className="field-group">
          <label>
            Phone or email <span className="muted" style={{ fontWeight: 400 }}>(optional)</span>
            <input
              value={contact}
              onChange={(e) => { setContact(e.target.value); setContactError(""); }}
              placeholder="10-digit mobile or email"
              className={contactError ? "input-error" : ""}
            />
          </label>
          {contactError && <p className="field-error">{contactError}</p>}
        </div>

        <p className="muted" style={{ fontSize: "0.82rem", marginBottom: "0.5rem" }}>
          Enter either — or both for a more specific result.
        </p>

        <button className="button primary" type="submit" disabled={status === "loading"}>
          {status === "loading" ? "Looking up…" : "Find my booking"}
        </button>

        {status === "error" && (
          <p className="form-message error" data-testid="lookup-error">{error}</p>
        )}
      </form>

      {/* Single booking result */}
      {status === "found" && result && (
        <div className="lookup-result">
          <p className="eyebrow">Ref: {result.bookingRef}</p>
          <h3>
            {SPORT_LABELS[result.sport] ?? result.sport} — {result.date}, {result.startTime}–{result.endTime}
            {result.slotCount > 1 && <span className="muted"> ({result.slotCount} slots)</span>}
          </h3>
          <p data-testid="lookup-status">
            Status: <span className={STATUS_CLASS[result.status]}>{STATUS_LABEL[result.status] ?? result.status}</span>
          </p>

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

          {result.status === "pending" && result.paymentRequired && !result.checkout && (
            <p className="muted" style={{ marginTop: "0.75rem" }}>
              To complete payment, enter your booking ref and phone or email together.
            </p>
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

      {/* List result (contact-only search) */}
      {status === "list" && resultList.length > 0 && (
        <div className="lookup-result">
          <p className="eyebrow">{resultList.length} booking{resultList.length > 1 ? "s" : ""} found</p>
          <div className="booking-list">
            {resultList.map((item) => (
              <div key={item.bookingRef} className="booking-list-card">
                <div className="booking-list-card-body">
                  <strong>
                    {SPORT_LABELS[item.sport] ?? item.sport} — {item.date}, {item.startTime}–{item.endTime}
                    {item.slotCount > 1 && <span className="muted"> ({item.slotCount} slots)</span>}
                  </strong>
                  <span className="muted" style={{ fontSize: "0.82rem" }}>Ref: {item.bookingRef}</span>
                  <span className={`status-badge ${STATUS_CLASS[item.status]}`}>
                    {STATUS_LABEL[item.status] ?? item.status}
                  </span>
                </div>
                <button
                  className="button secondary"
                  style={{ whiteSpace: "nowrap" }}
                  onClick={() => selectFromList(item)}
                >
                  {item.paymentRequired ? "Pay now" : "View"}
                </button>
              </div>
            ))}
          </div>
        </div>
      )}
    </section>
  );
}
