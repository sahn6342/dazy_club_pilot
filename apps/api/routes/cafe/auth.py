from fastapi import APIRouter, HTTPException, Request, status

from auth import verify_password, create_cashier_token
from deps import user_repo
from models import CafePinLoginRequest, AdminToken
from rate_limit import cashier_login_limiter

router = APIRouter()


@router.post("/cafe/login", response_model=AdminToken)
def cafe_pin_login(body: CafePinLoginRequest, req: Request):
    """PIN login for kiosk (cashier / kitchen roles). Issues a short-lived JWT."""
    client_ip = req.client.host if req.client else "unknown"
    cashier_login_limiter.check(client_ip)
    user = user_repo.get_by_username(body.username)
    if not user or user.role not in ("cashier", "kitchen"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials.")
    if not verify_password(body.pin, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials.")
    token = create_cashier_token(user.username, user.role)
    return AdminToken(access_token=token)
