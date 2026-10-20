"""Read access to the audit trail. Superadmin only: managers must not be able to read (or learn
the shape of) the log of their own actions."""
import re

from fastapi import APIRouter, Depends, HTTPException

from auth import require_superadmin
from deps import audit_repo

router = APIRouter()

_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


@router.get("/admin/audit")
def list_audit(
    action: str | None = None,
    actor: str | None = None,
    entityType: str | None = None,
    entityId: str | None = None,
    dateFrom: str | None = None,
    dateTo: str | None = None,
    limit: int = 50,
    offset: int = 0,
    _admin: dict = Depends(require_superadmin),
):
    """Newest first. `action` is a substring match (e.g. "refund", "user."); dates are YYYY-MM-DD in UTC."""
    for name, value in (("dateFrom", dateFrom), ("dateTo", dateTo)):
        if value and not _DATE.match(value):
            raise HTTPException(status_code=422, detail=f"{name} must be YYYY-MM-DD.")
    items, total = audit_repo.query(
        action=action or None, actor=actor or None, entity_type=entityType or None, entity_id=entityId or None,
        date_from=dateFrom or None, date_to=dateTo or None, limit=limit, offset=offset,
    )
    return {"items": items, "total": total}
