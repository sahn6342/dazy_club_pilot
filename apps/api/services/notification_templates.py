"""Message content for booking-lifecycle notifications (Detailed-Roadmap Phase 5)."""
import os

from brand import BRAND_NAME
from models import BookingRecord

_WEB_BASE_URL = os.environ.get("DAZY_WEB_BASE_URL", "http://localhost:5173")


def booking_payment_pending(booking: BookingRecord) -> tuple[str, str]:
    """Returns (subject, body) for a booking still awaiting payment — lets the
    customer resume from a link even if they closed the tab (no login/profile
    system, so the ref + contact IS the recovery mechanism)."""
    amount = f"Rs. {booking.price:.2f}" if booking.price is not None else "Rs. 0.00"
    subject = f"Complete your booking — {booking.bookingRef}"
    body = (
        f"Hi {booking.name},\n\n"
        f"Your slot is held for 15 minutes — complete payment to confirm it.\n\n"
        f"Ref: {booking.bookingRef}\n"
        f"Sport: {booking.sportSlug}\n"
        f"Date: {booking.date}\n"
        f"Time: {booking.startTime}-{booking.endTime}\n"
        f"Amount due: {amount}\n\n"
        f"Resume payment: {_WEB_BASE_URL}/my-bookings?ref={booking.bookingRef}\n\n"
        f"— {BRAND_NAME}"
    )
    return subject, body


def booking_confirmation(booking: BookingRecord) -> tuple[str, str]:
    """Returns (subject, body) for a confirmed, paid booking."""
    amount = f"Rs. {booking.price:.2f}" if booking.price is not None else "Rs. 0.00"
    subject = f"Booking confirmed — {booking.bookingRef}"
    body = (
        f"Hi {booking.name},\n\n"
        f"Your booking is confirmed.\n\n"
        f"Ref: {booking.bookingRef}\n"
        f"Sport: {booking.sportSlug}\n"
        f"Date: {booking.date}\n"
        f"Time: {booking.startTime}-{booking.endTime}\n"
        f"Party size: {booking.party_size}\n"
        f"Amount paid: {amount}\n\n"
        f"See you on court!\n— {BRAND_NAME}"
    )
    return subject, body


def booking_confirmation_whatsapp(booking: BookingRecord) -> str:
    """Short WhatsApp message for a confirmed booking (under 500 chars)."""
    amount = f"Rs. {booking.price:.2f}" if booking.price is not None else "free"
    return (
        f"Hi {booking.name}! Your {booking.sportSlug} booking is confirmed.\n"
        f"Ref: {booking.bookingRef} | Date: {booking.date} | {booking.startTime}-{booking.endTime}\n"
        f"Amount: {amount}\nSee you on court! — {BRAND_NAME}"
    )


def booking_confirmation_sms(booking: BookingRecord) -> str:
    """SMS confirmation (under 160 chars)."""
    return (
        f"{BRAND_NAME}: Booking {booking.bookingRef} confirmed. "
        f"{booking.sportSlug} {booking.date} {booking.startTime}-{booking.endTime}."
    )


def booking_cancelled(booking: BookingRecord) -> tuple[str, str]:
    """Returns (subject, body) for a cancelled/expired booking."""
    subject = f"Booking cancelled — {booking.bookingRef}"
    body = (
        f"Hi {booking.name},\n\n"
        f"Your booking (ref: {booking.bookingRef}) has been cancelled.\n\n"
        f"Sport: {booking.sportSlug}\n"
        f"Date: {booking.date}\n"
        f"Time: {booking.startTime}-{booking.endTime}\n\n"
        f"If you have any questions, please contact us.\n— {BRAND_NAME}"
    )
    return subject, body


def booking_refunded(booking: BookingRecord, amount: float | None = None, cancelled: bool = True, partial: bool = False) -> tuple[str, str]:
    """Returns (subject, body) for a refunded booking. `amount` is what was refunded this time
    (defaults to the booking price); `cancelled` says whether the booking was cancelled too."""
    value = amount if amount is not None else (booking.price or 0.0)
    amount = f"Rs. {value:.2f}"
    subject = f"{'Booking cancelled, refund' if cancelled else 'Refund'} processed — {booking.bookingRef}"
    lead = (
        f"Your booking {booking.bookingRef} has been cancelled and a {'partial ' if partial else ''}refund of {amount} has been processed."
        if cancelled
        else f"A {'partial ' if partial else ''}refund of {amount} has been processed for booking {booking.bookingRef}; your booking stays active."
    )
    body = (
        f"Hi {booking.name},\n\n"
        f"{lead}\n\n"
        f"Sport: {booking.sportSlug}\n"
        f"Date: {booking.date}\n"
        f"Time: {booking.startTime}-{booking.endTime}\n\n"
        f"Refunds typically appear within 5-7 business days.\n— {BRAND_NAME}"
    )
    return subject, body


def template_params(event: str, booking: BookingRecord, amount: float | None = None, cancelled: bool = True) -> list[str]:
    """Values for the numbered variables ({{1}}, {{2}}... / var1, var2...) of the approved WhatsApp and SMS
    templates. The ORDER is part of the contract with the template text registered at Meta / MSG91; it is
    documented, with the exact template bodies, in docs/App-Overview.md. Never reorder without re-approving."""
    sport = booking.sportSlug.capitalize()
    when = f"{booking.startTime}-{booking.endTime}"
    if event == "booking_pending":
        due = f"Rs. {booking.price:.2f}" if booking.price is not None else "Rs. 0.00"
        return [booking.name, booking.bookingRef, due, f"{_WEB_BASE_URL}/my-bookings?ref={booking.bookingRef}"]
    if event == "booking_confirmed":
        return [booking.name, booking.bookingRef, sport, booking.date, when]
    if event == "booking_cancelled":
        return [booking.name, booking.bookingRef, booking.date]
    if event == "booking_refunded":
        value = amount if amount is not None else (booking.price or 0.0)
        return [booking.name, booking.bookingRef, f"Rs. {value:.2f}", "cancelled" if cancelled else "still active"]
    return []
