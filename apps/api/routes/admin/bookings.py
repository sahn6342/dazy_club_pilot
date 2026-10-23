import csv
import io
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from audit import audit
from dataclasses import asdict

from models import BookingRecord, BookingStatusUpdate, BookingRefundRequest, CancelRefundRequest, CollectBalanceRequest
from auth import get_current_admin, require_superadmin
from deps import booking_repo, booking_payment_repo, order_repo
from services.advance import balance_due, amount_paid, is_advance, non_refundable
from services.refund_policy import build_quote, hours_until_start, load_tiers, money
from services.refund_service import REFUNDABLE_PAYMENT_STATES, refund_booking
from services.venue_tz import get_venue_zoneinfo
from services.booking_service import assert_valid_transition
from services.notification_service import notify_booking_confirmed, notify_booking_cancelled

router = APIRouter()

_DELETED_MODES = ("no", "only", "all")
_EXPORT_HEADERS = [
    "Ref", "Name", "Contact", "Sport", "Date", "Start", "End", "Players", "Price (INR)",
    "GST %", "GST Amount (INR)", "Promo", "Status", "Payment", "Payment Option", "Amount Paid (INR)", "Balance Due (INR)",
]


def _check_deleted(deleted: str) -> str:
    if deleted not in _DELETED_MODES:
        raise HTTPException(status_code=422, detail=f"deleted must be one of {', '.join(_DELETED_MODES)}.")
    return deleted


def _csv_cell(value) -> str:
    """Neutralise spreadsheet formulas: names and promo codes are customer-controlled, and a cell
    starting with = + - @ would execute when the owner opens the export in Excel/Sheets."""
    text = "" if value is None else str(value)
    return "'" + text if text[:1] in ("=", "+", "-", "@", "\t", "\r") else text


def _gst_amount(price, rate):
    if price is None or rate is None:
        return ""
    return f"{price - (price * 100) / (100 + rate):.2f}"


def _csv_stream(rows):
    """Yield the CSV in chunks while rows are read from the database in batches."""
    buf = io.StringIO()
    writer = csv.writer(buf, quoting=csv.QUOTE_ALL)
    writer.writerow(_EXPORT_HEADERS)
    yield "\ufeff" + buf.getvalue()  # BOM so Excel reads UTF-8 names correctly
    buf.seek(0)
    buf.truncate()
    n = 0
    for b in rows:
        writer.writerow([_csv_cell(v) for v in (
            b.bookingRef, b.name, b.contact, b.sportSlug, b.date, b.startTime, b.endTime, b.party_size,
            b.price, b.gst_rate_percent, _gst_amount(b.price, b.gst_rate_percent), b.promo_code, b.status, b.paymentStatus,
            "advance" if is_advance(b) else "full", f"{amount_paid(b):.2f}", f"{balance_due(b):.2f}")])
        n += 1
        if n % 200 == 0:
            yield buf.getvalue()
            buf.seek(0)
            buf.truncate()
    if buf.tell():
        yield buf.getvalue()


@router.get("/admin/bookings")
def list_bookings(
    sport: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    status: str | None = None,
    deleted: str = "no",
    sort_by: str = "date",
    sort_dir: str = "desc",
    limit: int = 25,
    offset: int = 0,
    _: str = Depends(get_current_admin),
):
    """One page, filtered and sorted in SQL. `deleted`: no (default) | only | all."""
    items, total = booking_repo.query(
        sport=sport, date_from=date_from, date_to=date_to, status=status, deleted=_check_deleted(deleted),
        sort_by=sort_by, sort_dir=sort_dir, limit=limit, offset=offset,
    )
    return {"items": items, "total": total}


@router.get("/admin/bookings/export")
def export_bookings(
    req: Request,
    sport: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    status: str | None = None,
    deleted: str = "no",
    sort_by: str = "date",
    sort_dir: str = "desc",
    admin: dict = Depends(get_current_admin),
):
    """CSV download, streamed row by row so a large export never sits in memory."""
    filters = dict(sport=sport, date_from=date_from, date_to=date_to, status=status, deleted=_check_deleted(deleted))
    audit("booking.export", admin, request=req, entity_type="booking", detail=filters)  # contains customer PII
    rows = booking_repo.iter_primary(**filters, sort_by=sort_by, sort_dir=sort_dir)
    filename = f"bookings-{datetime.now(timezone.utc).date().isoformat()}.csv"
    return StreamingResponse(_csv_stream(rows), media_type="text/csv; charset=utf-8",
                             headers={"Content-Disposition": f'attachment; filename="{filename}"'})


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
    """Soft delete: the booking disappears from every list and lookup but stays in the books.
    An active booking is cancelled first (its slot is freed and the customer told). Refused while
    money is still held (refund first) or café orders are linked."""
    booking = booking_repo.get_by_id(booking_id)
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found.")
    if booking.deleted_at:
        raise HTTPException(status_code=409, detail="This booking is already deleted.")
    if booking.paymentStatus in ("paid", "partially_refunded"):
        raise HTTPException(status_code=409, detail="This booking holds a payment. Use Cancel & refund (or Refund) before deleting it.")
    if order_repo.exists_for_booking(booking.id):
        raise HTTPException(status_code=409, detail="Café orders are linked to this booking, so it cannot be deleted.")
    was_active = booking.status in ("pending", "confirmed")
    if was_active:
        booking_repo.cancel_by_ref(booking.bookingRef)
    booking_repo.soft_delete(booking.bookingRef, admin["sub"])
    if was_active:
        notify_booking_cancelled(booking.bookingRef)
    audit("booking.delete", admin, request=req, entity_type="booking", entity_id=booking_id,
          detail={"bookingRef": booking.bookingRef, "status": booking.status, "paymentStatus": booking.paymentStatus,
                  "price": booking.price, "cancelledByDelete": was_active})


@router.post("/admin/bookings/{booking_id}/collect-balance")
def collect_balance(booking_id: str, body: CollectBalanceRequest, req: Request, admin: dict = Depends(get_current_admin)):
    """Record money taken at the venue for the balance of an advance booking (cash, UPI or card).
    Amount defaults to the whole balance and can never exceed it."""
    booking = _primary(booking_id)
    if booking.deleted_at:
        raise HTTPException(status_code=409, detail="This booking is deleted.")
    if not is_advance(booking):
        raise HTTPException(status_code=409, detail="This booking was paid in full online, so there is no balance to collect.")
    if booking.status not in ("confirmed", "completed") or booking.paymentStatus != "paid":
        raise HTTPException(status_code=409, detail="The balance can be collected only on a confirmed booking whose advance is paid.")
    due = money(balance_due(booking))
    if due <= 0:
        raise HTTPException(status_code=409, detail="The balance has already been collected.")
    amount = due if body.amount is None else money(body.amount)
    if amount > due:
        raise HTTPException(status_code=422, detail=f"Amount exceeds the balance due (Rs. {due}).")
    updated = booking_repo.add_balance_collected(booking.id, float(amount), body.mode, datetime.now(timezone.utc).isoformat(), admin["sub"])
    audit("booking.balance_collected", admin, request=req, entity_type="booking", entity_id=booking.id,
          detail={"bookingRef": booking.bookingRef, "amount": float(amount), "mode": body.mode,
                  "reference": body.reference, "balanceLeft": balance_due(updated)})
    return {"bookingRef": booking.bookingRef, "collected": float(amount), "balanceDue": balance_due(updated),
            "amountPaid": amount_paid(updated)}


@router.post("/admin/bookings/{booking_id}/restore")
def restore_booking(booking_id: str, req: Request, admin: dict = Depends(get_current_admin)):
    """Bring a soft-deleted booking back into the lists. It keeps the status it was left in (cancelled
    if the delete cancelled it): restoring never re-books a slot."""
    booking = booking_repo.get_by_id(booking_id)
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found.")
    if not booking.deleted_at:
        raise HTTPException(status_code=409, detail="This booking is not deleted.")
    booking_repo.restore(booking.bookingRef)
    audit("booking.restore", admin, request=req, entity_type="booking", entity_id=booking_id,
          detail={"bookingRef": booking.bookingRef, "status": booking.status})
    return booking_repo.get_by_id(booking_id)


@router.delete("/admin/bookings/{booking_id}/purge", status_code=204)
def purge_booking(booking_id: str, req: Request, admin: dict = Depends(require_superadmin)):
    """Permanent removal (superadmin only). Refused when a real payment exists: its record is a
    financial document. Dev (noop) payments carry no money and are removed with the booking."""
    booking = booking_repo.get_by_id(booking_id)
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found.")
    if order_repo.exists_for_booking(booking.id):
        raise HTTPException(status_code=409, detail="Café orders are linked to this booking, so it cannot be purged.")
    payments = booking_payment_repo.list_by_ref(booking.bookingRef)
    real_money = [p for p in payments if p.provider != "noop" and p.status in ("verified", "refunded", "partially_refunded", "paid_orphan", "amount_mismatch")]
    if real_money:
        raise HTTPException(status_code=409, detail="A real payment is recorded for this booking, so it cannot be purged.")
    booking_payment_repo.delete_by_ref(booking.bookingRef)
    removed = booking_repo.purge_by_ref(booking.bookingRef)
    audit("booking.purge", admin, request=req, entity_type="booking", entity_id=booking_id,
          detail={"bookingRef": booking.bookingRef, "rows": removed, "status": booking.status, "price": booking.price})


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
    return build_quote(payment.amount, payment.refundedAmount, hours, load_tiers(), non_refundable=non_refundable(booking))


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
