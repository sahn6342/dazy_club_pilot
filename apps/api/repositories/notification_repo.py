import uuid
from datetime import datetime, timezone

from sqlalchemy import select, delete as sa_delete

from models import NotificationMessageDto
from db import _session
from db_models import NotificationMessageRow


def _to_model(row: NotificationMessageRow) -> NotificationMessageDto:
    return NotificationMessageDto(
        id=row.id, refType=row.refType, refId=row.refId, channel=row.channel,
        recipient=row.recipient, status=row.status, errorMessage=row.errorMessage,
        createdAt=row.createdAt,
    )


class SqliteNotificationRepository:
    def record(
        self, ref_type: str, ref_id: str, channel: str, recipient: str,
        status: str, error_message: str | None = None,
    ) -> NotificationMessageDto:
        with _session() as s:
            row = NotificationMessageRow(
                id=str(uuid.uuid4()), refType=ref_type, refId=ref_id, channel=channel,
                recipient=recipient, status=status, errorMessage=error_message,
                createdAt=datetime.now(timezone.utc).isoformat(),
            )
            s.add(row)
            s.flush()
            return _to_model(row)

    def get_all(self, ref_type: str | None = None, ref_id: str | None = None) -> list[NotificationMessageDto]:
        with _session() as s:
            stmt = select(NotificationMessageRow).order_by(NotificationMessageRow.createdAt.desc())
            if ref_type:
                stmt = stmt.where(NotificationMessageRow.refType == ref_type)
            if ref_id:
                stmt = stmt.where(NotificationMessageRow.refId == ref_id)
            return [_to_model(r) for r in s.scalars(stmt).all()]

    def clear(self) -> None:
        with _session() as s:
            s.execute(sa_delete(NotificationMessageRow))
