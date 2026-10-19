import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Request
from models import ContactEnquiryRequest, CorporateEnquiryRequest, EnquiryRecord
from deps import enquiry_repo
from rate_limit import enquiry_limiter, client_ip
from services.turnstile import require_turnstile

router = APIRouter()


@router.post("/contact-enquiries", status_code=201)
def contact_enquiry(request: ContactEnquiryRequest, http_req: Request):
    enquiry_limiter.check(client_ip(http_req), "Too many enquiries. Please try again later.")
    require_turnstile(request.turnstileToken, client_ip(http_req))
    record = EnquiryRecord(
        id=str(uuid.uuid4()),
        type="contact",
        name=request.name,
        contact=request.contact,
        interestedSport=request.interestedSport,
        message=request.message,
        status="new",
        createdAt=datetime.now(timezone.utc).isoformat(),
    )
    enquiry_repo.create(record)
    return {"status": "received", "name": request.name, "id": record.id}


@router.post("/corporate-enquiries", status_code=201)
def corporate_enquiry(request: CorporateEnquiryRequest, http_req: Request):
    enquiry_limiter.check(client_ip(http_req), "Too many enquiries. Please try again later.")
    require_turnstile(request.turnstileToken, client_ip(http_req))
    record = EnquiryRecord(
        id=str(uuid.uuid4()),
        type="corporate",
        name=request.contactName,
        contact=request.contact,
        company=request.company,
        eventType=request.eventType,
        estimatedGroupSize=request.estimatedGroupSize,
        preferredDate=request.preferredDate,
        preferredSport=request.preferredSport,
        message=request.message,
        status="new",
        createdAt=datetime.now(timezone.utc).isoformat(),
    )
    enquiry_repo.create(record)
    return {"status": "received", "company": request.company, "id": record.id}
