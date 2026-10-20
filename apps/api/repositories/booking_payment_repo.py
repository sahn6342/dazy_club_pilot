import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select, delete as sa_delete, update as sa_update

from models import BookingPaymentDto
from db import _session
from db_models import BookingPaymentRow


def _to_model(row: BookingPaymentRow) -> BookingPaymentDto:
    return BookingPaymentDto(
        id=row.id, bookingRef=row.bookingRef, provider=row.provider,
        providerOrderId=row.providerOrderId, providerPaymentId=row.providerPaymentId,
        amount=float(row.amount), status=row.status, checkoutJson=row.checkoutJson,
        createdAt=row.createdAt, refundedAmount=float(row.refunded_amount or 0),
    )


# booking_payments.status lifecycle
CREATED = "created"            # order made, awaiting payment
VERIFIED = "verified"          # paid and booking confirmed
EXPIRED = "expired"            # booking timed out unpaid
REFUNDED = "refunded"          # refunded in full via admin or auto-refund
PARTIALLY_REFUNDED = "partially_refunded"  # some, not all, of the payment refunded
PAID_ORPHAN = "paid_orphan"    # paid after booking expired; refund failed, needs admin action
AMOUNT_MISMATCH = "amount_mismatch"  # webhook amount != order amount; booking NOT confirmed, needs admin review


class SqliteBookingPaymentRepository:
    def create(
        self, booking_ref: str, provider: str, provider_order_id: str, amount: float,
        checkout_json: str | None = None,
    ) -> BookingPaymentDto:
        with _session() as s:
            row = BookingPaymentRow(
                id=str(uuid.uuid4()), bookingRef=booking_ref, provider=provider,
                providerOrderId=provider_order_id, providerPaymentId=None,
                amount=amount, status=CREATED, checkoutJson=checkout_json,
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

    def mark_expired_by_refs(self, booking_refs: list[str]) -> None:
        """Mark unpaid payment records as expired for timed-out bookings."""
        if not booking_refs:
            return
        with _session() as s:
            s.execute(
                sa_update(BookingPaymentRow)
                .where(
                    BookingPaymentRow.bookingRef.in_(booking_refs),
                    BookingPaymentRow.status == CREATED,
                )
                .values(status="expired")
            )

    def list_unsettled(self, older_than_iso: str, newer_than_iso: str) -> list[BookingPaymentDto]:
        """Orders still awaiting a payment signal (created, or expired in case the
        customer paid at the last second) inside the reconciliation window."""
        with _session() as s:
            rows = s.scalars(
                select(BookingPaymentRow).where(
                    BookingPaymentRow.status.in_([CREATED, EXPIRED]),
                    BookingPaymentRow.createdAt < older_than_iso,
                    BookingPaymentRow.createdAt > newer_than_iso,
                )
            ).all()
            return [_to_model(r) for r in rows]

    def set_status(self, provider_order_id: str, status: str) -> None:
        with _session() as s:
            row = s.scalar(select(BookingPaymentRow).where(BookingPaymentRow.providerOrderId == provider_order_id))
            if row:
                row.status = status

    def mark_late_payment(
        self, provider_order_id: str, provider_payment_id: str, signature: str | None, status: str
    ) -> Optional[BookingPaymentDto]:
        """Record a payment that arrived after the booking was no longer pending."""
        with _session() as s:
            row = s.scalar(select(BookingPaymentRow).where(BookingPaymentRow.providerOrderId == provider_order_id))
            if not row:
                return None
            row.status = status
            row.providerPaymentId = provider_payment_id
            row.signature = signature
            s.flush()
            return _to_model(row)

    def reserve_refund(self, payment_id: str, amount: float) -> bool:
        """Atomically add `amount` to refunded_amount iff it still fits within what was paid.
        One conditional UPDATE, so concurrent refunds cannot jointly exceed the payment."""
        with _session() as s:
            result = s.execute(
                sa_update(BookingPaymentRow)
                .where(
                    BookingPaymentRow.id == payment_id,
                    BookingPaymentRow.refunded_amount + amount <= BookingPaymentRow.amount + 0.004,  # float slop
                )
                .values(refunded_amount=BookingPaymentRow.refunded_amount + amount)
            )
            return result.rowcount == 1

    def release_refund(self, payment_id: str, amount: float) -> None:
        """Undo reserve_refund after the provider refused the refund."""
        with _session() as s:
            s.execute(
                sa_update(BookingPaymentRow)
                .where(BookingPaymentRow.id == payment_id)
                .values(refunded_amount=BookingPaymentRow.refunded_amount - amount)
            )

    def list_by_ref(self, booking_ref: str) -> list[BookingPaymentDto]:
        with _session() as s:
            rows = s.scalars(select(BookingPaymentRow).where(BookingPaymentRow.bookingRef == booking_ref)).all()
            return [_to_model(r) for r in rows]

    def delete_by_ref(self, booking_ref: str) -> int:
        with _session() as s:
            return s.execute(sa_delete(BookingPaymentRow).where(BookingPaymentRow.bookingRef == booking_ref)).rowcount

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
