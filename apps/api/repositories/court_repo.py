import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select

from db import _session
from db_models import CourtRow


class SqliteCourtRepository:
    """Read/write access to courts (the bookable resource)."""

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
        """First active court for a sport."""
        with _session() as s:
            return s.scalar(
                select(CourtRow).where(CourtRow.sport == sport, CourtRow.active.is_(True)).limit(1)
            )

    def id_for_sport(self, sport: str) -> Optional[str]:
        court = self.get_for_sport(sport)
        return court.id if court else None

    def create(self, venue_id: str, sport: str, name: str, capacity: int = 1) -> CourtRow:
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
            return row

    def update(self, court_id: str, name: Optional[str] = None, capacity: Optional[int] = None, active: Optional[bool] = None) -> Optional[CourtRow]:
        with _session() as s:
            row = s.get(CourtRow, court_id)
            if not row:
                return None
            if name is not None:
                row.name = name
            if capacity is not None:
                row.capacity = capacity
            if active is not None:
                row.active = active
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
        from sqlalchemy import delete as sa_delete
        with _session() as s:
            s.execute(sa_delete(CourtRow))
            s.flush()
