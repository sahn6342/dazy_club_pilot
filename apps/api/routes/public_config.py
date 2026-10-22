"""Public, read-only flags the web pages need to pick the right flow before the visitor acts.

Only non-sensitive switches belong here: no secrets, no provider names, nothing per-user."""
from fastapi import APIRouter

from services.otp_service import otp_disabled

router = APIRouter()


@router.get("/public-config")
def public_config():
    """`otpRequired`: whether searching bookings by phone/email needs a one-time code (DAZY_OTP_DISABLED unset)."""
    return {"otpRequired": not otp_disabled()}
