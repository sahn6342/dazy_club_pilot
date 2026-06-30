import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select

from db import _session
from db_models import MenuItemRow


class SqliteMenuItemRepository:
    def get_all(self, category_id: Optional[str] = None, available_only: bool = False) -> list[MenuItemRow]:
        with _session() as s:
            stmt = select(MenuItemRow).order_by(MenuItemRow.sortOrder, MenuItemRow.name)
            if category_id:
                stmt = stmt.where(MenuItemRow.category_id == category_id)
            if available_only:
                stmt = stmt.where(MenuItemRow.available.is_(True))
            return list(s.scalars(stmt).all())

    def get_by_id(self, item_id: str) -> Optional[MenuItemRow]:
        with _session() as s:
            return s.get(MenuItemRow, item_id)

    def create(self, category_id: str, name: str, price: float, **kwargs) -> MenuItemRow:
        with _session() as s:
            row = MenuItemRow(
                id=str(uuid.uuid4()),
                category_id=category_id,
                name=name,
                price=price,
                createdAt=datetime.now(timezone.utc).isoformat(),
                **{k: v for k, v in kwargs.items() if v is not None},
            )
            s.add(row)
            s.flush()
            return row

    def update(self, item_id: str, **kwargs) -> Optional[MenuItemRow]:
        with _session() as s:
            row = s.get(MenuItemRow, item_id)
            if not row:
                return None
            for k, v in kwargs.items():
                if v is not None and hasattr(row, k):
                    setattr(row, k, v)
            s.flush()
            return row

    def delete(self, item_id: str) -> bool:
        with _session() as s:
            row = s.get(MenuItemRow, item_id)
            if not row:
                return False
            row.available = False
            s.flush()
            return True

    def clear(self) -> None:
        from sqlalchemy import delete as sa_delete
        with _session() as s:
            s.execute(sa_delete(MenuItemRow))
            s.flush()
