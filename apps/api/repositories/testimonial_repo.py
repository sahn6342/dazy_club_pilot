from typing import Optional

from sqlalchemy import select, delete as sa_delete

from models import TestimonialAdmin
from repositories.base import BaseRepository
from db import _session
from db_models import TestimonialRow


def _to_model(row: TestimonialRow) -> TestimonialAdmin:
    return TestimonialAdmin(
        id=row.id, name=row.name, context=row.context, quote=row.quote, approved=row.approved
    )


class SqliteTestimonialRepository(BaseRepository[TestimonialAdmin]):
    def get_all(self) -> list[TestimonialAdmin]:
        with _session() as s:
            return [_to_model(r) for r in s.scalars(select(TestimonialRow)).all()]

    def get_by_id(self, id: str) -> Optional[TestimonialAdmin]:
        with _session() as s:
            row = s.get(TestimonialRow, id)
            return _to_model(row) if row else None

    def create(self, item: TestimonialAdmin) -> TestimonialAdmin:
        with _session() as s:
            row = TestimonialRow(**item.model_dump())
            s.add(row)
            s.flush()
            return _to_model(row)

    def update(self, id: str, data: dict) -> Optional[TestimonialAdmin]:
        with _session() as s:
            row = s.get(TestimonialRow, id)
            if not row:
                return None
            for k, v in data.items():
                if hasattr(row, k):
                    setattr(row, k, v)
            s.flush()
            return _to_model(row)

    def delete(self, id: str) -> bool:
        with _session() as s:
            row = s.get(TestimonialRow, id)
            if not row:
                return False
            s.delete(row)
            return True

    def clear(self) -> None:
        with _session() as s:
            s.execute(sa_delete(TestimonialRow))
