from fastapi import APIRouter, Depends, HTTPException
from models import (
    ScheduleRuleDto, ScheduleRuleCreate, ScheduleRuleUpdate,
    ScheduleExceptionDto, ScheduleExceptionCreate,
)
from auth import get_current_admin
from deps import court_repo, schedule_repo

router = APIRouter()


# ── Schedule rules ──
@router.get("/admin/schedule/rules", response_model=list[ScheduleRuleDto])
def list_rules(court_id: str | None = None, _: dict = Depends(get_current_admin)):
    return schedule_repo.list_rules(court_id)


@router.post("/admin/schedule/rules", response_model=ScheduleRuleDto, status_code=201)
def create_rule(body: ScheduleRuleCreate, _: dict = Depends(get_current_admin)):
    if not court_repo.get_by_id(body.court_id):
        raise HTTPException(status_code=404, detail="Court not found.")
    return schedule_repo.create_rule(body)


@router.patch("/admin/schedule/rules/{rule_id}", response_model=ScheduleRuleDto)
def update_rule(rule_id: str, body: ScheduleRuleUpdate, _: dict = Depends(get_current_admin)):
    updated = schedule_repo.update_rule(rule_id, body)
    if not updated:
        raise HTTPException(status_code=404, detail="Rule not found.")
    return updated


@router.delete("/admin/schedule/rules/{rule_id}", status_code=204)
def delete_rule(rule_id: str, _: dict = Depends(get_current_admin)):
    if not schedule_repo.delete_rule(rule_id):
        raise HTTPException(status_code=404, detail="Rule not found.")


# ── Schedule exceptions ──
@router.get("/admin/schedule/exceptions", response_model=list[ScheduleExceptionDto])
def list_exceptions(court_id: str | None = None, _: dict = Depends(get_current_admin)):
    return schedule_repo.list_exceptions(court_id)


@router.post("/admin/schedule/exceptions", response_model=ScheduleExceptionDto, status_code=201)
def create_exception(body: ScheduleExceptionCreate, _: dict = Depends(get_current_admin)):
    # court_id None = venue-wide (all courts); only validate when a specific court is given.
    if body.court_id is not None and not court_repo.get_by_id(body.court_id):
        raise HTTPException(status_code=404, detail="Court not found.")
    return schedule_repo.create_exception(body)


@router.delete("/admin/schedule/exceptions/{exc_id}", status_code=204)
def delete_exception(exc_id: str, _: dict = Depends(get_current_admin)):
    if not schedule_repo.delete_exception(exc_id):
        raise HTTPException(status_code=404, detail="Exception not found.")
