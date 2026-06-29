import os
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

import bcrypt as _bcrypt
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

if TYPE_CHECKING:
    from repositories.user_repo import InMemoryUserRepository

_SECRET = os.environ.get("JWT_SECRET", "dazy-dev-secret-change-in-production")
_ALGORITHM = "HS256"
_EXPIRES_HOURS = 8

_bearer = HTTPBearer()


def hash_password(plain: str) -> str:
    return _bcrypt.hashpw(plain.encode(), _bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return _bcrypt.checkpw(plain.encode(), hashed.encode())
    except Exception:
        return False


def create_access_token(username: str, role: str = "admin") -> str:
    payload = {
        "sub": username,
        "role": role,
        "exp": datetime.now(timezone.utc) + timedelta(hours=_EXPIRES_HOURS),
    }
    return jwt.encode(payload, _SECRET, algorithm=_ALGORITHM)


def verify_env_admin(username: str, password: str) -> bool:
    expected_user = os.environ.get("ADMIN_USERNAME", "admin")
    expected_pass = os.environ.get("ADMIN_PASSWORD", "dazy-admin-2024")
    return username == expected_user and password == expected_pass


def _decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, _SECRET, algorithms=[_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired.")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token.")


def get_current_admin(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
) -> dict:
    """Returns {"sub": username, "role": "admin"|"manager"}. Accepts both roles."""
    payload = _decode_token(credentials.credentials)
    return {"sub": payload["sub"], "role": payload.get("role", "admin")}


def require_superadmin(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
) -> dict:
    """Only env-var admin (role=admin) may pass. Managers are rejected."""
    payload = _decode_token(credentials.credentials)
    if payload.get("role", "admin") != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Superadmin only.")
    return {"sub": payload["sub"], "role": "admin"}
