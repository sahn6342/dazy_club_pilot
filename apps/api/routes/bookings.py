import json
import re
import uuid
from datetime import datetime, timezone, date as date_cls
from fastapi import APIRouter, Header, HTTPException, Request
from sqlalchemy.exc import IntegrityError

from models import BookingRequest, BookingRecord, BookingPaymentVerifyRequest, BookingLookupResult
from deps import booking_repo, court_repo, customer_repo, promo_repo, booking_payment_repo, payment_provider, cms_repo
from rate_limit import (
    booking_lookup_limiter, booking_create_limiter, booking_create_contact_limiter,
    payment_verify_limiter, client_ip,
)
from services.availability_service import find_slot
from services.pricing_service import apply_promo, gst_components, PromoError
from services.notification_service import notify_booking_confirmed, notify_booking_payment_pending
from services.payment_confirmation import confirm_verified_payment, LATE_REFUNDED
from services.turnstile import require_turnstile
from services.otp_service import normalize_contact, otp_disabled

_SEARCH_ALL_LIMIT = 200  # only used when OTP is disabled: "all bookings", but bounded
from auth import verify_otp_token

router = APIRouter()

# A customer may hold at most this many unpaid bookings at once (blocks slot-hoarding).
_MAX_PENDING_PER_CONTACT = 2

_PHONE_RE = re.compile(r"^\d{10}$")
_EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]{2,}$")


def _validate_contact_str(contact: str) -> str | None:
    v = contact.strip()
    if not v:
        return "Contact is required."
    if not _PHONE_RE.match(v) and not _EMAIL_RE.match(v):
        return "Enter a valid 10-digit mobile number or email address."
    return None


def _build_lookup_result(bookings: list, include_checkout: bool = True) -> BookingLookupResult:
    primary = next((b for b in bookings if b.is_primary), bookings[0])
    last = bookings[-1] if len(bookings) > 1 else primary
    _gst_rate = primary.gst_rate_percent
    _taxable, _gst_amt = gst_components(primary.price, _gst_rate) if (primary.price and _gst_rate) else (None, None)
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
        gst_rate_percent=_gst_rate,
        taxable_amount=_taxable,
        gst_amount=_gst_amt,
    )
    if include_checkout and result.paymentRequired:
        payment = booking_payment_repo.get_by_ref(primary.bookingRef)
        if payment and payment.checkoutJson:
            result.checkout = json.loads(payment.checkoutJson)
    return result


@router.post("/bookings", status_code=201)
def create_booking(request: BookingRequest, http_req: Request):
    booking_create_limiter.check(client_ip(http_req), "Too many booking attempts. Please try again later.")
    booking_create_contact_limiter.check(request.contact.strip().lower(), "Too many booking attempts for this contact. Please try again later.")
    require_turnstile(request.turnstileToken, client_ip(http_req))
    from services.availability_service import _sweep_stale_pending
    _sweep_stale_pending()  # expired holds must not count against the cap
    if booking_repo.count_pending_by_contact(request.contact) >= _MAX_PENDING_PER_CONTACT:
        raise HTTPException(
            status_code=429,
            detail="You already have bookings waiting for payment. Complete or wait for them to expire (15 minutes) before booking more.",
        )
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

    # Read GST rate from CMS (default 18% if key not yet present).
    gst_entry = cms_repo.get_by_id("booking_gst_rate")
    gst_rate = float(gst_entry.value) if gst_entry and gst_entry.value else 18.0

    customer = customer_repo.upsert_by_contact(request.name, request.contact, email=request.email)
    ref = str(uuid.uuid4())[:8].upper()
    now = datetime.now(timezone.utc).isoformat()

    # Build one BookingRow per slot. Primary row carries price/promo/message/GST rate.
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
            gst_rate_percent=gst_rate if i == 0 else None,
            email=request.email if i == 0 else None,
        )
        for i, slot in enumerate(slots)
    ]

    # For paid bookings, create the payment order BEFORE writing any DB rows.
    # This ensures a Razorpay outage returns a clean 503 with nothing persisted
    # and no promo usage consumed.
    order = None
    if final_price:
        try:
            order = payment_provider.create_order(amount=final_price, ref=ref)
        except RuntimeError:
            if applied_promo:
                promo_repo.decrement_use(applied_promo)
            raise HTTPException(status_code=503, detail="Payment gateway unavailable — please try again.")

    try:
        booking_repo.create_many(records)  # one transaction: all slots or none
    except IntegrityError:
        # Partial unique index uq_active_court_slot fired on one of the slots.
        # The provider order made above is simply abandoned: Razorpay has no cancel-order API,
        # and the client never receives its checkout payload, so it cannot be paid.
        if applied_promo:
            promo_repo.decrement_use(applied_promo)
        raise HTTPException(status_code=409, detail="One or more slots are unavailable (booking conflict).")

    taxable_val, gst_amt = gst_components(final_price, gst_rate) if final_price else (None, None)
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
        "gstRatePercent": gst_rate,
        "taxableAmount": taxable_val,
        "gstAmount": gst_amt,
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
def verify_booking_payment(booking_ref: str, body: BookingPaymentVerifyRequest, http_req: Request):
    payment_verify_limiter.check(client_ip(http_req), "Too many requests. Please try again shortly.")
    bookings = booking_repo.get_by_ref(booking_ref)
    if not bookings:
        raise HTTPException(status_code=404, detail="Booking not found.")
    primary = next((b for b in bookings if b.is_primary), bookings[0])

    # Idempotent — the client callback and the provider webhook can both land here.
    if primary.paymentStatus == "paid":
        return {"status": "confirmed", "paymentStatus": "paid"}

    # Fetch the payment record for THIS booking to get the authoritative providerOrderId.
    # Never trust the client-supplied providerOrderId for HMAC verification — an attacker
    # could supply a valid signature from a different (cheaper) booking to confirm this one.
    stored_payment = booking_payment_repo.get_by_ref(booking_ref)
    if not stored_payment or not stored_payment.providerOrderId:
        raise HTTPException(status_code=404, detail="No payment record found for this booking.")

    verification = payment_provider.verify_payment(
        stored_payment.providerOrderId,  # from DB — not client-supplied
        body.providerPaymentId,
        body.signature,
    )
    if not verification.verified:
        raise HTTPException(status_code=400, detail=verification.reason or "Payment verification failed.")

    result = confirm_verified_payment(
        booking_ref, stored_payment.providerOrderId, verification.providerPaymentId, body.signature
    )
    if not result.booking_confirmed:
        detail = (
            "This booking expired before payment completed. Your payment has been refunded."
            if result.outcome == LATE_REFUNDED
            else "This booking expired before payment completed. Contact support for a refund."
        )
        raise HTTPException(status_code=409, detail=detail)
    return {"status": "confirmed", "paymentStatus": "paid"}


@router.get("/bookings/lookup", response_model=BookingLookupResult)
def lookup_booking(ref: str, req: Request, contact: str | None = None):
    """Self-service lookup. Contact is optional:
    - With contact: strict identity check, checkout included (enables payment).
    - Without contact: basic info only, checkout stripped (requires contact for payment)."""
    booking_lookup_limiter.check(client_ip(req), message="Too many lookup attempts. Try again later.")

    bookings = booking_repo.get_by_ref(ref)
    if not bookings:
        raise HTTPException(status_code=404, detail="Booking not found.")
    primary = next((b for b in bookings if b.is_primary), bookings[0])

    if contact is not None:
        if primary.contact.strip().lower() != contact.strip().lower():
            raise HTTPException(status_code=404, detail="Booking not found.")
        return _build_lookup_result(bookings, include_checkout=True)

    return _build_lookup_result(bookings, include_checkout=False)


@router.get("/bookings/search", response_model=list[BookingLookupResult])
def search_bookings(contact: str, req: Request, x_otp_token: str | None = Header(default=None)):
    """Look up bookings by phone or email, newest first.
    Normally requires an OTP token (POST /otp/request then /otp/verify) proving the caller controls the contact,
    and returns up to 10. With DAZY_OTP_DISABLED=1 no code is needed and every booking is returned (capped at
    _SEARCH_ALL_LIMIT as a safety net)."""
    booking_lookup_limiter.check(client_ip(req), message="Too many lookup attempts. Try again later.")

    err = _validate_contact_str(contact)
    if err:
        raise HTTPException(status_code=422, detail=err)
    open_search = otp_disabled()
    if not open_search:
        if not x_otp_token:
            raise HTTPException(status_code=401, detail="otp_required")
        verify_otp_token(x_otp_token, normalize_contact(contact))

    primary_rows = booking_repo.search_by_contact(contact, limit=_SEARCH_ALL_LIMIT if open_search else 10)
    if not primary_rows:
        raise HTTPException(status_code=404, detail="No bookings found for that contact.")

    results = []
    for primary in primary_rows:
        all_rows = booking_repo.get_by_ref(primary.bookingRef)
        results.append(_build_lookup_result(all_rows, include_checkout=False))
    return results
