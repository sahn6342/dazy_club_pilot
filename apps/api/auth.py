import hmac
import os
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

import bcrypt as _bcrypt
import jwt
import time
import uuid
from typing import Optional

from fastapi import Depends, HTTPException, Request, Response, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

if TYPE_CHECKING:
    from repositories.user_repo import InMemoryUserRepository

_SECRET = os.environ.get("JWT_SECRET", "dazy-dev-secret-change-in-production")
_ALGORITHM = "HS256"
_EXPIRES_HOURS = 8
_CASHIER_EXPIRES_HOURS = 2

# auto_error off: a missing Authorization header is handled below so a session cookie can stand in.
_bearer = HTTPBearer(auto_error=False)

ADMIN_COOKIE = "dazy_admin"
KIOSK_COOKIE = "dazy_kiosk"
_CSRF_HEADER = "x-requested-with"
_CSRF_VALUE = "dazy"
_SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


def hash_password(plain: str) -> str:
    return _bcrypt.hashpw(plain.encode(), _bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return _bcrypt.checkpw(plain.encode(), hashed.encode())
    except Exception:
        return False


def _session_token(username: str, role: str, ttl: timedelta, ver: Optional[int]) -> str:
    payload = {
        "sub": username,
        "role": role,
        "exp": datetime.now(timezone.utc) + ttl,
        "jti": uuid.uuid4().hex,  # lets a single session be revoked on logout
    }
    if ver is not None:
        payload["ver"] = ver  # compared with users.token_version / ADMIN_SESSION_EPOCH on every request
    return jwt.encode(payload, _SECRET, algorithm=_ALGORITHM)


def admin_session_epoch() -> int:
    """ADMIN_SESSION_EPOCH: bump the env var to revoke every env-admin session at once."""
    try:
        return int(os.environ.get("ADMIN_SESSION_EPOCH", "0") or 0)
    except ValueError:
        return 0


def create_access_token(username: str, role: str = "admin", ver: Optional[int] = None) -> str:
    return _session_token(username, role, timedelta(hours=_EXPIRES_HOURS), ver)


def create_cashier_token(username: str, role: str = "cashier", ver: Optional[int] = None) -> str:
    """Short-lived token (2h) for kiosk staff."""
    return _session_token(username, role, timedelta(hours=_CASHIER_EXPIRES_HOURS), ver)


# ── Session cookies ───────────────────────────────────────────────────────────
# The SPAs authenticate with an httpOnly cookie so a script injected into the page cannot read
# the session. Cross-origin calls from the SPA carry it (fetch credentials: include) and must
# send X-Requested-With: dazy, which a cross-site form or image cannot add (CSRF defence).
# Bearer tokens keep working for scripts/tests; they are not ambient credentials, so no CSRF check.

def _cookie_samesite() -> str:
    v = os.environ.get("DAZY_COOKIE_SAMESITE", "lax").strip().lower()
    return v if v in ("lax", "strict", "none") else "lax"


def _cookie_secure() -> bool:
    flag = os.environ.get("DAZY_COOKIE_SECURE")
    if flag is not None and flag != "":
        return flag == "1"
    from config_guard import is_production
    return is_production() or _cookie_samesite() == "none"  # SameSite=None requires Secure


def _cookie_kwargs() -> dict:
    return {
        "path": "/",
        "domain": os.environ.get("DAZY_COOKIE_DOMAIN") or None,  # e.g. ".dazyclub.com"; unset = API host only
        "secure": _cookie_secure() or _cookie_samesite() == "none",
        "samesite": _cookie_samesite(),
    }


def set_session_cookie(response: Response, name: str, token: str) -> None:
    max_age = int((_CASHIER_EXPIRES_HOURS if name == KIOSK_COOKIE else _EXPIRES_HOURS) * 3600)
    response.set_cookie(name, token, max_age=max_age, httponly=True, **_cookie_kwargs())


def clear_session_cookie(response: Response, name: str) -> None:
    response.delete_cookie(name, httponly=True, **_cookie_kwargs())


# ── Revocation (logout) ───────────────────────────────────────────────────────

def revoke_token(token: Optional[str]) -> None:
    """Add a token's jti to the revocation list. Silent for missing/invalid/expired tokens."""
    if not token:
        return
    try:
        payload = jwt.decode(token, _SECRET, algorithms=[_ALGORITHM], options={"verify_exp": False})
    except jwt.InvalidTokenError:
        return
    jti, exp = payload.get("jti"), payload.get("exp")
    if not jti or not exp:
        return
    from sqlalchemy import delete as _delete
    from db import _session
    from db_models import RevokedTokenRow
    with _session() as s:
        s.execute(_delete(RevokedTokenRow).where(RevokedTokenRow.exp < time.time()))  # prune
        if s.get(RevokedTokenRow, jti) is None:
            s.add(RevokedTokenRow(jti=jti, exp=float(exp)))


def _is_revoked(jti: str) -> bool:
    from db import _session
    from db_models import RevokedTokenRow
    with _session() as s:
        return s.get(RevokedTokenRow, jti) is not None


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


def _extract(request: Request, creds: Optional[HTTPAuthorizationCredentials], cookie: str) -> tuple[str, bool]:
    """(token, came_from_cookie). Authorization header wins over the cookie."""
    if creds is not None and creds.credentials:
        return creds.credentials, False
    cookie_token = request.cookies.get(cookie)
    if cookie_token:
        return cookie_token, True
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated.")


def _enforce_csrf(request: Request, from_cookie: bool) -> None:
    if from_cookie and request.method not in _SAFE_METHODS and request.headers.get(_CSRF_HEADER) != _CSRF_VALUE:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Missing CSRF header.")


def _check_session(payload: dict) -> None:
    """Revocation list, account existence and token version. Tokens minted before these
    claims existed (no jti/ver) are treated as version 0 and cannot be individually revoked."""
    jti = payload.get("jti")
    if jti and _is_revoked(jti):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session ended. Please sign in again.")
    role = payload.get("role", "admin")
    ver = int(payload.get("ver", 0))
    if role in ("manager", "cashier", "kitchen"):
        from repositories.user_repo import SqliteUserRepository
        user = SqliteUserRepository().get_by_username(payload["sub"])
        if not user:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Account no longer exists.")
        if ver != user.token_version:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session expired. Please sign in again.")
    elif role == "admin" and ver != admin_session_epoch():
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session expired. Please sign in again.")


def _authenticate(request: Request, creds: Optional[HTTPAuthorizationCredentials], cookie: str) -> dict:
    token, from_cookie = _extract(request, creds, cookie)
    _enforce_csrf(request, from_cookie)
    return _decode_token(token)


def get_current_admin(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
) -> dict:
    """Returns {"sub": username, "role": "admin"|"manager"}. Accepts both roles."""
    payload = _authenticate(request, credentials, ADMIN_COOKIE)
    role = payload.get("role", "admin")
    if role not in ("admin", "manager"):
        # Cashier/kitchen kiosk tokens must never reach back-office routes.
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required.")
    _check_session(payload)
    return {"sub": payload["sub"], "role": role}


def require_superadmin(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
) -> dict:
    """Only env-var admin (role=admin) may pass. Managers are rejected."""
    payload = _authenticate(request, credentials, ADMIN_COOKIE)
    if payload.get("role", "admin") != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Superadmin only.")
    _check_session(payload)
    return {"sub": payload["sub"], "role": "admin"}


def get_current_cashier(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
) -> dict:
    """Accepts cashier, kitchen, manager, or admin roles."""
    payload = _authenticate(request, credentials, KIOSK_COOKIE)
    role = payload.get("role", "admin")
    if role not in ("admin", "manager", "cashier", "kitchen"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Kiosk access required.")
    _check_session(payload)
    return {"sub": payload["sub"], "role": role}


def end_session(request: Request, response: Response, creds: Optional[HTTPAuthorizationCredentials], cookie: str) -> None:
    """Logout: revoke the presented token (if any) and clear the cookie. Never raises."""
    token = creds.credentials if creds is not None and creds.credentials else request.cookies.get(cookie)
    revoke_token(token)
    clear_session_cookie(response, cookie)
