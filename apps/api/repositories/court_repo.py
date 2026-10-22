import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import delete as sa_delete, select

from db import _session
from db_models import CourtRow, CourtSportRow


class CourtSportsError(ValueError):
    """The requested set of sports is not allowed for this court."""


def _normalised(primary: str, sports: Optional[list[str]]) -> list[str]:
    """The primary sport first, then the extras, without duplicates."""
    return list(dict.fromkeys([primary, *(sports or [])]))


class SqliteCourtRepository:
    """Read/write access to courts (the bookable resource) and the sports each one serves."""

    def get_all(self, active_only: bool = True) -> list[CourtRow]:
        with _session() as s:
            stmt = select(CourtRow)
            if active_only:
                stmt = stmt.where(CourtRow.active.is_(True))
            return list(s.scalars(stmt).all())

    def get_by_id(self, court_id: str) -> Optional[CourtRow]:
        with _session() as s:
            return s.get(CourtRow, court_id)

    def sports_by_court(self) -> dict[str, list[str]]:
        """{court_id: [sports it serves]}, primary sport first."""
        with _session() as s:
            out: dict[str, list[str]] = {c.id: [c.sport] for c in s.scalars(select(CourtRow)).all()}
            for link in s.scalars(select(CourtSportRow).order_by(CourtSportRow.sport_slug)).all():
                if link.court_id in out and link.sport_slug not in out[link.court_id]:
                    out[link.court_id].append(link.sport_slug)
            return out

    def sports_for(self, court_id: str) -> list[str]:
        return self.sports_by_court().get(court_id, [])

    def get_for_sport(self, sport: str) -> Optional[CourtRow]:
        """First active court that serves a sport (its own, or shared)."""
        with _session() as s:
            return s.scalar(
                select(CourtRow)
                .join(CourtSportRow, CourtSportRow.court_id == CourtRow.id)
                .where(CourtSportRow.sport_slug == sport, CourtRow.active.is_(True))
                .order_by(CourtRow.createdAt, CourtRow.id)
                .limit(1)
            )

    def id_for_sport(self, sport: str) -> Optional[str]:
        court = self.get_for_sport(sport)
        return court.id if court else None

    def create(self, venue_id: str, sport: str, name: str, capacity: int = 1, sports: Optional[list[str]] = None) -> CourtRow:
        with _session() as s:
            row = CourtRow(
                id=str(uuid.uuid4()),
                venue_id=venue_id,
                sport=sport,
                name=name,
                capacity=capacity,
                active=True,
                createdAt=datetime.now(timezone.utc).isoformat(),
            )
            s.add(row)
            s.flush()
            for slug in _normalised(sport, sports):
                s.add(CourtSportRow(court_id=row.id, sport_slug=slug))
            s.flush()
            return row

    def update(self, court_id: str, name: Optional[str] = None, capacity: Optional[int] = None, active: Optional[bool] = None,
               sports: Optional[list[str]] = None) -> Optional[CourtRow]:
        with _session() as s:
            row = s.get(CourtRow, court_id)
            if not row:
                return None
            if sports is not None and row.sport not in sports:
                raise CourtSportsError(f"A court must keep its own sport ({row.sport}); add others next to it.")
            if name is not None:
                row.name = name
            if capacity is not None:
                row.capacity = capacity
            if active is not None:
                row.active = active
            if sports is not None:
                # Dropping a sport only stops new bookings under it; existing bookings keep their sportSlug.
                s.execute(sa_delete(CourtSportRow).where(CourtSportRow.court_id == court_id))
                for slug in _normalised(row.sport, sports):
                    s.add(CourtSportRow(court_id=court_id, sport_slug=slug))
            s.flush()
            return row

    def deactivate(self, court_id: str) -> bool:
        with _session() as s:
            row = s.get(CourtRow, court_id)
            if not row:
                return False
            row.active = False
            s.flush()
            return True

    def clear(self) -> None:
        with _session() as s:
            s.execute(sa_delete(CourtSportRow))
            s.execute(sa_delete(CourtRow))
            s.flush()
