from fastapi import APIRouter
from deps import cms_repo

router = APIRouter()

_VENUE_KEYS = {
    "venue_name", "venue_address", "venue_phone",
    "venue_email", "venue_hours", "social_instagram", "social_facebook",
}


@router.get("/venue")
def get_venue_info():
    """Public endpoint — returns venue contact details stored in CMS."""
    entries = cms_repo.get_all()
    return [{"key": e.key, "value": e.value} for e in entries if e.key in _VENUE_KEYS]
