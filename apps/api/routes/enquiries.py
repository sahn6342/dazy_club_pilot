import uuid
from datetime import datetime, timezone
from fastapi import APIRouter
from models import ContactEnquiryRequest, CorporateEnquiryRequest, EnquiryRecord
from deps import enquiry_repo

router = APIRouter()


@router.post("/contact-enquiries", status_code=201)
def contact_enquiry(request: ContactEnquiryRequest):
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
def corporate_enquiry(request: CorporateEnquiryRequest):
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
