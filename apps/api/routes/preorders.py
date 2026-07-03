"""Café × turf synergy (Detailed-Roadmap Phase 7, sub-step 1): let a customer
add café items to their confirmed booking so the counter can have it ready
for when they arrive. Public — identity is the booking ref + matching
contact (same trust model as booking creation), no login."""
from fastapi import APIRouter, HTTPException

from deps import booking_repo, menu_item_repo, menu_category_repo, order_repo
from models import PreOrderRequest, PreOrderResult, PreOrderLineDto, PublicMenuResponse, PublicMenuItemDto, MenuCategoryDto
from services.pos_service import create_order as svc_create_order

router = APIRouter()


@router.get("/menu", response_model=PublicMenuResponse)
def get_public_menu():
    categories = [MenuCategoryDto.model_validate(c) for c in menu_category_repo.get_all(active_only=True)]
    items = [PublicMenuItemDto.model_validate(i) for i in menu_item_repo.get_all(available_only=True)]
    return PublicMenuResponse(categories=categories, items=items)


@router.post("/bookings/{booking_ref}/preorder", response_model=PreOrderResult, status_code=201)
def create_preorder(booking_ref: str, body: PreOrderRequest):
    bookings = booking_repo.get_by_ref(booking_ref)
    if not bookings:
        raise HTTPException(status_code=404, detail="Booking not found.")
    primary = next((b for b in bookings if b.is_primary), bookings[0])

    # Generic 404 either way — avoids leaking whether a ref exists to a guesser
    # trying contacts, matches the payment-verify / lookup trust model.
    if primary.contact.strip().lower() != body.contact.strip().lower():
        raise HTTPException(status_code=404, detail="Booking not found.")
    if primary.status != "confirmed":
        raise HTTPException(status_code=400, detail="Booking must be confirmed before adding a pre-order.")

    for item_req in body.items:
        if not menu_item_repo.get_by_id(item_req.menu_item_id):
            raise HTTPException(status_code=404, detail=f"Menu item {item_req.menu_item_id} not found.")

    order = svc_create_order(
        order_type="takeaway",
        created_by="customer",
        items=body.items,
        table_id=None,
        notes=f"Pre-order for booking {booking_ref}",
        booking_id=primary.id,
    )
    lines = order_repo.get_items(order.id)
    return PreOrderResult(
        orderNo=order.orderNo,
        total=float(order.total),
        items=[PreOrderLineDto(name=l.nameSnapshot, qty=float(l.qty), lineTotal=float(l.lineTotal)) for l in lines],
    )
