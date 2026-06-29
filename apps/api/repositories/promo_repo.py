import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select, delete as sa_delete, update as sa_update

from db import _session
from db_models import PromoCodeRow
from models import PromoCodeDto, PromoCodeCreate, PromoCodeUpdate


def _promo_dto(r: PromoCodeRow) -> PromoCodeDto:
    return PromoCodeDto(
        id=r.id, code=r.code, kind=r.kind, value=float(r.value), active=r.active,
        valid_from=r.valid_from, valid_to=r.valid_to,
        max_uses=r.max_uses, used_count=r.used_count, sport_slug=r.sport_slug,
        createdAt=r.createdAt,
    )


class SqlitePromoRepository:
    def get_all(self) -> list[PromoCodeDto]:
        with _session() as s:
            return [_promo_dto(r) for r in s.scalars(select(PromoCodeRow)).all()]

    def get_by_code(self, code: str) -> Optional[PromoCodeRow]:
        """Returns the ORM row (detached after commit) so callers can read used_count."""
        with _session() as s:
            return s.scalar(select(PromoCodeRow).where(PromoCodeRow.code == code.strip().upper()))

    def create(self, data: PromoCodeCreate) -> PromoCodeDto:
        with _session() as s:
            row = PromoCodeRow(
                id=str(uuid.uuid4()),
                code=data.code.strip().upper(),
                kind=data.kind,
                value=data.value,
                active=data.active,
                valid_from=data.valid_from,
                valid_to=data.valid_to,
                max_uses=data.max_uses,
                used_count=0,
                sport_slug=data.sport_slug,
                createdAt=datetime.now(timezone.utc).isoformat(),
            )
            s.add(row)
            s.flush()
            return _promo_dto(row)

    def update(self, promo_id: str, data: PromoCodeUpdate) -> Optional[PromoCodeDto]:
        with _session() as s:
            row = s.get(PromoCodeRow, promo_id)
            if not row:
                return None
            for k, v in data.model_dump(exclude_unset=True).items():
                setattr(row, k, v)
            s.flush()
            return _promo_dto(row)

    def delete(self, promo_id: str) -> bool:
        with _session() as s:
            row = s.get(PromoCodeRow, promo_id)
            if not row:
                return False
            s.delete(row)
            return True

    def increment_use(self, code: str) -> None:
        with _session() as s:
            s.execute(
                sa_update(PromoCodeRow)
                .where(PromoCodeRow.code == code.strip().upper())
                .values(used_count=PromoCodeRow.used_count + 1)
            )

    def clear(self) -> None:
        with _session() as s:
            s.execute(sa_delete(PromoCodeRow))
