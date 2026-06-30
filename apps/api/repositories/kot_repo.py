import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select

from db import _session
from db_models import KotRow, OrderItemRow


class SqliteKotRepository:
    def create(self, order_id: str, station: str, item_ids: list[str]) -> KotRow:
        with _session() as s:
            ts_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
            kot_no = f"KOT-{ts_ms % 100000:05d}"
            now = datetime.now(timezone.utc).isoformat()
            kot = KotRow(
                id=str(uuid.uuid4()),
                kotNo=kot_no,
                order_id=order_id,
                station=station,
                status="pending",
                printedAt=None,
                createdAt=now,
            )
            s.add(kot)
            s.flush()
            # Update the order items with kot reference
            for item_id in item_ids:
                item = s.get(OrderItemRow, item_id)
                if item:
                    item.kot_id = kot.id
                    item.kotStatus = "sent"
            s.flush()
            return kot

    def get_all(
        self,
        station: Optional[str] = None,
        status: Optional[str] = None,
    ) -> list[KotRow]:
        with _session() as s:
            stmt = select(KotRow).order_by(KotRow.createdAt.desc())
            if station is not None:
                stmt = stmt.where(KotRow.station == station)
            if status is not None:
                stmt = stmt.where(KotRow.status == status)
            return list(s.scalars(stmt).all())

    def get_by_id(self, kot_id: str) -> Optional[KotRow]:
        with _session() as s:
            return s.get(KotRow, kot_id)

    def update_status(self, kot_id: str, status: str) -> Optional[KotRow]:
        with _session() as s:
            kot = s.get(KotRow, kot_id)
            if not kot:
                return None
            kot.status = status
            # Propagate kotStatus to associated order items
            stmt = select(OrderItemRow).where(OrderItemRow.kot_id == kot_id)
            for item in s.scalars(stmt).all():
                item.kotStatus = status
            s.flush()
            return kot
