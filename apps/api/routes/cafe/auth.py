from fastapi import APIRouter, HTTPException, Request, status

from auth import verify_password, create_cashier_token
from deps import user_repo
from models import CafePinLoginRequest, AdminToken
from rate_limit import cashier_login_limiter, cashier_pin_lockout, client_ip

router = APIRouter()


@router.post("/cafe/login", response_model=AdminToken)
def cafe_pin_login(body: CafePinLoginRequest, req: Request):
    """PIN login for kiosk (cashier / kitchen roles). Issues a short-lived JWT."""
    cashier_login_limiter.check(client_ip(req), "Too many login attempts. Try again later.")
    # Per-username lockout: a 4-digit PIN is only safe if guesses are capped per account,
    # not just per IP. Only failed attempts count; a correct PIN clears the counter.
    lock_key = body.username.strip().lower()
    if cashier_pin_lockout.is_blocked(lock_key):
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                            detail="Too many failed PIN attempts. Try again in 15 minutes.")
    user = user_repo.get_by_username(body.username)
    if not user or user.role not in ("cashier", "kitchen") or not verify_password(body.pin, user.hashed_password):
        cashier_pin_lockout.hit(lock_key)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials.")
    cashier_pin_lockout.reset(lock_key)
    token = create_cashier_token(user.username, user.role)
    return AdminToken(access_token=token)
