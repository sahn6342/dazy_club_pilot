from fastapi import APIRouter, Depends, HTTPException
from models import CmsEntry, CmsEntryUpdate, CmsCreate
from auth import get_current_admin
from deps import cms_repo

router = APIRouter()


@router.get("/admin/cms")
def list_cms(_: str = Depends(get_current_admin)):
    return cms_repo.get_all()


@router.post("/admin/cms", status_code=201)
def create_cms_entry(body: CmsCreate, _: str = Depends(get_current_admin)):
    if cms_repo.get_by_id(body.key):
        raise HTTPException(status_code=409, detail="CMS key already exists.")
    return cms_repo.create(CmsEntry(key=body.key, label=body.label, value=body.value))


@router.put("/admin/cms/{key}")
def update_cms_entry(
    key: str,
    body: CmsEntryUpdate,
    _: str = Depends(get_current_admin),
):
    updates = {k: v for k, v in body.model_dump(exclude_unset=True).items() if v is not None}
    if not updates:
        raise HTTPException(status_code=422, detail="Nothing to update.")
    updated = cms_repo.update(key, updates)
    if not updated:
        raise HTTPException(status_code=404, detail="CMS entry not found.")
    return updated


@router.delete("/admin/cms/{key}", status_code=204)
def delete_cms_entry(key: str, _: str = Depends(get_current_admin)):
    if not cms_repo.delete(key):
        raise HTTPException(status_code=404, detail="CMS entry not found.")
