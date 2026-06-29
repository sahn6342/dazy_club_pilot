from fastapi import APIRouter, HTTPException, status
from models import AdminLoginRequest, AdminToken
from auth import create_access_token, verify_env_admin, verify_password
from deps import user_repo

router = APIRouter()


@router.post("/admin/login", response_model=AdminToken)
def login(request: AdminLoginRequest):
    # Check env-var superadmin first
    if verify_env_admin(request.username, request.password):
        return AdminToken(access_token=create_access_token(request.username, role="admin"))

    # Check manager repo
    user = user_repo.get_by_username(request.username)
    if user and verify_password(request.password, user.hashed_password):
        return AdminToken(access_token=create_access_token(request.username, role=user.role))

    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials.")
