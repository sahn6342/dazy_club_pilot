import hmac
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
_CASHIER_EXPIRES_HOURS = 2

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


def create_cashier_token(username: str, role: str = "cashier") -> str:
    """Short-lived token (2h) for kiosk staff."""
    payload = {
        "sub": username,
        "role": role,
        "exp": datetime.now(timezone.utc) + timedelta(hours=_CASHIER_EXPIRES_HOURS),
    }
    return jwt.encode(payload, _SECRET, algorithm=_ALGORITHM)


def verify_env_admin(username: str, password: str) -> bool:
    expected_user = os.environ.get("ADMIN_USERNAME", "admin")
    user_ok = hmac.compare_digest(username.encode(), expected_user.encode())
    expected_hash = os.environ.get("ADMIN_PASSWORD_HASH")
    if expected_hash:
        # Preferred in production: only a bcrypt hash of the password lives in the env.
        pass_ok = verify_password(password, expected_hash)
    else:
        pass_ok = hmac.compare_digest(password.encode(), os.environ.get("ADMIN_PASSWORD", "admin").encode())
    return user_ok and pass_ok


_PRINT_EXPIRES_SECONDS = 120


def create_print_token(invoice_id: str) -> str:
    """Short-lived, single-invoice token for the browser print window (which can't
    send an Authorization header). role="print" keeps it out of every role check."""
    payload = {
        "sub": invoice_id,
        "role": "print",
        "purpose": "invoice_print",
        "exp": datetime.now(timezone.utc) + timedelta(seconds=_PRINT_EXPIRES_SECONDS),
    }
    return jwt.encode(payload, _SECRET, algorithm=_ALGORITHM)


def verify_print_token(token: str, invoice_id: str) -> None:
    payload = _decode_token(token)
    if payload.get("purpose") != "invoice_print" or payload.get("sub") != invoice_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid print link.")


_OTP_EXPIRES_MINUTES = 15


def create_otp_token(contact: str) -> str:
    """Proof that `contact` passed an OTP check. role="otp" keeps it out of every role check."""
    payload = {
        "sub": contact, "role": "otp", "purpose": "booking_search",
        "exp": datetime.now(timezone.utc) + timedelta(minutes=_OTP_EXPIRES_MINUTES),
    }
    return jwt.encode(payload, _SECRET, algorithm=_ALGORITHM)


def verify_otp_token(token: str, contact: str) -> None:
    payload = _decode_token(token)
    if payload.get("purpose") != "booking_search" or payload.get("sub") != contact:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Verification does not match this contact.")


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
    role = payload.get("role", "admin")
    if role not in ("admin", "manager"):
        # Cashier/kitchen kiosk tokens must never reach back-office routes.
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required.")
    if role == "manager":
        # Verify the manager account still exists (guards against deleted-token reuse).
        from repositories.user_repo import SqliteUserRepository
        if not SqliteUserRepository().get_by_username(payload["sub"]):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Account no longer exists.")
    return {"sub": payload["sub"], "role": role}


def require_superadmin(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
) -> dict:
    """Only env-var admin (role=admin) may pass. Managers are rejected."""
    payload = _decode_token(credentials.credentials)
    if payload.get("role", "admin") != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Superadmin only.")
    return {"sub": payload["sub"], "role": "admin"}


def get_current_cashier(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
) -> dict:
    """Accepts cashier, kitchen, manager, or admin roles."""
    payload = _decode_token(credentials.credentials)
    role = payload.get("role", "admin")
    if role not in ("admin", "manager", "cashier", "kitchen"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Kiosk access required.")
    if role in ("manager", "cashier", "kitchen"):
        from repositories.user_repo import SqliteUserRepository
        if not SqliteUserRepository().get_by_username(payload["sub"]):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Account no longer exists.")
    return {"sub": payload["sub"], "role": role}
