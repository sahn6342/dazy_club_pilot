from fastapi import APIRouter, Depends, HTTPException
from models import BookingRecord, BookingStatusUpdate
from auth import get_current_admin
from deps import booking_repo
from services.booking_service import assert_valid_transition

router = APIRouter()


@router.get("/admin/bookings")
def list_bookings(
    sport: str | None = None,
    date: str | None = None,
    status: str | None = None,
    limit: int = 500,
    offset: int = 0,
    _: str = Depends(get_current_admin),
):
    result = booking_repo.get_all()
    if sport:
        result = [b for b in result if b.sportSlug == sport]
    if date:
        result = [b for b in result if b.date == date]
    if status:
        result = [b for b in result if b.status == status]
    return result[offset: offset + min(limit, 1000)]


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
    # Cancellation must propagate to all secondary slot rows sharing the same bookingRef.
    if body.status == "cancelled":
        booking_repo.cancel_by_ref(booking.bookingRef)
        return booking_repo.get_by_id(booking_id)
    updated = booking_repo.update(booking_id, {"status": body.status})
    return updated


@router.delete("/admin/bookings/{booking_id}", status_code=204)
def delete_booking(booking_id: str, _: str = Depends(get_current_admin)):
    if not booking_repo.delete(booking_id):
        raise HTTPException(status_code=404, detail="Booking not found.")
