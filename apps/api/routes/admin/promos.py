from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError

from models import PromoCodeDto, PromoCodeCreate, PromoCodeUpdate
from auth import get_current_admin
from deps import promo_repo

router = APIRouter()


@router.get("/admin/promos", response_model=list[PromoCodeDto])
def list_promos(_: dict = Depends(get_current_admin)):
    return promo_repo.get_all()


@router.post("/admin/promos", response_model=PromoCodeDto, status_code=201)
def create_promo(body: PromoCodeCreate, _: dict = Depends(get_current_admin)):
    try:
        return promo_repo.create(body)
    except IntegrityError:
        raise HTTPException(status_code=409, detail="Promo code already exists.")


@router.patch("/admin/promos/{promo_id}", response_model=PromoCodeDto)
def update_promo(promo_id: str, body: PromoCodeUpdate, _: dict = Depends(get_current_admin)):
    updated = promo_repo.update(promo_id, body)
    if not updated:
        raise HTTPException(status_code=404, detail="Promo not found.")
    return updated


@router.delete("/admin/promos/{promo_id}", status_code=204)
def delete_promo(promo_id: str, _: dict = Depends(get_current_admin)):
    if not promo_repo.delete(promo_id):
        raise HTTPException(status_code=404, detail="Promo not found.")
