import uuid
from datetime import datetime, timezone

from sqlalchemy import select

from db import _session
from db_models import CafeSettingsRow

_SINGLETON_ID = "cafe-settings"


class SqliteCafeSettingsRepository:
    def get(self) -> CafeSettingsRow:
        """Return the single settings row; create with defaults if absent."""
        with _session() as s:
            row = s.get(CafeSettingsRow, _SINGLETON_ID)
            if not row:
                now = datetime.now(timezone.utc).isoformat()
                row = CafeSettingsRow(
                    id=_SINGLETON_ID,
                    scheme="regular",
                    priceIncludesTax=True,
                    defaultTaxRate=5.0,
                    invoiceSeriesPrefix="INV",
                    billOfSupplySeriesPrefix="BOS",
                    roundingEnabled=True,
                    createdAt=now,
                    updatedAt=now,
                )
                s.add(row)
                s.flush()
            return row

    def update(self, **kwargs) -> CafeSettingsRow:
        with _session() as s:
            row = s.get(CafeSettingsRow, _SINGLETON_ID)
            if not row:
                now = datetime.now(timezone.utc).isoformat()
                row = CafeSettingsRow(
                    id=_SINGLETON_ID,
                    scheme="regular",
                    priceIncludesTax=True,
                    defaultTaxRate=5.0,
                    invoiceSeriesPrefix="INV",
                    billOfSupplySeriesPrefix="BOS",
                    roundingEnabled=True,
                    createdAt=now,
                    updatedAt=now,
                )
                s.add(row)
            for k, v in kwargs.items():
                if v is not None and hasattr(row, k):
                    setattr(row, k, v)
            row.updatedAt = datetime.now(timezone.utc).isoformat()
            s.flush()
            return row
