from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from models import AdminLoginRequest, AdminToken
from auth import (
    ADMIN_COOKIE, _bearer, admin_session_epoch, clear_session_cookie, create_access_token, end_session,
    get_current_admin, set_session_cookie, verify_env_admin, verify_password,
)
from deps import user_repo
from rate_limit import admin_login_limiter, client_ip

router = APIRouter()


def clear_login_attempts() -> None:
    """Reset all rate-limit state. Call from test fixtures after DB reset."""
    admin_login_limiter.clear()


@router.post("/admin/login", response_model=AdminToken)
def login(request: AdminLoginRequest, req: Request, response: Response):
    admin_login_limiter.check(client_ip(req), "Too many login attempts. Try again later.")

    # Check env-var superadmin first
    if verify_env_admin(request.username, request.password):
        token = create_access_token(request.username, role="admin", ver=admin_session_epoch())
        set_session_cookie(response, ADMIN_COOKIE, token)
        return AdminToken(access_token=token)

    # Check manager repo
    user = user_repo.get_by_username(request.username)
    if user and user.role == "manager" and verify_password(request.password, user.hashed_password):
        token = create_access_token(request.username, role=user.role, ver=user.token_version)
        set_session_cookie(response, ADMIN_COOKIE, token)
        return AdminToken(access_token=token)

    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials.")


@router.post("/admin/logout", status_code=204)
def logout(req: Request, response: Response, credentials=Depends(_bearer)):
    """Revoke this session and clear the cookie. Idempotent; works with an expired or missing session."""
    end_session(req, response, credentials, ADMIN_COOKIE)
    response.status_code = 204


@router.get("/admin/me")
def me(admin: dict = Depends(get_current_admin)):
    """Who am I? The SPA calls this on load to learn whether its session cookie is still valid."""
    return {"username": admin["sub"], "role": admin["role"]}
