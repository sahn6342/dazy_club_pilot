import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select

from db import _session
from db_models import InvoiceRow, InvoiceLineRow, InvoiceSequenceRow, OrderItemRow


# ── Indian numbering: amount in words ──

_ONES = [
    "", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine",
    "Ten", "Eleven", "Twelve", "Thirteen", "Fourteen", "Fifteen", "Sixteen",
    "Seventeen", "Eighteen", "Nineteen",
]
_TENS = ["", "", "Twenty", "Thirty", "Forty", "Fifty", "Sixty", "Seventy", "Eighty", "Ninety"]


def _words_below_hundred(n: int) -> str:
    if n < 20:
        return _ONES[n]
    return (_TENS[n // 10] + (" " + _ONES[n % 10] if n % 10 else "")).strip()


def _words_below_thousand(n: int) -> str:
    if n < 100:
        return _words_below_hundred(n)
    hundreds = n // 100
    remainder = n % 100
    parts = [_ONES[hundreds] + " Hundred"]
    if remainder:
        parts.append(_words_below_hundred(remainder))
    return " ".join(parts)


def amount_in_words(n: float) -> str:
    """Convert a float rupee amount to Indian-style words (no external deps)."""
    n = round(n, 2)
    rupees = int(n)
    paise = round((n - rupees) * 100)

    def _rupee_words(amount: int) -> str:
        if amount == 0:
            return "Zero"
        parts = []
        crore = amount // 10_000_000
        amount %= 10_000_000
        lakh = amount // 100_000
        amount %= 100_000
        thousand = amount // 1_000
        amount %= 1_000
        remainder = amount

        if crore:
            parts.append(_words_below_thousand(crore) + " Crore")
        if lakh:
            parts.append(_words_below_thousand(lakh) + " Lakh")
        if thousand:
            parts.append(_words_below_thousand(thousand) + " Thousand")
        if remainder:
            parts.append(_words_below_thousand(remainder))
        return " ".join(parts)

    result = _rupee_words(rupees) + " Rupees"
    if paise:
        result += " and " + _words_below_hundred(paise) + " Paise"
    result += " Only"
    return result


def _financial_year() -> str:
    """Return financial year string like '2526' for FY 2025-26."""
    now = datetime.now(timezone.utc)
    year = now.year
    if now.month < 4:
        year -= 1
    return f"{str(year)[2:]}{str(year + 1)[2:]}"


class SqliteInvoiceRepository:
    def next_number(self, series: str, financial_year: str) -> int:
        """Atomically increment and return the next invoice sequence number."""
        with _session() as s:
            seq_id = f"{series}-{financial_year}"
            row = s.get(InvoiceSequenceRow, seq_id)
            if not row:
                row = InvoiceSequenceRow(
                    id=seq_id,
                    series=series,
                    financialYear=financial_year,
                    lastNumber=0,
                )
                s.add(row)
                s.flush()
            row.lastNumber += 1
            s.flush()
            return row.lastNumber

    def create(
        self,
        order,
        settings,
        issued_by: str,
        customer_name: Optional[str] = None,
        customer_gstin: Optional[str] = None,
    ) -> InvoiceRow:
        """
        Build an invoice from an OrderRow and CafeSettingsRow.
        Computes GST per line item (CGST + SGST split equally).
        """
        with _session() as s:
            # Determine invoice type and series
            gstin = getattr(settings, "gstin", None)
            scheme = getattr(settings, "scheme", "regular")
            if scheme == "unregistered" or not gstin:
                invoice_type = "bill_of_supply"
                series = getattr(settings, "billOfSupplySeriesPrefix", "BOS")
            else:
                invoice_type = "tax_invoice"
                series = getattr(settings, "invoiceSeriesPrefix", "INV")

            fy = _financial_year()
            num = self.next_number(series, fy)
            invoice_no = f"{series}/{fy}/{num:04d}"
            now = datetime.now(timezone.utc).isoformat()

            # Fetch non-voided order items
            stmt = select(OrderItemRow).where(
                OrderItemRow.order_id == order.id,
                OrderItemRow.voided.is_(False),
            )
            order_items = list(s.scalars(stmt).all())

            # Build invoice lines
            total_taxable = 0.0
            total_cgst = 0.0
            total_sgst = 0.0
            invoice_id = str(uuid.uuid4())
            line_rows = []

            for oi in order_items:
                line_subtotal = float(oi.lineSubtotal)
                line_tax = float(oi.lineTax)
                gst_rate = float(oi.taxRatePercent)
                half_tax = round(line_tax / 2, 2)
                line_total = round(line_subtotal + line_tax, 2)

                total_taxable += line_subtotal
                total_cgst += half_tax
                total_sgst += half_tax

                line_row = InvoiceLineRow(
                    id=str(uuid.uuid4()),
                    invoice_id=invoice_id,
                    description=oi.nameSnapshot,
                    hsnSac=oi.hsnSacSnapshot,
                    qty=float(oi.qty),
                    unit=None,
                    rate=float(oi.unitPrice),
                    taxableValue=round(line_subtotal, 2),
                    gstRatePercent=gst_rate,
                    cgst=half_tax,
                    sgst=half_tax,
                    lineTotal=line_total,
                )
                line_rows.append(line_row)

            total_taxable = round(total_taxable, 2)
            total_cgst = round(total_cgst, 2)
            total_sgst = round(total_sgst, 2)
            gross = total_taxable + total_cgst + total_sgst
            rounded = round(gross)
            round_off = round(rounded - gross, 2)
            total = round(gross + round_off, 2)

            invoice = InvoiceRow(
                id=invoice_id,
                invoiceNo=invoice_no,
                invoiceType=invoice_type,
                series=series,
                financialYear=fy,
                order_id=order.id,
                customerName=customer_name,
                customerGstin=customer_gstin,
                taxableValue=total_taxable,
                cgst=total_cgst,
                sgst=total_sgst,
                roundOff=round_off,
                total=total,
                amountInWords=amount_in_words(total),
                status="issued",
                issuedBy=issued_by,
                issuedAt=now,
            )
            s.add(invoice)
            s.flush()
            for lr in line_rows:
                s.add(lr)
            s.flush()
            return invoice

    def get_by_id(self, invoice_id: str) -> Optional[InvoiceRow]:
        with _session() as s:
            return s.get(InvoiceRow, invoice_id)

    def get_lines(self, invoice_id: str) -> list[InvoiceLineRow]:
        with _session() as s:
            stmt = select(InvoiceLineRow).where(InvoiceLineRow.invoice_id == invoice_id)
            return list(s.scalars(stmt).all())

    def cancel(self, invoice_id: str) -> Optional[InvoiceRow]:
        with _session() as s:
            row = s.get(InvoiceRow, invoice_id)
            if not row:
                return None
            row.status = "cancelled"
            s.flush()
            return row

    def get_all(self, order_id: Optional[str] = None) -> list[InvoiceRow]:
        with _session() as s:
            stmt = select(InvoiceRow).order_by(InvoiceRow.issuedAt.desc())
            if order_id is not None:
                stmt = stmt.where(InvoiceRow.order_id == order_id)
            return list(s.scalars(stmt).all())
