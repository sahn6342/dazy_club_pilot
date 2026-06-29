"""Public promo-code endpoints (no auth — read-only, no usage increment)."""
from datetime import date as date_cls

from fastapi import APIRouter

from deps import promo_repo
from services.pricing_service import validate_promo, apply_promo, PromoError

router = APIRouter()


@router.get("/promos/validate")
def validate_promo_code(code: str, sport: str, amount: float | None = None):
    """Check whether a promo is valid for a sport/amount without redeeming it.

    Returns {valid, code, kind, value, discountedAmount, savedAmount} on success
    or     {valid: false, code, error} on failure.
    Amount is optional — omit for free-slot checks.
    """
    promo = promo_repo.get_by_code(code)
    today = date_cls.today().isoformat()
    try:
        validate_promo(promo, sport, today)
    except PromoError as e:
        return {"valid": False, "code": code.strip().upper(), "error": e.detail}

    discounted = apply_promo(promo, amount) if amount is not None else None
    saved: float | None = None
    if amount is not None and discounted is not None:
        saved = round(amount - discounted, 2)

    return {
        "valid": True,
        "code": promo.code,
        "kind": promo.kind,
        "value": float(promo.value),
        "discountedAmount": discounted,
        "savedAmount": saved,
    }
