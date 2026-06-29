from fastapi import APIRouter, Depends, HTTPException
from models import CmsEntryUpdate
from auth import get_current_admin
from deps import cms_repo

router = APIRouter()


@router.get("/admin/cms")
def list_cms(_: str = Depends(get_current_admin)):
    return cms_repo.get_all()


@router.put("/admin/cms/{key}")
def update_cms_entry(
    key: str,
    body: CmsEntryUpdate,
    _: str = Depends(get_current_admin),
):
    updated = cms_repo.update(key, {"value": body.value})
    if not updated:
        raise HTTPException(status_code=404, detail="CMS entry not found.")
    return updated
