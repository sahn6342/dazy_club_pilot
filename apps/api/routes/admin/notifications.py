from fastapi import APIRouter, Depends, HTTPException, Request, Response

from audit import audit
from auth import get_current_admin
from deps import notification_repo
from logging_config import mask_contact
from models import NotificationMessageDto
from services.notification_service import resend

router = APIRouter()


@router.get("/admin/notifications", response_model=list[NotificationMessageDto])
def list_notifications(
    response: Response,
    refType: str | None = None,
    refId: str | None = None,
    status: str | None = None,
    channel: str | None = None,
    limit: int = 200,
    offset: int = 0,
    _: dict = Depends(get_current_admin),
):
    """Newest first, filtered and paged in SQL; the full count is in the X-Total-Count header.
    status: sending | sent | retrying | failed | skipped. Message bodies are never returned."""
    items, total = notification_repo.query(status=status, channel=channel, ref_type=refType, ref_id=refId,
                                           limit=min(limit, 1000), offset=offset)
    response.headers["X-Total-Count"] = str(total)
    return items


@router.post("/admin/notifications/{notification_id}/resend", response_model=NotificationMessageDto)
def resend_notification(notification_id: str, req: Request, admin: dict = Depends(get_current_admin)):
    """Send a failed / skipped / waiting-to-retry message again, now. One attempt: the result is final
    (sent, or failed with the reason) because the admin is looking at it."""
    found = notification_repo.get(notification_id)
    if not found:
        raise HTTPException(status_code=404, detail="Notification not found.")
    outcome = resend(notification_id)
    if outcome is None:
        raise HTTPException(status_code=409, detail="This message cannot be resent (already sent, in progress, or it has no stored content).")
    status, row = outcome
    audit("notification.resend", admin, request=req, entity_type="notification", entity_id=notification_id,
          detail={"channel": row.channel, "event": row.event, "recipient": mask_contact(row.recipient), "outcome": status})
    return row
