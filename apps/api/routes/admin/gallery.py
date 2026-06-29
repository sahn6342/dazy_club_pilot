import uuid
from fastapi import APIRouter, Depends, HTTPException
from models import GalleryItemAdmin, GalleryItemAdminUpdate
from auth import get_current_admin
from deps import gallery_repo

router = APIRouter()


@router.get("/admin/gallery")
def list_gallery(_: str = Depends(get_current_admin)):
    return gallery_repo.get_all()


@router.post("/admin/gallery", status_code=201)
def add_gallery_item(body: GalleryItemAdmin, _: str = Depends(get_current_admin)):
    body = GalleryItemAdmin(**{**body.model_dump(), "id": str(uuid.uuid4())})
    return gallery_repo.create(body)


@router.patch("/admin/gallery/{item_id}")
def update_gallery_item(
    item_id: str,
    body: GalleryItemAdminUpdate,
    _: str = Depends(get_current_admin),
):
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    updated = gallery_repo.update(item_id, updates)
    if not updated:
        raise HTTPException(status_code=404, detail="Gallery item not found.")
    return updated


@router.delete("/admin/gallery/{item_id}", status_code=204)
def delete_gallery_item(item_id: str, _: str = Depends(get_current_admin)):
    if not gallery_repo.delete(item_id):
        raise HTTPException(status_code=404, detail="Gallery item not found.")
