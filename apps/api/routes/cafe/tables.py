from fastapi import APIRouter, Depends

from auth import get_current_cashier
from deps import cafe_table_repo
from models import CafeTableDto

router = APIRouter()


@router.get("/cafe/tables", response_model=list[CafeTableDto])
def get_tables(_=Depends(get_current_cashier)):
    """Active tables with their current status."""
    return [CafeTableDto.model_validate(t) for t in cafe_table_repo.get_all(active_only=True)]
