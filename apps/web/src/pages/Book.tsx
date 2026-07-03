import React, { useCallback, useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import type { Slot } from "@dazy/shared";
import { createBooking, getNext7Days, getSlots, SPORT_LABELS, validatePromo, type CheckoutConfig, type PromoValidationResult } from "../lib/api";
import { validateName, validateContact, validatePlayers } from "../lib/validate";
import { PaymentPanel } from "../components/PaymentPanel";
import { PreOrderPanel } from "../components/PreOrderPanel";

type FormStatus = "idle" | "payment" | "success" | "error";

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

function totalFinalPrice(slots: Slot[]): number | null {
  if (slots.length === 0) return null;
  if (slots.every((s) => s.finalPrice == null)) return null;
  return slots.reduce((sum, s) => sum + (s.finalPrice ?? 0), 0);
}

function formatDuration(slots: Slot[]): string {
  if (slots.length <= 1) return "";
  const [fh, fm] = slots[0].startTime.split(":").map(Number);
  const [eh, em] = slots[slots.length - 1].endTime.split(":").map(Number);
  const totalMin = eh * 60 + em - (fh * 60 + fm);
  const h = Math.floor(totalMin / 60);
  const m = totalMin % 60;
  if (h === 0) return `${m} min`;
  if (m === 0) return `${h} hr`;
  return `${h} hr ${m} min`;
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
  const [selectedCourtId, setSelectedCourtId] = useState<string>("all");

  const [selectedSlots, setSelectedSlots] = useState<Slot[]>([]);
  const [bookingStatus, setBookingStatus] = useState<FormStatus>("idle");
  const [bookingRef, setBookingRef] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const [promo, setPromo] = useState("");
  const [promoError, setPromoError] = useState("");
  const [promoStatus, setPromoStatus] = useState<"idle" | "checking" | "valid" | "invalid">("idle");
  const [promoResult, setPromoResult] = useState<PromoValidationResult | null>(null);

  const [bookedPrice, setBookedPrice] = useState<number | null>(null);
  const [bookedPromo, setBookedPromo] = useState<string | null>(null);
  const [bookedStartTime, setBookedStartTime] = useState("");
  const [bookedEndTime, setBookedEndTime] = useState("");
  const [bookedSlotCount, setBookedSlotCount] = useState(1);
  const [pendingCheckout, setPendingCheckout] = useState<CheckoutConfig | null>(null);

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
    setSelectedSlots([]);
    setBookingStatus("idle");
    setSelectedCourtId("all");
    setPendingCheckout(null);
    loadSlots();
  }, [loadSlots]);

  // Derived: total price across all selected slots.
  const slotTotal = totalFinalPrice(selectedSlots);
  const firstSlot = selectedSlots[0] ?? null;
  const lastSlot = selectedSlots[selectedSlots.length - 1] ?? null;

  // Live promo validation — debounced 600ms, fires after 3+ chars.
  useEffect(() => {
    const trimmed = promo.trim();
    if (!firstSlot || trimmed.length < 3) {
      setPromoStatus("idle");
      setPromoResult(null);
      if (!trimmed) setPromoError("");
      return;
    }
    setPromoStatus("checking");
    const timer = setTimeout(async () => {
      try {
        const res = await validatePromo(trimmed, firstSlot.sportSlug, slotTotal);
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
  }, [promo, firstSlot, slotTotal]);

  function onBlur(field: keyof FieldErrors) {
    setTouched((t) => ({ ...t, [field]: true }));
    validateFields({ ...fields, _touchField: field } as any);
  }

  function validateFields(vals: BookingFields): FieldErrors {
    const max = firstSlot?.maxPlayers ?? 12;
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

  function handleSlotClick(slot: Slot) {
    if (!slot.available) return;
    // A pending payment or a just-confirmed booking must not be silently
    // abandoned by an accidental tap on another slot — only "Book another
    // slot" (which explicitly resets everything) should exit these states.
    if (bookingStatus === "payment" || bookingStatus === "success") return;

    setBookingStatus("idle");

    if (selectedSlots.length === 0) {
      setSelectedSlots([slot]);
      return;
    }

    const last = selectedSlots[selectedSlots.length - 1];

    // Clicking the last selected slot trims it off.
    if (slot.id === last.id) {
      const next = selectedSlots.slice(0, -1);
      setSelectedSlots(next);
      if (next.length === 0) {
        setPromo(""); setPromoError(""); setPromoStatus("idle"); setPromoResult(null);
        setErrors({}); setTouched({ name: false, contact: false, players: false });
      }
      return;
    }

    // Extend if adjacent to the last selected slot on the same court.
    if (slot.startTime === last.endTime && slot.courtId === last.courtId) {
      setSelectedSlots([...selectedSlots, slot]);
      return;
    }

    // Start a fresh selection.
    setSelectedSlots([slot]);
    setFields((f) => ({ ...f, players: "1" }));
    setErrors({});
    setPromo(""); setPromoError(""); setPromoStatus("idle"); setPromoResult(null);
    setTouched({ name: false, contact: false, players: false });
  }

  async function submitBooking(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!firstSlot) return;

    setTouched({ name: true, contact: true, players: true });
    const errs = validateFields(fields);
    if (Object.values(errs).some(Boolean)) return;

    setSubmitting(true);
    setPromoError("");
    try {
      const result = await createBooking({
        name: fields.name.trim(),
        contact: fields.contact.trim(),
        slotIds: selectedSlots.map((s) => s.id),
        slotId: firstSlot.id,
        sportSlug: firstSlot.sportSlug,
        date: firstSlot.date,
        startTime: firstSlot.startTime,
        players: Number(fields.players),
        promoCode: promo.trim() || undefined,
        message: fields.message.trim(),
      });
      setBookingRef(result.bookingRef);
      setBookedPrice(result.price ?? null);
      setBookedPromo(result.promoCode ?? null);
      setBookedStartTime(result.startTime ?? firstSlot.startTime);
      setBookedEndTime(result.endTime ?? lastSlot!.endTime);
      setBookedSlotCount(result.slotCount ?? selectedSlots.length);
      if (result.paymentRequired && result.checkout) {
        setPendingCheckout(result.checkout);
        setBookingStatus("payment");
      } else {
        setBookingStatus("success");
        loadSlots();
      }
    } catch (err: any) {
      const msg = err?.message ?? "Booking failed.";
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
  const duration = formatDuration(selectedSlots);

  // Unique courts present in the loaded slot list.
  const courtOptions: { id: string; name: string }[] = [];
  const seen = new Set<string>();
  for (const s of slots) {
    if (s.courtId && !seen.has(s.courtId)) {
      seen.add(s.courtId);
      courtOptions.push({ id: s.courtId, name: s.courtName ?? s.courtId });
    }
  }
  const multiCourt = courtOptions.length > 1;

  // Slots shown in the grid — filtered by the selected court pill.
  const displaySlots = multiCourt && selectedCourtId !== "all"
    ? slots.filter((s) => s.courtId === selectedCourtId)
    : slots;

  // Show court labels on chips only when "All courts" view is active.
  const showCourtLabel = multiCourt && selectedCourtId === "all";

  return (
    <section id="book" className="section">
      <div className="section-heading">
        <p className="eyebrow">Book a court</p>
        <h2>Pick your sport, date, and slot.</h2>
        <p>Select one or more consecutive slots and confirm your booking.</p>
      </div>

      <div className="sport-tabs" role="tablist">
        {Object.entries(SPORT_LABELS).map(([slug, label]) => (
          <button
            key={slug}
            role="tab"
            className={`tab-btn${bookSport === slug ? " active" : ""}`}
            disabled={bookingStatus === "payment" || bookingStatus === "success"}
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
            disabled={bookingStatus === "payment" || bookingStatus === "success"}
            onClick={() => setBookDate(d.iso)}
          >
            {d.short}
          </button>
        ))}
      </div>

      {multiCourt && (
        <div className="court-pills" role="group" aria-label="Select court">
          <button
            className={`court-pill${selectedCourtId === "all" ? " active" : ""}`}
            onClick={() => { setSelectedCourtId("all"); setSelectedSlots([]); }}
          >
            All courts
          </button>
          {courtOptions.map((c) => (
            <button
              key={c.id}
              className={`court-pill${selectedCourtId === c.id ? " active" : ""}`}
              onClick={() => { setSelectedCourtId(c.id); setSelectedSlots([]); }}
            >
              {c.name}
            </button>
          ))}
        </div>
      )}

      <div className="slot-section">
        <p className="slot-heading">
          {SPORT_LABELS[bookSport]} — {selectedDay?.label}
          {selectedSlots.length > 0 && (
            <span className="slot-range-badge">
              {firstSlot!.startTime}–{lastSlot!.endTime}
              {duration && <> &nbsp;·&nbsp; {duration}</>}
            </span>
          )}
        </p>
        {selectedSlots.length > 1 && (
          <p className="slot-hint">Tap the last selected slot to shorten. Tap an adjacent slot to extend.</p>
        )}
        {selectedSlots.length === 1 && (
          <p className="slot-hint">Tap the next adjacent slot to book multiple hours, or fill in the form below.</p>
        )}
        {slotsLoading ? (
          <p className="slot-loading">Loading slots…</p>
        ) : slotsError ? (
          <p className="slot-loading" style={{ color: "var(--color-error, #f87171)" }}>{slotsError}</p>
        ) : displaySlots.length === 0 ? (
          <p className="slot-loading">No slots available for this selection.</p>
        ) : (
          <div className="slot-grid">
            {displaySlots.map((slot) => {
              const isSelected = selectedSlots.some((s) => s.id === slot.id);
              const isFirst = firstSlot?.id === slot.id;
              const isLast = lastSlot?.id === slot.id;
              return (
                <button
                  key={slot.id}
                  disabled={!slot.available}
                  className={[
                    "slot-chip",
                    !slot.available ? "unavailable" : "",
                    isSelected ? "selected" : "",
                    isSelected && selectedSlots.length > 1 && isFirst ? "slot-range-start" : "",
                    isSelected && selectedSlots.length > 1 && isLast ? "slot-range-end" : "",
                  ].filter(Boolean).join(" ")}
                  onClick={() => handleSlotClick(slot)}
                  title={
                    slot.available
                      ? isLast && selectedSlots.length > 1
                        ? `Tap to remove this slot from your selection`
                        : `${slot.startTime}–${slot.endTime}, up to ${slot.maxPlayers} players`
                      : "Already booked"
                  }
                >
                  {slot.startTime}
                  {showCourtLabel && slot.courtName && (
                    <span className="slot-court-label">{slot.courtName}</span>
                  )}
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
              );
            })}
          </div>
        )}
      </div>

      {selectedSlots.length > 0 && bookingStatus !== "success" && bookingStatus !== "payment" && (
        <div className="booking-form-wrap">
          <div className="booking-summary">
            <span className="eyebrow">Selected slot{selectedSlots.length > 1 ? "s" : ""}</span>
            <strong>
              {SPORT_LABELS[firstSlot!.sportSlug]} &nbsp;·&nbsp; {selectedDay?.label} &nbsp;·&nbsp;
              {firstSlot!.startTime}–{lastSlot!.endTime}
              {duration && <span className="muted"> &nbsp;({duration})</span>}
              {firstSlot!.courtName && multiCourt && (
                <span className="muted"> &nbsp;· {firstSlot!.courtName}</span>
              )}
            </strong>
            <span className="muted">Up to {firstSlot!.maxPlayers} players</span>
            {slotTotal != null && (
              <span className="summary-total" data-testid="summary-total">
                Total: ₹{slotTotal}
                {selectedSlots.length > 1 && (
                  <span className="muted"> ({selectedSlots.length} slots)</span>
                )}
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
                  max={firstSlot!.maxPlayers}
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
                  maxLength={40}
                  data-testid="promo-input"
                />
              </label>
              {promoStatus === "checking" && (
                <p className="promo-feedback checking" data-testid="promo-checking">Checking…</p>
              )}
              {promoStatus === "valid" && promoResult && (
                <p className="promo-feedback valid" data-testid="promo-valid">
                  ✓ {promoResult.code} applied
                  {promoResult.discountedAmount != null && slotTotal != null && (
                    <>
                      {" — "}
                      <s className="promo-original">₹{slotTotal}</s>
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
              {submitting ? "Confirming…" : `Confirm booking${selectedSlots.length > 1 ? ` (${selectedSlots.length} slots)` : ""}`}
            </button>
            {bookingStatus === "error" && (
              <p className="form-message error">Booking failed. One or more slots may have just been taken. Please choose again.</p>
            )}
          </form>
        </div>
      )}

      {bookingStatus === "payment" && pendingCheckout && (
        <PaymentPanel
          bookingRef={bookingRef}
          checkout={pendingCheckout}
          amount={bookedPrice ?? 0}
          customerName={fields.name.trim()}
          customerContact={fields.contact.trim()}
          onSuccess={() => { setBookingStatus("success"); loadSlots(); }}
        />
      )}

      {bookingStatus === "success" && (
        <div className="booking-confirmed">
          <p className="eyebrow">Booking confirmed</p>
          <h3>You're booked in!</h3>
          <p>
            <strong>Ref: {bookingRef}</strong> &nbsp;—&nbsp;
            {SPORT_LABELS[firstSlot!.sportSlug]}, {selectedDay?.label}, {bookedStartTime}–{bookedEndTime}
            {bookedSlotCount > 1 && <span className="muted"> &nbsp;({bookedSlotCount} slots)</span>}
          </p>
          {bookedPrice != null && (
            <p className="summary-total" data-testid="confirmed-amount">
              Amount paid: ₹{bookedPrice}
              {bookedPromo && <span className="muted"> — promo {bookedPromo}</span>}
            </p>
          )}
          <p>We'll reach out to confirm details. Save your reference number.</p>
          <PreOrderPanel bookingRef={bookingRef} contact={fields.contact} />
          <button
            className="button secondary"
            onClick={() => {
              setSelectedSlots([]);
              setBookingStatus("idle");
              setBookingRef("");
              setFields({ name: "", contact: "", players: "1", message: "" });
              setErrors({});
              setPromo(""); setPromoError(""); setPromoStatus("idle"); setPromoResult(null);
              setBookedPrice(null); setBookedPromo(null);
              setBookedStartTime(""); setBookedEndTime(""); setBookedSlotCount(1);
              setPendingCheckout(null);
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
