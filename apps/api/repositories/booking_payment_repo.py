import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select, delete as sa_delete

from models import BookingPaymentDto
from db import _session
from db_models import BookingPaymentRow


def _to_model(row: BookingPaymentRow) -> BookingPaymentDto:
    return BookingPaymentDto(
        id=row.id, bookingRef=row.bookingRef, provider=row.provider,
        providerOrderId=row.providerOrderId, providerPaymentId=row.providerPaymentId,
        amount=float(row.amount), status=row.status, createdAt=row.createdAt,
    )


class SqliteBookingPaymentRepository:
    def create(self, booking_ref: str, provider: str, provider_order_id: str, amount: float) -> BookingPaymentDto:
        with _session() as s:
            row = BookingPaymentRow(
                id=str(uuid.uuid4()), bookingRef=booking_ref, provider=provider,
                providerOrderId=provider_order_id, providerPaymentId=None,
                amount=amount, status="created",
                createdAt=datetime.now(timezone.utc).isoformat(),
            )
            s.add(row)
            s.flush()
            return _to_model(row)

    def get_by_order_id(self, provider_order_id: str) -> Optional[BookingPaymentDto]:
        with _session() as s:
            row = s.scalar(select(BookingPaymentRow).where(BookingPaymentRow.providerOrderId == provider_order_id))
            return _to_model(row) if row else None

    def get_by_ref(self, booking_ref: str) -> Optional[BookingPaymentDto]:
        with _session() as s:
            row = s.scalar(
                select(BookingPaymentRow)
                .where(BookingPaymentRow.bookingRef == booking_ref)
                .order_by(BookingPaymentRow.createdAt.desc())
            )
            return _to_model(row) if row else None

    def mark_verified(self, provider_order_id: str, provider_payment_id: str, signature: str | None) -> Optional[BookingPaymentDto]:
        with _session() as s:
            row = s.scalar(select(BookingPaymentRow).where(BookingPaymentRow.providerOrderId == provider_order_id))
            if not row:
                return None
            row.status = "verified"
            row.providerPaymentId = provider_payment_id
            row.signature = signature
            s.flush()
            return _to_model(row)

    def mark_refunded(self, booking_ref: str) -> None:
        with _session() as s:
            row = s.scalar(
                select(BookingPaymentRow)
                .where(BookingPaymentRow.bookingRef == booking_ref)
                .order_by(BookingPaymentRow.createdAt.desc())
            )
            if row:
                row.status = "refunded"
                s.flush()

    def clear(self) -> None:
        with _session() as s:
            s.execute(sa_delete(BookingPaymentRow))
