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


def test_cafe_login_rate_limited_after_threshold(client):
    uname = f"cashier_{uuid.uuid4().hex[:6]}"
    user_repo.create(UserRecord(
        id=str(uuid.uuid4()), username=uname,
        hashed_password=hash_password("1234"), role="cashier",
        createdAt=datetime.now(timezone.utc).isoformat(), createdBy="admin",
    ))
    for _ in range(10):
        r = client.post("/api/v1/cafe/login", json={"username": uname, "pin": "0000"})
        assert r.status_code == 401
    r = client.post("/api/v1/cafe/login", json={"username": uname, "pin": "0000"})
    assert r.status_code == 429


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
