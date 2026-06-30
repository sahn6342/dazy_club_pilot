from fastapi import APIRouter, Depends, HTTPException

from auth import get_current_cashier
from deps import kot_repo, order_repo, payment_repo
from models import KotDto, KotItemDto, KotStatusUpdate, OrderItemDto

router = APIRouter()


def _kot_dto(kot) -> KotDto:
    """Build KotDto including orderNo and items."""
    from db import _session
    from db_models import OrderItemRow
    from sqlalchemy import select

    dto = KotDto.model_validate(kot)

    # Populate orderNo
    order = order_repo.get_by_id(kot.order_id)
    if order:
        dto.orderNo = order.orderNo

    # Populate items
    with _session() as s:
        stmt = select(OrderItemRow).where(
            OrderItemRow.kot_id == kot.id,
            OrderItemRow.voided.is_(False),
        )
        items = list(s.scalars(stmt).all())
    dto.items = [KotItemDto.model_validate(i) for i in items]

    return dto


@router.get("/cafe/kots", response_model=list[KotDto])
def list_kots(
    station: str | None = None,
    status: str | None = None,
    _=Depends(get_current_cashier),
):
    kots = kot_repo.get_all(station=station, status=status)
    return [_kot_dto(k) for k in kots]


@router.patch("/cafe/kots/{kot_id}/status", response_model=KotDto)
def update_kot_status(kot_id: str, body: KotStatusUpdate, _=Depends(get_current_cashier)):
    kot = kot_repo.update_status(kot_id, body.status)
    if not kot:
        raise HTTPException(status_code=404, detail="KOT not found.")
    return _kot_dto(kot)
