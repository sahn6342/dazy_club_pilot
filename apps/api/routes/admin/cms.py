from fastapi import APIRouter, Depends, HTTPException
import re

from models import CmsEntry, CmsEntryUpdate, CmsCreate, GSTIN_PATTERN
from auth import get_current_admin
from deps import cms_repo
from services.advance import ADVANCE_KEY, parse_advance
from services.refund_policy import POLICY_KEY, PolicyError, parse_policy

router = APIRouter()


def _validate_policy(value: str) -> None:
    try:
        parse_policy(value)
    except PolicyError as e:
        raise HTTPException(status_code=422, detail=str(e))


def _validate_value(key: str, value: str) -> None:
    """Keys whose value drives money logic are checked here, so a typo cannot reach a booking."""
    if key == POLICY_KEY:
        _validate_policy(value)
    elif key == "venue_gstin":  # printed on every bill: empty (not registered) or a well-formed GSTIN
        if value.strip() and not re.fullmatch(GSTIN_PATTERN, value.strip().upper()):
            raise HTTPException(status_code=422, detail="GSTIN must be 15 characters, e.g. 10ABCDE1234F1Z5.")
    elif key == ADVANCE_KEY:
        try:
            parse_advance(value)
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e))


@router.get("/admin/cms")
def list_cms(_: str = Depends(get_current_admin)):
    return cms_repo.get_all()


@router.post("/admin/cms", status_code=201)
def create_cms_entry(body: CmsCreate, _: str = Depends(get_current_admin)):
    if cms_repo.get_by_id(body.key):
        raise HTTPException(status_code=409, detail="CMS key already exists.")
    _validate_value(body.key, body.value)
    return cms_repo.create(CmsEntry(key=body.key, label=body.label, value=body.value))


@router.put("/admin/cms/{key}")
def update_cms_entry(
    key: str,
    body: CmsEntryUpdate,
    _: str = Depends(get_current_admin),
):
    updates = {k: v for k, v in body.model_dump(exclude_unset=True).items() if v is not None}
    if not updates:
        raise HTTPException(status_code=422, detail="Nothing to update.")
    if "value" in updates:
        _validate_value(key, updates["value"])
    updated = cms_repo.update(key, updates)
    if not updated:
        raise HTTPException(status_code=404, detail="CMS entry not found.")
    return updated


@router.delete("/admin/cms/{key}", status_code=204)
def delete_cms_entry(key: str, _: str = Depends(get_current_admin)):
    if not cms_repo.delete(key):
        raise HTTPException(status_code=404, detail="CMS entry not found.")
