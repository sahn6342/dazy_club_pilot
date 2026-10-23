"""Advance (partial) payment.

A customer may pay only a fixed, NON-REFUNDABLE advance online and the rest at the venue; the booking is
confirmed as soon as the advance is paid. The advance is one flat amount per booking, set in Admin ->
Contact Details (CMS key `booking_advance_amount`, 0 = switched off) and capped by the booking total:
it is offered only when the total is MORE than the advance.

Data model: `booking.price` stays the total; `booking.depositAmount` is the advance charged online (NULL = paid
in full); `booking_payments.amount` is what the provider order was for (so webhook, reconciliation and refund
caps keep working unchanged); `booking.balance_collected` is what the venue took afterwards."""
import logging
from decimal import Decimal, InvalidOperation

from services.refund_policy import money

logger = logging.getLogger(__name__)

ADVANCE_KEY = "booking_advance_amount"
DEFAULT_ADVANCE = Decimal("500.00")  # used until the key exists in the CMS
MAX_ADVANCE = Decimal("1000000")


def parse_advance(value: str) -> Decimal:
    """A non-negative rupee amount; raises ValueError with a message for the admin otherwise."""
    try:
        amount = Decimal(str(value).strip())
    except InvalidOperation:
        raise ValueError("The advance must be a number, for example 500 (0 switches the advance off).")
    if not amount.is_finite() or amount < 0 or amount > MAX_ADVANCE:
        raise ValueError("The advance must be between 0 and 1,000,000 (0 switches the advance off).")
    return money(amount)


def configured_advance() -> Decimal:
    """The live setting; 0 when switched off or unreadable (an unreadable value must not block bookings)."""
    from deps import cms_repo
    entry = cms_repo.get_by_id(ADVANCE_KEY)
    if entry is None:
        return DEFAULT_ADVANCE
    if not (entry.value or "").strip():
        return Decimal("0.00")
    try:
        return parse_advance(entry.value)
    except ValueError as e:
        logger.error("Invalid %s in CMS (%s); the advance option is off.", ADVANCE_KEY, e)
        return Decimal("0.00")


def advance_offer(total) -> Decimal | None:
    """The advance a booking of `total` could pay now, or None when the option does not apply
    (switched off, free booking, or the total is not more than the advance)."""
    advance = configured_advance()
    if advance <= 0 or not total or money(total) <= advance:
        return None
    return advance


def is_advance(booking) -> bool:
    return booking.depositAmount is not None


def balance_due(booking) -> float:
    """Still to pay at the venue for an advance booking (0 for paid-in-full and cancelled bookings)."""
    if not is_advance(booking) or booking.status == "cancelled":
        return 0.0
    due = money(booking.price or 0) - money(booking.depositAmount) - money(booking.balance_collected)
    return float(max(due, Decimal("0.00")))


def amount_paid(booking) -> float:
    """Received so far: the online payment (once paid) plus anything collected at the venue."""
    online = money(0)
    if booking.paymentStatus != "unpaid":
        online = money(booking.depositAmount) if is_advance(booking) else money(booking.price or 0)
    return float(online + money(booking.balance_collected))


def non_refundable(booking) -> Decimal:
    """The part of the online payment that is never refunded: the whole advance, nothing for paid-in-full."""
    return money(booking.depositAmount) if is_advance(booking) else money(0)
