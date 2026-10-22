"""API errors that carry a short machine-readable `code` next to the human `detail`.

Clients used to guess the kind of failure by searching the message text (which broke as soon as two different
errors shared a word). The body is now {"detail": "<message>", "code": "<code>"}: `detail` is unchanged, so
older clients keep working, and `code` says what happened.

Codes used by the booking and payment routes:
  slot_not_found, slot_unavailable, slots_not_consecutive, promo_invalid, pending_cap, rate_limited,
  verification_required (Turnstile), payment_unavailable (gateway down), booking_not_found,
  payment_record_missing, payment_verification_failed, booking_expired_paid, booking_expired_refunded,
  contact_invalid, otp_required, no_bookings_found
"""
from fastapi import HTTPException


class ApiError(HTTPException):
    def __init__(self, status_code: int, detail: str, code: str, headers: dict | None = None):
        super().__init__(status_code=status_code, detail=detail, headers=headers)
        self.code = code
