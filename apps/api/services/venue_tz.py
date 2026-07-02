"""Shared venue-timezone helper for owner-reporting day boundaries (Phase 4, DEC-024).

Booking/slot code already resolves per-court venue timezone inline
(services/availability_service.py) — this module is reporting-only and does not
touch that path. Single-venue pilot: reporting uses the one seeded venue's tz.
"""
from datetime import date as date_cls, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select

from db import _session
from db_models import VenueRow

_UTC = ZoneInfo("UTC")


def get_venue_zoneinfo() -> ZoneInfo:
    with _session() as s:
        venue = s.scalars(select(VenueRow)).first()
        return ZoneInfo(venue.timezone if venue else "UTC")


def local_today(tz: ZoneInfo) -> str:
    return datetime.now(tz).date().isoformat()


def day_bounds_utc(local_date: str, tz: ZoneInfo) -> tuple[str, str]:
    """Half-open [start, end) UTC ISO bounds for one calendar day in `tz`."""
    d = date_cls.fromisoformat(local_date)
    start_local = datetime.combine(d, datetime.min.time(), tzinfo=tz)
    end_local = start_local + timedelta(days=1)
    return start_local.astimezone(_UTC).isoformat(), end_local.astimezone(_UTC).isoformat()
