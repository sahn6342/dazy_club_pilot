"""
Slot generation + availability, derived from schedule data (ScheduleRule/Exception)
against bookings. Slots are value objects, never stored.
"""
import logging
from datetime import date as date_cls, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import select, func, or_

from db import _session
from db_models import CourtRow, CourtSportRow, VenueRow, ScheduleRuleRow, ScheduleExceptionRow, BookingRow
from models import SlotDto
from services.pricing_service import slot_price

# for rebuild
# Per-slot display cap (max players in a single booking). Distinct from court.capacity
# (max concurrent parties per slot), which Phase 2 uses for availability.
_MAX_PLAYERS = {"cricket": 25, "football": 25, "badminton": 4, "pickleball": 4}
_DEFAULT_DAYS = 7

# Phase 3: online-prepay timeout. A booking left "pending" (slot reserved, not
# yet paid) longer than this is released so the slot becomes bookable again.
_PENDING_TIMEOUT_MINUTES = 15


def _sweep_stale_pending() -> int:
    """Cancel payment-timeout pending bookings. Runs on every availability
    read (cheap — one indexed UPDATE) rather than needing a background
    scheduler; lazy-imports deps to match this codebase's existing
    convention for avoiding startup-order/circular-import coupling.
    Also run on a schedule via POST /internal/sweep so expiry does not depend on
    someone reading slots. Returns how many bookings were expired."""
    from deps import booking_repo, booking_payment_repo, promo_repo
    from services.notification_service import notify_booking_cancelled
    cutoff = (datetime.now(timezone.utc) - timedelta(minutes=_PENDING_TIMEOUT_MINUTES)).isoformat()
    expired = booking_repo.expire_stale_pending(cutoff)
    if expired:
        booking_payment_repo.mark_expired_by_refs([b.bookingRef for b in expired])
    for booking in expired:
        if booking.promo_code:
            try:
                promo_repo.decrement_use(booking.promo_code)
            except Exception:
                logging.getLogger(__name__).exception(
                    "Failed to release promo %s for expired booking %s", booking.promo_code, booking.bookingRef)
        notify_booking_cancelled(booking.bookingRef)
    return len(expired)


def _hhmm_to_min(t: str) -> int:
    h, m = t.split(":")
    return int(h) * 60 + int(m)


def _min_to_hhmm(mins: int) -> str:
    mins = mins % 1440
    return f"{mins // 60:02d}:{mins % 60:02d}"


def _blocks_for(court_id: str, d: str, weekday: int, s) -> list[tuple[str, str, int, float | None, int | None]]:
    """Return [(open, close, slot_minutes, price, discount_percent)] for a court on a date, applying exceptions."""
    rules = s.scalars(
        select(ScheduleRuleRow).where(
            ScheduleRuleRow.court_id == court_id, ScheduleRuleRow.weekday == weekday
        ).order_by(ScheduleRuleRow.open_time)
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
            # Every court that serves this sport: its own, or one it shares (court_sports).
            cstmt = cstmt.where(CourtRow.id.in_(select(CourtSportRow.court_id).where(CourtSportRow.sport_slug == sport)))
        courts = list(s.scalars(cstmt).all())
        if not courts:
            return []

        # venue timezone cache
        tz_cache: dict[str, ZoneInfo] = {}

        for court in courts:
            shown_sport = sport or court.sport  # with no sport filter, a shared court is listed once, under its own sport
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
                d_obj = date_cls.fromisoformat(d)
                wd = d_obj.weekday()
                blocks = _blocks_for(court.id, d, wd, s)
                # Phase 2: capacity-aware occupied counts (cancel frees slot)
                occupied = _occupied_by_slot(court.id, d, s)
                seen_ids: set[str] = set()  # dedup cross-midnight overlap within this date

                def _emit_slot(cur: int, step: int, date_str: str, base_price, final_price, discount) -> None:
                    start_hhmm = _min_to_hhmm(cur)
                    end_hhmm = _min_to_hhmm(cur + step)
                    is_past = (date_str == today_local and cur <= (now_local.hour * 60 + now_local.minute))
                    if is_past and drop_past:
                        return
                    sid = f"slot-{court.id}-{date_str}-{start_hhmm.replace(':', '')}"
                    if sid in seen_ids:
                        return
                    seen_ids.add(sid)
                    # One court = one booking per slot (matches the uq_active_court_slot index).
                    under_capacity = occupied.get(sid, 0) == 0
                    out.append(SlotDto(
                        id=sid,
                        courtId=court.id,
                        courtName=court.name,
                        sportSlug=shown_sport,  # the sport asked for (a shared court serves several)
                        date=date_str,
                        startTime=start_hhmm,
                        endTime=end_hhmm,
                        available=under_capacity and not is_past,
                        maxPlayers=_MAX_PLAYERS.get(shown_sport, court.capacity),
                        price=base_price,
                        discountPercent=discount,
                        finalPrice=final_price,
                    ))

                # Same-day slots (including same-day portion of cross-midnight blocks).
                for open_t, close_t, step, price, discount in blocks:
                    base_price, final_price = slot_price(price, discount)
                    open_min = _hhmm_to_min(open_t)
                    close_min = _hhmm_to_min(close_t)
                    cross_midnight = close_min < open_min or close_min == 0
                    end = 1440 if cross_midnight else close_min
                    cur = open_min
                    while cur + step <= end:
                        _emit_slot(cur, step, d, base_price, final_price, discount)
                        cur += step

                # Cross-midnight overflow: after-midnight portion from previous day's rules.
                prev_d_obj = d_obj - timedelta(days=1)
                if prev_d_obj >= start_date - timedelta(days=1):
                    prev_d = prev_d_obj.isoformat()
                    prev_wd = prev_d_obj.weekday()
                    prev_blocks = _blocks_for(court.id, prev_d, prev_wd, s)
                    for open_t, close_t, step, price, discount in prev_blocks:
                        close_min = _hhmm_to_min(close_t)
                        open_min = _hhmm_to_min(open_t)
                        if close_min >= open_min or close_min == 0:
                            continue  # not cross-midnight, or closes exactly at midnight
                        base_price, final_price = slot_price(price, discount)
                        cur = 0
                        while cur + step <= close_min:
                            _emit_slot(cur, step, d, base_price, final_price, discount)
                            cur += step
    return sorted(out, key=lambda s: (s.date, s.startTime, s.courtId))


def find_slot(sport: str, date: str, slot_id: str) -> SlotDto | None:
    """Find a single slot for booking validation (includes past slots, flagged unavailable)."""
    for sl in generate_slots(sport=sport, date=date, drop_past=False):
        if sl.id == slot_id:
            return sl
    return None
