"""Refund execution shared by every admin refund path (full/partial refund, cancel-and-refund).

Order matters because money moves outside our database:
  1. reserve the amount in booking_payments.refunded_amount with ONE conditional UPDATE, so two
     concurrent requests can never refund more than was paid;
  2. call the payment provider;
  3. on provider failure release the reservation and change nothing else;
  4. on success record the new payment/booking state.
A crash between 2 and 4 leaves the reservation in place, so the balance errs on the side of
"already refunded" and an admin can reconcile from the provider dashboard (it is logged loudly)."""
import logging
from dataclasses import dataclass
from decimal import Decimal

from fastapi import HTTPException

from audit import audit
from deps import booking_repo, booking_payment_repo, payment_provider
from repositories.booking_payment_repo import REFUNDED, PARTIALLY_REFUNDED
from services.notification_service import notify_booking_refunded
from services.refund_policy import money

logger = logging.getLogger(__name__)

REFUNDABLE_PAYMENT_STATES = ("paid", PARTIALLY_REFUNDED)


@dataclass
class RefundResult:
    amount: float
    refunded_total: float
    remaining: float
    payment_status: str   # paid | partially_refunded | refunded
    cancelled: bool


def refund_booking(
    booking, *, amount: Decimal | None, force_cancel: bool, actor, request=None,
    reason: str | None = None, extra_detail: dict | None = None,
) -> RefundResult:
    """Refund `amount` (default: everything still refundable) of a paid booking.
    Cancels the booking when `force_cancel` or when the refund brings it to zero balance.
    Raises HTTPException (409/422/502) without side effects when the refund cannot be made."""
    if booking.paymentStatus not in REFUNDABLE_PAYMENT_STATES:
        raise HTTPException(status_code=409, detail=f"Cannot refund a booking with paymentStatus '{booking.paymentStatus}'.")
    payment = booking_payment_repo.get_by_ref(booking.bookingRef)
    if not payment or not payment.providerPaymentId:
        raise HTTPException(status_code=409, detail="No verified payment found for this booking.")

    paid = money(payment.amount)
    already = money(payment.refundedAmount)
    remaining = max(paid - already, Decimal("0.00"))
    amount = remaining if amount is None else money(amount)
    if amount <= 0:
        raise HTTPException(status_code=422, detail="Refund amount must be greater than zero.")
    if amount > remaining:
        raise HTTPException(status_code=422, detail=f"Refund exceeds the refundable balance (Rs. {remaining}).")

    if not booking_payment_repo.reserve_refund(payment.id, float(amount)):
        raise HTTPException(status_code=409, detail="Another refund for this booking is in progress. Reload and try again.")

    detail_base = {"bookingRef": booking.bookingRef, "amount": float(amount), "providerPaymentId": payment.providerPaymentId,
                   "reason": reason, **(extra_detail or {})}
    try:
        ok = payment_provider.refund(payment.providerPaymentId, float(amount))
    except Exception:
        logger.exception("Refund call raised for booking %s", booking.bookingRef)
        ok = False
    if not ok:
        booking_payment_repo.release_refund(payment.id, float(amount))
        audit("booking.refund_failed", actor, request=request, entity_type="booking", entity_id=booking.id, detail=detail_base)
        raise HTTPException(status_code=502, detail="Refund failed at the payment provider.")

    new_total = already + amount
    fully = new_total >= paid
    payment_status = REFUNDED if fully else PARTIALLY_REFUNDED
    cancel = force_cancel or fully
    try:
        booking_repo.apply_refund_state(booking.bookingRef, payment_status, cancel)
        booking_payment_repo.set_status(payment.providerOrderId, payment_status)
    except Exception:
        logger.critical("REFUND ISSUED BUT STATE NOT SAVED: booking %s, Rs. %s, payment %s — fix by hand.",
                        booking.bookingRef, amount, payment.providerPaymentId, exc_info=True)
        raise

    audit("booking.refund", actor, request=request, entity_type="booking", entity_id=booking.id,
          detail={**detail_base, "partial": not fully, "cancelled": cancel, "refundedTotal": float(new_total)})
    notify_booking_refunded(booking.bookingRef, amount=float(amount), cancelled=cancel, partial=not fully)
    return RefundResult(float(amount), float(new_total), float(paid - new_total), payment_status, cancel)
