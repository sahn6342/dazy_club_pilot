from typing import Optional

from sqlalchemy import select

from db import _session
from db_models import CourtRow


class SqliteCourtRepository:
    """Read access to courts (the bookable resource)."""

    def get_all(self, active_only: bool = True) -> list[CourtRow]:
        with _session() as s:
            stmt = select(CourtRow)
            if active_only:
                stmt = stmt.where(CourtRow.active.is_(True))
            return list(s.scalars(stmt).all())

    def get_by_id(self, court_id: str) -> Optional[CourtRow]:
        with _session() as s:
            return s.get(CourtRow, court_id)

    def get_for_sport(self, sport: str) -> Optional[CourtRow]:
        """First active court for a sport (one court per sport in the pilot)."""
        with _session() as s:
            return s.scalar(
                select(CourtRow).where(CourtRow.sport == sport, CourtRow.active.is_(True)).limit(1)
            )

    def id_for_sport(self, sport: str) -> Optional[str]:
        court = self.get_for_sport(sport)
        return court.id if court else None
