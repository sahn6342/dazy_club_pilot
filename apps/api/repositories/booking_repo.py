from typing import Optional

from sqlalchemy import select, delete as sa_delete, update as sa_update

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
