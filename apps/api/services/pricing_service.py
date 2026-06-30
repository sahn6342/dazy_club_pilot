"""
Pricing + promo logic — single source of truth for both slot generation
(base/block-discount price) and booking (promo application).
Money math in Decimal, exposed as float (matches repo DTO casting).
"""
from decimal import Decimal, ROUND_HALF_UP


class PromoError(Exception):
    """Raised when a promo code fails validation. Route maps .detail to HTTP 400."""
    def __init__(self, detail: str):
        self.detail = detail
        super().__init__(detail)


def _round(d: Decimal) -> float:
    return float(d.quantize(Decimal("0.01"), ROUND_HALF_UP))


def slot_price(rule_price, discount_percent) -> tuple[float | None, float | None]:
    """Return (base, final). rule_price None => free play (both None)."""
    if rule_price is None:
        return None, None
    base = Decimal(str(rule_price))
    if discount_percent:
        final = base * (Decimal(100 - int(discount_percent)) / Decimal(100))
    else:
        final = base
    return _round(base), _round(final)


def validate_promo(promo_row, sport: str, today: str) -> None:
    """Raise PromoError on any failure. today = 'YYYY-MM-DD' (lexicographic compare OK)."""
    if promo_row is None:
        raise PromoError("Invalid promo code.")
    if not promo_row.active:
        raise PromoError("Promo code is inactive.")
    if promo_row.valid_from and today < promo_row.valid_from:
        raise PromoError("Promo not yet valid.")
    if promo_row.valid_to and today > promo_row.valid_to:
        raise PromoError("Promo code expired.")
    if promo_row.max_uses is not None and promo_row.used_count >= promo_row.max_uses:
        raise PromoError("Promo code usage limit reached.")
    if promo_row.sport_slug and promo_row.sport_slug != sport:
        raise PromoError("Promo code not valid for this sport.")
    if promo_row.kind == "percent" and promo_row.value > 100:
        raise PromoError("Promo code has invalid discount value.")


def apply_promo(promo_row, amount: float | None) -> float | None:
    """amount is slot.finalPrice. promo_row must be pre-validated. Free slot stays free."""
    if amount is None:
        return None
    amt = Decimal(str(amount))
    val = Decimal(str(promo_row.value))
    if promo_row.kind == "percent":
        out = amt * (Decimal(100) - val) / Decimal(100)
    else:  # flat
        out = max(Decimal(0), amt - val)
    return _round(out)
