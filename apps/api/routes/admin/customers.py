from fastapi import APIRouter, Depends
from models import CustomerRecord
from auth import get_current_admin
from deps import customer_repo

router = APIRouter()


@router.get("/admin/customers", response_model=list[CustomerRecord])
def list_customers(_: dict = Depends(get_current_admin)):
    return customer_repo.get_all()
