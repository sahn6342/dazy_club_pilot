"""Workstream C: audit trail — explicit events, middleware fallback, access control, filters."""
import json
import uuid
from datetime import date, datetime, timedelta, timezone

import pytest

import deps
from audit import audit, normalise_path
from auth import create_cashier_token, hash_password
from models import UserRecord


def _rows(**filters):
    items, total = deps.audit_repo.query(limit=200, **filters)
    return items, total


def _by_action(action):
    return [r for r in _rows()[0] if r.action == action]


def _tomorrow():
    return (date.today() + timedelta(days=1)).isoformat()


def _book(client, contact="9876543210"):
    slot = [s for s in client.get(f"/api/v1/slots?sport=cricket&date={_tomorrow()}").json() if s["available"]][0]
    r = client.post("/api/v1/bookings", json={
        "name": "Jane", "contact": contact, "slotIds": [slot["id"]], "sportSlug": "cricket",
        "date": slot["date"], "startTime": slot["startTime"], "players": 1})
    assert r.status_code == 201, r.text
    return r.json()


def _admin_booking(client, auth_headers, ref):
    items = client.get("/api/v1/admin/bookings?limit=100", headers=auth_headers).json()["items"]
    return next(b for b in items if b["bookingRef"] == ref)


def _make_user(role, secret):
    name = f"{role}_{uuid.uuid4().hex[:6]}"
    deps.user_repo.create(UserRecord(
        id=str(uuid.uuid4()), username=name, hashed_password=hash_password(secret), role=role,
        createdAt=datetime.now(timezone.utc).isoformat(), createdBy="admin"))
    return name


# ── logins ─────────────────────────────────────────────────────────────────

def test_admin_login_success_and_failure_are_recorded(client):
    client.post("/api/v1/admin/login", json={"username": "admin", "password": "admin"})
    client.post("/api/v1/admin/login", json={"username": "admin", "password": "hunter2-wrong"})
    ok, = _by_action("auth.login")
    bad, = _by_action("auth.login_failed")
    assert ok.actor == "admin" and ok.actorRole == "admin" and ok.ip
    assert bad.actor == "admin" and bad.detail is None
    # No row anywhere holds the attempted password.
    assert all("hunter2" not in json.dumps(r.model_dump()) for r in _rows()[0])


def test_unknown_username_failure_is_recorded_with_that_name(client):
    client.post("/api/v1/admin/login", json={"username": "mallory", "password": "x" * 8})
    row, = _by_action("auth.login_failed")
    assert row.actor == "mallory" and row.entityType == "user"


def test_logout_is_recorded(client):
    token = client.post("/api/v1/admin/login", json={"username": "admin", "password": "admin"}).json()["access_token"]
    client.post("/api/v1/admin/logout", headers={"Authorization": f"Bearer {token}"})
    row, = _by_action("auth.logout")
    assert row.actor == "admin"
    client.post("/api/v1/admin/logout")  # no session: nothing to record
    assert len(_by_action("auth.logout")) == 1


def test_kiosk_login_failure_and_lockout_are_recorded(client):
    name = _make_user("cashier", "1234")
    for _ in range(5):
        client.post("/api/v1/cafe/login", json={"username": name, "pin": "0000"})
    client.post("/api/v1/cafe/login", json={"username": name, "pin": "1234"})  # locked out
    assert len(_by_action("kiosk.login_failed")) == 5
    assert len(_by_action("kiosk.lockout")) == 1 and _by_action("kiosk.lockout")[0].actor == name
    assert _by_action("kiosk.login") == []


def test_kiosk_login_success_recorded(client):
    name = _make_user("cashier", "1234")
    client.post("/api/v1/cafe/login", json={"username": name, "pin": "1234"})
    row, = _by_action("kiosk.login")
    assert row.actor == name and row.actorRole == "cashier"


# ── bookings ───────────────────────────────────────────────────────────────

def test_status_change_records_from_and_to(client, auth_headers):
    b = _book(client)
    bid = _admin_booking(client, auth_headers, b["bookingRef"])["id"]
    assert client.patch(f"/api/v1/admin/bookings/{bid}", json={"status": "confirmed"}, headers=auth_headers).status_code == 200
    row, = _by_action("booking.status_change")
    assert row.actor == "admin" and row.entityId == bid
    assert json.loads(row.detail) == {"bookingRef": b["bookingRef"], "from": "pending", "to": "confirmed"}


def test_invalid_transition_is_not_recorded(client, auth_headers):
    b = _book(client)
    bid = _admin_booking(client, auth_headers, b["bookingRef"])["id"]
    assert client.patch(f"/api/v1/admin/bookings/{bid}", json={"status": "completed"}, headers=auth_headers).status_code == 409
    assert _by_action("booking.status_change") == []


def test_refund_is_recorded_with_amount(client, auth_headers):
    b = _book(client)
    client.post(f"/api/v1/bookings/{b['bookingRef']}/payment/verify", json={
        "providerOrderId": b["checkout"]["providerOrderId"], "providerPaymentId": "noop_pay_audit"})
    bid = _admin_booking(client, auth_headers, b["bookingRef"])["id"]
    assert client.post(f"/api/v1/admin/bookings/{bid}/refund", json={}, headers=auth_headers).status_code == 200
    row, = _by_action("booking.refund")
    detail = json.loads(row.detail)
    assert detail["bookingRef"] == b["bookingRef"] and detail["amount"] == b["price"]


def test_failed_refund_is_recorded(client, auth_headers, monkeypatch):
    b = _book(client)
    client.post(f"/api/v1/bookings/{b['bookingRef']}/payment/verify", json={
        "providerOrderId": b["checkout"]["providerOrderId"], "providerPaymentId": "noop_pay_audit"})
    bid = _admin_booking(client, auth_headers, b["bookingRef"])["id"]
    import routes.admin.bookings as rb
    monkeypatch.setattr(rb.payment_provider, "refund", lambda *a, **k: False)
    assert client.post(f"/api/v1/admin/bookings/{bid}/refund", json={}, headers=auth_headers).status_code == 502
    assert len(_by_action("booking.refund_failed")) == 1 and _by_action("booking.refund") == []


def test_booking_delete_records_what_was_deleted(client, auth_headers):
    b = _book(client)
    bid = _admin_booking(client, auth_headers, b["bookingRef"])["id"]
    assert client.delete(f"/api/v1/admin/bookings/{bid}", headers=auth_headers).status_code == 204
    row, = _by_action("booking.delete")
    d = json.loads(row.detail)
    assert d["bookingRef"] == b["bookingRef"] and d["status"] == "pending" and d["price"] == b["price"]


# ── users ──────────────────────────────────────────────────────────────────

def test_user_lifecycle_is_recorded_without_secrets(client, auth_headers):
    created = client.post("/api/v1/admin/users", json={"username": "mgr_audit", "password": "SuperSecret99"}, headers=auth_headers).json()
    client.patch(f"/api/v1/admin/users/{created['id']}", json={"password": "EvenMoreSecret1"}, headers=auth_headers)
    client.patch(f"/api/v1/admin/users/{created['id']}", json={"role": "cashier", "password": "4321"}, headers=auth_headers)
    client.delete(f"/api/v1/admin/users/{created['id']}", headers=auth_headers)

    assert json.loads(_by_action("user.create")[0].detail) == {"username": "mgr_audit", "role": "manager"}
    updates = sorted(_by_action("user.update"), key=lambda r: r.at)
    assert json.loads(updates[0].detail) == {"username": "mgr_audit", "passwordChanged": True, "role": None}
    assert json.loads(updates[1].detail)["role"] == {"from": "manager", "to": "cashier"}
    assert json.loads(_by_action("user.delete")[0].detail) == {"username": "mgr_audit", "role": "cashier"}
    blob = json.dumps([r.model_dump() for r in _rows()[0]])
    assert "SuperSecret99" not in blob and "EvenMoreSecret1" not in blob and "4321" not in blob


# ── payment anomalies ──────────────────────────────────────────────────────

def test_late_payment_refund_is_recorded_as_system_event(client):
    import json as _json
    from datetime import timezone as tz
    from db import _session
    from db_models import BookingRow
    b = _book(client)
    old = (datetime.now(tz.utc) - timedelta(minutes=30)).isoformat()
    with _session() as s:
        s.query(BookingRow).filter(BookingRow.bookingRef == b["bookingRef"]).update({"createdAt": old})
    client.get(f"/api/v1/slots?sport=cricket&date={_tomorrow()}")  # sweep -> cancelled
    r = client.post("/api/v1/payments/razorpay/webhook", content=_json.dumps({
        "providerOrderId": b["checkout"]["providerOrderId"], "providerPaymentId": "noop_pay_late"}))
    assert r.status_code == 200
    row, = _by_action("payment.late_refunded")
    assert row.actor == "system" and row.entityId == b["bookingRef"]
    assert json.loads(row.detail)["providerPaymentId"] == "noop_pay_late"


def test_amount_mismatch_is_recorded(client, monkeypatch):
    import routes.payments as rp
    from integrations.payments.base import PaymentVerification
    b = _book(client)

    class _P:
        def verify_webhook(self, raw, sig):
            return PaymentVerification(True, "pay_x", amount=1.0), b["checkout"]["providerOrderId"]

    monkeypatch.setattr(rp, "payment_provider", _P())
    client.post("/api/v1/payments/razorpay/webhook", content=b"{}")
    row, = _by_action("payment.amount_mismatch")
    assert json.loads(row.detail) == {"bookingRef": b["bookingRef"], "expected": b["price"], "captured": 1.0}


# ── middleware fallback ────────────────────────────────────────────────────

def test_other_admin_writes_are_recorded_by_the_fallback(client, auth_headers):
    r = client.post("/api/v1/admin/promos", json={"code": "AUDIT5", "kind": "percent", "value": 5, "active": True}, headers=auth_headers)
    assert r.status_code == 201
    promo_id = r.json()["id"]
    client.delete(f"/api/v1/admin/promos/{promo_id}", headers=auth_headers)
    created, = _by_action("POST /admin/promos")
    assert created.actor == "admin" and created.actorRole == "admin" and created.entityType == "promos"
    deleted, = _by_action("DELETE /admin/promos/{id}")
    assert deleted.entityId == promo_id


def test_keyed_resource_records_its_key(client, auth_headers):
    client.put("/api/v1/admin/cms/booking_gst_rate", json={"value": "12"}, headers=auth_headers)
    row, = _by_action("PUT /admin/cms/booking_gst_rate")
    assert row.entityType == "cms" and row.entityId == "booking_gst_rate"


def test_explicit_events_are_not_logged_twice(client, auth_headers):
    b = _book(client)
    bid = _admin_booking(client, auth_headers, b["bookingRef"])["id"]
    client.patch(f"/api/v1/admin/bookings/{bid}", json={"status": "confirmed"}, headers=auth_headers)
    assert [r.action for r in _rows()[0] if "bookings" in r.action or r.action.startswith("booking")] == ["booking.status_change"]


def test_reads_and_failed_writes_are_not_recorded(client, auth_headers):
    deps.audit_repo.clear()  # drop the fixture's own login event
    client.get("/api/v1/admin/bookings", headers=auth_headers)
    client.delete("/api/v1/admin/bookings/does-not-exist", headers=auth_headers)  # 404
    client.post("/api/v1/admin/promos", json={"nonsense": True}, headers=auth_headers)  # 422
    assert _rows()[0] == []


def test_bearer_and_cookie_writes_both_attribute_the_actor(client):
    client.post("/api/v1/admin/login", json={"username": "admin", "password": "admin"})  # cookie in the jar
    client.post("/api/v1/admin/promos", json={"code": "CK1", "kind": "percent", "value": 5, "active": True},
                headers={"X-Requested-With": "dazy"})
    row, = _by_action("POST /admin/promos")
    assert row.actor == "admin"


def test_audit_failure_never_breaks_the_request(client, auth_headers, monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("audit db down")
    monkeypatch.setattr(deps.audit_repo, "record", boom)
    r = client.post("/api/v1/admin/promos", json={"code": "SAFE1", "kind": "percent", "value": 5, "active": True}, headers=auth_headers)
    assert r.status_code == 201


def test_long_detail_is_truncated():
    audit("test.long", "tester", detail={"blob": "x" * 5000})
    row, = _by_action("test.long")
    assert len(row.detail) <= 2000


@pytest.mark.parametrize("path,expected", [
    ("/api/v1/admin/promos", ("/admin/promos", "promos", None)),
    ("/api/v1/admin/promos/0f8fad5b-d9cb-469f-a165-70867728950e", ("/admin/promos/{id}", "promos", "0f8fad5b-d9cb-469f-a165-70867728950e")),
    ("/api/v1/admin/cms/booking_gst_rate", ("/admin/cms/booking_gst_rate", "cms", "booking_gst_rate")),
    ("/api/v1/admin/schedule/rules/42", ("/admin/schedule/rules/{id}", "schedule", "42")),
])
def test_normalise_path(path, expected):
    assert normalise_path(path) == expected


# ── reading the log ────────────────────────────────────────────────────────

def _seed(client):
    deps.audit_repo.clear()  # the auth_headers fixture logs in, which is itself audited
    audit("a.one", "alice", entity_type="thing", entity_id="1")
    audit("a.two", "bob", entity_type="thing", entity_id="2")
    audit("b.three", "alice", entity_type="other", entity_id="3")


def test_audit_endpoint_is_superadmin_only(client, auth_headers):
    client.cookies.clear()  # the fixture login left a session cookie in the jar
    assert client.get("/api/v1/admin/audit").status_code == 401
    client.post("/api/v1/admin/users", json={"username": "mgr_x", "password": "password123"}, headers=auth_headers)
    tok = client.post("/api/v1/admin/login", json={"username": "mgr_x", "password": "password123"}).json()["access_token"]
    assert client.get("/api/v1/admin/audit", headers={"Authorization": f"Bearer {tok}"}).status_code == 403
    cashier = _make_user("cashier", "1234")
    assert client.get("/api/v1/admin/audit", headers={"Authorization": f"Bearer {create_cashier_token(cashier, 'cashier')}"}).status_code == 403
    assert client.get("/api/v1/admin/audit", headers=auth_headers).status_code == 200


def test_audit_filters_and_pagination(client, auth_headers):
    _seed(client)
    get = lambda q="": client.get(f"/api/v1/admin/audit?{q}", headers=auth_headers).json()  # noqa: E731
    assert get()["total"] == 3
    assert [i["action"] for i in get("actor=alice")["items"]] == ["b.three", "a.one"]  # newest first
    assert get("action=a.")["total"] == 2 and get("action=THREE")["total"] == 1  # substring, case-insensitive
    assert get("entityType=other")["total"] == 1 and get("entityId=2")["items"][0]["actor"] == "bob"
    page = get("limit=2&offset=0")
    assert len(page["items"]) == 2 and page["total"] == 3
    assert len(get("limit=2&offset=2")["items"]) == 1


def test_audit_date_filters_are_inclusive(client, auth_headers):
    _seed(client)
    today = datetime.now(timezone.utc).date().isoformat()
    yesterday = (datetime.now(timezone.utc).date() - timedelta(days=1)).isoformat()
    tomorrow = _tomorrow()
    get = lambda q: client.get(f"/api/v1/admin/audit?{q}", headers=auth_headers).json()["total"]  # noqa: E731
    assert get(f"dateFrom={today}&dateTo={today}") == 3
    assert get(f"dateFrom={tomorrow}") == 0 and get(f"dateTo={yesterday}") == 0
    assert client.get("/api/v1/admin/audit?dateFrom=nope", headers=auth_headers).status_code == 422


# ── customers upsert race (found while reading test logs) ──────────────────

def test_customer_upsert_survives_losing_the_unique_phone_race(monkeypatch):
    from sqlalchemy.exc import IntegrityError
    repo = deps.customer_repo
    real = repo._upsert
    calls = {"n": 0}

    def flaky(name, contact, email):
        calls["n"] += 1
        if calls["n"] == 1:
            real(name, contact, email)  # the "other" request wins and commits first ...
            raise IntegrityError("INSERT", {}, Exception("UNIQUE constraint failed: customers.phone"))  # ... we lose
        return real(name, contact, email)

    monkeypatch.setattr(repo, "_upsert", flaky)
    rec = repo.upsert_by_contact("Racer", "9555000111")
    assert rec.phone == "9555000111" and calls["n"] == 2
    assert len([c for c in repo.get_all() if c.phone == "9555000111"]) == 1
