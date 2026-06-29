from typing import Optional

from sqlalchemy import select, delete as sa_delete

from models import CmsEntry
from repositories.base import BaseRepository
from db import _session
from db_models import CmsRow


def _to_model(row: CmsRow) -> CmsEntry:
    return CmsEntry(key=row.key, label=row.label, value=row.value)


class SqliteCmsRepository(BaseRepository[CmsEntry]):
    """CMS uses 'key' as the identifier."""

    def get_all(self) -> list[CmsEntry]:
        with _session() as s:
            return [_to_model(r) for r in s.scalars(select(CmsRow)).all()]

    def get_by_id(self, id: str) -> Optional[CmsEntry]:
        with _session() as s:
            row = s.get(CmsRow, id)
            return _to_model(row) if row else None

    def create(self, item: CmsEntry) -> CmsEntry:
        with _session() as s:
            row = CmsRow(key=item.key, label=item.label, value=item.value)
            s.add(row)
            s.flush()
            return _to_model(row)

    def update(self, id: str, data: dict) -> Optional[CmsEntry]:
        with _session() as s:
            row = s.get(CmsRow, id)
            if not row:
                return None
            for k, v in data.items():
                if hasattr(row, k):
                    setattr(row, k, v)
            s.flush()
            return _to_model(row)

    def delete(self, id: str) -> bool:
        with _session() as s:
            row = s.get(CmsRow, id)
            if not row:
                return False
            s.delete(row)
            return True

    def clear(self) -> None:
        with _session() as s:
            s.execute(sa_delete(CmsRow))
