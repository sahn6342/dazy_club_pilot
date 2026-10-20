from fastapi import APIRouter, Depends, HTTPException, Request, Response, status

from auth import (
    KIOSK_COOKIE, _bearer, create_cashier_token, end_session, get_current_cashier, set_session_cookie, verify_password,
)
from audit import audit
from deps import user_repo
from models import CafePinLoginRequest, AdminToken
from rate_limit import cashier_login_limiter, cashier_pin_lockout, client_ip

router = APIRouter()


@router.post("/cafe/login", response_model=AdminToken)
def cafe_pin_login(body: CafePinLoginRequest, req: Request, response: Response):
    """PIN login for kiosk (cashier / kitchen roles). Issues a short-lived JWT."""
    cashier_login_limiter.check(client_ip(req), "Too many login attempts. Try again later.")
    # Per-username lockout: a 4-digit PIN is only safe if guesses are capped per account,
    # not just per IP. Only failed attempts count; a correct PIN clears the counter.
    lock_key = body.username.strip().lower()
    if cashier_pin_lockout.is_blocked(lock_key):
        audit("kiosk.lockout", body.username, request=req, entity_type="user")
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                            detail="Too many failed PIN attempts. Try again in 15 minutes.")
    user = user_repo.get_by_username(body.username)
    if not user or user.role not in ("cashier", "kitchen") or not verify_password(body.pin, user.hashed_password):
        cashier_pin_lockout.hit(lock_key)
        audit("kiosk.login_failed", body.username, request=req, entity_type="user")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials.")
    cashier_pin_lockout.reset(lock_key)
    audit("kiosk.login", {"sub": user.username, "role": user.role}, request=req, entity_type="user", entity_id=user.id)
    token = create_cashier_token(user.username, user.role, ver=user.token_version)
    set_session_cookie(response, KIOSK_COOKIE, token)
    return AdminToken(access_token=token)


@router.post("/cafe/logout", status_code=204)
def cafe_logout(req: Request, response: Response, credentials=Depends(_bearer)):
    who = end_session(req, response, credentials, KIOSK_COOKIE)
    if who:
        audit("kiosk.logout", who, request=req, entity_type="user")
    response.status_code = 204


@router.get("/cafe/me")
def cafe_me(staff: dict = Depends(get_current_cashier)):
    return {"username": staff["sub"], "role": staff["role"]}
