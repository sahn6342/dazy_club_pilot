import json
import uuid
from datetime import datetime, timezone, date as date_cls
from fastapi import APIRouter, HTTPException, Request
from sqlalchemy.exc import IntegrityError

from models import BookingRequest, BookingRecord, BookingPaymentVerifyRequest, BookingLookupResult
from deps import booking_repo, court_repo, customer_repo, promo_repo, booking_payment_repo, payment_provider
from rate_limit import booking_lookup_limiter
from services.availability_service import find_slot
from services.pricing_service import apply_promo, PromoError
from services.notification_service import notify_booking_confirmed, notify_booking_payment_pending

router = APIRouter()


@router.post("/bookings", status_code=201)
def create_booking(request: BookingRequest):
    # Resolve all requested slots (in order).
    slots = []
    for sid in request.slotIds:
        slot = find_slot(request.sportSlug, request.date, sid)
        if not slot:
            raise HTTPException(status_code=404, detail=f"Slot {sid} not found.")
        if not slot.available:
            raise HTTPException(status_code=409, detail=f"Slot {slot.startTime} is unavailable (already booked or elapsed).")
        slots.append(slot)

    # Validate contiguity for multi-slot bookings.
    for i in range(1, len(slots)):
        if slots[i - 1].endTime != slots[i].startTime:
            raise HTTPException(
                status_code=400,
                detail=f"Slots {slots[i-1].startTime}–{slots[i-1].endTime} and {slots[i].startTime}–{slots[i].endTime} are not consecutive.",
            )

    court_id = slots[0].courtId or court_repo.id_for_sport(request.sportSlug)

    # Pricing: sum all slot prices, then apply promo on the total.
    all_free = all(s.finalPrice is None for s in slots)
    base_total: float | None = None if all_free else sum(s.finalPrice or 0.0 for s in slots)

    final_price = base_total
    applied_promo = None
    if request.promoCode:
        today = date_cls.today().isoformat()
        try:
            promo = promo_repo.validate_and_increment(request.promoCode, request.sportSlug, today)
        except PromoError as e:
            raise HTTPException(status_code=400, detail=e.detail)
        final_price = apply_promo(promo, base_total)
        applied_promo = promo.code

    customer = customer_repo.upsert_by_contact(request.name, request.contact)
    ref = str(uuid.uuid4())[:8].upper()
    now = datetime.now(timezone.utc).isoformat()

    # Build one BookingRow per slot. Primary row carries price/promo/message.
    records = [
        BookingRecord(
            id=str(uuid.uuid4()),
            bookingRef=ref,
            customer_id=customer.id,
            court_id=court_id,
            slotId=slot.id,
            name=request.name,
            contact=request.contact,
            sportSlug=request.sportSlug,
            date=request.date,
            startTime=slot.startTime,
            endTime=slot.endTime,
            party_size=request.players,
            price=final_price if i == 0 else None,
            promo_code=applied_promo if i == 0 else None,
            message=request.message if i == 0 else None,
            status="pending",
            createdAt=now,
            is_primary=(i == 0),
        )
        for i, slot in enumerate(slots)
    ]

    try:
        for rec in records:
            booking_repo.create(rec)
    except IntegrityError:
        # Partial unique index uq_active_court_slot fired on one of the slots.
        if applied_promo:
            promo_repo.decrement_use(applied_promo)
        raise HTTPException(status_code=409, detail="One or more slots are unavailable (booking conflict).")

    response = {
        "bookingRef": ref,
        "name": request.name,
        "sport": request.sportSlug,
        "date": request.date,
        "startTime": slots[0].startTime,
        "endTime": slots[-1].endTime,
        "time": slots[0].startTime,
        "slotCount": len(slots),
        "price": final_price,
        "basePrice": base_total,
        "discountPercent": slots[0].discountPercent,
        "promoCode": applied_promo,
    }

    # A free booking (promo covers it entirely, or the slot has no price) needs
    # no payment step — confirm immediately. Otherwise the slot is held
    # "pending" (see the timeout sweep in availability_service) until payment
    # is verified via /bookings/{ref}/payment/verify or the provider webhook.
    if not final_price:
        booking_repo.confirm_payment_by_ref(ref)
        notify_booking_confirmed(ref)
        response["status"] = "confirmed"
        response["paymentRequired"] = False
        return response

    order = payment_provider.create_order(amount=final_price, ref=ref)
    booking_payment_repo.create(
        booking_ref=ref, provider=order.provider, provider_order_id=order.providerOrderId,
        amount=order.amount, checkout_json=json.dumps(order.checkout),
    )
    notify_booking_payment_pending(ref)
    response["status"] = "pending"
    response["paymentRequired"] = True
    response["checkout"] = order.checkout
    return response


@router.post("/bookings/{booking_ref}/payment/verify")
def verify_booking_payment(booking_ref: str, body: BookingPaymentVerifyRequest):
    bookings = booking_repo.get_by_ref(booking_ref)
    if not bookings:
        raise HTTPException(status_code=404, detail="Booking not found.")
    primary = next((b for b in bookings if b.is_primary), bookings[0])

    # Idempotent — the client callback and the provider webhook can both land here.
    if primary.paymentStatus == "paid":
        return {"status": "confirmed", "paymentStatus": "paid"}

    verification = payment_provider.verify_payment(body.providerOrderId, body.providerPaymentId, body.signature)
    if not verification.verified:
        raise HTTPException(status_code=400, detail=verification.reason or "Payment verification failed.")

    booking_payment_repo.mark_verified(body.providerOrderId, verification.providerPaymentId, body.signature)
    booking_repo.confirm_payment_by_ref(booking_ref)
    notify_booking_confirmed(booking_ref)
    return {"status": "confirmed", "paymentStatus": "paid"}


@router.get("/bookings/lookup", response_model=BookingLookupResult)
def lookup_booking(ref: str, contact: str, req: Request):
    """Self-service resume/lookup — no login. Identity is the ref + matching
    contact (same trust model as the café pre-order endpoint). Reuses the
    payment order created at booking time so a customer resuming payment
    never gets handed a second, orphaned Razorpay order."""
    client_ip = req.client.host if req.client else "unknown"
    booking_lookup_limiter.check(client_ip, message="Too many lookup attempts. Try again later.")

    bookings = booking_repo.get_by_ref(ref)
    if not bookings:
        raise HTTPException(status_code=404, detail="Booking not found.")
    primary = next((b for b in bookings if b.is_primary), bookings[0])

    if primary.contact.strip().lower() != contact.strip().lower():
        raise HTTPException(status_code=404, detail="Booking not found.")

    last = bookings[-1] if len(bookings) > 1 else primary
    result = BookingLookupResult(
        bookingRef=primary.bookingRef,
        name=primary.name,
        status=primary.status,
        sport=primary.sportSlug,
        date=primary.date,
        startTime=primary.startTime,
        endTime=last.endTime,
        slotCount=len(bookings),
        price=primary.price,
        paymentRequired=primary.status == "pending" and primary.paymentStatus != "paid",
    )
    if result.paymentRequired:
        payment = booking_payment_repo.get_by_ref(ref)
        if payment and payment.checkoutJson:
            result.checkout = json.loads(payment.checkoutJson)
    return result
