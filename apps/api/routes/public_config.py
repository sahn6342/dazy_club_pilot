"""Public, read-only flags the web pages need to pick the right flow before the visitor acts.

Only non-sensitive switches belong here: no secrets, no provider names, nothing per-user."""
from fastapi import APIRouter

from services.advance import configured_advance
from services.otp_service import otp_disabled

router = APIRouter()


@router.get("/public-config")
def public_config():
    """`otpRequired`: whether searching bookings by phone/email needs a one-time code (DAZY_OTP_DISABLED unset).
    `advanceAmount`: the non-refundable advance a customer may pay instead of the full price (0 = no advance option);
    the booking page shows it up front, create-booking enforces it."""
    return {"otpRequired": not otp_disabled(), "advanceAmount": float(configured_advance())}
