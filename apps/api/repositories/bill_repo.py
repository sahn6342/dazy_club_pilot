import uuid
from datetime import date as date_cls, datetime, timezone

from sqlalchemy import delete as sa_delete, func, or_, select
from sqlalchemy.exc import IntegrityError

from db import _session
from db_models import BillLineRow, BillRow, BillSequenceRow
from repositories.invoice_repo import amount_in_words
from services.billing import BillTotals

SERIES = "BILL"


def financial_year(local_date: str) -> str:
    """'2627' for any date in FY 2026-27 (the year starts on 1 April)."""
    d = date_cls.fromisoformat(local_date)
    start = d.year if d.month >= 4 else d.year - 1
    return f"{start % 100:02d}{(start + 1) % 100:02d}"


def financial_year_label(local_date: str) -> str:
    """'2026-27' for any date in FY 2026-27: the form printed in the bill number."""
    d = date_cls.fromisoformat(local_date)
    start = d.year if d.month >= 4 else d.year - 1
    return f"{start}-{(start + 1) % 100:02d}"


def _line_dto(r: BillLineRow) -> dict:
    return {
        "position": r.position, "description": r.description, "qty": float(r.qty), "rate": float(r.rate),
        "gstRatePercent": float(r.gst_rate_percent), "taxableValue": float(r.taxable_value),
        "cgst": float(r.cgst), "sgst": float(r.sgst), "lineTotal": float(r.line_total),
    }


def _dto(r: BillRow, lines: list[BillLineRow] | None = None) -> dict:
    out = {
        "id": r.id, "billNo": r.bill_no, "billDate": r.bill_date, "financialYear": r.financial_year,
        "customerName": r.customer_name, "customerPhone": r.customer_phone, "customerGstin": r.customer_gstin,
        "notes": r.notes, "bookingRef": r.booking_ref,
        "taxableValue": float(r.taxable_value), "cgst": float(r.cgst), "sgst": float(r.sgst),
        "roundOff": float(r.round_off), "total": float(r.total), "amountInWords": r.amount_in_words,
        "pricesIncludeTax": bool(r.prices_include_tax),
        "status": r.status, "voidReason": r.void_reason, "voidedAt": r.voided_at, "voidedBy": r.voided_by,
        "createdBy": r.created_by, "createdAt": r.created_at,
    }
    if lines is not None:
        out["lines"] = [_line_dto(x) for x in sorted(lines, key=lambda x: x.position)]
    return out


def _escape_like(q: str) -> str:
    return q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


class SqliteBillRepository:
    def _next_number(self, s, fy: str) -> int:
        """Bump and return the sequence inside the caller's transaction, so a rolled-back bill burns no number.
        The row lock (a no-op on SQLite) makes two simultaneous bills on Postgres take turns."""
        seq_id = f"{SERIES}-{fy}"
        row = s.execute(select(BillSequenceRow).where(BillSequenceRow.id == seq_id).with_for_update()).scalar_one_or_none()
        if row is None:
            try:
                with s.begin_nested():
                    s.add(BillSequenceRow(id=seq_id, last_number=0))
                    s.flush()
            except IntegrityError:  # another request created it first
                pass
            row = s.execute(select(BillSequenceRow).where(BillSequenceRow.id == seq_id).with_for_update()).scalar_one()
        row.last_number += 1
        s.flush()
        return row.last_number

    def create(self, *, local_date: str, totals: BillTotals, customer_name, customer_phone, customer_gstin,
               notes, booking_ref, created_by: str) -> dict:
        with _session() as s:
            fy = financial_year(local_date)
            num = self._next_number(s, fy)
            bill = BillRow(
                id=str(uuid.uuid4()), bill_no=f"{financial_year_label(local_date)}/{num:04d}", series=SERIES, financial_year=fy,
                bill_date=local_date, customer_name=customer_name, customer_phone=customer_phone,
                customer_gstin=customer_gstin, notes=notes, booking_ref=booking_ref,
                taxable_value=totals.taxable, cgst=totals.cgst, sgst=totals.sgst, round_off=totals.round_off,
                prices_include_tax=True, total=totals.total, amount_in_words=amount_in_words(float(totals.total)), status="active",
                created_by=created_by, created_at=datetime.now(timezone.utc).isoformat(),
            )
            s.add(bill)
            s.flush()
            lines = [
                BillLineRow(
                    id=str(uuid.uuid4()), bill_id=bill.id, position=i + 1, description=c.description, qty=c.qty,
                    rate=c.rate, gst_rate_percent=c.gst_rate_percent, taxable_value=c.taxable, cgst=c.cgst,
                    sgst=c.sgst, line_total=c.line_total,
                )
                for i, c in enumerate(totals.lines)
            ]
            s.add_all(lines)
            s.flush()
            return _dto(bill, lines)

    def get(self, bill_id: str) -> dict | None:
        with _session() as s:
            bill = s.get(BillRow, bill_id)
            if not bill:
                return None
            lines = list(s.scalars(select(BillLineRow).where(BillLineRow.bill_id == bill_id)).all())
            return _dto(bill, lines)

    def query(self, *, q: str | None = None, date_from: str | None = None, date_to: str | None = None,
              status: str | None = None, limit: int = 25, offset: int = 0) -> tuple[list[dict], int]:
        conds = []
        if q and q.strip():
            like = f"%{_escape_like(q.strip().lower())}%"
            conds.append(or_(
                func.lower(BillRow.bill_no).like(like, escape="\\"),
                func.lower(func.coalesce(BillRow.customer_name, "")).like(like, escape="\\"),
                func.coalesce(BillRow.customer_phone, "").like(like, escape="\\"),
            ))
        if date_from:
            conds.append(BillRow.bill_date >= date_from)
        if date_to:
            conds.append(BillRow.bill_date <= date_to)
        if status:
            conds.append(BillRow.status == status)
        with _session() as s:
            total = s.scalar(select(func.count()).select_from(BillRow).where(*conds)) or 0
            rows = s.scalars(
                select(BillRow).where(*conds).order_by(BillRow.created_at.desc(), BillRow.bill_no.desc())
                .offset(max(offset, 0)).limit(max(1, min(limit, 100)))
            ).all()
            return [_dto(r) for r in rows], total

    def void(self, bill_id: str, reason: str, by: str) -> dict | None:
        """Mark a bill void. Its number stays used; returns None if the bill does not exist."""
        with _session() as s:
            bill = s.get(BillRow, bill_id)
            if not bill:
                return None
            if bill.status != "void":
                bill.status, bill.void_reason = "void", reason
                bill.voided_at, bill.voided_by = datetime.now(timezone.utc).isoformat(), by
                s.flush()
            lines = list(s.scalars(select(BillLineRow).where(BillLineRow.bill_id == bill_id)).all())
            return _dto(bill, lines)

    def clear(self) -> None:
        """Tests only."""
        with _session() as s:
            s.execute(sa_delete(BillLineRow))
            s.execute(sa_delete(BillRow))
            s.execute(sa_delete(BillSequenceRow))
