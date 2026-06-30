from fastapi import APIRouter, Depends

from auth import get_current_admin
from deps import cafe_settings_repo
from models import CafeSettingsDto, CafeSettingsUpdate

router = APIRouter()


@router.get("/admin/cafe/settings", response_model=CafeSettingsDto)
def get_settings(_=Depends(get_current_admin)):
    return CafeSettingsDto.model_validate(cafe_settings_repo.get())


@router.put("/admin/cafe/settings", response_model=CafeSettingsDto)
def update_settings(body: CafeSettingsUpdate, _=Depends(get_current_admin)):
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    return CafeSettingsDto.model_validate(cafe_settings_repo.update(**updates))
