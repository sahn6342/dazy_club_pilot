"""Catch payments whose webhook never arrived (API asleep, gateway outage, misconfigured
endpoint): ask the provider about every unsettled order in a recent window and funnel any
captured payment through the same confirmation path the webhook uses."""
import logging
from datetime import datetime, timedelta, timezone

from audit import audit
from deps import booking_payment_repo, payment_provider
from repositories.booking_payment_repo import AMOUNT_MISMATCH
from services.payment_confirmation import confirm_verified_payment

logger = logging.getLogger(__name__)

_MIN_AGE = timedelta(minutes=2)   # give the normal webhook/callback a head start
_MAX_AGE = timedelta(hours=24)


def reconcile_unsettled_payments() -> int:
    """Returns how many orders were settled (confirmed or refunded-as-late)."""
    now = datetime.now(timezone.utc)
    pending = booking_payment_repo.list_unsettled(
        older_than_iso=(now - _MIN_AGE).isoformat(), newer_than_iso=(now - _MAX_AGE).isoformat())
    settled = 0
    for p in pending:
        try:
            captured = payment_provider.fetch_captured_payment(p.providerOrderId)
            if captured is None:
                continue
            if abs(captured.amount - p.amount) > 0.01:
                logger.error("AMOUNT MISMATCH reconciling order %s: expected %.2f, captured %.2f",
                             p.providerOrderId, p.amount, captured.amount)
                booking_payment_repo.set_status(p.providerOrderId, AMOUNT_MISMATCH)
                audit("payment.amount_mismatch", "system", entity_type="booking_payment", entity_id=p.bookingRef,
                      detail={"bookingRef": p.bookingRef, "expected": p.amount, "captured": captured.amount, "source": "reconciliation"})
                continue
            result = confirm_verified_payment(p.bookingRef, p.providerOrderId, captured.providerPaymentId, None)
            audit("payment.reconciled", "system", entity_type="booking_payment", entity_id=p.bookingRef,
                  detail={"bookingRef": p.bookingRef, "outcome": result.outcome})
            settled += 1
        except Exception:
            logger.exception("Reconciliation failed for order %s", p.providerOrderId)
    return settled
