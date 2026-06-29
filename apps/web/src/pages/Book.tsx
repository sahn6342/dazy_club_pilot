import React, { useCallback, useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import type { Slot } from "@dazy/shared";
import { createBooking, getNext7Days, getSlots, SPORT_LABELS, validatePromo, type PromoValidationResult } from "../lib/api";
import { validateName, validateContact, validatePlayers } from "../lib/validate";

type FormStatus = "idle" | "success" | "error";

interface BookingFields {
  name: string;
  contact: string;
  players: string;
  message: string;
}

interface FieldErrors {
  name?: string;
  contact?: string;
  players?: string;
}

export function Book() {
  const [searchParams] = useSearchParams();
  const initialSport = searchParams.get("sport") ?? "cricket";

  const days = getNext7Days();
  const [bookSport, setBookSport] = useState(SPORT_LABELS[initialSport] ? initialSport : "cricket");
  const [bookDate, setBookDate] = useState(days[0].iso);
  const [slots, setSlots] = useState<Slot[]>([]);
  const [slotsLoading, setSlotsLoading] = useState(false);
  const [slotsError, setSlotsError] = useState("");
  const [selectedSlot, setSelectedSlot] = useState<Slot | null>(null);
  const [bookingStatus, setBookingStatus] = useState<FormStatus>("idle");
  const [bookingRef, setBookingRef] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [promo, setPromo] = useState("");
  const [promoError, setPromoError] = useState("");
  const [promoStatus, setPromoStatus] = useState<"idle" | "checking" | "valid" | "invalid">("idle");
  const [promoResult, setPromoResult] = useState<PromoValidationResult | null>(null);
  const [bookedPrice, setBookedPrice] = useState<number | null>(null);
  const [bookedPromo, setBookedPromo] = useState<string | null>(null);

  const [fields, setFields] = useState<BookingFields>({ name: "", contact: "", players: "1", message: "" });
  const [errors, setErrors] = useState<FieldErrors>({});
  const [touched, setTouched] = useState<Record<keyof FieldErrors, boolean>>({ name: false, contact: false, players: false });

  const loadSlots = useCallback(() => {
    setSlotsLoading(true);
    setSlotsError("");
    getSlots(bookSport, bookDate)
      .then((data) => { setSlots(data); setSlotsLoading(false); })
      .catch((err) => { setSlotsError(err?.message ?? "Failed to load slots."); setSlotsLoading(false); });
  }, [bookSport, bookDate]);

  useEffect(() => {
    setSelectedSlot(null);
    setBookingStatus("idle");
    loadSlots();
  }, [loadSlots]);

  // Live promo validation — debounced 600ms, fires after 3+ chars
  useEffect(() => {
    const trimmed = promo.trim();
    if (!selectedSlot || trimmed.length < 3) {
      setPromoStatus("idle");
      setPromoResult(null);
      if (!trimmed) setPromoError("");
      return;
    }
    setPromoStatus("checking");
    const timer = setTimeout(async () => {
      try {
        const res = await validatePromo(trimmed, selectedSlot.sportSlug, selectedSlot.finalPrice);
        if (res.valid) {
          setPromoStatus("valid");
          setPromoResult(res);
          setPromoError("");
        } else {
          setPromoStatus("invalid");
          setPromoResult(null);
          setPromoError(res.error ?? "Invalid promo code.");
        }
      } catch {
        setPromoStatus("invalid");
        setPromoResult(null);
        setPromoError("Could not validate promo code.");
      }
    }, 600);
    return () => clearTimeout(timer);
  }, [promo, selectedSlot]);

  function onBlur(field: keyof FieldErrors) {
    setTouched((t) => ({ ...t, [field]: true }));
    validateFields({ ...fields, _touchField: field } as any);
  }

  function validateFields(vals: BookingFields): FieldErrors {
    const max = selectedSlot?.maxPlayers ?? 12;
    const errs: FieldErrors = {
      name: validateName(vals.name) ?? undefined,
      contact: validateContact(vals.contact) ?? undefined,
      players: validatePlayers(Number(vals.players), max) ?? undefined,
    };
    setErrors(errs);
    return errs;
  }

  function change(field: keyof BookingFields, value: string) {
    const next = { ...fields, [field]: value };
    setFields(next);
    if (touched[field as keyof FieldErrors]) {
      validateFields(next);
    }
  }

  async function submitBooking(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedSlot) return;

    // Mark all fields touched and validate
    setTouched({ name: true, contact: true, players: true });
    const errs = validateFields(fields);
    if (Object.values(errs).some(Boolean)) return;

    setSubmitting(true);
    setPromoError("");
    try {
      const result = await createBooking({
        name: fields.name.trim(),
        contact: fields.contact.trim(),
        slotId: selectedSlot.id,
        sportSlug: selectedSlot.sportSlug,
        date: selectedSlot.date,
        startTime: selectedSlot.startTime,
        players: Number(fields.players),
        promoCode: promo.trim() || undefined,
        message: fields.message.trim(),
      });
      setBookingRef(result.bookingRef);
      setBookedPrice(result.price ?? null);
      setBookedPromo(result.promoCode ?? null);
      setBookingStatus("success");
      loadSlots();
    } catch (err: any) {
      const msg = err?.message ?? "Booking failed.";
      // Promo-specific failures come back as 400 with a "promo" message — show inline.
      if (/promo/i.test(msg)) {
        setPromoError(msg);
      } else {
        setBookingStatus("error");
        loadSlots();
      }
    } finally {
      setSubmitting(false);
    }
  }

  const selectedDay = days.find((d) => d.iso === bookDate);

  return (
    <section id="book" className="section">
      <div className="section-heading">
        <p className="eyebrow">Book a court</p>
        <h2>Pick your sport, date, and slot.</h2>
        <p>Select an available slot below and confirm your booking.</p>
      </div>

      <div className="sport-tabs" role="tablist">
        {Object.entries(SPORT_LABELS).map(([slug, label]) => (
          <button
            key={slug}
            role="tab"
            className={`tab-btn${bookSport === slug ? " active" : ""}`}
            onClick={() => setBookSport(slug)}
          >
            {label}
          </button>
        ))}
      </div>

      <div className="date-pills" role="group" aria-label="Select date">
        {days.map((d) => (
          <button
            key={d.iso}
            className={`date-pill${bookDate === d.iso ? " active" : ""}`}
            onClick={() => setBookDate(d.iso)}
          >
            {d.short}
          </button>
        ))}
      </div>

      <div className="slot-section">
        <p className="slot-heading">
          {SPORT_LABELS[bookSport]} — {selectedDay?.label}
        </p>
        {slotsLoading ? (
          <p className="slot-loading">Loading slots…</p>
        ) : slotsError ? (
          <p className="slot-loading" style={{ color: "var(--color-error, #f87171)" }}>{slotsError}</p>
        ) : slots.length === 0 ? (
          <p className="slot-loading">No slots available for this selection.</p>
        ) : (
          <div className="slot-grid">
            {slots.map((slot) => (
              <button
                key={slot.id}
                disabled={!slot.available}
                className={`slot-chip${!slot.available ? " unavailable" : ""}${selectedSlot?.id === slot.id ? " selected" : ""}`}
                onClick={() => {
                  if (slot.available) {
                    setSelectedSlot(slot);
                    setBookingStatus("idle");
                    setFields((f) => ({ ...f, players: "1" }));
                    setErrors({});
                    setPromo("");
                    setPromoError("");
                    setPromoStatus("idle");
                    setPromoResult(null);
                    setTouched({ name: false, contact: false, players: false });
                  }
                }}
                title={slot.available ? `${slot.startTime}–${slot.endTime}, up to ${slot.maxPlayers} players` : "Already booked"}
              >
                {slot.startTime}
                {slot.finalPrice != null ? (
                  <span className="slot-price" data-testid="slot-price">
                    {slot.discountPercent ? (
                      <>
                        <s className="slot-price-strike">₹{slot.price}</s> ₹{slot.finalPrice}
                        <span className="slot-discount-badge">-{slot.discountPercent}%</span>
                      </>
                    ) : (
                      <>₹{slot.finalPrice}</>
                    )}
                  </span>
                ) : (
                  slot.price == null && <span className="slot-price">Free</span>
                )}
                {!slot.available && <span className="slot-booked-tag">Booked</span>}
              </button>
            ))}
          </div>
        )}
      </div>

      {selectedSlot && bookingStatus !== "success" && (
        <div className="booking-form-wrap">
          <div className="booking-summary">
            <span className="eyebrow">Selected slot</span>
            <strong>
              {SPORT_LABELS[selectedSlot.sportSlug]} &nbsp;·&nbsp; {selectedDay?.label} &nbsp;·&nbsp;
              {selectedSlot.startTime}–{selectedSlot.endTime}
            </strong>
            <span className="muted">Up to {selectedSlot.maxPlayers} players</span>
            {selectedSlot.finalPrice != null && (
              <span className="summary-total" data-testid="summary-total">
                Total: ₹{selectedSlot.finalPrice}
                {selectedSlot.discountPercent ? <span className="muted"> (was ₹{selectedSlot.price})</span> : null}
              </span>
            )}
          </div>
          <form className="form-card" onSubmit={submitBooking} noValidate>
            <div className="field-group">
              <label>
                Name
                <input
                  value={fields.name}
                  onChange={(e) => change("name", e.target.value)}
                  onBlur={() => onBlur("name")}
                  className={touched.name && errors.name ? "input-error" : ""}
                  placeholder="Your full name"
                />
              </label>
              {touched.name && errors.name && <p className="field-error">{errors.name}</p>}
            </div>

            <div className="field-group">
              <label>
                Phone or email
                <input
                  value={fields.contact}
                  onChange={(e) => change("contact", e.target.value)}
                  onBlur={() => onBlur("contact")}
                  className={touched.contact && errors.contact ? "input-error" : ""}
                  placeholder="10-digit mobile or email"
                />
              </label>
              {touched.contact && errors.contact && <p className="field-error">{errors.contact}</p>}
            </div>

            <div className="field-group">
              <label>
                Number of players
                <input
                  type="number"
                  min="1"
                  max={selectedSlot.maxPlayers}
                  value={fields.players}
                  onChange={(e) => change("players", e.target.value)}
                  onBlur={() => onBlur("players")}
                  className={touched.players && errors.players ? "input-error" : ""}
                />
              </label>
              {touched.players && errors.players && <p className="field-error">{errors.players}</p>}
            </div>

            <div className="field-group promo-row">
              <label>
                Promo code (optional)
                <input
                  value={promo}
                  onChange={(e) => { setPromo(e.target.value.toUpperCase()); setPromoError(""); }}
                  className={`promo-input${promoStatus === "valid" ? " input-valid" : promoError ? " input-error" : ""}`}
                  placeholder="e.g. WELCOME10"
                  data-testid="promo-input"
                />
              </label>
              {promoStatus === "checking" && (
                <p className="promo-feedback checking" data-testid="promo-checking">Checking…</p>
              )}
              {promoStatus === "valid" && promoResult && (
                <p className="promo-feedback valid" data-testid="promo-valid">
                  ✓ {promoResult.code} applied
                  {promoResult.discountedAmount != null && selectedSlot?.finalPrice != null && (
                    <>
                      {" — "}
                      <s className="promo-original">₹{selectedSlot.finalPrice}</s>
                      {" → "}
                      <strong data-testid="promo-discounted-price">₹{promoResult.discountedAmount}</strong>
                      {promoResult.savedAmount != null && (
                        <span className="promo-saving"> (save ₹{promoResult.savedAmount})</span>
                      )}
                    </>
                  )}
                </p>
              )}
              {promoError && <p className="field-error" data-testid="promo-error">{promoError}</p>}
            </div>

            <label>Message (optional) <textarea value={fields.message} onChange={(e) => change("message", e.target.value)} rows={3} /></label>

            <button className="button primary" type="submit" disabled={submitting}>
              {submitting ? "Confirming…" : "Confirm booking"}
            </button>
            {bookingStatus === "error" && (
              <p className="form-message error">Booking failed. Slot may have just been taken. Please choose another.</p>
            )}
          </form>
        </div>
      )}

      {bookingStatus === "success" && (
        <div className="booking-confirmed">
          <p className="eyebrow">Booking confirmed</p>
          <h3>You're booked in!</h3>
          <p>
            <strong>Ref: {bookingRef}</strong> &nbsp;—&nbsp;
            {SPORT_LABELS[selectedSlot!.sportSlug]}, {selectedDay?.label}, {selectedSlot!.startTime}–{selectedSlot!.endTime}
          </p>
          {bookedPrice != null && (
            <p className="summary-total" data-testid="confirmed-amount">
              Amount paid: ₹{bookedPrice}
              {bookedPromo && <span className="muted"> — promo {bookedPromo}</span>}
            </p>
          )}
          <p>We'll reach out to confirm details. Save your reference number.</p>
          <button
            className="button secondary"
            onClick={() => {
              setSelectedSlot(null);
              setBookingStatus("idle");
              setBookingRef("");
              setFields({ name: "", contact: "", players: "1", message: "" });
              setErrors({});
              setPromo("");
              setPromoError("");
              setPromoStatus("idle");
              setPromoResult(null);
              setBookedPrice(null);
              setBookedPromo(null);
              setTouched({ name: false, contact: false, players: false });
            }}
          >
            Book another slot
          </button>
        </div>
      )}
    </section>
  );
}
