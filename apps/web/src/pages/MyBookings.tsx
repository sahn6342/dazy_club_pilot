import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import {
  lookupBooking, searchBookingsByContact, requestOtp, verifyOtp, getPublicConfig, OtpRequiredError, TURNSTILE_SITE_KEY,
  SPORT_LABELS, type BookingLookupResult,
} from "../lib/api";
import { Turnstile } from "../components/Turnstile";
import { validateContact } from "../lib/validate";
import { PaymentPanel } from "../components/PaymentPanel";

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

  // Contact-only search is gated by a one-time code (email, or WhatsApp for a phone number),
  // so knowing someone's number is not enough to list their bookings.
  const [otpStage, setOtpStage] = useState<"idle" | "code">("idle");
  const [otpChannel, setOtpChannel] = useState<"email" | "whatsapp">("email");
  const [otpContact, setOtpContact] = useState("");
  const [otpToken, setOtpToken] = useState<string | null>(null);
  // Whether the API wants a code for contact-only search (GET /public-config). null = still loading.
  const [otpNeeded, setOtpNeeded] = useState<boolean | null>(null);
  useEffect(() => {
    let alive = true;
    getPublicConfig().then((c) => { if (alive) setOtpNeeded(c.otpRequired); });
    return () => { alive = false; };
  }, []);
  const [code, setCode] = useState("");
  const [tsToken, setTsToken] = useState<string | null>(null);
  const [tsReset, setTsReset] = useState(0);

  function resetOtp() {
    setOtpStage("idle");
    setOtpToken(null);
    setOtpContact("");
    setCode("");
  }

  async function runSearch(contactValue: string, token: string) {
    try {
      const list = await searchBookingsByContact(contactValue, token);
      setResultList(list);
      setStatus("list");
    } catch (err: any) {
      if (err instanceof OtpRequiredError) {
        resetOtp(); // token expired: start over
        setStatus("error");
        setError("Your verification expired. Please request a new code.");
      } else {
        setStatus("error");
        setError(err?.message ?? "No bookings found.");
      }
    }
  }

  async function sendCode() {
    if (TURNSTILE_SITE_KEY && !tsToken) {
      setStatus("error");
      setError("Please complete the verification challenge first.");
      return;
    }
    try {
      const { channel } = await requestOtp(contact.trim(), tsToken ?? undefined);
      setOtpChannel(channel);
      setOtpContact(contact.trim());
      setOtpStage("code");
      setCode("");
      setStatus("idle");
    } catch (err: any) {
      setStatus("error");
      setError(err?.message ?? "Could not send a code.");
    } finally {
      setTsReset((n) => n + 1);
    }
  }

  async function submitCode(e: React.FormEvent) {
    e.preventDefault();
    if (!/^\d{6}$/.test(code.trim())) { setError("Enter the 6-digit code."); setStatus("error"); return; }
    setStatus("loading");
    setError("");
    try {
      const token = await verifyOtp(otpContact, code.trim());
      setOtpToken(token);
      await runSearch(otpContact, token);
    } catch (err: any) {
      setStatus("error");
      setError(err?.message ?? "That code is incorrect or has expired.");
    }
  }

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
        // Contact only → list all bookings for this phone/email (newest first). The API says up front
        // (GET /public-config) whether a one-time code is needed; if that changed since the page loaded it
        // still answers "otp_required", and we switch to the code flow.
        if (otpToken && otpContact === contact.trim()) {
          await runSearch(contact.trim(), otpToken);
        } else if (otpNeeded !== false) {
          await sendCode();
        } else {
          try {
            const list = await searchBookingsByContact(contact.trim());
            setResultList(list);
            setStatus("list");
          } catch (err: any) {
            if (!(err instanceof OtpRequiredError)) throw err;
            setOtpNeeded(true);
            await sendCode();
          }
        }
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
              onChange={(e) => { setContact(e.target.value); setContactError(""); if (e.target.value.trim() !== otpContact) resetOtp(); }}
              placeholder="10-digit mobile or email"
              className={contactError ? "input-error" : ""}
            />
          </label>
          {contactError && <p className="field-error">{contactError}</p>}
        </div>

        <p className="muted" style={{ fontSize: "0.82rem", marginBottom: "0.5rem" }}>
          Enter either — or both for a more specific result.
        </p>

        {otpNeeded === true && otpStage === "idle" && !ref.trim() && contact.trim() && <Turnstile onToken={setTsToken} resetKey={tsReset} />}

        <button className="button primary" type="submit" disabled={status === "loading" || otpStage === "code" || (otpNeeded === null && !ref.trim() && !!contact.trim())}>
          {status === "loading" ? "Looking up…" : otpNeeded === true && !ref.trim() && contact.trim() ? "Send me a code" : "Find my booking"}
        </button>

        {otpStage === "code" && (
          <div className="otp-step" data-testid="otp-step" style={{ marginTop: "1rem" }}>
            <p className="muted" style={{ fontSize: "0.85rem" }}>
              We sent a 6-digit code to your {otpChannel === "email" ? "email" : "WhatsApp"} ({otpContact}). It is valid for 10 minutes.
            </p>
            <label>
              Verification code
              <input
                data-testid="otp-code"
                inputMode="numeric"
                autoComplete="one-time-code"
                maxLength={6}
                value={code}
                onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))}
                placeholder="123456"
              />
            </label>
            <button className="button primary" type="button" data-testid="otp-verify" onClick={submitCode} disabled={status === "loading"}>
              Verify and show my bookings
            </button>{" "}
            <button className="button" type="button" onClick={resetOtp}>Use a different contact</button>
          </div>
        )}

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

          {result.status === "confirmed" && result.price != null && (
            <p className="summary-total">Amount paid: ₹{result.price}</p>
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
