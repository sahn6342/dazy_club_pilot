"""Customer OTP: prove control of an email / phone to unlock contact-only booking search."""
from fastapi import APIRouter, HTTPException, Request

from auth import create_otp_token
from models import OtpRequestBody, OtpVerifyBody
from rate_limit import otp_request_limiter, otp_verify_limiter, client_ip
from services.otp_service import request_otp, verify_otp, validate_contact, normalize_contact
from services.turnstile import require_turnstile

router = APIRouter()


@router.post("/otp/request")
def otp_request(body: OtpRequestBody, req: Request):
    ip = client_ip(req)
    err = validate_contact(body.contact)
    if err:
        raise HTTPException(status_code=422, detail=err)
    otp_request_limiter.check(ip, "Too many code requests. Please try again later.")
    otp_request_limiter.check(f"c:{normalize_contact(body.contact)}", "Too many code requests for this contact. Please try again later.")
    require_turnstile(body.turnstileToken, ip)
    channel = request_otp(body.contact)
    # Same response whether or not the contact has any bookings: no account/booking enumeration.
    return {"status": "sent", "channel": channel}


@router.post("/otp/verify")
def otp_verify(body: OtpVerifyBody, req: Request):
    otp_verify_limiter.check(client_ip(req), "Too many attempts. Please try again later.")
    otp_verify_limiter.check(f"c:{normalize_contact(body.contact)}", "Too many attempts. Please request a new code.")
    if not verify_otp(body.contact, body.code):
        raise HTTPException(status_code=400, detail="That code is incorrect or has expired.")
    return {"otpToken": create_otp_token(normalize_contact(body.contact))}
