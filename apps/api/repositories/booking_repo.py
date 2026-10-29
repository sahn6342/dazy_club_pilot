from typing import Iterator, Optional

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
        balance_collected=float(row.balance_collected or 0),
        balance_mode=row.balance_mode,
        balance_collected_at=row.balance_collected_at,
        balance_collected_by=row.balance_collected_by,
        source=row.source,
        payment_mode=row.payment_mode,
        payment_reference=row.payment_reference,
        created_by=row.created_by,
        deleted_at=row.deleted_at,
        deleted_by=row.deleted_by,
    )


class SqliteBookingRepository(BaseRepository[BookingRecord]):
    # ── admin listing: filtering, sorting and paging happen in SQL ──────────────
    _SORTABLE = {
        "date": BookingRow.date, "createdAt": BookingRow.createdAt, "price": BookingRow.price,
        "name": func.lower(BookingRow.name), "sportSlug": BookingRow.sportSlug, "status": BookingRow.status,
    }

    @staticmethod
    def _conditions(sport, date_from, date_to, status, deleted):
        conds = [BookingRow.is_primary.is_(True)]  # one row per booking
        if sport:
            conds.append(BookingRow.sportSlug == sport)
        if date_from:
            conds.append(BookingRow.date >= date_from)
        if date_to:
            conds.append(BookingRow.date <= date_to)
        if status:
            conds.append(BookingRow.status == status)
        if deleted == "only":
            conds.append(BookingRow.deleted_at.is_not(None))
        elif deleted != "all":
            conds.append(BookingRow.deleted_at.is_(None))
        return conds

    def _ordered(self, stmt, sort_by: str, sort_dir: str):
        col = self._SORTABLE.get(sort_by, self._SORTABLE["date"])
        desc = sort_dir == "desc"
        if sort_by == "price":  # unpriced (free) bookings sort last ascending, first descending
            nulls = BookingRow.price.is_(None)
            stmt = stmt.order_by(nulls.desc() if desc else nulls.asc(), col.desc() if desc else col.asc())
        else:
            stmt = stmt.order_by(col.desc() if desc else col.asc())
        return stmt.order_by(BookingRow.createdAt.desc(), BookingRow.id)  # stable paging

    def query(
        self, *, sport: str | None = None, date_from: str | None = None, date_to: str | None = None,
        status: str | None = None, deleted: str = "no", sort_by: str = "date", sort_dir: str = "desc",
        limit: int = 25, offset: int = 0,
    ) -> "tuple[list[BookingRecord], int]":
        """One page of primary rows plus the total matching count (two queries, however big the table)."""
        conds = self._conditions(sport, date_from, date_to, status, deleted)
        with _session() as s:
            total = s.scalar(select(func.count()).select_from(BookingRow).where(*conds)) or 0
            stmt = self._ordered(select(BookingRow).where(*conds), sort_by, sort_dir)
            rows = s.scalars(stmt.offset(max(offset, 0)).limit(max(1, min(limit, 100)))).all()
            return [_to_model(r) for r in rows], total

    def iter_primary(
        self, *, sport: str | None = None, date_from: str | None = None, date_to: str | None = None,
        status: str | None = None, deleted: str = "no", sort_by: str = "date", sort_dir: str = "desc",
        batch: int = 500,
    ) -> Iterator[BookingRecord]:
        """Stream every matching primary row in batches (server-side cursor): memory stays flat for exports."""
        conds = self._conditions(sport, date_from, date_to, status, deleted)
        with _session() as s:
            stmt = self._ordered(select(BookingRow).where(*conds), sort_by, sort_dir).execution_options(yield_per=batch)
            for row in s.scalars(stmt):
                yield _to_model(row)

    def get_all(self) -> list[BookingRecord]:
        """Every live primary row. Tests and small tools only: the admin API pages in SQL instead."""
        return list(self.iter_primary(sort_by="createdAt", sort_dir="asc"))

    def get_by_id(self, id: str) -> Optional[BookingRecord]:
        with _session() as s:
            row = s.get(BookingRow, id)
            return _to_model(row) if row else None

    def create(self, item: BookingRecord) -> BookingRecord:
        with _session() as s:
            row = BookingRow(**item.model_dump(), contact_norm=item.contact.strip().lower())
            s.add(row)
            s.flush()
            return _to_model(row)

    def create_many(self, items: list[BookingRecord]) -> list[BookingRecord]:
        """Insert all rows in ONE transaction: if any row violates the unique-slot
        index (IntegrityError), none are persisted."""
        with _session() as s:
            rows = [BookingRow(**item.model_dump(), contact_norm=item.contact.strip().lower()) for item in items]
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

    def get_by_ref(self, booking_ref: str, include_deleted: bool = False) -> list[BookingRecord]:
        """Rows sharing a ref. Soft-deleted bookings are invisible unless `include_deleted`
        (internal money/notification paths set it; customer-facing lookups never do)."""
        conds = [BookingRow.bookingRef == booking_ref]
        if not include_deleted:
            conds.append(BookingRow.deleted_at.is_(None))
        with _session() as s:
            rows = s.scalars(select(BookingRow).where(*conds)).all()
            return [_to_model(r) for r in rows]

    def soft_delete(self, booking_ref: str, actor: str) -> None:
        from datetime import datetime, timezone
        with _session() as s:
            s.execute(sa_update(BookingRow).where(BookingRow.bookingRef == booking_ref)
                      .values(deleted_at=datetime.now(timezone.utc).isoformat(), deleted_by=actor))

    def restore(self, booking_ref: str) -> None:
        with _session() as s:
            s.execute(sa_update(BookingRow).where(BookingRow.bookingRef == booking_ref)
                      .values(deleted_at=None, deleted_by=None))

    def purge_by_ref(self, booking_ref: str) -> int:
        """Permanently remove every row of a booking. Superadmin purge only."""
        with _session() as s:
            return s.execute(sa_delete(BookingRow).where(BookingRow.bookingRef == booking_ref)).rowcount

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

    def add_balance_collected(self, booking_id: str, amount: float, mode: str, at: str, by: str) -> Optional[BookingRecord]:
        """Record money taken at the venue against the primary row (adds to what was collected before)."""
        with _session() as s:
            row = s.get(BookingRow, booking_id)
            if not row:
                return None
            row.balance_collected = round(float(row.balance_collected or 0) + amount, 2)
            row.balance_mode, row.balance_collected_at, row.balance_collected_by = mode, at, by
            s.flush()
            return _to_model(row)

    def apply_refund_state(self, booking_ref: str, payment_status: str, cancel: bool) -> None:
        """After a (partial) refund: record paymentStatus on every row; also cancel (frees the slot)."""
        values = {"paymentStatus": payment_status}
        if cancel:
            values["status"] = "cancelled"
        with _session() as s:
            s.execute(sa_update(BookingRow).where(BookingRow.bookingRef == booking_ref).values(**values))

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

    def count_pending_by_contact(self, contact: str) -> int:
        """Bookings (not rows) still awaiting payment for this contact, case-insensitive."""
        with _session() as s:
            return s.scalar(
                select(func.count()).select_from(BookingRow).where(
                    BookingRow.is_primary.is_(True),
                    BookingRow.status == "pending",
                    BookingRow.deleted_at.is_(None),
                    BookingRow.contact_norm == contact.strip().lower(),
                )
            ) or 0

    def search_by_contact(self, contact: str, limit: int = 10) -> list[BookingRecord]:
        """Primary rows where contact OR email matches (case-insensitive). Newest first, at most `limit`."""
        with _session() as s:
            contact_lc = contact.strip().lower()
            rows = s.scalars(
                select(BookingRow)
                .where(
                    BookingRow.is_primary.is_(True),
                    BookingRow.deleted_at.is_(None),
                    or_(
                        BookingRow.contact_norm == contact_lc,
                        func.lower(BookingRow.email) == contact_lc,
                    ),
                )
                .order_by(BookingRow.createdAt.desc())
                .limit(limit)
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
