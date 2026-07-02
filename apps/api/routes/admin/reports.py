from fastapi import APIRouter, Depends

from auth import get_current_admin
from models import DashboardDto, DayCloseDto
from services import analytics_service

router = APIRouter()


@router.get("/admin/reports/dashboard", response_model=DashboardDto)
def get_dashboard(_: dict = Depends(get_current_admin)):
    return analytics_service.dashboard()


@router.get("/admin/reports/day-close", response_model=DayCloseDto)
def get_day_close(date: str | None = None, _: dict = Depends(get_current_admin)):
    return analytics_service.day_close(date)
