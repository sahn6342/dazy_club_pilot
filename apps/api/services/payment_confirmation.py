"""Single place that turns a verified provider payment into a confirmed booking.

Used by both the client callback (POST /bookings/{ref}/payment/verify) and the
provider webhook so the two can never disagree. A payment that lands after the
booking is no longer pending (timeout sweep / admin cancel) must not resurrect
the booking — its slot may already belong to someone else — so it is refunded
(or flagged for an admin when the refund call fails)."""
import logging
from dataclasses import dataclass

from audit import audit
from deps import booking_repo, booking_payment_repo, payment_provider
from repositories.booking_payment_repo import VERIFIED, REFUNDED, PAID_ORPHAN
from services.notification_service import notify_booking_confirmed, notify_booking_refunded

logger = logging.getLogger(__name__)

CONFIRMED = "confirmed"
ALREADY_CONFIRMED = "already_confirmed"
LATE_REFUNDED = "late_refunded"
LATE_NEEDS_REVIEW = "late_needs_review"


@dataclass
class ConfirmationResult:
    outcome: str

    @property
    def booking_confirmed(self) -> bool:
        return self.outcome in (CONFIRMED, ALREADY_CONFIRMED)


def confirm_verified_payment(
    booking_ref: str, provider_order_id: str, provider_payment_id: str, signature: str | None
) -> ConfirmationResult:
    """Call only after the provider payment/webhook signature was verified."""
    if booking_repo.confirm_payment_by_ref(booking_ref) > 0:
        booking_payment_repo.mark_verified(provider_order_id, provider_payment_id, signature)
        notify_booking_confirmed(booking_ref)
        return ConfirmationResult(CONFIRMED)

    bookings = booking_repo.get_by_ref(booking_ref)
    if bookings and all(b.paymentStatus == "paid" and b.status != "cancelled" for b in bookings):
        return ConfirmationResult(ALREADY_CONFIRMED)  # idempotent redelivery

    # Late payment: booking expired/cancelled before the money arrived.
    payment = booking_payment_repo.get_by_order_id(provider_order_id)
    amount = payment.amount if payment else 0.0
    if payment and payment.status == REFUNDED:
        return ConfirmationResult(LATE_REFUNDED)  # redelivery after auto-refund
    refunded = False
    try:
        refunded = bool(amount) and payment_provider.refund(provider_payment_id, amount)
    except Exception:
        logger.exception("Auto-refund raised for late payment %s (ref %s)", provider_payment_id, booking_ref)
    booking_payment_repo.mark_late_payment(
        provider_order_id, provider_payment_id, signature, REFUNDED if refunded else PAID_ORPHAN
    )
    audit("payment.late_refunded" if refunded else "payment.orphan", "system", entity_type="booking_payment",
          entity_id=booking_ref, detail={"bookingRef": booking_ref, "providerPaymentId": provider_payment_id, "amount": amount})
    if refunded:
        notify_booking_refunded(booking_ref)
        return ConfirmationResult(LATE_REFUNDED)
    logger.error(
        "ORPHAN PAYMENT: %s paid for expired booking %s and auto-refund failed — refund manually.",
        provider_payment_id, booking_ref,
    )
    return ConfirmationResult(LATE_NEEDS_REVIEW)
