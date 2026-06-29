from fastapi import APIRouter, Response
from seed import SPORTS

router = APIRouter()


@router.get("/sports")
def get_sports(response: Response):
    response.headers["Cache-Control"] = "public, max-age=60"
    return SPORTS
