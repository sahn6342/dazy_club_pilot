"""Cancellation refund policy: how much of what the customer paid comes back, by notice given.

Stored in the CMS under `refund_policy` as JSON so the owner can change it without a deploy:

    {"tiers": [{"hoursBefore": 24, "percent": 100}, {"hoursBefore": 4, "percent": 50}]}

A booking cancelled with at least `hoursBefore` hours of notice gets that tier's percent; the
first (largest) matching tier wins; less notice than every tier gets 0%. Notice is measured to
the start of the booking's first slot in the venue's timezone. The amount is a suggestion: an
admin can override it (never above what is still refundable)."""
import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import ROUND_HALF_UP, Decimal
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)

POLICY_KEY = "refund_policy"
DEFAULT_TIERS: list[tuple[float, float]] = [(24.0, 100.0), (4.0, 50.0)]
DEFAULT_POLICY_JSON = json.dumps({"tiers": [{"hoursBefore": h, "percent": p} for h, p in DEFAULT_TIERS]})


class PolicyError(ValueError):
    pass


def parse_policy(raw: str) -> list[tuple[float, float]]:
    """Validate a policy JSON string and return its tiers sorted by notice, largest first.
    Raises PolicyError with a message an admin can act on."""
    try:
        data = json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        raise PolicyError("Refund policy must be valid JSON.")
    tiers = data.get("tiers") if isinstance(data, dict) else None
    if not isinstance(tiers, list) or not tiers:
        raise PolicyError('Refund policy needs a non-empty "tiers" list.')
    out: list[tuple[float, float]] = []
    for t in tiers:
        if not isinstance(t, dict):
            raise PolicyError("Each tier must be an object with hoursBefore and percent.")
        h, p = t.get("hoursBefore"), t.get("percent")
        if isinstance(h, bool) or isinstance(p, bool) or not isinstance(h, (int, float)) or not isinstance(p, (int, float)):
            raise PolicyError("hoursBefore and percent must be numbers.")
        if h < 0 or h > 24 * 365:
            raise PolicyError("hoursBefore must be between 0 and 8760.")
        if not 0 <= p <= 100:
            raise PolicyError("percent must be between 0 and 100.")
        out.append((float(h), float(p)))
    out.sort(key=lambda t: -t[0])
    if len({h for h, _ in out}) != len(out):
        raise PolicyError("Two tiers have the same hoursBefore.")
    return out


def load_tiers() -> list[tuple[float, float]]:
    """The live policy; falls back to the default (and logs) if the CMS value is missing or broken."""
    from deps import cms_repo
    entry = cms_repo.get_by_id(POLICY_KEY)
    if entry and entry.value:
        try:
            return parse_policy(entry.value)
        except PolicyError as e:
            logger.error("Invalid %s in CMS (%s); using the default policy.", POLICY_KEY, e)
    return list(DEFAULT_TIERS)


def percent_for_notice(hours: float, tiers: list[tuple[float, float]]) -> float:
    for min_hours, percent in tiers:  # largest notice first
        if hours >= min_hours:
            return percent
    return 0.0


def _now() -> datetime:
    return datetime.now(timezone.utc)


def hours_until_start(date: str, start_time: str, tz: ZoneInfo, now: datetime | None = None) -> float:
    """Hours from `now` to the local start time (negative once it has started)."""
    start = datetime.fromisoformat(f"{date}T{start_time}:00").replace(tzinfo=tz)
    return (start - (now or _now())).total_seconds() / 3600


def money(x) -> Decimal:
    return Decimal(str(x)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


@dataclass
class RefundQuote:
    paid: float
    refunded: float
    remaining: float
    hoursBefore: float
    percent: float
    policyAmount: float
    suggestedAmount: float  # policy amount, capped by what is still refundable


def build_quote(paid, refunded, hours: float, tiers: list[tuple[float, float]]) -> RefundQuote:
    paid_d, refunded_d = money(paid), money(refunded)
    remaining = max(paid_d - refunded_d, Decimal("0.00"))
    percent = percent_for_notice(hours, tiers)
    policy_amount = money(paid_d * Decimal(str(percent)) / Decimal(100))
    return RefundQuote(
        paid=float(paid_d), refunded=float(refunded_d), remaining=float(remaining),
        hoursBefore=round(hours, 2), percent=percent, policyAmount=float(policy_amount),
        suggestedAmount=float(min(policy_amount, remaining)),
    )
