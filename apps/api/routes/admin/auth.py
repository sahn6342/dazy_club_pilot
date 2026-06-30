import time
from collections import defaultdict

from fastapi import APIRouter, HTTPException, Request, status
from models import AdminLoginRequest, AdminToken
from auth import create_access_token, verify_env_admin, verify_password
from deps import user_repo

router = APIRouter()

_login_attempts: dict[str, list[float]] = defaultdict(list)
_RATE_WINDOW = 60   # seconds
_RATE_LIMIT = 10    # max attempts per IP per window


def _enforce_rate_limit(ip: str) -> None:
    now = time.time()
    window = [t for t in _login_attempts[ip] if now - t < _RATE_WINDOW]
    if len(window) >= _RATE_LIMIT:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many login attempts. Try again later.",
        )
    window.append(now)
    _login_attempts[ip] = window


def clear_login_attempts() -> None:
    """Reset all rate-limit state. Call from test fixtures after DB reset."""
    _login_attempts.clear()


@router.post("/admin/login", response_model=AdminToken)
def login(request: AdminLoginRequest, req: Request):
    client_ip = req.client.host if req.client else "unknown"
    _enforce_rate_limit(client_ip)

    # Check env-var superadmin first
    if verify_env_admin(request.username, request.password):
        return AdminToken(access_token=create_access_token(request.username, role="admin"))

    # Check manager repo
    user = user_repo.get_by_username(request.username)
    if user and verify_password(request.password, user.hashed_password):
        return AdminToken(access_token=create_access_token(request.username, role=user.role))

    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials.")
