from fastapi import APIRouter, Depends

from auth import get_current_cashier
from deps import menu_category_repo, menu_item_repo
from models import MenuCategoryDto, MenuItemDto, MenuResponse

router = APIRouter()


@router.get("/cafe/menu", response_model=MenuResponse)
def get_menu(_=Depends(get_current_cashier)):
    """Active categories + available items for the kiosk."""
    categories = [MenuCategoryDto.model_validate(c) for c in menu_category_repo.get_all(active_only=True)]
    items = [MenuItemDto.model_validate(i) for i in menu_item_repo.get_all(available_only=True)]
    return MenuResponse(categories=categories, items=items)
