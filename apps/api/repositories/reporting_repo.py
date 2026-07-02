from sqlalchemy import select, func

from db import _session
from db_models import BookingRow, InvoiceRow, PaymentRow


class SqliteReportingRepository:
    """Read-only cross-table aggregates for owner reporting (Phase 4, DEC-024)."""

    def booking_count_and_revenue(self, local_date: str) -> tuple[int, float]:
        with _session() as s:
            stmt = select(
                func.count(BookingRow.id),
                func.coalesce(func.sum(BookingRow.price), 0),
            ).where(
                BookingRow.date == local_date,
                BookingRow.status == "confirmed",
                BookingRow.is_primary.is_(True),
            )
            count, revenue = s.execute(stmt).one()
            return int(count), float(revenue)

    def occupied_slot_count(self, local_date: str) -> int:
        with _session() as s:
            stmt = select(func.count(func.distinct(BookingRow.slotId))).where(
                BookingRow.date == local_date,
                BookingRow.status.notin_(["cancelled", "no_show"]),
            )
            return int(s.scalar(stmt) or 0)

    def cafe_revenue(self, start_utc: str, end_utc: str) -> float:
        with _session() as s:
            stmt = select(func.coalesce(func.sum(InvoiceRow.total), 0)).where(
                InvoiceRow.status == "issued",
                InvoiceRow.issuedAt >= start_utc,
                InvoiceRow.issuedAt < end_utc,
            )
            return float(s.scalar(stmt) or 0)

    def payments_by_mode(self, start_utc: str, end_utc: str) -> list[tuple[str, float, int]]:
        with _session() as s:
            stmt = (
                select(
                    PaymentRow.mode,
                    func.coalesce(func.sum(PaymentRow.amount), 0),
                    func.count(PaymentRow.id),
                )
                .where(PaymentRow.createdAt >= start_utc, PaymentRow.createdAt < end_utc)
                .group_by(PaymentRow.mode)
            )
            return [(mode, float(total), int(cnt)) for mode, total, cnt in s.execute(stmt).all()]
