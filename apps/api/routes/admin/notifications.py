from fastapi import APIRouter, Depends

from auth import get_current_admin
from models import NotificationMessageDto
from deps import notification_repo

router = APIRouter()


@router.get("/admin/notifications", response_model=list[NotificationMessageDto])
def list_notifications(
    refType: str | None = None,
    refId: str | None = None,
    limit: int = 200,
    _: dict = Depends(get_current_admin),
):
    result = notification_repo.get_all(ref_type=refType, ref_id=refId)
    return result[:min(limit, 1000)]
