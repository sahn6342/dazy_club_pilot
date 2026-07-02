"""
Shared fixtures. Every test gets clean DB state so tests are order-independent.
Uses a throwaway temp-file SQLite DB — the env var MUST be set before importing
deps/main (engine is built at import time).
"""
import sys
import os
import tempfile

# Ensure app directory on path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Point at a throwaway DB before any app import builds the engine.
_tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_tmp.close()
os.environ["DAZY_DB_URL"] = f"sqlite:///{_tmp.name}"

import pytest
from starlette.testclient import TestClient

import deps
from db import init_db, seed_if_empty
from main import app
from routes.admin.auth import clear_login_attempts
from rate_limit import cashier_login_limiter

# Create schema once before any test runs.
init_db()


def _reset_repos():
    deps.booking_repo.clear()
    deps.enquiry_repo.clear()
    deps.user_repo.clear()
    deps.gallery_repo.clear()
    deps.testimonial_repo.clear()
    deps.cms_repo.clear()
    deps.schedule_repo.clear()  # clear rules + exceptions; seed re-adds default rules
    deps.court_repo.clear()    # clear courts; seed re-adds 3 seeded courts
    deps.customer_repo.clear()
    deps.promo_repo.clear()  # clear promos; seed re-adds WELCOME10 + FLAT100
    deps.booking_payment_repo.clear()
    deps.notification_repo.clear()
    seed_if_empty()  # re-insert gallery/testimonials/cms + venue/courts/rules idempotently
    clear_login_attempts()  # reset admin rate-limit counters so test fixture logins never hit the cap
    cashier_login_limiter.clear()  # same for cashier PIN login


@pytest.fixture(autouse=True)
def reset_state():
    _reset_repos()
    yield


@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def admin_token(client):
    r = client.post("/api/v1/admin/login", json={"username": "admin", "password": "admin"})
    return r.json()["access_token"]


@pytest.fixture()
def auth_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


def pytest_sessionfinish(session, exitstatus):
    try:
        os.unlink(_tmp.name)
    except OSError:
        pass
