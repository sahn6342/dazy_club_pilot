from fastapi import APIRouter, Response
from seed import NOTIFICATIONS

router = APIRouter()


@router.get("/notifications")
def get_notifications(response: Response):
    response.headers["Cache-Control"] = "public, max-age=60"
    return NOTIFICATIONS
