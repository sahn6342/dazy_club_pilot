from fastapi import APIRouter
from brand import BRAND_NAME

router = APIRouter()


@router.get("/health")
def health():
    return {"status": "ok", "app": f"{BRAND_NAME} API"}
