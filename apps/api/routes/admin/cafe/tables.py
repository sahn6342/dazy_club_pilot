from fastapi import APIRouter, HTTPException, Depends

from auth import get_current_admin
from deps import cafe_table_repo
from models import CafeTableDto, CafeTableCreate, CafeTableUpdate

router = APIRouter()


@router.get("/admin/cafe/tables", response_model=list[CafeTableDto])
def list_tables(_=Depends(get_current_admin)):
    return [CafeTableDto.model_validate(t) for t in cafe_table_repo.get_all(active_only=False)]


@router.post("/admin/cafe/tables", response_model=CafeTableDto, status_code=201)
def create_table(body: CafeTableCreate, _=Depends(get_current_admin)):
    row = cafe_table_repo.create(
        label=body.label,
        capacity=body.capacity,
        area=body.area,
        sort_order=body.sortOrder,
    )
    return CafeTableDto.model_validate(row)


@router.patch("/admin/cafe/tables/{table_id}", response_model=CafeTableDto)
def update_table(table_id: str, body: CafeTableUpdate, _=Depends(get_current_admin)):
    updates = {k: v for k, v in body.model_dump(exclude_unset=True).items()}
    row = cafe_table_repo.update(table_id, **updates)
    if not row:
        raise HTTPException(status_code=404, detail="Table not found.")
    return CafeTableDto.model_validate(row)


@router.delete("/admin/cafe/tables/{table_id}", status_code=204)
def delete_table(table_id: str, _=Depends(get_current_admin)):
    if not cafe_table_repo.delete(table_id):
        raise HTTPException(status_code=404, detail="Table not found.")
