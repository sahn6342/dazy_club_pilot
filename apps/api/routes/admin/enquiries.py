from fastapi import APIRouter, Depends, HTTPException
from models import EnquiryStatusUpdate
from auth import get_current_admin
from deps import enquiry_repo

router = APIRouter()


@router.get("/admin/enquiries")
def list_enquiries(
    type: str | None = None,
    status: str | None = None,
    _: str = Depends(get_current_admin),
):
    result = enquiry_repo.get_all()
    if type:
        result = [e for e in result if e.type == type]
    if status:
        result = [e for e in result if e.status == status]
    return result


@router.patch("/admin/enquiries/{enquiry_id}")
def update_enquiry(
    enquiry_id: str,
    body: EnquiryStatusUpdate,
    _: str = Depends(get_current_admin),
):
    updated = enquiry_repo.update(enquiry_id, {"status": body.status})
    if not updated:
        raise HTTPException(status_code=404, detail="Enquiry not found.")
    return updated
