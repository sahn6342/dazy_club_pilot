"""Advance (partial) payment: pay a non-refundable advance now, the rest at the venue; the booking is
confirmed as soon as the advance is paid."""
import json
import uuid
from datetime import date, datetime, timedelta, timezone

import pytest

import deps
from auth import create_cashier_token, hash_password
from models import UserRecord
from services import advance as adv
from services.refund_policy import build_quote
from services.notification_templates import booking_payment_pending, template_params

CRICKET_PRICE = 1200.0


def _tomorrow():
    return (date.today() + timedelta(days=1)).isoformat()


def _book(client, option=None, contact="9876543210", slot_index=0, sport="cricket", **extra):
    slots = [s for s in client.get(f"/api/v1/slots?sport={sport}&date={_tomorrow()}").json() if s["available"]]
    slot = slots[slot_index]
    body = {"name": "Jane", "contact": contact, "slotIds": [slot["id"]], "sportSlug": sport,
            "date": slot["date"], "startTime": slot["startTime"], "players": 1, **extra}
    if option:
        body["paymentOption"] = option
    return client.post("/api/v1/bookings", json=body)


def _booked(client, option=None, **kw):
    r = _book(client, option, **kw)
    assert r.status_code == 201, r.text
    return r.json()


def _pay(client, b):
    r = client.post(f"/api/v1/bookings/{b['bookingRef']}/payment/verify", json={
        "providerOrderId": b["checkout"]["providerOrderId"], "providerPaymentId": f"noop_pay_{uuid.uuid4().hex[:8]}"})
    assert r.status_code == 200, r.text


def _admin(client, auth_headers, ref):
    items = client.get("/api/v1/admin/bookings?limit=100", headers=auth_headers).json()["items"]
    return next(x for x in items if x["bookingRef"] == ref)


def _lookup(client, b, contact="9876543210"):
    r = client.get(f"/api/v1/bookings/lookup?ref={b['bookingRef']}&contact={contact}")
    assert r.status_code == 200, r.text
    return r.json()


@pytest.fixture
def advance_booking(client, auth_headers):
    """A confirmed booking where only the advance was paid, and its admin-side record."""
    b = _booked(client, "advance")
    _pay(client, b)
    return b, _admin(client, auth_headers, b["bookingRef"])


# ── setting ─────────────────────────────────────────────────────────────────

def test_default_advance_is_500_and_editable(client, auth_headers):
    assert adv.configured_advance() == 500
    r = client.put("/api/v1/admin/cms/booking_advance_amount", json={"value": "300"}, headers=auth_headers)
    assert r.status_code == 200 and adv.configured_advance() == 300


@pytest.mark.parametrize("bad", ["abc", "-1", "nan", "inf", "99999999", "5 00"])
def test_the_setting_is_validated(client, auth_headers, bad):
    r = client.put("/api/v1/admin/cms/booking_advance_amount", json={"value": bad}, headers=auth_headers)
    assert r.status_code == 422, r.text
    assert adv.configured_advance() == 500  # unchanged


def test_a_broken_or_empty_setting_switches_the_option_off(client):
    deps.cms_repo.update("booking_advance_amount", {"value": "oops"})  # bypasses route validation
    assert adv.configured_advance() == 0 and adv.advance_offer(1200) is None
    deps.cms_repo.update("booking_advance_amount", {"value": ""})
    assert adv.configured_advance() == 0
    assert _book(client, "advance").status_code == 422
    assert _book(client).status_code == 201  # paying in full is unaffected


def test_missing_key_falls_back_to_the_default(client):
    deps.cms_repo.delete("booking_advance_amount")
    assert adv.configured_advance() == 500


@pytest.mark.parametrize("total,expected", [(1200, 500), (500.01, 500), (500, None), (499, None), (0, None), (None, None)])
def test_advance_is_offered_only_when_the_total_is_more_than_the_advance(client, total, expected):
    offer = adv.advance_offer(total)
    assert (float(offer) if offer is not None else None) == expected


# ── creating the booking ────────────────────────────────────────────────────

def test_advance_option_charges_only_the_advance(client):
    b = _booked(client, "advance")
    assert b["status"] == "pending" and b["paymentRequired"] is True
    assert b["price"] == CRICKET_PRICE                      # the total is unchanged
    assert b["paymentOption"] == "advance" and b["advanceAmount"] == 500.0
    assert b["amountDue"] == 500.0 and b["balanceDue"] == 700.0
    assert b["checkout"]["amount"] == 500.0                 # the provider order is for the advance
    pay = deps.booking_payment_repo.get_by_ref(b["bookingRef"])
    assert pay.amount == 500.0
    row = deps.booking_repo.get_by_ref(b["bookingRef"])[0]
    assert row.price == CRICKET_PRICE and row.depositAmount == 500.0


def test_paying_in_full_is_the_default_and_unchanged(client):
    for option in (None, "full"):
        b = _booked(client, option, slot_index=0 if option is None else 1, contact="9000000001" if option is None else "9000000002")
        assert b["paymentOption"] == "full" and b["advanceAmount"] is None
        assert b["amountDue"] == CRICKET_PRICE and b["balanceDue"] == 0
        assert b["checkout"]["amount"] == CRICKET_PRICE
        assert deps.booking_repo.get_by_ref(b["bookingRef"])[0].depositAmount is None


def test_unknown_payment_option_is_rejected(client):
    assert _book(client, "half").status_code == 422


def test_advance_is_rejected_when_switched_off(client, auth_headers):
    client.put("/api/v1/admin/cms/booking_advance_amount", json={"value": "0"}, headers=auth_headers)
    r = _book(client, "advance")
    assert r.status_code == 422 and r.json()["code"] == "advance_not_available"
    assert deps.booking_repo.get_all() == []  # nothing persisted


def test_advance_is_rejected_when_the_total_is_not_more_than_the_advance(client, auth_headers):
    client.put("/api/v1/admin/cms/booking_advance_amount", json={"value": "1200"}, headers=auth_headers)
    r = _book(client, "advance")
    assert r.status_code == 422 and r.json()["code"] == "advance_not_available"
    assert _book(client, "full").status_code == 201


def test_advance_follows_the_promo_discounted_total(client, auth_headers):
    client.post("/api/v1/admin/promos", json={"code": "HALF", "kind": "percent", "value": 50, "max_uses": 10}, headers=auth_headers)
    b = _booked(client, "advance", promoCode="HALF")
    assert b["price"] == 600.0 and b["advanceAmount"] == 500.0 and b["balanceDue"] == 100.0
    assert b["checkout"]["amount"] == 500.0


def test_a_promo_that_removes_the_advance_option_releases_the_promo(client, auth_headers):
    r = client.post("/api/v1/admin/promos", json={"code": "ALMOST", "kind": "percent", "value": 70, "max_uses": 1}, headers=auth_headers)
    assert r.status_code in (200, 201), r.text
    bad = _book(client, "advance", promoCode="ALMOST")  # 1200 -> 360, not more than 500
    assert bad.status_code == 422 and bad.json()["code"] == "advance_not_available"
    assert _book(client, "full", promoCode="ALMOST").status_code == 201  # the single use was given back


def test_a_free_booking_cannot_ask_for_an_advance(client, auth_headers):
    client.post("/api/v1/admin/promos", json={"code": "FREE", "kind": "percent", "value": 100, "max_uses": 5}, headers=auth_headers)
    r = _book(client, "advance", promoCode="FREE")
    assert r.status_code == 422 and r.json()["code"] == "advance_not_available"


# ── paying the advance ──────────────────────────────────────────────────────

def test_paying_the_advance_confirms_the_booking(client, auth_headers, advance_booking):
    b, ab = advance_booking
    assert ab["status"] == "confirmed" and ab["paymentStatus"] == "paid"
    assert ab["depositAmount"] == 500.0 and ab["price"] == CRICKET_PRICE
    look = _lookup(client, b)
    assert look["status"] == "confirmed" and look["paymentRequired"] is False
    assert look["paymentOption"] == "advance" and look["advanceAmount"] == 500.0
    assert look["amountPaid"] == 500.0 and look["balanceDue"] == 700.0 and look["price"] == CRICKET_PRICE


def test_verifying_twice_is_still_idempotent(client, advance_booking):
    b, _ = advance_booking
    r = client.post(f"/api/v1/bookings/{b['bookingRef']}/payment/verify", json={
        "providerOrderId": b["checkout"]["providerOrderId"], "providerPaymentId": "noop_pay_again"})
    assert r.status_code == 200 and r.json()["status"] == "confirmed"


def test_a_pending_advance_booking_resumes_with_the_advance_checkout(client):
    b = _booked(client, "advance")
    look = _lookup(client, b)
    assert look["paymentRequired"] is True and look["amountDue"] == 500.0 and look["checkout"]["amount"] == 500.0
    assert look["amountPaid"] == 0 and look["balanceDue"] == 700.0 and look["paymentOption"] == "advance"


def test_the_webhook_amount_check_uses_the_advance(client, monkeypatch):
    """Provider says it captured the full price on an advance order: that is a mismatch, not a confirmation."""
    from integrations.payments.base import PaymentVerification

    b = _booked(client, "advance")

    class _Provider:
        def __init__(self, amount):
            self.amount = amount

        def verify_webhook(self, *_a, **_k):
            return PaymentVerification(verified=True, providerPaymentId="pay_x", amount=self.amount), b["checkout"]["providerOrderId"]

    monkeypatch.setattr(deps, "payment_provider", _Provider(CRICKET_PRICE))
    import routes.payments as rp
    monkeypatch.setattr(rp, "payment_provider", deps.payment_provider)
    r = client.post("/api/v1/payments/razorpay/webhook", content=b"{}", headers={"X-Razorpay-Signature": "x"})
    assert r.json().get("status") == "amount_mismatch"
    assert deps.booking_repo.get_by_ref(b["bookingRef"])[0].status == "pending"
    monkeypatch.setattr(rp, "payment_provider", _Provider(500.0))
    r = client.post("/api/v1/payments/razorpay/webhook", content=b"{}", headers={"X-Razorpay-Signature": "x"})
    assert deps.booking_repo.get_by_ref(b["bookingRef"])[0].status == "confirmed"


def test_an_unpaid_advance_hold_expires_like_any_other(client):
    from services.availability_service import _sweep_stale_pending
    b = _booked(client, "advance")
    old = (datetime.now(timezone.utc) - timedelta(minutes=30)).isoformat()
    row = deps.booking_repo.get_by_ref(b["bookingRef"])[0]
    deps.booking_repo.update(row.id, {"createdAt": old})
    _sweep_stale_pending()
    assert deps.booking_repo.get_by_ref(b["bookingRef"])[0].status == "cancelled"


def test_a_paid_advance_booking_is_not_swept(client, advance_booking):
    from services.availability_service import _sweep_stale_pending
    b, ab = advance_booking
    deps.booking_repo.update(ab["id"], {"createdAt": (datetime.now(timezone.utc) - timedelta(hours=3)).isoformat()})
    _sweep_stale_pending()
    assert deps.booking_repo.get_by_ref(b["bookingRef"])[0].status == "confirmed"


# ── refunds: the advance is never refunded ─────────────────────────────────

def test_quote_for_an_advance_booking_has_nothing_refundable(client, auth_headers, advance_booking):
    _, ab = advance_booking
    r = client.get(f"/api/v1/admin/bookings/{ab['id']}/refund-quote", headers=auth_headers).json()
    q = r["quote"]
    assert r["refundable"] is False and r["cancellable"] is True
    assert q["paid"] == 500.0 and q["nonRefundable"] == 500.0 and q["remaining"] == 0 and q["suggestedAmount"] == 0


def test_refunding_an_advance_booking_is_refused_and_the_provider_not_called(client, auth_headers, advance_booking, monkeypatch):
    _, ab = advance_booking
    calls = []
    monkeypatch.setattr(deps.payment_provider, "refund", lambda *a: calls.append(a) or True)
    for body in ({}, {"amount": 100}, {"amount": 500}):
        r = client.post(f"/api/v1/admin/bookings/{ab['id']}/refund", json=body, headers=auth_headers)
        assert r.status_code == 409 and "non-refundable" in r.json()["detail"], r.text
    r = client.post(f"/api/v1/admin/bookings/{ab['id']}/cancel-and-refund", json={"amount": 100}, headers=auth_headers)
    assert r.status_code == 422
    assert calls == []
    assert deps.booking_payment_repo.get_by_ref(ab["bookingRef"]).refundedAmount == 0


def test_cancelling_an_advance_booking_keeps_the_advance(client, auth_headers, advance_booking, monkeypatch):
    b, ab = advance_booking
    calls = []
    monkeypatch.setattr(deps.payment_provider, "refund", lambda *a: calls.append(a) or True)
    r = client.post(f"/api/v1/admin/bookings/{ab['id']}/cancel-and-refund", json={}, headers=auth_headers)
    assert r.status_code == 200 and r.json()["refunded"] == 0 and calls == []
    after = _admin(client, auth_headers, b["bookingRef"])
    assert after["status"] == "cancelled" and after["paymentStatus"] == "paid"
    assert _lookup(client, b)["balanceDue"] == 0  # nothing more is owed on a cancelled booking


def test_full_payment_refunds_are_unchanged(client, auth_headers):
    b = _booked(client)
    _pay(client, b)
    ab = _admin(client, auth_headers, b["bookingRef"])
    q = client.get(f"/api/v1/admin/bookings/{ab['id']}/refund-quote", headers=auth_headers).json()["quote"]
    assert q["paid"] == CRICKET_PRICE and q["nonRefundable"] == 0 and q["remaining"] == CRICKET_PRICE


def test_build_quote_excludes_the_non_refundable_part():
    q = build_quote(1000, 0, 30, [(24.0, 100.0)], non_refundable=400)
    assert (q.paid, q.nonRefundable, q.remaining, q.policyAmount, q.suggestedAmount) == (1000, 400, 600, 600, 600)
    q = build_quote(500, 0, 30, [(24.0, 100.0)], non_refundable=500)
    assert q.remaining == 0 and q.suggestedAmount == 0
    q = build_quote(300, 0, 30, [(24.0, 100.0)], non_refundable=500)  # never negative
    assert q.remaining == 0 and q.nonRefundable == 300


# ── collecting the balance at the venue ────────────────────────────────────

def _collect(client, auth_headers, bid, **body):
    body.setdefault("mode", "cash")
    return client.post(f"/api/v1/admin/bookings/{bid}/collect-balance", json=body, headers=auth_headers)


def test_collect_the_whole_balance(client, auth_headers, advance_booking):
    b, ab = advance_booking
    r = _collect(client, auth_headers, ab["id"], reference="receipt 14")
    assert r.status_code == 200, r.text
    assert r.json() == {"bookingRef": b["bookingRef"], "collected": 700.0, "balanceDue": 0.0, "amountPaid": CRICKET_PRICE}
    after = _admin(client, auth_headers, b["bookingRef"])
    assert after["balance_collected"] == 700.0 and after["balance_mode"] == "cash" and after["balance_collected_by"]
    look = _lookup(client, b)
    assert look["balanceDue"] == 0 and look["amountPaid"] == CRICKET_PRICE
    row = next(r for r in deps.audit_repo.query(action="booking.balance_collected")[0])
    detail = json.loads(row.detail)
    assert detail["amount"] == 700.0 and detail["mode"] == "cash" and detail["reference"] == "receipt 14"


def test_collect_in_instalments(client, auth_headers, advance_booking):
    _, ab = advance_booking
    assert _collect(client, auth_headers, ab["id"], amount=200, mode="upi").json()["balanceDue"] == 500.0
    assert _collect(client, auth_headers, ab["id"], amount=500, mode="card").json()["balanceDue"] == 0.0
    assert _collect(client, auth_headers, ab["id"]).status_code == 409  # nothing left


def test_collecting_more_than_the_balance_is_rejected(client, auth_headers, advance_booking):
    _, ab = advance_booking
    r = _collect(client, auth_headers, ab["id"], amount=700.01)
    assert r.status_code == 422 and "balance" in r.json()["detail"]
    assert _admin(client, auth_headers, ab["bookingRef"])["balance_collected"] == 0


@pytest.mark.parametrize("body", [{"mode": "cheque"}, {"mode": "cash", "amount": 0}, {"mode": "cash", "amount": -5}, {}])
def test_collect_balance_validates_input(client, auth_headers, advance_booking, body):
    _, ab = advance_booking
    r = client.post(f"/api/v1/admin/bookings/{ab['id']}/collect-balance", json=body, headers=auth_headers)
    assert r.status_code == 422


def test_balance_is_collected_only_on_confirmed_advance_bookings(client, auth_headers):
    full = _booked(client)
    _pay(client, full)
    assert _collect(client, auth_headers, _admin(client, auth_headers, full["bookingRef"])["id"]).status_code == 409  # paid in full

    pending = _booked(client, "advance", contact="9000000003", slot_index=1)  # advance not yet paid
    assert _collect(client, auth_headers, _admin(client, auth_headers, pending["bookingRef"])["id"]).status_code == 409

    assert _collect(client, auth_headers, "nope").status_code == 404


def test_kiosk_staff_cannot_collect_the_balance(client, advance_booking):
    _, ab = advance_booking
    name = f"cashier_{uuid.uuid4().hex[:6]}"
    deps.user_repo.create(UserRecord(id=str(uuid.uuid4()), username=name, hashed_password=hash_password("1234"),
                                     role="cashier", createdAt=datetime.now(timezone.utc).isoformat(), createdBy="admin"))
    h = {"Authorization": f"Bearer {create_cashier_token(name, 'cashier')}"}
    r = client.post(f"/api/v1/admin/bookings/{ab['id']}/collect-balance", json={"mode": "cash"}, headers=h)
    assert r.status_code == 403
    client.cookies.clear()
    assert client.post(f"/api/v1/admin/bookings/{ab['id']}/collect-balance", json={"mode": "cash"}).status_code == 401


# ── notifications, CSV ──────────────────────────────────────────────────────

def test_the_pending_notice_asks_for_the_advance_not_the_total(client):
    b = _booked(client, "advance")
    row = deps.booking_repo.get_by_ref(b["bookingRef"])[0]
    _, body = booking_payment_pending(row)
    assert "Amount due: Rs. 500.00" in body
    assert template_params("booking_pending", row)[2] == "Rs. 500.00"


def test_the_confirmation_shows_paid_and_pending(client, advance_booking):
    b, _ = advance_booking
    row = deps.booking_repo.get_by_ref(b["bookingRef"])[0]
    params = template_params("booking_confirmed", row)
    assert params[6:8] == ["Rs. 500.00", "Rs. 700.00"] and len(params) == 9  # the template variable order is unchanged


def test_the_csv_export_has_the_payment_columns(client, auth_headers, advance_booking):
    import csv
    import io
    b, ab = advance_booking
    _collect(client, auth_headers, ab["id"], amount=200)
    text = client.get("/api/v1/admin/bookings/export", headers=auth_headers).content.decode("utf-8-sig")
    rows = list(csv.DictReader(io.StringIO(text)))
    row = next(r for r in rows if r["Ref"] == b["bookingRef"])
    assert row["Payment Option"] == "advance" and row["Amount Paid (INR)"] == "700.00" and row["Balance Due (INR)"] == "500.00"
    assert row["Price (INR)"] == "1200.0" or float(row["Price (INR)"]) == CRICKET_PRICE
