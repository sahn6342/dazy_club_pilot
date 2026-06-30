from fastapi import APIRouter, HTTPException, Depends

from auth import get_current_admin
from deps import court_repo
from models import CourtDto, CourtCreate, CourtUpdate

router = APIRouter()


@router.get("/admin/courts", response_model=list[CourtDto])
def list_courts(_: dict = Depends(get_current_admin)):
    rows = court_repo.get_all(active_only=False)
    return [CourtDto(
        id=r.id, venue_id=r.venue_id, sport=r.sport,
        name=r.name, capacity=r.capacity, active=r.active,
        createdAt=r.createdAt,
    ) for r in rows]


@router.post("/admin/courts", response_model=CourtDto, status_code=201)
def create_court(data: CourtCreate, _: dict = Depends(get_current_admin)):
    row = court_repo.create(
        venue_id=data.venue_id,
        sport=data.sport,
        name=data.name,
        capacity=data.capacity,
    )
    return CourtDto(
        id=row.id, venue_id=row.venue_id, sport=row.sport,
        name=row.name, capacity=row.capacity, active=row.active,
        createdAt=row.createdAt,
    )


@router.patch("/admin/courts/{court_id}", response_model=CourtDto)
def update_court(court_id: str, data: CourtUpdate, _: dict = Depends(get_current_admin)):
    row = court_repo.update(
        court_id=court_id,
        name=data.name,
        capacity=data.capacity,
        active=data.active,
    )
    if not row:
        raise HTTPException(status_code=404, detail="Court not found.")
    return CourtDto(
        id=row.id, venue_id=row.venue_id, sport=row.sport,
        name=row.name, capacity=row.capacity, active=row.active,
        createdAt=row.createdAt,
    )


@router.delete("/admin/courts/{court_id}", status_code=204)
def deactivate_court(court_id: str, _: dict = Depends(get_current_admin)):
    ok = court_repo.deactivate(court_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Court not found.")
