"""Workstream B: httpOnly cookie sessions, CSRF header, logout/revocation, token versions,
CORS with credentials and response security headers."""
import time
import uuid
from datetime import datetime, timezone

import jwt
import pytest
from starlette.testclient import TestClient

import auth
import deps
from auth import create_access_token, create_cashier_token, hash_password
from main import app
from models import UserRecord

CSRF = {"X-Requested-With": "dazy"}
ORIGIN = "http://localhost:5174"


def _admin_login(c, user="admin", password="admin"):
    r = c.post("/api/v1/admin/login", json={"username": user, "password": password})
    assert r.status_code == 200, r.text
    return r


def _set_cookies(r):
    return r.headers.get_list("set-cookie")


def _make_user(role, secret):
    name = f"{role}_{uuid.uuid4().hex[:6]}"
    deps.user_repo.create(UserRecord(
        id=str(uuid.uuid4()), username=name, hashed_password=hash_password(secret), role=role,
        createdAt=datetime.now(timezone.utc).isoformat(), createdBy="admin"))
    return name


# ── cookie issuance ─────────────────────────────────────────────────────────

def test_login_sets_httponly_session_cookie_and_still_returns_token(client):
    r = _admin_login(client)
    cookie = next(c for c in _set_cookies(r) if c.startswith("dazy_admin="))
    low = cookie.lower()
    assert "httponly" in low and "samesite=lax" in low and "path=/" in low and "secure" not in low
    assert "max-age=28800" in low  # 8 h, same as the token
    assert r.json()["access_token"]  # scripts/tests keep working


def test_cookie_alone_authenticates(client):
    _admin_login(client)  # cookie jar now holds dazy_admin; no Authorization header is sent below
    r = client.get("/api/v1/admin/me")
    assert r.status_code == 200 and r.json() == {"username": "admin", "role": "admin"}
    assert client.get("/api/v1/admin/bookings").status_code == 200


def test_no_credentials_is_401(client):
    assert client.get("/api/v1/admin/me").status_code == 401
    assert client.get("/api/v1/cafe/me").status_code == 401


def test_cookie_flags_follow_config(client, monkeypatch):
    monkeypatch.setenv("DAZY_COOKIE_SAMESITE", "none")
    monkeypatch.setenv("DAZY_COOKIE_DOMAIN", ".example.com")
    cookie = next(c for c in _set_cookies(_admin_login(client)) if c.startswith("dazy_admin=")).lower()
    assert "samesite=none" in cookie and "secure" in cookie and "domain=.example.com" in cookie


def test_cookie_is_secure_in_production(client, monkeypatch):
    monkeypatch.setenv("RENDER", "true")
    cookie = next(c for c in _set_cookies(_admin_login(client)) if c.startswith("dazy_admin=")).lower()
    assert "secure" in cookie
    monkeypatch.setenv("DAZY_COOKIE_SECURE", "0")  # explicit override wins
    cookie = next(c for c in _set_cookies(_admin_login(client)) if c.startswith("dazy_admin=")).lower()
    assert "secure" not in cookie


# ── CSRF ────────────────────────────────────────────────────────────────────

def test_cookie_auth_requires_csrf_header_on_writes(client):
    _admin_login(client)
    assert client.delete("/api/v1/admin/bookings/none").status_code == 403           # cookie, no header
    assert client.delete("/api/v1/admin/bookings/none", headers=CSRF).status_code == 404  # passes auth
    assert client.delete("/api/v1/admin/bookings/none", headers={"X-Requested-With": "other"}).status_code == 403


def test_reads_with_cookie_need_no_csrf_header(client):
    _admin_login(client)
    assert client.get("/api/v1/admin/bookings").status_code == 200


def test_bearer_auth_needs_no_csrf_header(client):
    token = create_access_token("admin", "admin")
    assert client.delete("/api/v1/admin/bookings/none", headers={"Authorization": f"Bearer {token}"}).status_code == 404


def test_authorization_header_wins_over_cookie(client):
    _admin_login(client)  # valid cookie present
    r = client.get("/api/v1/admin/me", headers={"Authorization": "Bearer garbage"})
    assert r.status_code == 401  # the bad bearer is not silently replaced by the cookie


# ── logout / revocation ────────────────────────────────────────────────────

def test_logout_revokes_the_token_and_clears_the_cookie(client):
    token = _admin_login(client).json()["access_token"]
    bearer = {"Authorization": f"Bearer {token}"}
    assert client.get("/api/v1/admin/me", headers=bearer).status_code == 200

    r = client.post("/api/v1/admin/logout")  # session identified by the cookie
    assert r.status_code == 204
    cleared = next(c for c in _set_cookies(r) if c.startswith("dazy_admin=")).lower()
    assert "max-age=0" in cleared or "expires=" in cleared

    assert client.get("/api/v1/admin/me", headers=bearer).status_code == 401  # even though the JWT has not expired
    assert "ended" in client.get("/api/v1/admin/me", headers=bearer).json()["detail"].lower()


def test_logout_only_ends_that_session(client):
    first = _admin_login(client).json()["access_token"]
    second = create_access_token("admin", "admin", ver=0)
    client.post("/api/v1/admin/logout", headers={"Authorization": f"Bearer {first}"})
    assert client.get("/api/v1/admin/me", headers={"Authorization": f"Bearer {second}"}).status_code == 200


def test_logout_is_idempotent_without_a_session(client):
    assert client.post("/api/v1/admin/logout").status_code == 204
    assert client.post("/api/v1/admin/logout", headers={"Authorization": "Bearer junk"}).status_code == 204
    assert client.post("/api/v1/cafe/logout").status_code == 204


def test_revocation_list_is_pruned(client):
    from db import _session
    from db_models import RevokedTokenRow
    with _session() as s:
        s.add(RevokedTokenRow(jti="stale", exp=time.time() - 10))
    auth.revoke_token(create_access_token("admin", "admin"))
    with _session() as s:
        assert s.get(RevokedTokenRow, "stale") is None
        assert s.query(RevokedTokenRow).count() == 1


def test_tokens_without_jti_or_ver_still_work_until_they_expire(client):
    legacy = jwt.encode({"sub": "admin", "role": "admin", "exp": time.time() + 600}, auth._SECRET, algorithm="HS256")
    assert client.get("/api/v1/admin/me", headers={"Authorization": f"Bearer {legacy}"}).status_code == 200


# ── token version: password/role change and env epoch ──────────────────────

def test_password_change_revokes_existing_sessions(client, auth_headers):
    name = _make_user("manager", "password-one")
    old = client.post("/api/v1/admin/login", json={"username": name, "password": "password-one"}).json()["access_token"]
    old_h = {"Authorization": f"Bearer {old}"}
    assert client.get("/api/v1/admin/me", headers=old_h).status_code == 200

    uid = deps.user_repo.get_by_username(name).id
    r = client.patch(f"/api/v1/admin/users/{uid}", json={"password": "password-two"}, headers=auth_headers)
    assert r.status_code == 200

    r = client.get("/api/v1/admin/me", headers=old_h)
    assert r.status_code == 401 and "expired" in r.json()["detail"].lower()
    new = client.post("/api/v1/admin/login", json={"username": name, "password": "password-two"}).json()["access_token"]
    assert client.get("/api/v1/admin/me", headers={"Authorization": f"Bearer {new}"}).status_code == 200


def test_role_change_revokes_existing_sessions(client, auth_headers):
    name = _make_user("manager", "password-one")
    old = client.post("/api/v1/admin/login", json={"username": name, "password": "password-one"}).json()["access_token"]
    uid = deps.user_repo.get_by_username(name).id
    client.patch(f"/api/v1/admin/users/{uid}", json={"role": "cashier"}, headers=auth_headers)
    assert client.get("/api/v1/admin/me", headers={"Authorization": f"Bearer {old}"}).status_code == 401


def test_env_admin_epoch_revokes_all_env_admin_sessions(client, monkeypatch):
    token = _admin_login(client).json()["access_token"]
    h = {"Authorization": f"Bearer {token}"}
    assert client.get("/api/v1/admin/me", headers=h).status_code == 200
    monkeypatch.setenv("ADMIN_SESSION_EPOCH", "1")
    assert client.get("/api/v1/admin/me", headers=h).status_code == 401
    fresh = _admin_login(client).json()["access_token"]
    assert client.get("/api/v1/admin/me", headers={"Authorization": f"Bearer {fresh}"}).status_code == 200


# ── kiosk cookie ───────────────────────────────────────────────────────────

def test_kiosk_login_logout_with_separate_cookie(client):
    name = _make_user("cashier", "1234")
    r = client.post("/api/v1/cafe/login", json={"username": name, "pin": "1234"})
    assert r.status_code == 200
    cookie = next(c for c in _set_cookies(r) if c.startswith("dazy_kiosk=")).lower()
    assert "httponly" in cookie and "max-age=7200" in cookie  # 2 h
    assert client.get("/api/v1/cafe/me").json() == {"username": name, "role": "cashier"}
    assert client.get("/api/v1/admin/me").status_code == 401  # kiosk session never opens the back office

    token = r.json()["access_token"]
    assert client.post("/api/v1/cafe/logout").status_code == 204
    assert client.get("/api/v1/cafe/me", headers={"Authorization": f"Bearer {token}"}).status_code == 401


def test_admin_and_kiosk_sessions_coexist_in_one_browser(client):
    _admin_login(client)
    name = _make_user("cashier", "1234")
    client.post("/api/v1/cafe/login", json={"username": name, "pin": "1234"})
    assert client.get("/api/v1/admin/me").json()["role"] == "admin"
    assert client.get("/api/v1/cafe/me").json()["role"] == "cashier"
    client.post("/api/v1/cafe/logout")
    assert client.get("/api/v1/admin/me").status_code == 200  # kiosk logout left the admin cookie alone


def test_kiosk_writes_with_cookie_need_csrf_header(client):
    name = _make_user("cashier", "1234")
    client.post("/api/v1/cafe/login", json={"username": name, "pin": "1234"})
    body = {"orderType": "quick", "items": []}
    assert client.post("/api/v1/cafe/orders", json=body).status_code == 403
    assert client.post("/api/v1/cafe/orders", json=body, headers=CSRF).status_code != 403


def test_kiosk_token_version_bump_ends_session(client, auth_headers):
    name = _make_user("cashier", "1234")
    token = client.post("/api/v1/cafe/login", json={"username": name, "pin": "1234"}).json()["access_token"]
    uid = deps.user_repo.get_by_username(name).id
    client.patch(f"/api/v1/admin/users/{uid}", json={"password": "4321"}, headers=auth_headers)
    assert client.get("/api/v1/cafe/me", headers={"Authorization": f"Bearer {token}"}).status_code == 401


# ── CORS and headers ───────────────────────────────────────────────────────

def test_cors_allows_credentials_for_known_origin_only(client):
    ok = client.options("/api/v1/admin/me", headers={
        "Origin": ORIGIN, "Access-Control-Request-Method": "GET", "Access-Control-Request-Headers": "x-requested-with"})
    assert ok.status_code == 200
    assert ok.headers["access-control-allow-origin"] == ORIGIN
    assert ok.headers["access-control-allow-credentials"] == "true"
    bad = client.options("/api/v1/admin/me", headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "GET"})
    assert "access-control-allow-origin" not in bad.headers


def test_cors_rejects_unlisted_request_headers(client):
    r = client.options("/api/v1/admin/me", headers={
        "Origin": ORIGIN, "Access-Control-Request-Method": "GET", "Access-Control-Request-Headers": "x-evil"})
    assert r.status_code == 400


def test_security_headers_and_no_store(client):
    h = client.get("/api/v1/venue")
    assert h.headers["x-content-type-options"] == "nosniff" and h.headers["referrer-policy"] == "no-referrer"
    assert "no-store" not in h.headers.get("cache-control", "")
    _admin_login(client)
    assert client.get("/api/v1/admin/me").headers["cache-control"] == "no-store"
    assert client.get("/api/v1/bookings/lookup?ref=X").headers["cache-control"] == "no-store"
