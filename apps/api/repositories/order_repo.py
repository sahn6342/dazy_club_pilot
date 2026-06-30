import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select

from db import _session
from db_models import OrderRow, OrderItemRow


class SqliteOrderRepository:
    def create(
        self,
        order_type: str,
        created_by: str,
        table_id: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> OrderRow:
        with _session() as s:
            ts_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
            order_no = f"ORD-{ts_ms % 100000:05d}"
            now = datetime.now(timezone.utc).isoformat()
            row = OrderRow(
                id=str(uuid.uuid4()),
                orderNo=order_no,
                orderType=order_type,
                table_id=table_id,
                customer_id=None,
                status="open",
                subtotal=0.0,
                discountAmount=0.0,
                taxAmount=0.0,
                roundOff=0.0,
                total=0.0,
                notes=notes,
                createdBy=created_by,
                createdAt=now,
                updatedAt=now,
            )
            s.add(row)
            s.flush()
            return row

    def get_by_id(self, order_id: str) -> Optional[OrderRow]:
        with _session() as s:
            return s.get(OrderRow, order_id)

    def get_all(
        self,
        status: Optional[str] = None,
        table_id: Optional[str] = None,
    ) -> list[OrderRow]:
        with _session() as s:
            stmt = select(OrderRow).order_by(OrderRow.createdAt.desc())
            if status is not None:
                stmt = stmt.where(OrderRow.status == status)
            if table_id is not None:
                stmt = stmt.where(OrderRow.table_id == table_id)
            return list(s.scalars(stmt).all())

    def update(self, order_id: str, **kwargs) -> Optional[OrderRow]:
        with _session() as s:
            row = s.get(OrderRow, order_id)
            if not row:
                return None
            for k, v in kwargs.items():
                if v is not None and hasattr(row, k):
                    setattr(row, k, v)
            row.updatedAt = datetime.now(timezone.utc).isoformat()
            s.flush()
            return row

    def add_item(
        self,
        order_id: str,
        menu_item_id: str,
        qty: float,
        unit_price: float,
        tax_rate: float,
        name_snapshot: str,
        hsn_sac: Optional[str] = None,
    ) -> OrderItemRow:
        with _session() as s:
            line_subtotal = round(qty * unit_price, 2)
            line_tax = round(line_subtotal * (tax_rate / 100), 2)
            line_total = round(line_subtotal + line_tax, 2)
            now = datetime.now(timezone.utc).isoformat()
            item = OrderItemRow(
                id=str(uuid.uuid4()),
                order_id=order_id,
                menu_item_id=menu_item_id,
                kot_id=None,
                nameSnapshot=name_snapshot,
                qty=qty,
                unitPrice=unit_price,
                taxRatePercent=tax_rate,
                hsnSacSnapshot=hsn_sac,
                lineSubtotal=line_subtotal,
                lineTax=line_tax,
                lineTotal=line_total,
                kotStatus=None,
                voided=False,
                voidReason=None,
                createdAt=now,
            )
            s.add(item)
            s.flush()
            self._recalc_totals(order_id, s)
            s.flush()
            return item

    def void_item(self, item_id: str, reason: str) -> Optional[OrderItemRow]:
        with _session() as s:
            item = s.get(OrderItemRow, item_id)
            if not item:
                return None
            item.voided = True
            item.voidReason = reason
            s.flush()
            self._recalc_totals(item.order_id, s)
            s.flush()
            return item

    def get_items(self, order_id: str) -> list[OrderItemRow]:
        with _session() as s:
            stmt = select(OrderItemRow).where(OrderItemRow.order_id == order_id)
            return list(s.scalars(stmt).all())

    def _recalc_totals(self, order_id: str, session) -> None:
        stmt = select(OrderItemRow).where(
            OrderItemRow.order_id == order_id,
            OrderItemRow.voided.is_(False),
        )
        items = list(session.scalars(stmt).all())
        subtotal = round(sum(float(i.lineSubtotal) for i in items), 2)
        tax_amount = round(sum(float(i.lineTax) for i in items), 2)
        gross = subtotal + tax_amount
        # Simple rounding: difference between nearest rupee and computed total
        rounded = round(gross)
        round_off = round(rounded - gross, 2)
        total = round(gross + round_off, 2)

        order = session.get(OrderRow, order_id)
        if order:
            order.subtotal = subtotal
            order.taxAmount = tax_amount
            order.roundOff = round_off
            order.total = total
            order.updatedAt = datetime.now(timezone.utc).isoformat()
