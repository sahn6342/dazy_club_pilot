from fastapi import APIRouter, Response
from seed import TESTIMONIALS

router = APIRouter()


@router.get("/testimonials")
def get_testimonials(response: Response):
    response.headers["Cache-Control"] = "public, max-age=60"
    return TESTIMONIALS
