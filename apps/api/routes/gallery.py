from fastapi import APIRouter, Response
from seed import GALLERY_ITEMS

router = APIRouter()


@router.get("/gallery")
def get_gallery(response: Response):
    response.headers["Cache-Control"] = "public, max-age=60"
    return GALLERY_ITEMS
