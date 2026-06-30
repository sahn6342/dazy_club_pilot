from fastapi import APIRouter, Depends, HTTPException, Body

from auth import get_current_cashier
from deps import order_repo, menu_item_repo, payment_repo, invoice_repo, cafe_settings_repo
from models import (
    OrderCreate, OrderDto, OrderItemDto, OrderUpdate,
    OrderItemCreate, VoidItemRequest,
    KotDto, PaymentCreate, PaymentDto,
    InvoiceDto, InvoiceLineDto, IssueInvoiceRequest,
)
from services.pos_service import create_order as svc_create_order, fire_kot as svc_fire_kot

router = APIRouter()


def _order_dto(order_id: str) -> OrderDto:
    """Fetch order + items + payments and build OrderDto."""
    row = order_repo.get_by_id(order_id)
    if not row:
        raise HTTPException(status_code=404, detail="Order not found.")
    items = order_repo.get_items(order_id)
    payments = payment_repo.get_by_order(order_id)
    dto = OrderDto.model_validate(row)
    dto.items = [OrderItemDto.model_validate(i) for i in items]
    dto.payments = [PaymentDto.model_validate(p) for p in payments]
    return dto


@router.post("/cafe/orders", response_model=OrderDto, status_code=201)
def create_order(body: OrderCreate, cashier=Depends(get_current_cashier)):
    # Validate each requested menu item exists
    for item_req in body.items:
        if not menu_item_repo.get_by_id(item_req.menu_item_id):
            raise HTTPException(status_code=404, detail=f"Menu item {item_req.menu_item_id} not found.")
    order = svc_create_order(
        order_type=body.orderType,
        created_by=cashier["sub"],
        items=body.items,
        table_id=body.table_id,
        notes=body.notes,
    )
    return _order_dto(order.id)


@router.get("/cafe/orders", response_model=list[OrderDto])
def list_orders(
    status: str | None = None,
    table_id: str | None = None,
    _=Depends(get_current_cashier),
):
    rows = order_repo.get_all(status=status, table_id=table_id)
    result = []
    for row in rows:
        items = order_repo.get_items(row.id)
        pmts = payment_repo.get_by_order(row.id)
        dto = OrderDto.model_validate(row)
        dto.items = [OrderItemDto.model_validate(i) for i in items]
        dto.payments = [PaymentDto.model_validate(p) for p in pmts]
        result.append(dto)
    return result


@router.get("/cafe/orders/{order_id}", response_model=OrderDto)
def get_order(order_id: str, _=Depends(get_current_cashier)):
    return _order_dto(order_id)


@router.patch("/cafe/orders/{order_id}", response_model=OrderDto)
def update_order(order_id: str, body: OrderUpdate, _=Depends(get_current_cashier)):
    updates = {k: v for k, v in body.model_dump(exclude_unset=True).items() if v is not None}
    row = order_repo.update(order_id, **updates)
    if not row:
        raise HTTPException(status_code=404, detail="Order not found.")
    return _order_dto(order_id)


@router.post("/cafe/orders/{order_id}/items", response_model=OrderItemDto, status_code=201)
def add_item(order_id: str, body: OrderItemCreate, _=Depends(get_current_cashier)):
    order = order_repo.get_by_id(order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found.")
    menu_item = menu_item_repo.get_by_id(body.menu_item_id)
    if not menu_item:
        raise HTTPException(status_code=404, detail="Menu item not found.")
    item_row = order_repo.add_item(
        order_id=order_id,
        menu_item_id=menu_item.id,
        qty=body.qty,
        unit_price=float(menu_item.price),
        tax_rate=float(menu_item.taxRatePercent),
        name_snapshot=menu_item.name,
        hsn_sac=menu_item.hsnSac,
    )
    return OrderItemDto.model_validate(item_row)


@router.delete("/cafe/orders/{order_id}/items/{item_id}", status_code=204)
def void_item(
    order_id: str,
    item_id: str,
    body: VoidItemRequest,
    _=Depends(get_current_cashier),
):
    # Ensure item belongs to the given order
    items = order_repo.get_items(order_id)
    if not any(i.id == item_id for i in items):
        raise HTTPException(status_code=404, detail="Order item not found.")
    result = order_repo.void_item(item_id, body.reason)
    if not result:
        raise HTTPException(status_code=404, detail="Order item not found.")


@router.post("/cafe/orders/{order_id}/kot", response_model=list[KotDto])
def fire_kot(order_id: str, cashier=Depends(get_current_cashier)):
    order = order_repo.get_by_id(order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found.")
    kots = svc_fire_kot(order_id=order_id, cashier=cashier)
    if not kots:
        raise HTTPException(status_code=400, detail="No pending items to send to kitchen.")
    # Update order status to in_kitchen
    order_repo.update(order_id, status="in_kitchen")
    return [KotDto.model_validate(k) for k in kots]


@router.post("/cafe/orders/{order_id}/payments", response_model=PaymentDto, status_code=201)
def add_payment(order_id: str, body: PaymentCreate, cashier=Depends(get_current_cashier)):
    order = order_repo.get_by_id(order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found.")
    payment = payment_repo.create(
        order_id=order_id,
        mode=body.mode,
        amount=body.amount,
        created_by=cashier["sub"],
        reference=body.reference,
    )
    # Check if fully paid
    total_paid = payment_repo.total_paid(order_id)
    order_total = float(order.total)
    if total_paid >= order_total and order_total > 0:
        order_repo.update(order_id, status="paid")
    return PaymentDto.model_validate(payment)


@router.post("/cafe/orders/{order_id}/invoice", response_model=InvoiceDto, status_code=201)
def issue_invoice(order_id: str, body: IssueInvoiceRequest, cashier=Depends(get_current_cashier)):
    order = order_repo.get_by_id(order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found.")
    settings = cafe_settings_repo.get()
    invoice = invoice_repo.create(
        order=order,
        settings=settings,
        issued_by=cashier["sub"],
        customer_name=body.customerName,
        customer_gstin=body.customerGstin,
    )
    lines = invoice_repo.get_lines(invoice.id)
    dto = InvoiceDto.model_validate(invoice)
    dto.lines = [InvoiceLineDto.model_validate(l) for l in lines]
    return dto
