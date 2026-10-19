"""Phase 0 hardening regressions: role separation, fail-closed prod config,
late-payment handling, atomic multi-slot create, payment-status expiry and
signed invoice print links."""
import json
import uuid
from datetime import date, datetime, timedelta, timezone

import pytest
from sqlalchemy.exc import IntegrityError

import deps
from auth import create_cashier_token, create_print_token, hash_password
from config_guard import assert_production_config, config_problems
from db import _session
from db_models import BookingRow
from models import BookingRecord, UserRecord


# ── helpers ────────────────────────────────────────────────────────────────

def _tomorrow():
    return (date.today() + timedelta(days=1)).isoformat()


def _slots(client, sport="cricket"):
    r = client.get(f"/api/v1/slots?sport={sport}&date={_tomorrow()}")
    return [s for s in r.json() if s["available"]]


def _book(client, slot, **overrides):
    payload = {
        "name": "Jane Doe", "contact": "9876543210", "slotIds": [slot["id"]],
        "sportSlug": slot["sportSlug"], "date": slot["date"], "startTime": slot["startTime"], "players": 2,
    }
    payload.update(overrides)
    r = client.post("/api/v1/bookings", json=payload)
    assert r.status_code == 201, r.text
    return r.json()


def _backdate(ref, minutes):
    stale = (datetime.now(timezone.utc) - timedelta(minutes=minutes)).isoformat()
    with _session() as s:
        s.query(BookingRow).filter(BookingRow.bookingRef == ref).update({"createdAt": stale})


def _make_user(role, password):
    uname = f"{role}_{uuid.uuid4().hex[:6]}"
    deps.user_repo.create(UserRecord(
        id=str(uuid.uuid4()), username=uname, hashed_password=hash_password(password), role=role,
        createdAt=datetime.now(timezone.utc).isoformat(), createdBy="admin",
    ))
    return uname


def _webhook(client, order_id, payment_id="noop_pay_w"):
    return client.post("/api/v1/payments/razorpay/webhook",
                       content=json.dumps({"providerOrderId": order_id, "providerPaymentId": payment_id}))


def _admin_booking(client, auth_headers, ref):
    items = client.get("/api/v1/admin/bookings", headers=auth_headers).json()["items"]
    return next(b for b in items if b["bookingRef"] == ref)


# ── 1. role separation ─────────────────────────────────────────────────────

@pytest.mark.parametrize("role", ["cashier", "kitchen"])
def test_kiosk_token_rejected_on_admin_routes(client, role):
    uname = _make_user(role, "1234")
    h = {"Authorization": f"Bearer {create_cashier_token(uname, role)}"}
    assert client.get("/api/v1/admin/bookings", headers=h).status_code == 403
    assert client.post("/api/v1/admin/bookings/x/refund", json={}, headers=h).status_code == 403
    assert client.delete("/api/v1/admin/bookings/x", headers=h).status_code == 403


@pytest.mark.parametrize("role", ["cashier", "kitchen"])
def test_kiosk_staff_cannot_login_to_admin(client, role):
    uname = _make_user(role, "1234")
    r = client.post("/api/v1/admin/login", json={"username": uname, "password": "1234"})
    assert r.status_code == 401


def test_kiosk_token_still_works_on_kiosk_routes(client):
    uname = _make_user("cashier", "1234")
    h = {"Authorization": f"Bearer {create_cashier_token(uname, 'cashier')}"}
    assert client.get("/api/v1/cafe/menu", headers=h).status_code == 200


def test_manager_still_has_admin_access(client, auth_headers):
    client.post("/api/v1/admin/users", json={"username": "mgr9", "password": "secure123"}, headers=auth_headers)
    tok = client.post("/api/v1/admin/login", json={"username": "mgr9", "password": "secure123"}).json()["access_token"]
    assert client.get("/api/v1/admin/bookings", headers={"Authorization": f"Bearer {tok}"}).status_code == 200


# ── 2. fail-closed production config ───────────────────────────────────────

_GOOD = {
    "DAZY_ENV": "production", "JWT_SECRET": "x" * 40, "ADMIN_USERNAME": "owner", "ADMIN_PASSWORD": "S3cure-pass!",
    "DAZY_PAYMENT_PROVIDER": "razorpay", "RAZORPAY_WEBHOOK_SECRET": "whsec",
}


def _set_env(monkeypatch, env):
    for k in ("DAZY_ENV", "RENDER", "JWT_SECRET", "ADMIN_USERNAME", "ADMIN_PASSWORD",
              "DAZY_PAYMENT_PROVIDER", "RAZORPAY_WEBHOOK_SECRET"):
        monkeypatch.delenv(k, raising=False)
    for k, v in env.items():
        monkeypatch.setenv(k, v)


def test_prod_guard_passes_with_good_config(monkeypatch):
    _set_env(monkeypatch, _GOOD)
    assert config_problems() == []
    assert_production_config()


@pytest.mark.parametrize("bad", [
    {"JWT_SECRET": "short"},
    {"JWT_SECRET": "dazy-dev-secret-change-in-production"},
    {"JWT_SECRET": "replace-with-a-random-32-plus-character-string"},
    {"ADMIN_PASSWORD": "admin"},
    {"DAZY_PAYMENT_PROVIDER": "noop"},
    {"RAZORPAY_WEBHOOK_SECRET": ""},
])
def test_prod_guard_refuses_unsafe_config(monkeypatch, bad):
    _set_env(monkeypatch, {**_GOOD, **bad})
    with pytest.raises(RuntimeError, match="unsafe production config"):
        assert_production_config()


def test_prod_guard_triggers_on_render_env_and_skips_dev(monkeypatch):
    _set_env(monkeypatch, {"RENDER": "true"})  # defaults everywhere
    with pytest.raises(RuntimeError):
        assert_production_config()
    _set_env(monkeypatch, {})  # dev: nothing set -> no-op
    assert_production_config()


# ── 3. late payment must not resurrect an expired booking ──────────────────

def _expire(client, ref):
    _backdate(ref, 30)
    client.get(f"/api/v1/slots?sport=cricket&date={_tomorrow()}")  # triggers the lazy sweep


def test_webhook_after_expiry_refunds_and_keeps_booking_cancelled(client, auth_headers):
    slot = _slots(client)[0]
    b = _book(client, slot)
    ref, order_id = b["bookingRef"], b["checkout"]["providerOrderId"]
    _expire(client, ref)
    assert _admin_booking(client, auth_headers, ref)["status"] == "cancelled"

    r = _webhook(client, order_id)
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "late_refunded"

    booking = _admin_booking(client, auth_headers, ref)
    assert booking["status"] == "cancelled" and booking["paymentStatus"] == "unpaid"
    pay = deps.booking_payment_repo.get_by_order_id(order_id)
    assert pay.status == "refunded"

    # Redelivery is a no-op, still 200.
    assert _webhook(client, order_id).status_code == 200


def test_late_payment_for_rebooked_slot_does_not_500(client, auth_headers):
    slot = _slots(client)[0]
    b = _book(client, slot)
    _expire(client, b["bookingRef"])
    _book(client, slot, contact="9000000001")  # someone else takes the freed slot

    assert _webhook(client, b["checkout"]["providerOrderId"]).status_code == 200
    # New holder keeps the slot untouched.
    held = [x for x in client.get("/api/v1/admin/bookings", headers=auth_headers).json()["items"]
            if x["contact"] == "9000000001"]
    assert held and held[0]["status"] == "pending"


def test_late_payment_refund_failure_flags_orphan(client, monkeypatch):
    slot = _slots(client)[0]
    b = _book(client, slot)
    _expire(client, b["bookingRef"])
    monkeypatch.setattr(deps.payment_provider, "refund", lambda *a, **k: False)
    import services.payment_confirmation as pc
    monkeypatch.setattr(pc.payment_provider, "refund", lambda *a, **k: False)

    r = _webhook(client, b["checkout"]["providerOrderId"])
    assert r.status_code == 200 and r.json()["status"] == "late_needs_review"
    assert deps.booking_payment_repo.get_by_order_id(b["checkout"]["providerOrderId"]).status == "paid_orphan"


def test_verify_callback_after_expiry_returns_409(client):
    slot = _slots(client)[0]
    b = _book(client, slot)
    _expire(client, b["bookingRef"])
    r = client.post(f"/api/v1/bookings/{b['bookingRef']}/payment/verify", json={
        "providerOrderId": b["checkout"]["providerOrderId"], "providerPaymentId": "noop_pay_late"})
    assert r.status_code == 409


def test_admin_confirmed_then_paid_is_marked_paid_not_refunded(client, auth_headers):
    slot = _slots(client)[0]
    b = _book(client, slot)
    ref = b["bookingRef"]
    bid = _admin_booking(client, auth_headers, ref)["id"]
    client.patch(f"/api/v1/admin/bookings/{bid}", json={"status": "confirmed"}, headers=auth_headers)

    assert _webhook(client, b["checkout"]["providerOrderId"]).json()["status"] == "ok"
    booking = _admin_booking(client, auth_headers, ref)
    assert booking["status"] == "confirmed" and booking["paymentStatus"] == "paid"


def test_normal_payment_still_confirms(client, auth_headers):
    slot = _slots(client)[0]
    b = _book(client, slot)
    assert _webhook(client, b["checkout"]["providerOrderId"]).json()["status"] == "ok"
    booking = _admin_booking(client, auth_headers, b["bookingRef"])
    assert booking["status"] == "confirmed" and booking["paymentStatus"] == "paid"


# ── 4. atomic multi-slot create ────────────────────────────────────────────

def _record(slot, ref, primary):
    return BookingRecord(
        id=str(uuid.uuid4()), bookingRef=ref, customer_id=None, court_id=slot["courtId"], slotId=slot["id"],
        name="X", contact="9111111111", sportSlug=slot["sportSlug"], date=slot["date"],
        startTime=slot["startTime"], endTime=slot["endTime"], party_size=1, status="pending",
        createdAt=datetime.now(timezone.utc).isoformat(), is_primary=primary,
    )


def test_create_many_rolls_back_all_rows_on_conflict(client):
    s = _slots(client)
    a, taken = s[0], s[1]
    deps.booking_repo.create(_record(taken, "TAKEN001", True))
    with pytest.raises(IntegrityError):
        deps.booking_repo.create_many([_record(a, "MULTI001", True), _record(taken, "MULTI001", False)])
    assert deps.booking_repo.get_by_ref("MULTI001") == []


# ── 5. payment rows flip created -> expired ────────────────────────────────

def test_sweep_marks_payment_expired(client):
    slot = _slots(client)[0]
    b = _book(client, slot)
    assert deps.booking_payment_repo.get_by_ref(b["bookingRef"]).status == "created"
    _expire(client, b["bookingRef"])
    assert deps.booking_payment_repo.get_by_ref(b["bookingRef"]).status == "expired"


# ── 6. invoice print requires a signed link ────────────────────────────────

def _invoice(client, auth_headers):
    uname = _make_user("cashier", "1234")
    h = {"Authorization": f"Bearer {create_cashier_token(uname, 'cashier')}"}
    cat = client.post("/api/v1/admin/cafe/categories", json={"name": f"C{uuid.uuid4().hex[:5]}", "kind": "food"},
                      headers=auth_headers).json()["id"]
    item = client.post("/api/v1/admin/cafe/items", json={
        "category_id": cat, "name": "<b>Tea</b>", "price": 50.0, "taxRatePercent": 5.0}, headers=auth_headers).json()
    order = client.post("/api/v1/cafe/orders", json={"orderType": "quick", "items": [
        {"menu_item_id": item["id"], "qty": 1}]}, headers=h).json()
    inv = client.post(f"/api/v1/cafe/orders/{order['id']}/invoice", json={}, headers=h).json()
    return inv["id"], h


def test_print_requires_signed_link(client, auth_headers):
    inv_id, h = _invoice(client, auth_headers)
    assert client.get(f"/api/v1/cafe/invoices/{inv_id}/print").status_code == 401
    assert client.get(f"/api/v1/cafe/invoices/{inv_id}/print", headers=h).status_code == 401  # Bearer alone isn't enough
    assert client.get(f"/api/v1/cafe/invoices/{inv_id}/print?t=garbage").status_code == 401
    other = create_print_token("some-other-invoice")
    assert client.get(f"/api/v1/cafe/invoices/{inv_id}/print?t={other}").status_code == 403


def test_print_link_flow_and_escaping(client, auth_headers):
    inv_id, h = _invoice(client, auth_headers)
    link = client.post(f"/api/v1/cafe/invoices/{inv_id}/print-link", headers=h)
    assert link.status_code == 200
    page = client.get(link.json()["url"])
    assert page.status_code == 200
    assert "&lt;b&gt;Tea&lt;/b&gt;" in page.text and "<b>Tea</b>" not in page.text


def test_print_link_requires_kiosk_auth_and_print_token_is_not_a_login(client, auth_headers):
    inv_id, _ = _invoice(client, auth_headers)
    assert client.post(f"/api/v1/cafe/invoices/{inv_id}/print-link").status_code in (401, 403)
    tok = create_print_token(inv_id)
    h = {"Authorization": f"Bearer {tok}"}
    assert client.get("/api/v1/admin/bookings", headers=h).status_code == 403
    assert client.get("/api/v1/cafe/menu", headers=h).status_code == 403


# ── 7. admin password hash, noop blocked in production, real boot refusal ──

def test_admin_login_with_password_hash(client, monkeypatch):
    monkeypatch.setenv("ADMIN_PASSWORD_HASH", hash_password("Correct-Horse-9"))
    monkeypatch.setenv("ADMIN_PASSWORD", "ignored-when-hash-set")
    ok = client.post("/api/v1/admin/login", json={"username": "admin", "password": "Correct-Horse-9"})
    assert ok.status_code == 200
    for bad in ("ignored-when-hash-set", "admin", "wrong"):
        assert client.post("/api/v1/admin/login", json={"username": "admin", "password": bad}).status_code == 401


def test_prod_guard_accepts_hash_without_plain_password(monkeypatch):
    _set_env(monkeypatch, {**_GOOD, "ADMIN_PASSWORD_HASH": hash_password("Correct-Horse-9")})
    monkeypatch.delenv("ADMIN_PASSWORD", raising=False)
    assert config_problems() == []


def test_prod_guard_rejects_non_bcrypt_hash(monkeypatch):
    _set_env(monkeypatch, {**_GOOD, "ADMIN_PASSWORD_HASH": "plaintext-not-a-hash"})
    assert any("bcrypt" in p for p in config_problems())


def test_noop_provider_cannot_be_built_in_production(monkeypatch):
    from integrations.payments.factory import get_payment_provider
    _set_env(monkeypatch, {"RENDER": "true", "DAZY_PAYMENT_PROVIDER": "noop"})
    with pytest.raises(RuntimeError, match="unsafe production config"):
        get_payment_provider()
    _set_env(monkeypatch, {"DAZY_PAYMENT_PROVIDER": "noop"})  # dev/test still fine
    assert get_payment_provider().name == "noop"


def test_real_process_refuses_to_boot_with_unsafe_prod_config(tmp_path):
    import os
    import subprocess
    import sys
    env = {k: v for k, v in os.environ.items()
           if k not in ("JWT_SECRET", "ADMIN_USERNAME", "ADMIN_PASSWORD", "ADMIN_PASSWORD_HASH",
                        "DAZY_PAYMENT_PROVIDER", "RAZORPAY_KEY_ID", "RAZORPAY_KEY_SECRET", "RAZORPAY_WEBHOOK_SECRET")}
    env.update({"DAZY_ENV": "production", "DAZY_DB_URL": f"sqlite:///{tmp_path / 'boot.db'}"})
    api_dir = os.path.join(os.path.dirname(__file__), "..")
    code = ("from starlette.testclient import TestClient\nimport main\n"
            "with TestClient(main.app):\n    pass\nprint('BOOTED')")
    r = subprocess.run([sys.executable, "-c", code], cwd=api_dir, env=env, capture_output=True, text=True, timeout=60)
    assert r.returncode != 0 and "BOOTED" not in r.stdout
    assert "unsafe production config" in r.stderr
