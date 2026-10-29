"""Counter-bill arithmetic. Prices are entered INCLUDING GST: what is typed is what the customer pays, and the tax is
backed out of it, split equally into CGST and SGST (intra-state supply). All maths is in Decimal, to the paisa; the
client never supplies a total.

Per line: amount = qty x rate; GST = amount - amount x 100 / (100 + rate%); CGST = SGST = half of the GST, rounded
down to the paisa so the two halves are always equal. Any odd paisa stays in the taxable value, so
taxable + CGST + SGST always equals the amount exactly. The bill total is the sum of the amounts (no rounding)."""
from dataclasses import dataclass
from decimal import Decimal, ROUND_DOWN, ROUND_HALF_UP

from services.refund_policy import money

_HUNDRED = Decimal(100)
_CENT = Decimal("0.01")


@dataclass
class BillLineCalc:
    description: str
    qty: Decimal
    rate: Decimal  # per unit, GST included
    gst_rate_percent: Decimal
    taxable: Decimal
    cgst: Decimal
    sgst: Decimal
    line_total: Decimal


@dataclass
class BillTotals:
    lines: list[BillLineCalc]
    taxable: Decimal
    cgst: Decimal
    sgst: Decimal
    round_off: Decimal  # always 0 for tax-inclusive bills; kept for bills issued before they were
    total: Decimal


def calc_line(description: str, qty, rate, gst_rate_percent) -> BillLineCalc:
    q = Decimal(str(qty)).quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)
    r = money(rate)
    pct = money(gst_rate_percent)
    amount = money(q * r)
    gst = amount - money(amount * _HUNDRED / (_HUNDRED + pct))
    half = (gst / 2).quantize(_CENT, rounding=ROUND_DOWN)
    return BillLineCalc(description, q, r, pct, amount - half - half, half, half, amount)


def calc_bill(lines: list[tuple[str, float, float, float]]) -> BillTotals:
    calcs = [calc_line(*ln) for ln in lines]
    zero = Decimal("0.00")
    return BillTotals(
        calcs,
        sum((c.taxable for c in calcs), zero),
        sum((c.cgst for c in calcs), zero),
        sum((c.sgst for c in calcs), zero),
        zero,
        sum((c.line_total for c in calcs), zero),
    )
