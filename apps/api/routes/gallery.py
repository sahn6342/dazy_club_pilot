from fastapi import APIRouter, Response

from deps import gallery_repo

router = APIRouter()


@router.get("/gallery")
def get_gallery(response: Response):
    """Public gallery — live from DB, approved items only."""
    response.headers["Cache-Control"] = "public, max-age=10"
    return [g for g in gallery_repo.get_all() if g.approved]
