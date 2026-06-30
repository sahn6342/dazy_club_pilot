import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select

from db import _session
from db_models import MenuCategoryRow


class SqliteMenuCategoryRepository:
    def get_all(self, active_only: bool = True) -> list[MenuCategoryRow]:
        with _session() as s:
            stmt = select(MenuCategoryRow).order_by(MenuCategoryRow.sortOrder, MenuCategoryRow.name)
            if active_only:
                stmt = stmt.where(MenuCategoryRow.active.is_(True))
            return list(s.scalars(stmt).all())

    def get_by_id(self, cat_id: str) -> Optional[MenuCategoryRow]:
        with _session() as s:
            return s.get(MenuCategoryRow, cat_id)

    def create(self, name: str, kind: str, veg_type: Optional[str] = None, sort_order: int = 0) -> MenuCategoryRow:
        with _session() as s:
            row = MenuCategoryRow(
                id=str(uuid.uuid4()),
                name=name,
                kind=kind,
                vegType=veg_type,
                sortOrder=sort_order,
                active=True,
                createdAt=datetime.now(timezone.utc).isoformat(),
            )
            s.add(row)
            s.flush()
            return row

    def update(self, cat_id: str, **kwargs) -> Optional[MenuCategoryRow]:
        with _session() as s:
            row = s.get(MenuCategoryRow, cat_id)
            if not row:
                return None
            for k, v in kwargs.items():
                if v is not None and hasattr(row, k):
                    setattr(row, k, v)
            s.flush()
            return row

    def delete(self, cat_id: str) -> bool:
        with _session() as s:
            row = s.get(MenuCategoryRow, cat_id)
            if not row:
                return False
            row.active = False
            s.flush()
            return True

    def clear(self) -> None:
        from sqlalchemy import delete as sa_delete
        with _session() as s:
            s.execute(sa_delete(MenuCategoryRow))
            s.flush()
