from fastapi import APIRouter, HTTPException, Request, status
from models import AdminLoginRequest, AdminToken
from auth import create_access_token, verify_env_admin, verify_password
from deps import user_repo
from rate_limit import admin_login_limiter

router = APIRouter()


def clear_login_attempts() -> None:
    """Reset all rate-limit state. Call from test fixtures after DB reset."""
    admin_login_limiter.clear()


@router.post("/admin/login", response_model=AdminToken)
def login(request: AdminLoginRequest, req: Request):
    client_ip = req.client.host if req.client else "unknown"
    admin_login_limiter.check(client_ip)

    # Check env-var superadmin first
    if verify_env_admin(request.username, request.password):
        return AdminToken(access_token=create_access_token(request.username, role="admin"))

    # Check manager repo
    user = user_repo.get_by_username(request.username)
    if user and verify_password(request.password, user.hashed_password):
        return AdminToken(access_token=create_access_token(request.username, role=user.role))

    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials.")
