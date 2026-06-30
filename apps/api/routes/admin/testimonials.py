import uuid
from fastapi import APIRouter, Depends, HTTPException
from models import TestimonialAdmin, TestimonialAdminUpdate, TestimonialCreate, TestimonialUpdate
from auth import get_current_admin
from deps import testimonial_repo

router = APIRouter()


@router.get("/admin/testimonials")
def list_testimonials(_: str = Depends(get_current_admin)):
    return testimonial_repo.get_all()


@router.post("/admin/testimonials", status_code=201)
def create_testimonial(body: TestimonialCreate, _: str = Depends(get_current_admin)):
    item = TestimonialAdmin(id=str(uuid.uuid4()), **body.model_dump())
    return testimonial_repo.create(item)


@router.patch("/admin/testimonials/{testimonial_id}")
def update_testimonial_approved(
    testimonial_id: str,
    body: TestimonialAdminUpdate,
    _: str = Depends(get_current_admin),
):
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    updated = testimonial_repo.update(testimonial_id, updates)
    if not updated:
        raise HTTPException(status_code=404, detail="Testimonial not found.")
    return updated


@router.put("/admin/testimonials/{testimonial_id}")
def update_testimonial(
    testimonial_id: str,
    body: TestimonialUpdate,
    _: str = Depends(get_current_admin),
):
    updates = {k: v for k, v in body.model_dump(exclude_unset=True).items() if v is not None}
    updated = testimonial_repo.update(testimonial_id, updates)
    if not updated:
        raise HTTPException(status_code=404, detail="Testimonial not found.")
    return updated


@router.delete("/admin/testimonials/{testimonial_id}", status_code=204)
def delete_testimonial(testimonial_id: str, _: str = Depends(get_current_admin)):
    if not testimonial_repo.delete(testimonial_id):
        raise HTTPException(status_code=404, detail="Testimonial not found.")
