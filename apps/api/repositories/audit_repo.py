import uuid
from datetime import datetime, timezone

from sqlalchemy import select, delete as sa_delete, func

from models import AuditLogDto
from db import _session
from db_models import AuditLogRow


def _to_model(row: AuditLogRow) -> AuditLogDto:
    return AuditLogDto(
        id=row.id, at=row.at, actor=row.actor, actorRole=row.actorRole,
        action=row.action, entityType=row.entityType, entityId=row.entityId,
        detail=row.detail, ip=row.ip,
    )


class SqliteAuditRepository:
    def record(
        self, action: str, actor: str, actor_role: str | None = None,
        entity_type: str | None = None, entity_id: str | None = None,
        detail: str | None = None, ip: str | None = None,
    ) -> None:
        with _session() as s:
            row = AuditLogRow(
                id=str(uuid.uuid4()),
                at=datetime.now(timezone.utc).isoformat(),
                actor=actor, actorRole=actor_role, action=action,
                entityType=entity_type, entityId=entity_id, detail=detail, ip=ip,
            )
            s.add(row)
            s.flush()

    def list(
        self, action: str | None = None, actor: str | None = None,
        limit: int = 200, offset: int = 0,
    ) -> list[AuditLogDto]:
        with _session() as s:
            stmt = select(AuditLogRow).order_by(AuditLogRow.at.desc())
            if action:
                stmt = stmt.where(AuditLogRow.action == action)
            if actor:
                stmt = stmt.where(AuditLogRow.actor == actor)
            stmt = stmt.offset(offset).limit(min(limit, 1000))
            return [_to_model(r) for r in s.scalars(stmt).all()]

    def query(
        self, action: str | None = None, actor: str | None = None, entity_type: str | None = None,
        entity_id: str | None = None, date_from: str | None = None, date_to: str | None = None,
        limit: int = 50, offset: int = 0,
    ) -> "tuple[list[AuditLogDto], int]":  # quoted: this class defines a method named `list`
        """Newest first. `action` matches as a substring, the rest exactly; dates are YYYY-MM-DD (UTC, inclusive)."""
        conds = []
        if action:
            conds.append(AuditLogRow.action.ilike(f"%{action}%"))
        if actor:
            conds.append(AuditLogRow.actor == actor)
        if entity_type:
            conds.append(AuditLogRow.entityType == entity_type)
        if entity_id:
            conds.append(AuditLogRow.entityId == entity_id)
        if date_from:
            conds.append(AuditLogRow.at >= date_from)
        if date_to:
            conds.append(AuditLogRow.at < f"{date_to}T99")  # any time on date_to sorts below this
        with _session() as s:
            total = s.scalar(select(func.count()).select_from(AuditLogRow).where(*conds)) or 0
            rows = s.scalars(
                select(AuditLogRow).where(*conds).order_by(AuditLogRow.at.desc())
                .offset(max(offset, 0)).limit(max(1, min(limit, 200)))
            ).all()
            return [_to_model(r) for r in rows], total

    def clear(self) -> None:
        with _session() as s:
            s.execute(sa_delete(AuditLogRow))
