"""Message content for booking-lifecycle notifications (Detailed-Roadmap Phase 5)."""
from models import BookingRecord


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
