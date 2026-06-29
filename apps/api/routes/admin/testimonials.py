from fastapi import APIRouter, Depends, HTTPException
from models import TestimonialAdminUpdate
from auth import get_current_admin
from deps import testimonial_repo

router = APIRouter()


@router.get("/admin/testimonials")
def list_testimonials(_: str = Depends(get_current_admin)):
    return testimonial_repo.get_all()


@router.patch("/admin/testimonials/{testimonial_id}")
def update_testimonial(
    testimonial_id: str,
    body: TestimonialAdminUpdate,
    _: str = Depends(get_current_admin),
):
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    updated = testimonial_repo.update(testimonial_id, updates)
    if not updated:
        raise HTTPException(status_code=404, detail="Testimonial not found.")
    return updated
