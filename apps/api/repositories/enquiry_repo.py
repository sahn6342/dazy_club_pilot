from typing import Optional

from sqlalchemy import func, select, delete as sa_delete

from models import EnquiryRecord
from repositories.base import BaseRepository
from db import _session
from db_models import EnquiryRow


def _to_model(row: EnquiryRow) -> EnquiryRecord:
    return EnquiryRecord(
        id=row.id,
        type=row.type,
        name=row.name,
        contact=row.contact,
        company=row.company,
        eventType=row.eventType,
        estimatedGroupSize=row.estimatedGroupSize,
        preferredDate=row.preferredDate,
        preferredSport=row.preferredSport,
        interestedSport=row.interestedSport,
        message=row.message,
        status=row.status,
        createdAt=row.createdAt,
    )


class SqliteEnquiryRepository(BaseRepository[EnquiryRecord]):
    def get_all(self) -> list[EnquiryRecord]:
        with _session() as s:
            return [_to_model(r) for r in s.scalars(select(EnquiryRow)).all()]

    def query(self, type: str | None = None, status: str | None = None, limit: int = 500, offset: int = 0) -> "tuple[list[EnquiryRecord], int]":
        """Newest first, filtered and paged in SQL. Returns (page, total)."""
        conds = []
        if type:
            conds.append(EnquiryRow.type == type)
        if status:
            conds.append(EnquiryRow.status == status)
        with _session() as s:
            total = s.scalar(select(func.count()).select_from(EnquiryRow).where(*conds)) or 0
            rows = s.scalars(select(EnquiryRow).where(*conds).order_by(EnquiryRow.createdAt.desc(), EnquiryRow.id)
                             .offset(max(offset, 0)).limit(max(1, min(limit, 1000)))).all()
            return [_to_model(r) for r in rows], total

    def get_by_id(self, id: str) -> Optional[EnquiryRecord]:
        with _session() as s:
            row = s.get(EnquiryRow, id)
            return _to_model(row) if row else None

    def create(self, item: EnquiryRecord) -> EnquiryRecord:
        with _session() as s:
            row = EnquiryRow(**item.model_dump())
            s.add(row)
            s.flush()
            return _to_model(row)

    def update(self, id: str, data: dict) -> Optional[EnquiryRecord]:
        with _session() as s:
            row = s.get(EnquiryRow, id)
            if not row:
                return None
            for k, v in data.items():
                if hasattr(row, k):
                    setattr(row, k, v)
            s.flush()
            return _to_model(row)

    def delete(self, id: str) -> bool:
        with _session() as s:
            row = s.get(EnquiryRow, id)
            if not row:
                return False
            s.delete(row)
            return True

    def clear(self) -> None:
        with _session() as s:
            s.execute(sa_delete(EnquiryRow))
