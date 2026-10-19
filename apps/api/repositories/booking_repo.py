from typing import Optional

from sqlalchemy import select, delete as sa_delete, update as sa_update, func, or_

from models import BookingRecord
from repositories.base import BaseRepository
from db import _session
from db_models import BookingRow


def _to_model(row: BookingRow) -> BookingRecord:
    return BookingRecord(
        id=row.id,
        bookingRef=row.bookingRef,
        customer_id=row.customer_id,
        court_id=row.court_id,
        slotId=row.slotId,
        name=row.name,
        contact=row.contact,
        sportSlug=row.sportSlug,
        date=row.date,
        startTime=row.startTime,
        endTime=row.endTime,
        party_size=row.party_size,
        price=float(row.price) if row.price is not None else None,
        promo_code=row.promo_code,
        message=row.message,
        status=row.status,
        createdAt=row.createdAt,
        is_primary=row.is_primary,
        paymentStatus=row.paymentStatus,
        depositAmount=float(row.depositAmount) if row.depositAmount is not None else None,
        gst_rate_percent=float(row.gst_rate_percent) if row.gst_rate_percent is not None else None,
        email=row.email,
    )


class SqliteBookingRepository(BaseRepository[BookingRecord]):
    def get_all(self) -> list[BookingRecord]:
        """Return primary booking rows only (one per bookingRef)."""
        with _session() as s:
            return [
                _to_model(r)
                for r in s.scalars(select(BookingRow).where(BookingRow.is_primary.is_(True))).all()
            ]

    def get_by_id(self, id: str) -> Optional[BookingRecord]:
        with _session() as s:
            row = s.get(BookingRow, id)
            return _to_model(row) if row else None

    def create(self, item: BookingRecord) -> BookingRecord:
        with _session() as s:
            row = BookingRow(**item.model_dump())
            s.add(row)
            s.flush()
            return _to_model(row)

    def create_many(self, items: list[BookingRecord]) -> list[BookingRecord]:
        """Insert all rows in ONE transaction: if any row violates the unique-slot
        index (IntegrityError), none are persisted."""
        with _session() as s:
            rows = [BookingRow(**item.model_dump()) for item in items]
            s.add_all(rows)
            s.flush()
            return [_to_model(r) for r in rows]

    def update(self, id: str, data: dict) -> Optional[BookingRecord]:
        with _session() as s:
            row = s.get(BookingRow, id)
            if not row:
                return None
            for k, v in data.items():
                if hasattr(row, k):
                    setattr(row, k, v)
            s.flush()
            return _to_model(row)

    def cancel_by_ref(self, booking_ref: str) -> None:
        """Cancel all rows (primary + secondary) sharing a bookingRef."""
        with _session() as s:
            s.execute(
                sa_update(BookingRow)
                .where(BookingRow.bookingRef == booking_ref)
                .values(status="cancelled")
            )

    def get_by_ref(self, booking_ref: str) -> list[BookingRecord]:
        with _session() as s:
            rows = s.scalars(select(BookingRow).where(BookingRow.bookingRef == booking_ref)).all()
            return [_to_model(r) for r in rows]

    def confirm_payment_by_ref(self, booking_ref: str) -> int:
        """Payment verified — mark rows sharing this ref paid (pending rows also
        become confirmed). Returns rows updated; 0 means the booking is cancelled
        or already paid, so a late payment must NOT resurrect it."""
        with _session() as s:
            pending = s.execute(
                sa_update(BookingRow)
                .where(BookingRow.bookingRef == booking_ref, BookingRow.status == "pending")
                .values(status="confirmed", paymentStatus="paid")
            ).rowcount
            # Admin may have confirmed/completed it manually before the payment landed.
            manual = s.execute(
                sa_update(BookingRow)
                .where(
                    BookingRow.bookingRef == booking_ref,
                    BookingRow.status.in_(["confirmed", "completed"]),
                    BookingRow.paymentStatus == "unpaid",
                )
                .values(paymentStatus="paid")
            ).rowcount
            return pending + manual

    def refund_by_ref(self, booking_ref: str) -> None:
        """Refund issued — mark refunded and cancel (frees the slot)."""
        with _session() as s:
            s.execute(
                sa_update(BookingRow)
                .where(BookingRow.bookingRef == booking_ref)
                .values(status="cancelled", paymentStatus="refunded")
            )

    def expire_stale_pending(self, before_iso: str) -> list[BookingRecord]:
        """Cancel pending+unpaid bookings created before `before_iso` (the
        payment-timeout sweep) — frees their slots. Returns cancelled primary rows."""
        with _session() as s:
            stale = s.scalars(
                select(BookingRow).where(
                    BookingRow.status == "pending",
                    BookingRow.paymentStatus == "unpaid",
                    BookingRow.is_primary.is_(True),
                    BookingRow.createdAt < before_iso,
                )
            ).all()
            if not stale:
                return []
            refs = [r.bookingRef for r in stale]
            s.execute(
                sa_update(BookingRow)
                .where(
                    BookingRow.bookingRef.in_(refs),
                    BookingRow.status == "pending",
                    BookingRow.paymentStatus == "unpaid",
                )
                .values(status="cancelled")
            )
            return [_to_model(r) for r in stale]

    def delete(self, id: str) -> bool:
        with _session() as s:
            row = s.get(BookingRow, id)
            if not row:
                return False
            s.delete(row)
            return True

    def clear(self) -> None:
        with _session() as s:
            s.execute(sa_delete(BookingRow))

    def search_by_contact(self, contact: str) -> list[BookingRecord]:
        """Primary rows where contact OR email matches (case-insensitive). Newest first, max 10."""
        with _session() as s:
            contact_lc = contact.strip().lower()
            rows = s.scalars(
                select(BookingRow)
                .where(
                    BookingRow.is_primary.is_(True),
                    or_(
                        func.lower(BookingRow.contact) == contact_lc,
                        func.lower(BookingRow.email) == contact_lc,
                    ),
                )
                .order_by(BookingRow.createdAt.desc())
                .limit(10)
            ).all()
            return [_to_model(r) for r in rows]

    # ── slot-availability derivation helpers ──
    def exists_for_slot(self, slot_id: str) -> bool:
        with _session() as s:
            return s.scalar(select(BookingRow.id).where(BookingRow.slotId == slot_id).limit(1)) is not None

    def slot_ids_for_date(self, sport: str, date: str) -> set[str]:
        with _session() as s:
            rows = s.scalars(
                select(BookingRow.slotId).where(BookingRow.sportSlug == sport, BookingRow.date == date)
            ).all()
            return set(rows)
