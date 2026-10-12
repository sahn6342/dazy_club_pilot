from fastapi import APIRouter, Depends, HTTPException
from models import BookingRecord, BookingStatusUpdate, BookingRefundRequest
from auth import get_current_admin
from deps import booking_repo, booking_payment_repo, payment_provider
from services.booking_service import assert_valid_transition
from services.notification_service import notify_booking_confirmed, notify_booking_cancelled, notify_booking_refunded

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
    _: str = Depends(get_current_admin),
):
    booking = booking_repo.get_by_id(booking_id)
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found.")
    assert_valid_transition(booking.status, body.status)
    if body.status == "cancelled":
        booking_repo.cancel_by_ref(booking.bookingRef)
        notify_booking_cancelled(booking.bookingRef)
        return booking_repo.get_by_id(booking_id)
    updated = booking_repo.update(booking_id, {"status": body.status})
    if body.status == "confirmed":
        notify_booking_confirmed(booking.bookingRef)
    return updated


@router.delete("/admin/bookings/{booking_id}", status_code=204)
def delete_booking(booking_id: str, _: str = Depends(get_current_admin)):
    if not booking_repo.delete(booking_id):
        raise HTTPException(status_code=404, detail="Booking not found.")


@router.post("/admin/bookings/{booking_id}/refund")
def refund_booking(booking_id: str, body: BookingRefundRequest, _: str = Depends(get_current_admin)):
    booking = booking_repo.get_by_id(booking_id)
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found.")
    if booking.paymentStatus != "paid":
        raise HTTPException(status_code=409, detail=f"Cannot refund a booking with paymentStatus '{booking.paymentStatus}'.")

    payment = booking_payment_repo.get_by_ref(booking.bookingRef)
    if not payment or not payment.providerPaymentId:
        raise HTTPException(status_code=409, detail="No verified payment found for this booking.")

    if not payment_provider.refund(payment.providerPaymentId, payment.amount):
        raise HTTPException(status_code=502, detail="Refund failed at the payment provider.")

    booking_repo.refund_by_ref(booking.bookingRef)
    booking_payment_repo.mark_refunded(booking.bookingRef)
    notify_booking_refunded(booking.bookingRef)
    return {"status": "refunded", "bookingRef": booking.bookingRef}
