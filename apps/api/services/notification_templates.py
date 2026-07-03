"""Message content for booking-lifecycle notifications (Detailed-Roadmap Phase 5)."""
import os

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
        f"— Dazy.club"
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
        f"See you on court!\n— Dazy.club"
    )
    return subject, body
