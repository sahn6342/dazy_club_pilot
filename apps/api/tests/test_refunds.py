"""Workstream D: tiered refund policy, partial refunds, cancel-and-refund."""
import json
import uuid
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest

import deps
import services.refund_policy as rp
from auth import create_cashier_token, hash_password
from models import UserRecord
from services.refund_policy import (
    DEFAULT_TIERS, PolicyError, build_quote, hours_until_start, load_tiers, parse_policy, percent_for_notice,
)

IST = ZoneInfo("Asia/Kolkata")


# ── policy parsing and maths (pure) ────────────────────────────────────────

def test_parse_policy_sorts_largest_notice_first():
    tiers = parse_policy('{"tiers": [{"hoursBefore": 4, "percent": 50}, {"hoursBefore": 24, "percent": 100}]}')
    assert tiers == [(24.0, 100.0), (4.0, 50.0)]


@pytest.mark.parametrize("raw", [
    "not json", "[]", "{}", '{"tiers": []}', '{"tiers": "x"}', '{"tiers": [5]}',
    '{"tiers": [{"hoursBefore": "24", "percent": 100}]}',
    '{"tiers": [{"hoursBefore": 24, "percent": 101}]}',
    '{"tiers": [{"hoursBefore": 24, "percent": -1}]}',
    '{"tiers": [{"hoursBefore": -1, "percent": 50}]}',
    '{"tiers": [{"hoursBefore": 99999, "percent": 50}]}',
    '{"tiers": [{"hoursBefore": 24, "percent": 100}, {"hoursBefore": 24, "percent": 50}]}',
    '{"tiers": [{"hoursBefore": true, "percent": 100}]}',
    None,
])
def test_parse_policy_rejects_bad_input(raw):
    with pytest.raises(PolicyError):
        parse_policy(raw)


@pytest.mark.parametrize("hours,expected", [
    (72, 100), (24.0, 100), (23.99, 50), (10, 50), (4.0, 50), (3.99, 0), (0.5, 0), (0, 0), (-3, 0),
])
def test_percent_for_notice_boundaries(hours, expected):
    assert percent_for_notice(hours, list(DEFAULT_TIERS)) == expected


def test_percent_with_a_single_tier_and_a_zero_hour_tier():
    assert percent_for_notice(1, [(2.0, 90.0)]) == 0
    assert percent_for_notice(2, [(2.0, 90.0)]) == 90
    assert percent_for_notice(0.0, [(0.0, 25.0)]) == 25 and percent_for_notice(-0.01, [(0.0, 25.0)]) == 0


def test_hours_until_start_uses_the_venue_timezone():
    now = datetime(2026, 10, 20, 0, 30, tzinfo=timezone.utc)  # == 06:00 IST on 2026-10-20
    assert hours_until_start("2026-10-20", "06:00", IST, now) == 0
    assert hours_until_start("2026-10-21", "06:00", IST, now) == 24
    assert hours_until_start("2026-10-20", "05:00", IST, now) == -1  # already started


def test_quote_rounds_half_up_and_caps_at_the_remaining_balance():
    q = build_quote(1017.50, 0, 30, list(DEFAULT_TIERS))
    assert (q.percent, q.policyAmount, q.suggestedAmount, q.remaining) == (100, 1017.50, 1017.50, 1017.50)
    q = build_quote(1.01, 0, 10, list(DEFAULT_TIERS))
    assert q.policyAmount == 0.51  # 0.505 rounds half up, never banker's rounding
    q = build_quote(1200, 800, 30, list(DEFAULT_TIERS))  # 800 already refunded
    assert q.policyAmount == 1200 and q.remaining == 400 and q.suggestedAmount == 400


def test_load_tiers_uses_cms_and_falls_back_when_broken():
    assert load_tiers() == [(24.0, 100.0), (4.0, 50.0)]  # seeded default
    deps.cms_repo.update("refund_policy", {"value": '{"tiers": [{"hoursBefore": 1, "percent": 80}]}'})
    assert load_tiers() == [(1.0, 80.0)]
    deps.cms_repo.update("refund_policy", {"value": "{broken"})  # bypasses the route validation
    assert load_tiers() == list(DEFAULT_TIERS)
    deps.cms_repo.delete("refund_policy")
    assert load_tiers() == list(DEFAULT_TIERS)


# ── helpers for endpoint tests ─────────────────────────────────────────────

def _tomorrow():
    return (date.today() + timedelta(days=1)).isoformat()


def _book(client, contact="9876543210", email=None, slot_index=0, **extra):
    slots = [s for s in client.get(f"/api/v1/slots?sport=cricket&date={_tomorrow()}").json() if s["available"]]
    slot = slots[slot_index]
    body = {"name": "Jane", "contact": contact, "slotIds": [slot["id"]], "sportSlug": "cricket",
            "date": slot["date"], "startTime": slot["startTime"], "players": 1, **extra}
    if email:
        body["email"] = email
    r = client.post("/api/v1/bookings", json=body)
    assert r.status_code == 201, r.text
    return r.json()


def _pay(client, b):
    r = client.post(f"/api/v1/bookings/{b['bookingRef']}/payment/verify", json={
        "providerOrderId": b["checkout"]["providerOrderId"], "providerPaymentId": f"noop_pay_{uuid.uuid4().hex[:8]}"})
    assert r.status_code == 200, r.text


def _admin_booking(client, auth_headers, ref):
    items = client.get("/api/v1/admin/bookings?limit=100", headers=auth_headers).json()["items"]
    return next(x for x in items if x["bookingRef"] == ref)


@pytest.fixture
def paid(client, auth_headers):
    """A confirmed, paid cricket booking (price 1200) and its admin-side record."""
    b = _book(client)
    _pay(client, b)
    return b, _admin_booking(client, auth_headers, b["bookingRef"])


def _hours_before(monkeypatch, admin_booking, hours):
    """Freeze 'now' at `hours` before the booking's first slot starts (venue time)."""
    start = datetime.fromisoformat(f"{admin_booking['date']}T{admin_booking['startTime']}:00").replace(tzinfo=IST)
    fixed = (start - timedelta(hours=hours)).astimezone(timezone.utc)
    monkeypatch.setattr(rp, "_now", lambda: fixed)


def _payment(ref):
    return deps.booking_payment_repo.get_by_ref(ref)


def _slot_available(client, admin_booking):
    slots = client.get(f"/api/v1/slots?sport={admin_booking['sportSlug']}&date={admin_booking['date']}").json()
    return next(s for s in slots if s["id"] == admin_booking["slotId"])["available"]


class _Refunds:
    """Records provider refund calls (the noop provider otherwise just returns True)."""
    def __init__(self, monkeypatch, result=True, raises=False):
        self.calls = []
        self.result, self.raises = result, raises
        monkeypatch.setattr(deps.payment_provider, "refund", self)

    def __call__(self, payment_id, amount):
        self.calls.append((payment_id, amount))
        if self.raises:
            raise RuntimeError("gateway exploded")
        return self.result


def _quote(client, auth_headers, bid):
    r = client.get(f"/api/v1/admin/bookings/{bid}/refund-quote", headers=auth_headers)
    assert r.status_code == 200, r.text
    return r.json()


def _cr(client, auth_headers, bid, **body):
    return client.post(f"/api/v1/admin/bookings/{bid}/cancel-and-refund", json=body, headers=auth_headers)


# ── quote endpoint ─────────────────────────────────────────────────────────

@pytest.mark.parametrize("hours,percent,amount", [(30, 100, 1200.0), (10, 50, 600.0), (2, 0, 0.0)])
def test_quote_follows_the_notice_tier(client, auth_headers, paid, monkeypatch, hours, percent, amount):
    _, ab = paid
    _hours_before(monkeypatch, ab, hours)
    q = _quote(client, auth_headers, ab["id"])
    assert q["refundable"] is True and q["cancellable"] is True
    assert q["quote"]["percent"] == percent and q["quote"]["suggestedAmount"] == amount
    assert q["quote"]["paid"] == 1200.0 and q["quote"]["remaining"] == 1200.0


def test_quote_for_unpaid_booking_has_nothing_to_refund(client, auth_headers):
    b = _book(client)
    q = _quote(client, auth_headers, _admin_booking(client, auth_headers, b["bookingRef"])["id"])
    assert q["refundable"] is False and q["quote"] is None and q["cancellable"] is True


def test_quote_404_and_auth(client, auth_headers):
    assert client.get("/api/v1/admin/bookings/nope/refund-quote", headers=auth_headers).status_code == 404
    client.cookies.clear()
    assert client.get("/api/v1/admin/bookings/nope/refund-quote").status_code == 401


# ── cancel-and-refund ──────────────────────────────────────────────────────

def test_full_notice_refunds_everything_cancels_and_frees_the_slot(client, auth_headers, paid, monkeypatch):
    b, ab = paid
    calls = _Refunds(monkeypatch)
    _hours_before(monkeypatch, ab, 30)
    r = _cr(client, auth_headers, ab["id"])
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["refunded"] == 1200.0 and body["remaining"] == 0 and body["paymentStatus"] == "refunded"
    assert body["policy"]["percent"] == 100
    assert len(calls.calls) == 1 and calls.calls[0][1] == 1200.0
    after = _admin_booking(client, auth_headers, b["bookingRef"])
    assert after["status"] == "cancelled" and after["paymentStatus"] == "refunded"
    pay = _payment(b["bookingRef"])
    assert pay.status == "refunded" and pay.refundedAmount == 1200.0
    assert _slot_available(client, ab) is True


def test_half_notice_refunds_half_and_cancels(client, auth_headers, paid, monkeypatch):
    b, ab = paid
    calls = _Refunds(monkeypatch)
    _hours_before(monkeypatch, ab, 10)
    body = _cr(client, auth_headers, ab["id"]).json()
    assert body["refunded"] == 600.0 and body["remaining"] == 600.0 and body["paymentStatus"] == "partially_refunded"
    after = _admin_booking(client, auth_headers, b["bookingRef"])
    assert after["status"] == "cancelled" and after["paymentStatus"] == "partially_refunded"
    pay = _payment(b["bookingRef"])
    assert pay.status == "partially_refunded" and pay.refundedAmount == 600.0
    assert calls.calls[0][1] == 600.0


def test_late_cancellation_cancels_without_refund_or_provider_call(client, auth_headers, paid, monkeypatch):
    b, ab = paid
    calls = _Refunds(monkeypatch)
    _hours_before(monkeypatch, ab, 2)
    body = _cr(client, auth_headers, ab["id"]).json()
    assert body["refunded"] == 0 and body["paymentStatus"] == "paid" and body["policy"]["percent"] == 0
    assert calls.calls == []
    after = _admin_booking(client, auth_headers, b["bookingRef"])
    assert after["status"] == "cancelled" and after["paymentStatus"] == "paid"
    assert _payment(b["bookingRef"]).refundedAmount == 0
    assert _slot_available(client, ab) is True


def test_admin_can_override_the_policy_upwards(client, auth_headers, paid, monkeypatch):
    b, ab = paid
    calls = _Refunds(monkeypatch)
    _hours_before(monkeypatch, ab, 2)  # policy says 0%
    body = _cr(client, auth_headers, ab["id"], amount=1200, reason="Venue flooded").json()
    assert body["refunded"] == 1200.0 and body["paymentStatus"] == "refunded"
    audit_row = next(r for r in deps.audit_repo.query(action="booking.refund")[0])
    detail = json.loads(audit_row.detail)
    assert detail["reason"] == "Venue flooded" and detail["override"] is True and detail["policy"]["percent"] == 0
    assert detail["cancelled"] is True and detail["partial"] is False


def test_admin_can_override_downwards_including_zero(client, auth_headers, paid, monkeypatch):
    b, ab = paid
    calls = _Refunds(monkeypatch)
    _hours_before(monkeypatch, ab, 30)  # policy says 100%
    body = _cr(client, auth_headers, ab["id"], amount=0).json()
    assert body["refunded"] == 0 and calls.calls == []
    assert _admin_booking(client, auth_headers, b["bookingRef"])["status"] == "cancelled"
    row = next(r for r in deps.audit_repo.query(action="booking.cancel_refund")[0])
    assert json.loads(row.detail)["override"] is True


def test_override_above_the_balance_is_rejected_without_side_effects(client, auth_headers, paid, monkeypatch):
    b, ab = paid
    calls = _Refunds(monkeypatch)
    _hours_before(monkeypatch, ab, 30)
    r = _cr(client, auth_headers, ab["id"], amount=1200.01)
    assert r.status_code == 422 and "balance" in r.json()["detail"]
    assert calls.calls == []
    after = _admin_booking(client, auth_headers, b["bookingRef"])
    assert after["status"] == "confirmed" and after["paymentStatus"] == "paid"
    assert client.post(f"/api/v1/admin/bookings/{ab['id']}/cancel-and-refund", json={"amount": -5}, headers=auth_headers).status_code == 422


def test_cancelling_an_unpaid_booking_just_cancels(client, auth_headers, monkeypatch):
    calls = _Refunds(monkeypatch)
    b = _book(client)
    ab = _admin_booking(client, auth_headers, b["bookingRef"])
    body = _cr(client, auth_headers, ab["id"]).json()
    assert body["refunded"] == 0 and body["policy"] is None and calls.calls == []
    assert _admin_booking(client, auth_headers, b["bookingRef"])["status"] == "cancelled"


def test_unpaid_booking_cannot_be_refunded_money_it_never_paid(client, auth_headers, monkeypatch):
    calls = _Refunds(monkeypatch)
    b = _book(client)
    ab = _admin_booking(client, auth_headers, b["bookingRef"])
    assert _cr(client, auth_headers, ab["id"], amount=100).status_code == 422
    assert calls.calls == [] and _admin_booking(client, auth_headers, b["bookingRef"])["status"] == "pending"


def test_free_booking_cancels_without_a_refund(client, auth_headers, monkeypatch):
    calls = _Refunds(monkeypatch)
    client.post("/api/v1/admin/promos", json={"code": "FREEALL", "kind": "percent", "value": 100, "active": True}, headers=auth_headers)
    b = _book(client, promoCode="FREEALL")
    ab = _admin_booking(client, auth_headers, b["bookingRef"])
    assert ab["status"] == "confirmed"
    body = _cr(client, auth_headers, ab["id"]).json()
    assert body["refunded"] == 0 and calls.calls == []
    assert _admin_booking(client, auth_headers, b["bookingRef"])["status"] == "cancelled"


@pytest.mark.parametrize("status", ["completed", "no_show"])
def test_finished_bookings_cannot_be_cancelled_and_refunded(client, auth_headers, paid, status):
    _, ab = paid
    assert client.patch(f"/api/v1/admin/bookings/{ab['id']}", json={"status": status if status == "no_show" else "completed"}, headers=auth_headers).status_code == 200
    r = _cr(client, auth_headers, ab["id"])
    assert r.status_code == 409 and "cannot be cancelled" in r.json()["detail"]


def test_a_cancelled_but_unrefunded_paid_booking_can_still_be_refunded(client, auth_headers, paid, monkeypatch):
    """The old 'Cancel' button cancelled without refunding; this repairs those bookings."""
    b, ab = paid
    calls = _Refunds(monkeypatch)
    client.patch(f"/api/v1/admin/bookings/{ab['id']}", json={"status": "cancelled"}, headers=auth_headers)
    _hours_before(monkeypatch, ab, 30)
    body = _cr(client, auth_headers, ab["id"]).json()
    assert body["refunded"] == 1200.0 and body["paymentStatus"] == "refunded"
    assert len(calls.calls) == 1


def test_cancelled_booking_with_nothing_refundable_is_a_conflict(client, auth_headers, paid, monkeypatch):
    b, ab = paid
    _Refunds(monkeypatch)
    _hours_before(monkeypatch, ab, 30)
    assert _cr(client, auth_headers, ab["id"]).status_code == 200
    again = _cr(client, auth_headers, ab["id"])  # double click / retry
    assert again.status_code == 409
    assert _payment(b["bookingRef"]).refundedAmount == 1200.0  # not refunded twice


# ── partial refunds via /refund ────────────────────────────────────────────

def test_partial_refunds_accumulate_until_the_booking_is_fully_refunded(client, auth_headers, paid, monkeypatch):
    b, ab = paid
    calls = _Refunds(monkeypatch)
    url = f"/api/v1/admin/bookings/{ab['id']}/refund"

    r1 = client.post(url, json={"amount": 400}, headers=auth_headers).json()
    assert (r1["status"], r1["refunded"], r1["remaining"], r1["cancelled"]) == ("partially_refunded", 400.0, 800.0, False)
    mid = _admin_booking(client, auth_headers, b["bookingRef"])
    assert mid["status"] == "confirmed" and mid["paymentStatus"] == "partially_refunded"  # still a live booking

    r2 = client.post(url, json={}, headers=auth_headers).json()  # default = everything left
    assert (r2["status"], r2["refunded"], r2["remaining"], r2["cancelled"]) == ("refunded", 800.0, 0.0, True)
    end = _admin_booking(client, auth_headers, b["bookingRef"])
    assert end["status"] == "cancelled" and end["paymentStatus"] == "refunded"
    assert [c[1] for c in calls.calls] == [400.0, 800.0]

    assert client.post(url, json={}, headers=auth_headers).status_code == 409  # nothing left


def test_refund_amount_validation(client, auth_headers, paid, monkeypatch):
    _, ab = paid
    calls = _Refunds(monkeypatch)
    url = f"/api/v1/admin/bookings/{ab['id']}/refund"
    assert client.post(url, json={"amount": 0}, headers=auth_headers).status_code == 422
    assert client.post(url, json={"amount": -1}, headers=auth_headers).status_code == 422
    over = client.post(url, json={"amount": 1200.01}, headers=auth_headers)
    assert over.status_code == 422 and "balance" in over.json()["detail"]
    client.post(url, json={"amount": 1000}, headers=auth_headers)
    assert client.post(url, json={"amount": 300}, headers=auth_headers).status_code == 422  # only 200 left
    assert len(calls.calls) == 1


def test_a_partial_payment_state_is_visible_in_the_admin_list(client, auth_headers, paid, monkeypatch):
    b, ab = paid
    _Refunds(monkeypatch)
    client.post(f"/api/v1/admin/bookings/{ab['id']}/refund", json={"amount": 100}, headers=auth_headers)
    assert _admin_booking(client, auth_headers, b["bookingRef"])["paymentStatus"] == "partially_refunded"


# ── provider failures and concurrency ──────────────────────────────────────

@pytest.mark.parametrize("raises", [False, True])
def test_provider_failure_changes_nothing(client, auth_headers, paid, monkeypatch, raises):
    b, ab = paid
    _Refunds(monkeypatch, result=False, raises=raises)
    r = client.post(f"/api/v1/admin/bookings/{ab['id']}/refund", json={"amount": 500}, headers=auth_headers)
    assert r.status_code == 502
    pay = _payment(b["bookingRef"])
    assert pay.refundedAmount == 0 and pay.status == "verified"  # reservation released
    after = _admin_booking(client, auth_headers, b["bookingRef"])
    assert after["status"] == "confirmed" and after["paymentStatus"] == "paid"
    assert len([x for x in deps.audit_repo.query(action="booking.refund_failed")[0]]) == 1
    # And a retry once the gateway recovers works for the full amount.
    _Refunds(monkeypatch)
    assert client.post(f"/api/v1/admin/bookings/{ab['id']}/refund", json={}, headers=auth_headers).status_code == 200


def test_cancel_and_refund_provider_failure_keeps_the_booking_active(client, auth_headers, paid, monkeypatch):
    b, ab = paid
    _Refunds(monkeypatch, result=False)
    _hours_before(monkeypatch, ab, 30)
    assert _cr(client, auth_headers, ab["id"]).status_code == 502
    assert _admin_booking(client, auth_headers, b["bookingRef"])["status"] == "confirmed"
    assert _slot_available(client, ab) is False


def test_reservation_is_atomic_so_concurrent_refunds_cannot_exceed_the_payment(paid):
    b, _ = paid
    pay = _payment(b["bookingRef"])
    repo = deps.booking_payment_repo
    assert repo.reserve_refund(pay.id, 700.0) is True
    assert repo.reserve_refund(pay.id, 700.0) is False   # would total 1400 > 1200
    assert repo.reserve_refund(pay.id, 500.0) is True    # exactly the rest
    assert repo.reserve_refund(pay.id, 0.01) is False
    repo.release_refund(pay.id, 500.0)
    assert _payment(b["bookingRef"]).refundedAmount == 700.0
    assert repo.reserve_refund(pay.id, 500.0) is True


# ── notifications and audit ────────────────────────────────────────────────

class _Mail:
    name = "fake"

    def __init__(self):
        self.sent = []

    def send(self, to, subject, body):
        from integrations.notifications.base import NotificationResult
        self.sent.append((to, subject, body))
        return NotificationResult(status="sent")


def test_customer_is_told_the_refunded_amount(client, auth_headers, monkeypatch):
    import services.notification_service as ns
    b = _book(client, contact="refund@example.com", email="refund@example.com")
    _pay(client, b)
    ab = _admin_booking(client, auth_headers, b["bookingRef"])
    mail = _Mail()
    monkeypatch.setattr(ns, "notification_provider", mail)
    _Refunds(monkeypatch)
    _hours_before(monkeypatch, ab, 10)
    assert _cr(client, auth_headers, ab["id"]).status_code == 200
    refund_mail = [m for m in mail.sent if "refund" in m[1].lower()]
    assert len(refund_mail) == 1
    _, subject, body = refund_mail[0]
    assert "cancelled" in subject.lower() and "Rs. 600.00" in body and "partial refund" in body


def test_partial_refund_without_cancel_says_the_booking_stays_active(client, auth_headers, monkeypatch):
    import services.notification_service as ns
    b = _book(client, contact="keep@example.com", email="keep@example.com")
    _pay(client, b)
    ab = _admin_booking(client, auth_headers, b["bookingRef"])
    mail = _Mail()
    monkeypatch.setattr(ns, "notification_provider", mail)
    _Refunds(monkeypatch)
    client.post(f"/api/v1/admin/bookings/{ab['id']}/refund", json={"amount": 250}, headers=auth_headers)
    body = [m for m in mail.sent if "refund" in m[1].lower()][0][2]
    assert "Rs. 250.00" in body and "stays active" in body


def test_refund_audit_trail(client, auth_headers, paid, monkeypatch):
    b, ab = paid
    _Refunds(monkeypatch)
    client.post(f"/api/v1/admin/bookings/{ab['id']}/refund", json={"amount": 300, "reason": "goodwill"}, headers=auth_headers)
    row = next(iter(deps.audit_repo.query(action="booking.refund")[0]))
    d = json.loads(row.detail)
    assert row.actor == "admin" and row.entityId == ab["id"]
    assert d["amount"] == 300.0 and d["partial"] is True and d["cancelled"] is False
    assert d["refundedTotal"] == 300.0 and d["reason"] == "goodwill" and d["bookingRef"] == b["bookingRef"]
    assert len(deps.audit_repo.query(action="booking.refund")[0]) == 1  # recorded once, not again by the fallback


# ── policy editing through the CMS ─────────────────────────────────────────

def test_default_policy_is_seeded_in_the_cms(client, auth_headers):
    entries = {e["key"]: e for e in client.get("/api/v1/admin/cms", headers=auth_headers).json()}
    assert parse_policy(entries["refund_policy"]["value"]) == list(DEFAULT_TIERS)


def test_cms_rejects_an_invalid_refund_policy_and_accepts_a_valid_one(client, auth_headers, paid, monkeypatch):
    _, ab = paid
    for bad in ("nonsense", '{"tiers": []}', '{"tiers": [{"hoursBefore": 5, "percent": 150}]}'):
        r = client.put("/api/v1/admin/cms/refund_policy", json={"value": bad}, headers=auth_headers)
        assert r.status_code == 422, bad
    assert load_tiers() == list(DEFAULT_TIERS)  # untouched

    good = '{"tiers": [{"hoursBefore": 1, "percent": 80}]}'
    assert client.put("/api/v1/admin/cms/refund_policy", json={"value": good}, headers=auth_headers).status_code == 200
    _hours_before(monkeypatch, ab, 2)
    assert _quote(client, auth_headers, ab["id"])["quote"]["percent"] == 80
    _hours_before(monkeypatch, ab, 0.5)
    assert _quote(client, auth_headers, ab["id"])["quote"]["percent"] == 0


def test_other_cms_keys_are_not_policy_validated(client, auth_headers):
    assert client.put("/api/v1/admin/cms/hero_tagline", json={"value": "not json at all"}, headers=auth_headers).status_code == 200


# ── access control ─────────────────────────────────────────────────────────

def test_kiosk_staff_cannot_refund_or_cancel(client, paid):
    _, ab = paid
    name = f"cashier_{uuid.uuid4().hex[:6]}"
    deps.user_repo.create(UserRecord(id=str(uuid.uuid4()), username=name, hashed_password=hash_password("1234"),
                                     role="cashier", createdAt=datetime.now(timezone.utc).isoformat(), createdBy="admin"))
    h = {"Authorization": f"Bearer {create_cashier_token(name, 'cashier')}"}
    for path in ("refund", "cancel-and-refund"):
        assert client.post(f"/api/v1/admin/bookings/{ab['id']}/{path}", json={}, headers=h).status_code == 403
    assert client.get(f"/api/v1/admin/bookings/{ab['id']}/refund-quote", headers=h).status_code == 403


def test_a_manager_can_cancel_and_refund(client, auth_headers, paid, monkeypatch):
    _, ab = paid
    _Refunds(monkeypatch)
    client.post("/api/v1/admin/users", json={"username": "mgr_refund", "password": "password123"}, headers=auth_headers)
    tok = client.post("/api/v1/admin/login", json={"username": "mgr_refund", "password": "password123"}).json()["access_token"]
    _hours_before(monkeypatch, ab, 30)
    r = client.post(f"/api/v1/admin/bookings/{ab['id']}/cancel-and-refund", json={}, headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 200 and r.json()["refunded"] == 1200.0
    row = next(iter(deps.audit_repo.query(action="booking.refund")[0]))
    assert row.actor == "mgr_refund" and row.actorRole == "manager"


def test_unknown_booking_is_404(client, auth_headers):
    assert client.post("/api/v1/admin/bookings/nope/cancel-and-refund", json={}, headers=auth_headers).status_code == 404
    assert client.post("/api/v1/admin/bookings/nope/refund", json={}, headers=auth_headers).status_code == 404
