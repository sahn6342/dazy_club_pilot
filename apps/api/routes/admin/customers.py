from fastapi import APIRouter, Depends, Response
from models import CustomerRecord
from auth import get_current_admin
from deps import customer_repo

router = APIRouter()


@router.get("/admin/customers", response_model=list[CustomerRecord])
def list_customers(
    response: Response,
    limit: int = 500,
    offset: int = 0,
    _: dict = Depends(get_current_admin),
):
    """Newest first, paged in SQL. The full count is in the X-Total-Count header."""
    items, total = customer_repo.query(limit=limit, offset=offset)
    response.headers["X-Total-Count"] = str(total)
    return items
