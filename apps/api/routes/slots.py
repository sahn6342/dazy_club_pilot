from fastapi import APIRouter, Response
from services.availability_service import generate_slots

router = APIRouter()


@router.get("/slots")
def get_slots(sport: str | None = None, date: str | None = None, response: Response = None):
    slots = generate_slots(sport=sport, date=date, drop_past=True)
    if response:
        response.headers["Cache-Control"] = "no-store"
    return slots
