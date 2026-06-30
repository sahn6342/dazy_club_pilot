from fastapi import APIRouter, HTTPException, Depends

from auth import get_current_admin
from deps import menu_item_repo
from models import MenuItemDto, MenuItemCreate, MenuItemUpdate

router = APIRouter()


@router.get("/admin/cafe/items", response_model=list[MenuItemDto])
def list_items(category_id: str | None = None, _=Depends(get_current_admin)):
    return [MenuItemDto.model_validate(i) for i in menu_item_repo.get_all(category_id=category_id)]


@router.post("/admin/cafe/items", response_model=MenuItemDto, status_code=201)
def create_item(body: MenuItemCreate, _=Depends(get_current_admin)):
    extras = body.model_dump(exclude={"category_id", "name", "price"}, exclude_none=True)
    row = menu_item_repo.create(
        category_id=body.category_id,
        name=body.name,
        price=body.price,
        **extras,
    )
    return MenuItemDto.model_validate(row)


@router.patch("/admin/cafe/items/{item_id}", response_model=MenuItemDto)
def update_item(item_id: str, body: MenuItemUpdate, _=Depends(get_current_admin)):
    updates = {k: v for k, v in body.model_dump(exclude_unset=True).items()}
    row = menu_item_repo.update(item_id, **updates)
    if not row:
        raise HTTPException(status_code=404, detail="Item not found.")
    return MenuItemDto.model_validate(row)


@router.delete("/admin/cafe/items/{item_id}", status_code=204)
def delete_item(item_id: str, _=Depends(get_current_admin)):
    if not menu_item_repo.delete(item_id):
        raise HTTPException(status_code=404, detail="Item not found.")
