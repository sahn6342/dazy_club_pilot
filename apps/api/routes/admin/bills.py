from fastapi import APIRouter, Depends, HTTPException, Request

from audit import audit
from auth import get_current_admin
from brand import BRAND_NAME
from deps import bill_repo, booking_repo, cms_repo
from models import BillCreate, BillVoidRequest
from services.billing import calc_bill
from services.venue_tz import get_venue_zoneinfo, local_today

router = APIRouter()


def _cms(key: str) -> str | None:
    entry = cms_repo.get_by_id(key)
    return (entry.value or "").strip() or None if entry else None


@router.get("/admin/bills/business")
def bill_business(_: dict = Depends(get_current_admin)):
    """Who the bill is from (the print header): everything comes from Admin -> Contact Details. Without a GSTIN
    the bill is headed plain "Bill", not "Tax Invoice"."""
    gstin = (_cms("venue_gstin") or "").upper() or None
    return {
        "name": _cms("venue_name") or BRAND_NAME, "gstin": gstin, "address": _cms("venue_address"),
        "phone": _cms("venue_phone"), "email": _cms("venue_email"),
        "title": "Tax Invoice" if gstin else "Bill",
    }


@router.post("/admin/bills", status_code=201)
def create_bill(body: BillCreate, req: Request, admin: dict = Depends(get_current_admin)):
    if body.bookingRef and not booking_repo.get_by_ref(body.bookingRef):
        raise HTTPException(status_code=404, detail="No booking with that reference.")
    totals = calc_bill([(ln.description, ln.qty, ln.rate, ln.gstRatePercent) for ln in body.lines])
    if totals.total <= 0:
        raise HTTPException(status_code=422, detail="The bill total must be more than zero.")
    bill = bill_repo.create(
        local_date=local_today(get_venue_zoneinfo()), totals=totals, customer_name=body.customerName,
        customer_phone=body.customerPhone, customer_gstin=body.customerGstin, notes=body.notes,
        booking_ref=body.bookingRef, created_by=admin["sub"],
    )
    audit("bill.create", admin, request=req, entity_type="bill", entity_id=bill["id"],
          detail={"billNo": bill["billNo"], "total": bill["total"], "lines": len(bill["lines"])})
    return bill


@router.get("/admin/bills")
def list_bills(q: str | None = None, date_from: str | None = None, date_to: str | None = None,
               status: str | None = None, limit: int = 25, offset: int = 0, _: dict = Depends(get_current_admin)):
    if status not in (None, "", "active", "void"):
        raise HTTPException(status_code=422, detail="status must be active or void.")
    items, total = bill_repo.query(q=q, date_from=date_from, date_to=date_to, status=status or None,
                                   limit=limit, offset=offset)
    return {"items": items, "total": total}


@router.get("/admin/bills/{bill_id}")
def get_bill(bill_id: str, _: dict = Depends(get_current_admin)):
    bill = bill_repo.get(bill_id)
    if not bill:
        raise HTTPException(status_code=404, detail="Bill not found.")
    return bill


@router.post("/admin/bills/{bill_id}/void")
def void_bill(bill_id: str, body: BillVoidRequest, req: Request, admin: dict = Depends(get_current_admin)):
    """A bill is never edited or deleted (its number stays used); a mistake is voided with a reason."""
    existing = bill_repo.get(bill_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Bill not found.")
    if existing["status"] == "void":
        raise HTTPException(status_code=409, detail="This bill is already void.")
    bill = bill_repo.void(bill_id, body.reason.strip(), admin["sub"])
    audit("bill.void", admin, request=req, entity_type="bill", entity_id=bill_id,
          detail={"billNo": bill["billNo"], "total": bill["total"], "reason": body.reason.strip()})
    return bill
