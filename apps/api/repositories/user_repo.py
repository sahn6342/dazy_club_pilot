from typing import Optional

from sqlalchemy import select, delete as sa_delete

from models import UserRecord
from repositories.base import BaseRepository
from db import _session
from db_models import UserRow


def _to_model(row: UserRow) -> UserRecord:
    return UserRecord(
        id=row.id,
        username=row.username,
        hashed_password=row.hashed_password,
        role=row.role,
        createdAt=row.createdAt,
        createdBy=row.createdBy,
    )


class SqliteUserRepository(BaseRepository[UserRecord]):
    def get_all(self) -> list[UserRecord]:
        with _session() as s:
            return [_to_model(r) for r in s.scalars(select(UserRow)).all()]

    def get_by_id(self, id: str) -> Optional[UserRecord]:
        with _session() as s:
            row = s.get(UserRow, id)
            return _to_model(row) if row else None

    def get_by_username(self, username: str) -> Optional[UserRecord]:
        with _session() as s:
            row = s.scalar(select(UserRow).where(UserRow.username == username))
            return _to_model(row) if row else None

    def create(self, item: UserRecord) -> UserRecord:
        with _session() as s:
            row = UserRow(**item.model_dump())
            s.add(row)
            s.flush()
            return _to_model(row)

    def update(self, id: str, data: dict) -> Optional[UserRecord]:
        with _session() as s:
            row = s.get(UserRow, id)
            if not row:
                return None
            for k, v in data.items():
                if hasattr(row, k):
                    setattr(row, k, v)
            s.flush()
            return _to_model(row)

    def delete(self, id: str) -> bool:
        with _session() as s:
            row = s.get(UserRow, id)
            if not row:
                return False
            s.delete(row)
            return True

    def clear(self) -> None:
        with _session() as s:
            s.execute(sa_delete(UserRow))
