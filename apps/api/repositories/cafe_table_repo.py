import uuid
from typing import Optional

from sqlalchemy import select

from db import _session
from db_models import CafeTableRow


class SqliteCafeTableRepository:
    def get_all(self, active_only: bool = True) -> list[CafeTableRow]:
        with _session() as s:
            stmt = select(CafeTableRow).order_by(CafeTableRow.sortOrder, CafeTableRow.label)
            if active_only:
                stmt = stmt.where(CafeTableRow.active.is_(True))
            return list(s.scalars(stmt).all())

    def get_by_id(self, table_id: str) -> Optional[CafeTableRow]:
        with _session() as s:
            return s.get(CafeTableRow, table_id)

    def create(self, label: str, capacity: int = 4, area: Optional[str] = None, sort_order: int = 0) -> CafeTableRow:
        with _session() as s:
            row = CafeTableRow(
                id=str(uuid.uuid4()),
                label=label,
                area=area,
                capacity=capacity,
                status="free",
                active=True,
                sortOrder=sort_order,
            )
            s.add(row)
            s.flush()
            return row

    def update(self, table_id: str, **kwargs) -> Optional[CafeTableRow]:
        with _session() as s:
            row = s.get(CafeTableRow, table_id)
            if not row:
                return None
            for k, v in kwargs.items():
                if v is not None and hasattr(row, k):
                    setattr(row, k, v)
            s.flush()
            return row

    def delete(self, table_id: str) -> bool:
        with _session() as s:
            row = s.get(CafeTableRow, table_id)
            if not row:
                return False
            row.active = False
            s.flush()
            return True

    def clear(self) -> None:
        from sqlalchemy import delete as sa_delete
        with _session() as s:
            s.execute(sa_delete(CafeTableRow))
            s.flush()
