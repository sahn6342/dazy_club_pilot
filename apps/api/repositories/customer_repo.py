import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select, delete as sa_delete

from db import _session
from db_models import CustomerRow
from models import CustomerRecord


def _to_model(row: CustomerRow) -> CustomerRecord:
    return CustomerRecord(
        id=row.id,
        name=row.name,
        phone=row.phone,
        email=row.email,
        createdAt=row.createdAt,
    )


class SqliteCustomerRepository:
    def get_all(self) -> list[CustomerRecord]:
        with _session() as s:
            return [_to_model(r) for r in s.scalars(select(CustomerRow)).all()]

    def get_by_id(self, id: str) -> Optional[CustomerRecord]:
        with _session() as s:
            row = s.get(CustomerRow, id)
            return _to_model(row) if row else None

    def upsert_by_contact(self, name: str, contact: str) -> CustomerRecord:
        """Return existing customer for this contact or create a new one."""
        with _session() as s:
            row = s.scalar(select(CustomerRow).where(CustomerRow.phone == contact))
            if row:
                row.name = name  # refresh name in case it changed
            else:
                row = CustomerRow(
                    id=str(uuid.uuid4()),
                    name=name,
                    phone=contact,
                    createdAt=datetime.now(timezone.utc).isoformat(),
                )
                s.add(row)
            s.flush()
            return _to_model(row)

    def clear(self) -> None:
        with _session() as s:
            s.execute(sa_delete(CustomerRow))
