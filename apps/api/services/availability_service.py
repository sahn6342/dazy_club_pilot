"""
Slot generation + availability, derived from schedule data (ScheduleRule/Exception)
against bookings. Slots are value objects, never stored.
"""
from datetime import date as date_cls, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import select, func, or_

from db import _session
from db_models import CourtRow, VenueRow, ScheduleRuleRow, ScheduleExceptionRow, BookingRow
from models import SlotDto
from services.pricing_service import slot_price

# for rebuild
# Per-slot display cap (max players in a single booking). Distinct from court.capacity
# (max concurrent parties per slot), which Phase 2 uses for availability.
_MAX_PLAYERS = {"cricket": 11, "badminton": 4, "pickleball": 6}
_DEFAULT_DAYS = 7

# Phase 3: online-prepay timeout. A booking left "pending" (slot reserved, not
# yet paid) longer than this is released so the slot becomes bookable again.
_PENDING_TIMEOUT_MINUTES = 15


def _sweep_stale_pending() -> None:
    """Cancel payment-timeout pending bookings. Runs on every availability
    read (cheap — one indexed UPDATE) rather than needing a background
    scheduler; lazy-imports booking_repo to match this codebase's existing
    convention for avoiding startup-order/circular-import coupling."""
    from deps import booking_repo
    cutoff = (datetime.now(timezone.utc) - timedelta(minutes=_PENDING_TIMEOUT_MINUTES)).isoformat()
    booking_repo.expire_stale_pending(cutoff)


def _hhmm_to_min(t: str) -> int:
    h, m = t.split(":")
    return int(h) * 60 + int(m)


def _min_to_hhmm(mins: int) -> str:
    return f"{mins // 60:02d}:{mins % 60:02d}"


def _blocks_for(court_id: str, d: str, weekday: int, s) -> list[tuple[str, str, int, float | None, int | None]]:
    """Return [(open, close, slot_minutes, price, discount_percent)] for a court on a date, applying exceptions."""
    rules = s.scalars(
        select(ScheduleRuleRow).where(
            ScheduleRuleRow.court_id == court_id, ScheduleRuleRow.weekday == weekday
        )
    ).all()
    # Match a court-specific exception OR a venue-wide one (court_id IS NULL).
    # order_by puts court-specific first (False=0 sorts before True=1), so it wins.
    exc = s.scalar(
        select(ScheduleExceptionRow)
        .where(
            ScheduleExceptionRow.day == d,
            or_(ScheduleExceptionRow.court_id == court_id, ScheduleExceptionRow.court_id.is_(None)),
        )
        .order_by(ScheduleExceptionRow.court_id.is_(None))
    )
    if exc is not None:
        if exc.closed:
            return []
        if exc.open_time and exc.close_time:
            # Special hours inherit the weekday rule's price/discount, if any.
            base = rules[0] if rules else None
            price = float(base.price) if base is not None and base.price is not None else None
            disc = base.discount_percent if base is not None else None
            return [(exc.open_time, exc.close_time, 60, price, disc)]
        # exception present but no special hours -> treat as closed
        return []
    return [
        (r.open_time, r.close_time, r.slot_minutes,
         float(r.price) if r.price is not None else None, r.discount_percent)
        for r in rules
    ]


def _occupied_by_slot(court_id: str, d: str, s) -> dict[str, int]:
    """Return {slotId: sum(party_size)} for active bookings on this court+date.
    Active = status NOT IN ('cancelled', 'no_show') — cancel frees the slot."""
    rows = s.execute(
        select(BookingRow.slotId, func.sum(BookingRow.party_size).label("occ"))
        .where(
            BookingRow.court_id == court_id,
            BookingRow.date == d,
            BookingRow.status.notin_(["cancelled", "no_show"]),
        )
        .group_by(BookingRow.slotId)
    ).all()
    return {row.slotId: row.occ for row in rows}


def generate_slots(sport: str | None = None, date: str | None = None, drop_past: bool = True) -> list[SlotDto]:
    """Generate slots for active courts (optionally one sport / one date).
    drop_past=True omits elapsed slots (display); False keeps them flagged unavailable (booking lookup)."""
    _sweep_stale_pending()
    out: list[SlotDto] = []
    with _session() as s:
        cstmt = select(CourtRow).where(CourtRow.active.is_(True))
        if sport:
            cstmt = cstmt.where(CourtRow.sport == sport)
        courts = list(s.scalars(cstmt).all())
        if not courts:
            return []

        # venue timezone cache
        tz_cache: dict[str, ZoneInfo] = {}

        for court in courts:
            if court.venue_id not in tz_cache:
                venue = s.get(VenueRow, court.venue_id)
                tz_cache[court.venue_id] = ZoneInfo(venue.timezone if venue else "UTC")
            tz = tz_cache[court.venue_id]
            now_local = datetime.now(tz)
            start_date = now_local.date()
            today_local = start_date.isoformat()
            last_date = start_date + timedelta(days=_DEFAULT_DAYS - 1)  # bookable horizon

            if date:
                try:
                    dsel = date_cls.fromisoformat(date)
                except ValueError:
                    continue  # invalid date -> no slots
                if dsel < start_date or dsel > last_date:
                    continue  # past, or beyond the 7-day horizon -> no slots
                dates = [date]
            else:
                dates = [(start_date + timedelta(days=i)).isoformat() for i in range(_DEFAULT_DAYS)]

            for d in dates:
                wd = date_cls.fromisoformat(d).weekday()
                blocks = _blocks_for(court.id, d, wd, s)
                if not blocks:
                    continue
                # Phase 2: capacity-aware occupied counts (cancel frees slot)
                occupied = _occupied_by_slot(court.id, d, s)

                for open_t, close_t, step, price, discount in blocks:
                    base_price, final_price = slot_price(price, discount)
                    cur = _hhmm_to_min(open_t)
                    end = _hhmm_to_min(close_t)
                    while cur + step <= end:
                        start_hhmm = _min_to_hhmm(cur)
                        end_hhmm = _min_to_hhmm(cur + step)
                        is_past = (d == today_local and cur <= (now_local.hour * 60 + now_local.minute))
                        if is_past and drop_past:
                            cur += step
                            continue
                        sid = f"slot-{court.id}-{d}-{start_hhmm.replace(':', '')}"
                        # A slot is available when there's remaining capacity AND it's not past.
                        under_capacity = (occupied.get(sid, 0) + 1 <= court.capacity)
                        out.append(SlotDto(
                            id=sid,
                            courtId=court.id,
                            courtName=court.name,
                            sportSlug=court.sport,
                            date=d,
                            startTime=start_hhmm,
                            endTime=end_hhmm,
                            available=under_capacity and not is_past,
                            maxPlayers=_MAX_PLAYERS.get(court.sport, court.capacity),
                            price=base_price,
                            discountPercent=discount,
                            finalPrice=final_price,
                        ))
                        cur += step
    return out


def find_slot(sport: str, date: str, slot_id: str) -> SlotDto | None:
    """Find a single slot for booking validation (includes past slots, flagged unavailable)."""
    for sl in generate_slots(sport=sport, date=date, drop_past=False):
        if sl.id == slot_id:
            return sl
    return None
