from fastapi import APIRouter, Depends, HTTPException, Response
from models import EnquiryStatusUpdate
from auth import get_current_admin
from deps import enquiry_repo

router = APIRouter()


@router.get("/admin/enquiries")
def list_enquiries(
    response: Response,
    type: str | None = None,
    status: str | None = None,
    limit: int = 500,
    offset: int = 0,
    _: str = Depends(get_current_admin),
):
    """Newest first, filtered and paged in SQL. The full count is in the X-Total-Count header."""
    items, total = enquiry_repo.query(type=type, status=status, limit=limit, offset=offset)
    response.headers["X-Total-Count"] = str(total)
    return items


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
