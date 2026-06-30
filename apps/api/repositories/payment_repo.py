import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select, func

from db import _session
from db_models import PaymentRow


class SqlitePaymentRepository:
    def create(
        self,
        order_id: str,
        mode: str,
        amount: float,
        created_by: str,
        reference: Optional[str] = None,
    ) -> PaymentRow:
        with _session() as s:
            now = datetime.now(timezone.utc).isoformat()
            row = PaymentRow(
                id=str(uuid.uuid4()),
                order_id=order_id,
                invoice_id=None,
                mode=mode,
                amount=amount,
                reference=reference,
                createdBy=created_by,
                createdAt=now,
            )
            s.add(row)
            s.flush()
            return row

    def get_by_order(self, order_id: str) -> list[PaymentRow]:
        with _session() as s:
            stmt = select(PaymentRow).where(PaymentRow.order_id == order_id).order_by(PaymentRow.createdAt)
            return list(s.scalars(stmt).all())

    def total_paid(self, order_id: str) -> float:
        with _session() as s:
            stmt = select(func.sum(PaymentRow.amount)).where(PaymentRow.order_id == order_id)
            result = s.scalar(stmt)
            return float(result) if result is not None else 0.0
