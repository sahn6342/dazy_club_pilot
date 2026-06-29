from typing import Optional

from sqlalchemy import select, delete as sa_delete

from models import GalleryItemAdmin
from repositories.base import BaseRepository
from db import _session
from db_models import GalleryRow


def _to_model(row: GalleryRow) -> GalleryItemAdmin:
    return GalleryItemAdmin(
        id=row.id, title=row.title, sportSlug=row.sportSlug, tone=row.tone, approved=row.approved
    )


class SqliteGalleryRepository(BaseRepository[GalleryItemAdmin]):
    def get_all(self) -> list[GalleryItemAdmin]:
        with _session() as s:
            return [_to_model(r) for r in s.scalars(select(GalleryRow)).all()]

    def get_by_id(self, id: str) -> Optional[GalleryItemAdmin]:
        with _session() as s:
            row = s.get(GalleryRow, id)
            return _to_model(row) if row else None

    def create(self, item: GalleryItemAdmin) -> GalleryItemAdmin:
        with _session() as s:
            row = GalleryRow(**item.model_dump())
            s.add(row)
            s.flush()
            return _to_model(row)

    def update(self, id: str, data: dict) -> Optional[GalleryItemAdmin]:
        with _session() as s:
            row = s.get(GalleryRow, id)
            if not row:
                return None
            for k, v in data.items():
                if hasattr(row, k):
                    setattr(row, k, v)
            s.flush()
            return _to_model(row)

    def delete(self, id: str) -> bool:
        with _session() as s:
            row = s.get(GalleryRow, id)
            if not row:
                return False
            s.delete(row)
            return True

    def clear(self) -> None:
        with _session() as s:
            s.execute(sa_delete(GalleryRow))
