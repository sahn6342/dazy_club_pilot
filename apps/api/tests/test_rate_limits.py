"""Login rate limiting: admin password login and cashier PIN login are both
throttled per-IP (10 attempts / 60s window) so brute-forcing a 4-digit PIN
or an admin password is infeasible."""
import uuid

from deps import user_repo
from models import UserRecord
from auth import hash_password
from datetime import datetime, timezone


def test_admin_login_rate_limited_after_threshold(client):
    for _ in range(10):
        r = client.post("/api/v1/admin/login", json={"username": "admin", "password": "wrong"})
        assert r.status_code == 401
    r = client.post("/api/v1/admin/login", json={"username": "admin", "password": "wrong"})
    assert r.status_code == 429


def _cashier(pin="1234"):
    uname = f"cashier_{uuid.uuid4().hex[:6]}"
    user_repo.create(UserRecord(
        id=str(uuid.uuid4()), username=uname,
        hashed_password=hash_password(pin), role="cashier",
        createdAt=datetime.now(timezone.utc).isoformat(), createdBy="admin",
    ))
    return uname


def test_cafe_login_rate_limited_per_ip_after_threshold(client):
    """10 attempts/min per IP, even spread across different usernames."""
    for _ in range(10):
        r = client.post("/api/v1/cafe/login", json={"username": _cashier(), "pin": "0000"})
        assert r.status_code == 401
    r = client.post("/api/v1/cafe/login", json={"username": _cashier(), "pin": "0000"})
    assert r.status_code == 429


def test_cafe_pin_locks_account_after_five_failures(client):
    uname = _cashier("1234")
    for _ in range(5):
        assert client.post("/api/v1/cafe/login", json={"username": uname, "pin": "0000"}).status_code == 401
    # Locked: even the CORRECT pin is refused until the window passes.
    r = client.post("/api/v1/cafe/login", json={"username": uname, "pin": "1234"})
    assert r.status_code == 429
    # Another account is unaffected.
    assert client.post("/api/v1/cafe/login", json={"username": _cashier("4321"), "pin": "4321"}).status_code == 200


def test_cafe_pin_success_clears_failure_counter(client):
    uname = _cashier("1234")
    for _ in range(4):
        client.post("/api/v1/cafe/login", json={"username": uname, "pin": "0000"})
    assert client.post("/api/v1/cafe/login", json={"username": uname, "pin": "1234"}).status_code == 200
    for _ in range(4):  # counter was reset, so 4 more failures still don't lock
        assert client.post("/api/v1/cafe/login", json={"username": uname, "pin": "0000"}).status_code == 401


def test_cafe_login_rate_limit_independent_of_admin(client):
    """Hitting the admin limiter doesn't spuriously trip the cafe limiter."""
    for _ in range(10):
        client.post("/api/v1/admin/login", json={"username": "admin", "password": "wrong"})
    uname = f"cashier_{uuid.uuid4().hex[:6]}"
    user_repo.create(UserRecord(
        id=str(uuid.uuid4()), username=uname,
        hashed_password=hash_password("1234"), role="cashier",
        createdAt=datetime.now(timezone.utc).isoformat(), createdBy="admin",
    ))
    r = client.post("/api/v1/cafe/login", json={"username": uname, "pin": "1234"})
    assert r.status_code == 200


# ── client IP resolution & DB-backed state ────────────────────────────────

def test_client_ip_ignores_forged_xff_prefix(monkeypatch):
    from starlette.requests import Request
    from rate_limit import client_ip

    def req(xff):
        return Request({"type": "http", "headers": [(b"x-forwarded-for", xff.encode())] if xff else [],
                        "client": ("10.0.0.9", 1234)})

    monkeypatch.setenv("DAZY_PROXY_HOPS", "1")
    assert client_ip(req("6.6.6.6, 1.2.3.4")) == "1.2.3.4"  # forged leftmost entry ignored
    assert client_ip(req("")) == "10.0.0.9"
    monkeypatch.setenv("DAZY_PROXY_HOPS", "2")
    assert client_ip(req("6.6.6.6, 1.2.3.4, 10.1.1.1")) == "1.2.3.4"
    monkeypatch.setenv("DAZY_PROXY_HOPS", "0")
    assert client_ip(req("6.6.6.6")) == "10.0.0.9"


def test_limiter_state_is_persisted_in_db():
    from rate_limit import SlidingWindowLimiter
    a = SlidingWindowLimiter("persist_test", 2, 60)
    a.check("k"); a.check("k")
    b = SlidingWindowLimiter("persist_test", 2, 60)  # a fresh instance == a restarted process
    with __import__("pytest").raises(Exception) as ei:
        b.check("k")
    assert getattr(ei.value, "status_code", None) == 429
    a.clear()


def test_booking_create_is_rate_limited_per_ip(client):
    import json as _json
    body = {"name": "X", "contact": "9000000000", "slotIds": ["nope"], "sportSlug": "cricket",
            "date": "2099-01-01", "startTime": "06:00", "players": 1}
    codes = [client.post("/api/v1/bookings", content=_json.dumps({**body, "contact": f"90000000{i:02d}"}),
                         headers={"Content-Type": "application/json"}).status_code for i in range(11)]
    assert codes[:10] == [404] * 10 and codes[10] == 429


def test_enquiry_is_rate_limited(client):
    p = {"name": "A B", "contact": "9000000001", "message": "hello there"}
    codes = [client.post("/api/v1/contact-enquiries", json=p).status_code for _ in range(6)]
    assert codes.count(429) >= 1
