import uuid
from typing import Optional

from sqlalchemy import select, delete as sa_delete

from db import _session
from db_models import ScheduleRuleRow, ScheduleExceptionRow
from models import ScheduleRuleDto, ScheduleRuleCreate, ScheduleRuleUpdate, ScheduleExceptionDto, ScheduleExceptionCreate


def _rule_dto(r: ScheduleRuleRow) -> ScheduleRuleDto:
    return ScheduleRuleDto(
        id=r.id, court_id=r.court_id, weekday=r.weekday,
        open_time=r.open_time, close_time=r.close_time,
        slot_minutes=r.slot_minutes, price=float(r.price) if r.price is not None else None,
        discount_percent=r.discount_percent,
    )


def _exc_dto(r: ScheduleExceptionRow) -> ScheduleExceptionDto:
    return ScheduleExceptionDto(
        id=r.id, court_id=r.court_id, day=r.day, closed=r.closed,
        open_time=r.open_time, close_time=r.close_time,
    )


class SqliteScheduleRepository:
    # ── rules ──
    def list_rules(self, court_id: Optional[str] = None) -> list[ScheduleRuleDto]:
        with _session() as s:
            stmt = select(ScheduleRuleRow)
            if court_id:
                stmt = stmt.where(ScheduleRuleRow.court_id == court_id)
            return [_rule_dto(r) for r in s.scalars(stmt).all()]

    def create_rule(self, data: ScheduleRuleCreate) -> ScheduleRuleDto:
        with _session() as s:
            row = ScheduleRuleRow(
                id=str(uuid.uuid4()), court_id=data.court_id, weekday=data.weekday,
                open_time=data.open_time, close_time=data.close_time,
                slot_minutes=data.slot_minutes, price=data.price,
                discount_percent=data.discount_percent,
            )
            s.add(row)
            s.flush()
            return _rule_dto(row)

    def update_rule(self, rule_id: str, data: ScheduleRuleUpdate) -> Optional[ScheduleRuleDto]:
        with _session() as s:
            row = s.get(ScheduleRuleRow, rule_id)
            if not row:
                return None
            for k, v in data.model_dump(exclude_unset=True).items():
                setattr(row, k, v)
            s.flush()
            return _rule_dto(row)

    def delete_rule(self, rule_id: str) -> bool:
        with _session() as s:
            row = s.get(ScheduleRuleRow, rule_id)
            if not row:
                return False
            s.delete(row)
            return True

    # ── exceptions ──
    def list_exceptions(self, court_id: Optional[str] = None) -> list[ScheduleExceptionDto]:
        with _session() as s:
            stmt = select(ScheduleExceptionRow)
            if court_id:
                stmt = stmt.where(ScheduleExceptionRow.court_id == court_id)
            return [_exc_dto(r) for r in s.scalars(stmt).all()]

    def create_exception(self, data: ScheduleExceptionCreate) -> ScheduleExceptionDto:
        with _session() as s:
            row = ScheduleExceptionRow(
                id=str(uuid.uuid4()), court_id=data.court_id, day=data.day,
                closed=data.closed, open_time=data.open_time, close_time=data.close_time,
            )
            s.add(row)
            s.flush()
            return _exc_dto(row)

    def delete_exception(self, exc_id: str) -> bool:
        with _session() as s:
            row = s.get(ScheduleExceptionRow, exc_id)
            if not row:
                return False
            s.delete(row)
            return True

    def clear(self) -> None:
        with _session() as s:
            s.execute(sa_delete(ScheduleRuleRow))
            s.execute(sa_delete(ScheduleExceptionRow))
