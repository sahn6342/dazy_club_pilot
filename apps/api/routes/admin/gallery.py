import logging
import os
import uuid
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from models import GalleryItemAdmin, GalleryItemAdminUpdate, GalleryItemCreate
from auth import get_current_admin
from deps import gallery_repo
from media_store import ALLOWED_IMAGE_EXTS, MAX_UPLOAD_BYTES, get_storage, validate_magic_bytes

router = APIRouter()


@router.get("/admin/gallery")
def list_gallery(_: str = Depends(get_current_admin)):
    return gallery_repo.get_all()


@router.post("/admin/gallery/upload")
async def upload_image(file: UploadFile = File(...), _: str = Depends(get_current_admin)):
    """Store an uploaded image (local disk or R2, per DAZY_MEDIA_BACKEND); return its public URL."""
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in ALLOWED_IMAGE_EXTS:
        raise HTTPException(status_code=400, detail="Unsupported file type. Use jpg, png, webp, or gif.")
    # Read with a hard cap — avoids reading a multi-GB file into memory.
    content = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="File too large. Maximum 10 MB.")
    if not validate_magic_bytes(content, ext):
        raise HTTPException(status_code=400, detail="File content does not match the declared image type.")
    name = f"{uuid.uuid4()}{ext}"
    try:
        url = get_storage().save(name, content, ext)
    except Exception:
        logging.getLogger(__name__).exception("Media upload failed")
        raise HTTPException(status_code=502, detail="Could not store the image. Please try again.")
    return {"imageUrl": url}


@router.post("/admin/gallery", status_code=201)
def add_gallery_item(body: GalleryItemCreate, _: str = Depends(get_current_admin)):
    item = GalleryItemAdmin(id=str(uuid.uuid4()), **body.model_dump())
    return gallery_repo.create(item)


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
    existing = gallery_repo.get_by_id(item_id)
    if not gallery_repo.delete(item_id):
        raise HTTPException(status_code=404, detail="Gallery item not found.")
    # Best-effort cleanup of the stored file (external URLs are ignored by the backend).
    if existing is not None:
        get_storage().delete(existing.imageUrl)
        if existing.imageUrl and existing.imageUrl.startswith("/media/"):
            # Rows uploaded before a switch to R2 still point at local disk: clean those too.
            from media_store import LocalStorage
            LocalStorage().delete(existing.imageUrl)
