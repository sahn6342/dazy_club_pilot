from typing import Optional

from sqlalchemy import select, delete as sa_delete

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
