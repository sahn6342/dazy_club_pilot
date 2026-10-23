"""Message content for booking-lifecycle notifications (Detailed-Roadmap Phase 5)."""
import os

from brand import BRAND_NAME
from models import BookingRecord

_WEB_BASE_URL = os.environ.get("DAZY_WEB_BASE_URL", "http://localhost:5173")

VENUE_ADDRESS = os.environ.get("DAZY_VENUE_ADDRESS", "R.K. Puram, Saguna more")
VENUE_MAP_URL = os.environ.get("DAZY_VENUE_MAP_URL", "https://maps.app.goo.gl/Ag1HGe5WjDDc68Tg8?g_st=ic")
VENUE_PHONE = os.environ.get("DAZY_SUPPORT_PHONE", "")  # shown as "call <number> or reply"; empty = reply only
# Bookings carry no add-on data yet, so every confirmation says "None" rather than leaving the line out.
_ADDONS_NONE = "None"


def _assist() -> str:
    return f"call {VENUE_PHONE} or reply to this message." if VENUE_PHONE else "reply to this message."


def booking_payment_pending(booking: BookingRecord) -> tuple[str, str]:
    """Returns (subject, body) for a booking still awaiting payment — lets the
    customer resume from a link even if they closed the tab (no login/profile
    system, so the ref + contact IS the recovery mechanism)."""
    amount = _money(_amount_due_now(booking))
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


def _money(value: float) -> str:
    return f"Rs. {value:.2f}"


def _amount_due_now(booking: BookingRecord) -> float:
    """What the customer must pay online now: the advance for an advance booking, else the full price."""
    return booking.depositAmount if booking.depositAmount is not None else (booking.price or 0.0)


def _paid_and_pending(booking: BookingRecord) -> tuple[str, str]:
    """Amount received so far and what is still owed. A confirmed booking is normally paid in full;
    `depositAmount` (when set) is what was actually collected, the rest is pending."""
    total = booking.price or 0.0
    paid = booking.depositAmount if booking.depositAmount is not None else total
    return _money(paid), _money(max(total - paid, 0.0))


def _confirmation_lines(booking: BookingRecord) -> str:
    """The booking details block shared by the email and WhatsApp confirmation."""
    paid, pending = _paid_and_pending(booking)
    return (
        f"Date: {booking.date}\n"
        f"Time: {booking.startTime}-{booking.endTime}\n"
        f"Sport: {booking.sportSlug.capitalize()}\n"
        f"Total players: {booking.party_size}\n"
        f"Add-ons: {_ADDONS_NONE}\n"
        f"Amount paid: {paid}\n"
        f"Pending payment: {pending}\n"
        f"Booking id: {booking.bookingRef}\n"
        f"Address: {VENUE_ADDRESS}\n"
        f"Directions: {VENUE_MAP_URL}\n\n"
        f"For assistance, {_assist()}"
    )


def booking_confirmation(booking: BookingRecord) -> tuple[str, str]:
    """Returns (subject, body) for a confirmed, paid booking."""
    subject = f"Booking confirmed — {booking.bookingRef}"
    body = (
        f"Hi {booking.name},\n\n"
        f"Booking confirmed at {BRAND_NAME}. This is your booking confirmation:\n\n"
        f"{_confirmation_lines(booking)}"
    )
    return subject, body


def booking_confirmation_whatsapp(booking: BookingRecord) -> str:
    """WhatsApp text for a confirmed booking. Only delivered as free text inside WhatsApp's 24 h window;
    outside it the approved template (template_params below) is what actually goes out."""
    return (
        f"Hi {booking.name}, Booking confirmed at {BRAND_NAME}. This is your booking confirmation:\n"
        f"{_confirmation_lines(booking)}"
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
        due = _money(_amount_due_now(booking))
        return [booking.name, booking.bookingRef, due, f"{_WEB_BASE_URL}/my-bookings?ref={booking.bookingRef}"]
    if event == "booking_confirmed":
        paid, pending = _paid_and_pending(booking)
        return [booking.name, booking.date, when, sport, str(booking.party_size), _ADDONS_NONE,
                paid, pending, booking.bookingRef]
    if event == "booking_cancelled":
        return [booking.name, booking.bookingRef, booking.date]
    if event == "booking_refunded":
        value = amount if amount is not None else (booking.price or 0.0)
        return [booking.name, booking.bookingRef, f"Rs. {value:.2f}", "cancelled" if cancelled else "still active"]
    return []
