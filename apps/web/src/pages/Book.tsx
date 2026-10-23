import React, { useCallback, useEffect, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import type { Slot } from "@dazy/shared";
import { Turnstile } from "../components/Turnstile";
import { ApiError, createBooking, getNext7Days, getPublicConfig, TURNSTILE_SITE_KEY, getSlots, SPORT_LABELS, validatePromo, type CheckoutConfig, type PaymentOption, type PromoValidationResult } from "../lib/api";
import { validateName, validateContact, validatePlayers } from "../lib/validate";
import { PaymentPanel } from "../components/PaymentPanel";
import { ConfirmedBookingCard, type ConfirmedBooking } from "../components/ConfirmedBookingCard";

type FormStatus = "idle" | "payment" | "error";

interface BookingFields {
  name: string;
  contact: string;
  email: string;
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
  let totalMin = eh * 60 + em - (fh * 60 + fm);
  if (totalMin <= 0) totalMin += 1440; // cross-midnight
  const h = Math.floor(totalMin / 60);
  const m = totalMin % 60;
  if (h === 0) return `${m} min`;
  if (m === 0) return `${h} hr`;
  return `${h} hr ${m} min`;
}

const SLOT_TAKEN_MESSAGE = "Booking failed. One or more slots may have just been taken. Please choose again.";

/** What to show for a failed booking, decided by the API's status and code, never by searching the text. */
function describeBookingError(err: unknown): { message: string; slotsTaken: boolean; promo: boolean } {
  if (err instanceof ApiError) {
    // `code` is what the API says happened. A server that predates the codes sends none; then fall back to the
    // HTTP status (409 / 404 on booking = the slot is gone, 400 = the promo) rather than any word in the message.
    const slotLost = err.code ? err.code === "slot_unavailable" || err.code === "slot_not_found" : err.status === 409 || err.status === 404;
    if (slotLost) return { message: SLOT_TAKEN_MESSAGE, slotsTaken: true, promo: false };
    const promoProblem = err.code ? err.code === "promo_invalid" : err.status === 400 && /promo/i.test(err.message);
    if (promoProblem) return { message: err.message, slotsTaken: false, promo: true };
    return { message: err.message, slotsTaken: false, promo: false }; // gateway down, rate limit, verification, network...
  }
  return { message: "Booking failed. Please try again.", slotsTaken: false, promo: false };
}

export function Book() {
  const [searchParams] = useSearchParams();
  const initialSport = searchParams.get("sport") ?? "cricket";

  const days = getNext7Days();
  const [tsToken, setTsToken] = useState<string | null>(null);
  const [tsReset, setTsReset] = useState(0);
  const [bookingError, setBookingError] = useState("");
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
  const [bookedGstRate, setBookedGstRate] = useState<number | null>(null);
  const [bookedGstAmount, setBookedGstAmount] = useState<number | null>(null);
  const [bookedStartTime, setBookedStartTime] = useState("");
  const [bookedEndTime, setBookedEndTime] = useState("");
  const [bookedSlotCount, setBookedSlotCount] = useState(1);
  const [pendingCheckout, setPendingCheckout] = useState<CheckoutConfig | null>(null);
  const [bookedAmountDue, setBookedAmountDue] = useState<number | null>(null);
  const [bookedBalanceDue, setBookedBalanceDue] = useState(0);

  // Advance option: pay only a fixed, non-refundable advance now and the rest at the venue.
  const [advanceAmount, setAdvanceAmount] = useState(0);
  const [payOption, setPayOption] = useState<PaymentOption>("full");
  useEffect(() => { getPublicConfig().then((c) => setAdvanceAmount(c.advanceAmount)); }, []);

  // Confirmed bookings of this visit stay on the page as compact cards (newest first) while the visitor keeps booking.
  const [confirmed, setConfirmed] = useState<ConfirmedBooking[]>([]);
  const confirmedTop = useRef<HTMLDivElement>(null);
  const pendingInfo = useRef<ConfirmedBooking | null>(null); // the booking being paid for, turned into a card on success
  // A payment the visitor walked away from: its slot stays held for 15 minutes and can be resumed from My Bookings.
  const [leftPayment, setLeftPayment] = useState<string | null>(null);

  const [fields, setFields] = useState<BookingFields>({ name: "", contact: "", email: "", players: "1", message: "" });
  const [errors, setErrors] = useState<FieldErrors>({});
  const [touched, setTouched] = useState<Record<keyof FieldErrors, boolean>>({ name: false, contact: false, players: false });

  // Only the newest slots request may update the page: switching sport or date quickly must not let a slower,
  // older response overwrite the newer one.
  const slotsRequest = useRef(0);
  const loadSlots = useCallback(() => {
    const mine = ++slotsRequest.current;
    setSlotsLoading(true);
    setSlotsError("");
    getSlots(bookSport, bookDate)
      .then((data) => { if (mine === slotsRequest.current) { setSlots(data); setSlotsLoading(false); } })
      .catch((err) => { if (mine === slotsRequest.current) { setSlotsError(err?.message ?? "Failed to load slots."); setSlotsLoading(false); } });
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
  // What the customer would pay in total: the promo-discounted amount when a promo is applied.
  const payableTotal = promoStatus === "valid" && promoResult?.discountedAmount != null ? promoResult.discountedAmount : slotTotal;
  const advanceOffered = advanceAmount > 0 && payableTotal != null && payableTotal > advanceAmount;
  const chosenOption: PaymentOption = advanceOffered ? payOption : "full";

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
      } catch (err) {
        setPromoResult(null);
        if (err instanceof ApiError && err.isOutage) {
          // The check itself failed (server or network), so the code is not known to be wrong.
          setPromoStatus("idle");
          setPromoError("Couldn't check the promo code right now. You can still book and try it again.");
        } else {
          setPromoStatus("invalid");
          setPromoError("Could not validate promo code.");
        }
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
    // Tapping another slot while a payment is pending leaves that payment step (it can be resumed from My Bookings).
    if (bookingStatus === "payment") {
      leavePayment();
      setSelectedSlots([slot]);
      return;
    }

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

  /** Back to a clean booking form (keeps the confirmed cards). */
  function resetBookingForm() {
    setSelectedSlots([]);
    setBookingStatus("idle");
    setBookingRef("");
    setFields({ name: "", contact: "", email: "", players: "1", message: "" });
    setErrors({});
    setPromo(""); setPromoError(""); setPromoStatus("idle"); setPromoResult(null);
    setBookedPrice(null); setBookedPromo(null);
    setBookedGstRate(null); setBookedGstAmount(null);
    setBookedStartTime(""); setBookedEndTime(""); setBookedSlotCount(1);
    setBookedAmountDue(null); setBookedBalanceDue(0);
    setPayOption("full");
    setPendingCheckout(null);
    setTouched({ name: false, contact: false, players: false });
  }

  /** A confirmed booking becomes a card above the picker, and the form is free for the next booking. */
  function finishBooking() {
    const info = pendingInfo.current;
    pendingInfo.current = null;
    if (info) setConfirmed((list) => [info, ...list]);
    setLeftPayment(null);
    resetBookingForm();
    loadSlots();
    window.setTimeout(() => confirmedTop.current?.scrollIntoView({ behavior: "smooth", block: "start" }), 60);
  }

  /** Walk away from a pending payment without losing the booking: say where to resume it. */
  function leavePayment() {
    if (bookingStatus !== "payment") return;
    setLeftPayment(bookingRef);
    pendingInfo.current = null;
    setSelectedSlots([]);
    setBookingStatus("idle");
    setBookingRef("");
    setPendingCheckout(null);
    setBookedPrice(null); setBookedPromo(null);
    setBookedGstRate(null); setBookedGstAmount(null);
    setBookedStartTime(""); setBookedEndTime(""); setBookedSlotCount(1);
    setBookedAmountDue(null); setBookedBalanceDue(0);
  }

  function chooseSport(slug: string) { leavePayment(); setBookSport(slug); }
  function chooseDate(iso: string) { leavePayment(); setBookDate(iso); }

  async function submitBooking(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!firstSlot) return;

    setTouched({ name: true, contact: true, players: true });
    const errs = validateFields(fields);
    if (Object.values(errs).some(Boolean)) return;

    if (TURNSTILE_SITE_KEY && !tsToken) {
      setBookingError("Please complete the verification challenge first.");
      setBookingStatus("error");
      return;
    }

    setSubmitting(true);
    setPromoError("");
    setBookingError("");
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
        email: fields.email.trim() || undefined,
        turnstileToken: tsToken ?? undefined,
        paymentOption: chosenOption,
      });
      setBookingRef(result.bookingRef);
      setBookedPrice(result.price ?? null);
      setBookedAmountDue(result.amountDue ?? result.price ?? null);
      setBookedBalanceDue(result.balanceDue ?? 0);
      setBookedPromo(result.promoCode ?? null);
      setBookedGstRate(result.gstRatePercent ?? null);
      setBookedGstAmount(result.gstAmount ?? null);
      setBookedStartTime(result.startTime ?? firstSlot.startTime);
      setBookedEndTime(result.endTime ?? lastSlot!.endTime);
      setBookedSlotCount(result.slotCount ?? selectedSlots.length);
      setLeftPayment(null);
      pendingInfo.current = {
        ref: result.bookingRef,
        sportLabel: SPORT_LABELS[firstSlot.sportSlug] ?? firstSlot.sportSlug,
        dateLabel: days.find((d) => d.iso === firstSlot.date)?.label ?? firstSlot.date,
        start: result.startTime ?? firstSlot.startTime,
        end: result.endTime ?? lastSlot!.endTime,
        slotCount: result.slotCount ?? selectedSlots.length,
        price: result.price ?? null,
        promo: result.promoCode ?? null,
        gstRate: result.gstRatePercent ?? null,
        gstAmount: result.gstAmount ?? null,
        amountPaid: result.amountDue ?? result.price ?? null,
        balanceDue: result.balanceDue ?? 0,
        advance: result.paymentOption === "advance" ? (result.advanceAmount ?? null) : null,
        contact: fields.contact.trim(),
      };
      if (result.paymentRequired && result.checkout) {
        setPendingCheckout(result.checkout);
        setBookingStatus("payment");
      } else {
        finishBooking();
      }
    } catch (err: unknown) {
      const failure = describeBookingError(err);
      if (err instanceof ApiError && err.code === "advance_not_available") setPayOption("full"); // e.g. a promo lowered the total
      if (failure.promo) {
        setPromoError(failure.message);
      } else {
        setBookingError(failure.message);
        setBookingStatus("error");
        // Only a lost slot changes the grid; a gateway outage or rate limit keeps the selection so the user can retry.
        if (failure.slotsTaken) loadSlots();
      }
      setTsReset((n) => n + 1); // Turnstile tokens are single-use
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

      {confirmed.length > 0 && (
        <div className="confirmed-list" ref={confirmedTop} data-testid="confirmed-list">
          {confirmed.map((b) => <ConfirmedBookingCard key={b.ref} booking={b} />)}
        </div>
      )}

      {leftPayment && (
        <p className="form-message left-payment" data-testid="left-payment" role="status">
          Payment for <strong>{leftPayment}</strong> isn't finished. Its slot is held for 15 minutes; resume it from{" "}
          <a href="/my-bookings">My Bookings</a> with this ID, or just keep choosing.
          <button type="button" className="link-button" aria-label="Dismiss" onClick={() => setLeftPayment(null)}>×</button>
        </p>
      )}

      <div className="sport-tabs" role="tablist">
        {Object.entries(SPORT_LABELS).map(([slug, label]) => (
          <button
            key={slug}
            role="tab"
            className={`tab-btn${bookSport === slug ? " active" : ""}`}
            onClick={() => chooseSport(slug)}
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
            onClick={() => chooseDate(d.iso)}
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

      {selectedSlots.length > 0 && bookingStatus !== "payment" && (
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
            {advanceOffered && (
              <span className="muted" data-testid="summary-advance">
                Advance: ₹{advanceAmount} (non-refundable) — or pay in full
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

            <div>
              <label>
                Email (optional)
                <input
                  type="email"
                  value={fields.email}
                  onChange={(e) => change("email", e.target.value)}
                  placeholder="For booking confirmation"
                />
              </label>
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

            {advanceOffered && payableTotal != null && (
              <fieldset className="pay-options" data-testid="pay-options">
                <legend>How would you like to pay?</legend>
                <label className={`pay-option${chosenOption === "full" ? " active" : ""}`}>
                  <input type="radio" name="payOption" value="full" checked={chosenOption === "full"}
                    onChange={() => setPayOption("full")} data-testid="pay-option-full" />
                  <span>
                    <strong>Pay in full</strong>
                    <span className="pay-option-amount" data-testid="pay-option-full-amount">₹{payableTotal}</span>
                  </span>
                </label>
                <label className={`pay-option${chosenOption === "advance" ? " active" : ""}`}>
                  <input type="radio" name="payOption" value="advance" checked={chosenOption === "advance"}
                    onChange={() => setPayOption("advance")} data-testid="pay-option-advance" />
                  <span>
                    <strong>Pay ₹{advanceAmount} advance now</strong>
                    <span className="pay-option-amount" data-testid="pay-option-advance-note">
                      ₹{Math.round((payableTotal - advanceAmount) * 100) / 100} at the venue
                    </span>
                    <small className="muted">Your booking is confirmed once the advance is paid. The advance is non-refundable.</small>
                  </span>
                </label>
              </fieldset>
            )}

            <Turnstile onToken={setTsToken} resetKey={tsReset} />
            <button className="button primary" type="submit" disabled={submitting}>
              {submitting ? "Confirming…" : `Confirm booking${selectedSlots.length > 1 ? ` (${selectedSlots.length} slots)` : ""}`}
            </button>
            {bookingStatus === "error" && (
              <p className="form-message error" data-testid="booking-error">
                {bookingError || "Booking failed. Please try again."}
              </p>
            )}
          </form>
        </div>
      )}

      {bookingStatus === "payment" && pendingCheckout && (
        <PaymentPanel
          bookingRef={bookingRef}
          checkout={pendingCheckout}
          amount={bookedAmountDue ?? bookedPrice ?? 0}
          balanceDue={bookedBalanceDue}
          customerName={fields.name.trim()}
          customerContact={fields.contact.trim()}
          onSuccess={finishBooking}
          onChooseAnother={leavePayment}
        />
      )}
    </section>
  );
}
