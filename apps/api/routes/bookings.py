import uuid
from datetime import datetime, timezone, date as date_cls
from fastapi import APIRouter, HTTPException
from sqlalchemy.exc import IntegrityError

from models import BookingRequest, BookingRecord
from deps import booking_repo, court_repo, customer_repo, promo_repo
from services.availability_service import find_slot
from services.pricing_service import validate_promo, apply_promo, PromoError

router = APIRouter()


@router.post("/bookings", status_code=201)
def create_booking(request: BookingRequest):
    slot = find_slot(request.sportSlug, request.date, request.slotId)
    if not slot:
        raise HTTPException(status_code=404, detail="Slot not found.")
    if not slot.available:
        raise HTTPException(status_code=409, detail="Slot unavailable (already booked or elapsed).")

    court_id = slot.courtId or court_repo.id_for_sport(request.sportSlug)

    # Pricing: base/block-discount price from the slot, then optional promo on top.
    final_price = slot.finalPrice  # may be None (free play)
    applied_promo = None
    if request.promoCode:
        promo = promo_repo.get_by_code(request.promoCode)
        today = date_cls.today().isoformat()
        try:
            validate_promo(promo, request.sportSlug, today)
        except PromoError as e:
            raise HTTPException(status_code=400, detail=e.detail)
        final_price = apply_promo(promo, slot.finalPrice)
        applied_promo = promo.code

    # Upsert customer by contact — creates or returns existing record.
    customer = customer_repo.upsert_by_contact(request.name, request.contact)

    ref = str(uuid.uuid4())[:8].upper()
    record = BookingRecord(
        id=str(uuid.uuid4()),
        bookingRef=ref,
        customer_id=customer.id,
        court_id=court_id,
        slotId=request.slotId,
        name=request.name,
        contact=request.contact,
        sportSlug=request.sportSlug,
        date=request.date,
        startTime=request.startTime,
        endTime=slot.endTime,
        party_size=request.players,  # request.players is the public API name
        price=final_price,
        promo_code=applied_promo,
        message=request.message,
        status="pending",
        createdAt=datetime.now(timezone.utc).isoformat(),
    )

    try:
        booking_repo.create(record)
    except IntegrityError:
        # Partial unique index uq_active_court_slot fired — concurrent insert beat us (capacity=1 guard).
        # For capacity>1 courts: add BEGIN IMMEDIATE transactional re-check at the SQLite engine level.
        raise HTTPException(status_code=409, detail="Slot unavailable (booking conflict).")

    if applied_promo:
        promo_repo.increment_use(applied_promo)

    return {
        "status": "confirmed",
        "bookingRef": ref,
        "name": request.name,
        "sport": request.sportSlug,
        "date": request.date,
        "time": request.startTime,
        "price": final_price,
        "basePrice": slot.price,
        "discountPercent": slot.discountPercent,
        "promoCode": applied_promo,
    }
