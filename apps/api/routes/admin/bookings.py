from fastapi import APIRouter, Depends, HTTPException, Request
from audit import audit
from dataclasses import asdict

from models import BookingRecord, BookingStatusUpdate, BookingRefundRequest, CancelRefundRequest
from auth import get_current_admin
from deps import booking_repo, booking_payment_repo
from services.refund_policy import build_quote, hours_until_start, load_tiers, money
from services.refund_service import REFUNDABLE_PAYMENT_STATES, refund_booking
from services.venue_tz import get_venue_zoneinfo
from services.booking_service import assert_valid_transition
from services.notification_service import notify_booking_confirmed, notify_booking_cancelled

router = APIRouter()

_SORT_KEYS = {
    "date":      lambda b: b.date or "",
    "createdAt": lambda b: b.createdAt or "",
    "price":     lambda b: (b.price is None, b.price or 0),
    "name":      lambda b: (b.name or "").lower(),
    "sportSlug": lambda b: b.sportSlug or "",
    "status":    lambda b: b.status or "",
}


def _filter_and_sort(
    result: list[BookingRecord],
    sport: str | None,
    date_from: str | None,
    date_to: str | None,
    status: str | None,
    sort_by: str,
    sort_dir: str,
) -> list[BookingRecord]:
    if sport:
        result = [b for b in result if b.sportSlug == sport]
    if date_from:
        result = [b for b in result if b.date >= date_from]
    if date_to:
        result = [b for b in result if b.date <= date_to]
    if status:
        result = [b for b in result if b.status == status]
    key_fn = _SORT_KEYS.get(sort_by, _SORT_KEYS["date"])
    return sorted(result, key=key_fn, reverse=(sort_dir == "desc"))


@router.get("/admin/bookings")
def list_bookings(
    sport: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    status: str | None = None,
    sort_by: str = "date",
    sort_dir: str = "desc",
    limit: int = 25,
    offset: int = 0,
    _: str = Depends(get_current_admin),
):
    filtered = _filter_and_sort(
        booking_repo.get_all(), sport, date_from, date_to, status, sort_by, sort_dir
    )
    total = len(filtered)
    page_items = filtered[offset: offset + min(limit, 100)]
    return {"items": page_items, "total": total}


@router.get("/admin/bookings/export")
def export_bookings(
    sport: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    status: str | None = None,
    sort_by: str = "date",
    sort_dir: str = "desc",
    _: str = Depends(get_current_admin),
):
    return _filter_and_sort(
        booking_repo.get_all(), sport, date_from, date_to, status, sort_by, sort_dir
    )


@router.patch("/admin/bookings/{booking_id}")
def update_booking(
    booking_id: str,
    body: BookingStatusUpdate,
    req: Request,
    admin: dict = Depends(get_current_admin),
):
    booking = booking_repo.get_by_id(booking_id)
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found.")
    assert_valid_transition(booking.status, body.status)
    audit("booking.status_change", admin, request=req, entity_type="booking", entity_id=booking.id,
          detail={"bookingRef": booking.bookingRef, "from": booking.status, "to": body.status})
    if body.status == "cancelled":
        booking_repo.cancel_by_ref(booking.bookingRef)
        notify_booking_cancelled(booking.bookingRef)
        return booking_repo.get_by_id(booking_id)
    updated = booking_repo.update(booking_id, {"status": body.status})
    if body.status == "confirmed":
        notify_booking_confirmed(booking.bookingRef)
    return updated


@router.delete("/admin/bookings/{booking_id}", status_code=204)
def delete_booking(booking_id: str, req: Request, admin: dict = Depends(get_current_admin)):
    booking = booking_repo.get_by_id(booking_id)
    if not booking_repo.delete(booking_id):
        raise HTTPException(status_code=404, detail="Booking not found.")
    audit("booking.delete", admin, request=req, entity_type="booking", entity_id=booking_id,
          detail={"bookingRef": booking.bookingRef, "status": booking.status,
                  "paymentStatus": booking.paymentStatus, "price": booking.price} if booking else None)


def _primary(booking_id: str):
    booking = booking_repo.get_by_id(booking_id)
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found.")
    return booking


def _quote_for(booking):
    """Policy quote for a booking that has money to give back, else None."""
    if booking.paymentStatus not in REFUNDABLE_PAYMENT_STATES:
        return None
    payment = booking_payment_repo.get_by_ref(booking.bookingRef)
    if not payment:
        return None
    hours = hours_until_start(booking.date, booking.startTime, get_venue_zoneinfo())
    return build_quote(payment.amount, payment.refundedAmount, hours, load_tiers())


@router.get("/admin/bookings/{booking_id}/refund-quote")
def refund_quote(booking_id: str, _: dict = Depends(get_current_admin)):
    """What the refund policy would return if this booking were cancelled now (for the admin dialog)."""
    booking = _primary(booking_id)
    quote = _quote_for(booking)
    return {
        "bookingRef": booking.bookingRef, "status": booking.status, "paymentStatus": booking.paymentStatus,
        "refundable": quote is not None and quote.remaining > 0,
        "cancellable": booking.status in ("pending", "confirmed"),
        "quote": asdict(quote) if quote else None,
    }


@router.post("/admin/bookings/{booking_id}/refund")
def refund_booking_route(booking_id: str, body: BookingRefundRequest, req: Request, admin: dict = Depends(get_current_admin)):
    """Refund everything still refundable (default) or `amount`. A refund that brings the balance to
    zero cancels the booking; a partial one leaves it as it is."""
    booking = _primary(booking_id)
    result = refund_booking(booking, amount=money(body.amount) if body.amount is not None else None,
                            force_cancel=False, actor=admin, request=req, reason=body.reason)
    return {"status": "refunded" if result.payment_status == "refunded" else "partially_refunded",
            "bookingRef": booking.bookingRef, "refunded": result.amount, "refundedTotal": result.refunded_total,
            "remaining": result.remaining, "paymentStatus": result.payment_status, "cancelled": result.cancelled}


@router.post("/admin/bookings/{booking_id}/cancel-and-refund")
def cancel_and_refund(booking_id: str, body: CancelRefundRequest, req: Request, admin: dict = Depends(get_current_admin)):
    """Cancel the booking (freeing its slot) and refund per the cancellation policy, or `amount`
    (0 = cancel without refund). The amount can never exceed what is still refundable."""
    booking = _primary(booking_id)
    if booking.status not in ("pending", "confirmed", "cancelled"):
        raise HTTPException(status_code=409, detail=f"A {booking.status} booking cannot be cancelled.")
    quote = _quote_for(booking)
    suggested = quote.suggestedAmount if quote else 0.0
    amount = money(body.amount if body.amount is not None else suggested)
    remaining = money(quote.remaining) if quote else money(0)
    if amount > remaining:
        raise HTTPException(status_code=422, detail=f"Refund exceeds the refundable balance (Rs. {remaining}).")
    already_cancelled = booking.status == "cancelled"

    policy = {"percent": quote.percent, "hoursBefore": quote.hoursBefore, "policyAmount": quote.policyAmount} if quote else None
    extra = {"policy": policy, "override": body.amount is not None and quote is not None and float(amount) != quote.suggestedAmount}

    if amount > 0:
        result = refund_booking(booking, amount=amount, force_cancel=True, actor=admin, request=req,
                                reason=body.reason, extra_detail=extra)
        return {"status": "cancelled", "bookingRef": booking.bookingRef, "refunded": result.amount,
                "refundedTotal": result.refunded_total, "remaining": result.remaining,
                "paymentStatus": result.payment_status, "policy": policy}

    if already_cancelled:
        raise HTTPException(status_code=409, detail="This booking is already cancelled and has nothing left to refund.")
    assert_valid_transition(booking.status, "cancelled")
    booking_repo.cancel_by_ref(booking.bookingRef)
    notify_booking_cancelled(booking.bookingRef)
    audit("booking.cancel_refund", admin, request=req, entity_type="booking", entity_id=booking.id,
          detail={"bookingRef": booking.bookingRef, "amount": 0.0, "reason": body.reason, **extra})
    return {"status": "cancelled", "bookingRef": booking.bookingRef, "refunded": 0.0,
            "remaining": float(remaining), "paymentStatus": booking.paymentStatus, "policy": policy}
