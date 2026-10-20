import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select, update as sa_update, delete as sa_delete

from models import NotificationMessageDto
from db import _session
from db_models import NotificationMessageRow


def _to_model(row: NotificationMessageRow) -> NotificationMessageDto:
    return NotificationMessageDto(
        id=row.id, refType=row.refType, refId=row.refId, channel=row.channel,
        recipient=row.recipient, status=row.status, errorMessage=row.errorMessage,
        createdAt=row.createdAt, event=row.event, provider=row.provider, providerRef=row.provider_ref,
        attempts=row.attempts or 1, lastAttemptAt=row.last_attempt_at, nextAttemptAt=row.next_attempt_at,
        resendable=bool(row.payload) and row.status in ("failed", "skipped", "retrying"),
    )


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


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

    # ── outbox ──────────────────────────────────────────────────────────────
    def create_attempt(
        self, ref_type: str, ref_id: str, channel: str, recipient: str, event: str, payload: str, provider: str,
    ) -> str:
        """Insert the row BEFORE the provider is called, so a crash mid-send still leaves a trace."""
        row_id = str(uuid.uuid4())
        now = _now()
        with _session() as s:
            s.add(NotificationMessageRow(
                id=row_id, refType=ref_type, refId=ref_id, channel=channel, recipient=recipient, status="sending",
                createdAt=now, event=event, payload=payload, provider=provider, attempts=1, last_attempt_at=now,
            ))
        return row_id

    def finish_attempt(
        self, row_id: str, status: str, detail: str | None = None, provider_ref: str | None = None,
        next_attempt_at: str | None = None,
    ) -> None:
        with _session() as s:
            s.execute(sa_update(NotificationMessageRow).where(NotificationMessageRow.id == row_id).values(
                status=status, errorMessage=detail if status != "sent" else None,
                provider_ref=provider_ref if status == "sent" else None, next_attempt_at=next_attempt_at,
            ))

    def claim_due(self, now_iso: str, limit: int = 50) -> list[NotificationMessageDto]:
        """Atomically take retrying rows whose time has come (status -> sending, attempts + 1) so two
        overlapping sweeps can never send the same retry twice. Returns the rows it won."""
        claimed: list[NotificationMessageDto] = []
        with _session() as s:
            ids = s.scalars(
                select(NotificationMessageRow.id).where(
                    NotificationMessageRow.status == "retrying",
                    NotificationMessageRow.next_attempt_at <= now_iso,
                ).order_by(NotificationMessageRow.next_attempt_at).limit(limit)
            ).all()
            for row_id in ids:
                won = s.execute(sa_update(NotificationMessageRow).where(
                    NotificationMessageRow.id == row_id, NotificationMessageRow.status == "retrying",
                ).values(status="sending", attempts=NotificationMessageRow.attempts + 1,
                         last_attempt_at=now_iso, next_attempt_at=None)).rowcount
                if won:
                    claimed.append(_to_model(s.get(NotificationMessageRow, row_id)))
        return claimed

    def claim_for_resend(self, row_id: str) -> bool:
        """Manual resend: take a failed/skipped/retrying row regardless of its schedule."""
        with _session() as s:
            return bool(s.execute(sa_update(NotificationMessageRow).where(
                NotificationMessageRow.id == row_id,
                NotificationMessageRow.status.in_(["failed", "skipped", "retrying"]),
                NotificationMessageRow.payload.is_not(None),
            ).values(status="sending", attempts=NotificationMessageRow.attempts + 1,
                     last_attempt_at=_now(), next_attempt_at=None)).rowcount)

    def rescue_stuck(self, older_than_iso: str) -> int:
        """A process died between claiming and finishing: put those rows back in the queue (a duplicate
        send is possible, a silently lost one is worse)."""
        with _session() as s:
            return s.execute(sa_update(NotificationMessageRow).where(
                NotificationMessageRow.status == "sending",
                NotificationMessageRow.last_attempt_at < older_than_iso,
                NotificationMessageRow.payload.is_not(None),
            ).values(status="retrying", next_attempt_at=_now(), errorMessage="interrupted; re-queued")).rowcount

    def get(self, row_id: str):
        with _session() as s:
            row = s.get(NotificationMessageRow, row_id)
            return (_to_model(row), row.payload) if row else None

    def query(
        self, status: str | None = None, channel: str | None = None, ref_type: str | None = None,
        ref_id: str | None = None, limit: int = 50, offset: int = 0,
    ) -> "tuple[list[NotificationMessageDto], int]":
        conds = []
        if status:
            conds.append(NotificationMessageRow.status == status)
        if channel:
            conds.append(NotificationMessageRow.channel == channel)
        if ref_type:
            conds.append(NotificationMessageRow.refType == ref_type)
        if ref_id:
            conds.append(NotificationMessageRow.refId == ref_id)
        with _session() as s:
            total = s.scalar(select(func.count()).select_from(NotificationMessageRow).where(*conds)) or 0
            rows = s.scalars(select(NotificationMessageRow).where(*conds).order_by(NotificationMessageRow.createdAt.desc())
                             .offset(max(offset, 0)).limit(max(1, min(limit, 200)))).all()
            return [_to_model(r) for r in rows], total

    def counts_by_status(self) -> dict[str, int]:
        with _session() as s:
            return {st: n for st, n in s.execute(select(NotificationMessageRow.status, func.count()).group_by(NotificationMessageRow.status)).all()}

    def has_sent(self, ref_id: str, channel: str, ref_type: str | None = None) -> bool:
        """True if a 'sent' notification already exists for this ref_id + channel (+ ref_type)."""
        with _session() as s:
            stmt = select(NotificationMessageRow.id).where(
                NotificationMessageRow.refId == ref_id,
                NotificationMessageRow.channel == channel,
                NotificationMessageRow.status == "sent",
            )
            if ref_type:
                stmt = stmt.where(NotificationMessageRow.refType == ref_type)
            return s.scalar(stmt.limit(1)) is not None

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
