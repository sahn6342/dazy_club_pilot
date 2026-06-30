from fastapi import APIRouter, HTTPException, Depends

from auth import get_current_admin
from deps import menu_category_repo
from models import MenuCategoryDto, MenuCategoryCreate, MenuCategoryUpdate

router = APIRouter()


@router.get("/admin/cafe/categories", response_model=list[MenuCategoryDto])
def list_categories(_=Depends(get_current_admin)):
    return [MenuCategoryDto.model_validate(c) for c in menu_category_repo.get_all(active_only=False)]


@router.post("/admin/cafe/categories", response_model=MenuCategoryDto, status_code=201)
def create_category(body: MenuCategoryCreate, _=Depends(get_current_admin)):
    row = menu_category_repo.create(
        name=body.name,
        kind=body.kind,
        veg_type=body.vegType,
        sort_order=body.sortOrder,
    )
    return MenuCategoryDto.model_validate(row)


@router.patch("/admin/cafe/categories/{cat_id}", response_model=MenuCategoryDto)
def update_category(cat_id: str, body: MenuCategoryUpdate, _=Depends(get_current_admin)):
    updates = {k: v for k, v in body.model_dump(exclude_unset=True).items()}
    row = menu_category_repo.update(cat_id, **updates)
    if not row:
        raise HTTPException(status_code=404, detail="Category not found.")
    return MenuCategoryDto.model_validate(row)


@router.delete("/admin/cafe/categories/{cat_id}", status_code=204)
def delete_category(cat_id: str, _=Depends(get_current_admin)):
    if not menu_category_repo.delete(cat_id):
        raise HTTPException(status_code=404, detail="Category not found.")
