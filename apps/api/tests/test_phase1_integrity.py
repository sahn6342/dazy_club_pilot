"""Phase 1: webhook amount check, reconciliation of missed webhooks, scheduler endpoint."""
import json
from datetime import date, datetime, timedelta, timezone

import deps
from db import _session
from db_models import BookingPaymentRow, BookingRow
from integrations.payments.base import CapturedPayment, PaymentVerification


def _tomorrow():
    return (date.today() + timedelta(days=1)).isoformat()


def _slot(client, sport="cricket"):
    return [s for s in client.get(f"/api/v1/slots?sport={sport}&date={_tomorrow()}").json() if s["available"]][0]


def _book(client, **kw):
    s = _slot(client)
    body = {"name": "Jane", "contact": "9876543210", "slotIds": [s["id"]], "sportSlug": s["sportSlug"],
            "date": s["date"], "startTime": s["startTime"], "players": 1, **kw}
    r = client.post("/api/v1/bookings", json=body)
    assert r.status_code == 201, r.text
    return r.json()


def _age_payment(ref, minutes):
    old = (datetime.now(timezone.utc) - timedelta(minutes=minutes)).isoformat()
    with _session() as s:
        s.query(BookingPaymentRow).filter(BookingPaymentRow.bookingRef == ref).update({"createdAt": old})


def _age_booking(ref, minutes):
    old = (datetime.now(timezone.utc) - timedelta(minutes=minutes)).isoformat()
    with _session() as s:
        s.query(BookingRow).filter(BookingRow.bookingRef == ref).update({"createdAt": old})


def _status(client, auth_headers, ref):
    items = client.get("/api/v1/admin/bookings?limit=100", headers=auth_headers).json()["items"]
    b = next(x for x in items if x["bookingRef"] == ref)
    return b["status"], b["paymentStatus"]


class _FakeProvider:
    def __init__(self, amount=None, captured=None):
        self._amount, self._captured, self.refunds = amount, captured, []

    def verify_webhook(self, raw, sig):
        o = json.loads(raw)["order"]
        return PaymentVerification(True, "pay_fake", amount=self._amount), o

    def fetch_captured_payment(self, order_id):
        return self._captured

    def refund(self, pid, amount):
        self.refunds.append((pid, amount))
        return True


# ── webhook amount check ───────────────────────────────────────────────────

def test_webhook_amount_mismatch_does_not_confirm(client, auth_headers, monkeypatch):
    b = _book(client)
    import routes.payments as rp
    monkeypatch.setattr(rp, "payment_provider", _FakeProvider(amount=1.0))  # order is for 1200
    r = client.post("/api/v1/payments/razorpay/webhook", content=json.dumps({"order": b["checkout"]["providerOrderId"]}))
    assert r.status_code == 200 and r.json()["status"] == "amount_mismatch"
    assert _status(client, auth_headers, b["bookingRef"]) == ("pending", "unpaid")
    assert deps.booking_payment_repo.get_by_ref(b["bookingRef"]).status == "amount_mismatch"


def test_webhook_matching_amount_confirms(client, auth_headers, monkeypatch):
    b = _book(client)
    import routes.payments as rp
    monkeypatch.setattr(rp, "payment_provider", _FakeProvider(amount=b["price"]))
    r = client.post("/api/v1/payments/razorpay/webhook", content=json.dumps({"order": b["checkout"]["providerOrderId"]}))
    assert r.json()["status"] == "ok"
    assert _status(client, auth_headers, b["bookingRef"]) == ("confirmed", "paid")


# ── reconciliation ─────────────────────────────────────────────────────────

def _patch_reconcile(monkeypatch, fake):
    import services.reconciliation as rec
    import services.payment_confirmation as pc
    monkeypatch.setattr(rec, "payment_provider", fake)
    monkeypatch.setattr(pc, "payment_provider", fake)


def test_reconcile_confirms_booking_when_webhook_was_missed(client, auth_headers, monkeypatch):
    from services.reconciliation import reconcile_unsettled_payments
    b = _book(client)
    _age_payment(b["bookingRef"], 5)
    _patch_reconcile(monkeypatch, _FakeProvider(captured=CapturedPayment("pay_cap", b["price"])))
    assert reconcile_unsettled_payments() == 1
    assert _status(client, auth_headers, b["bookingRef"]) == ("confirmed", "paid")
    assert reconcile_unsettled_payments() == 0  # settled rows are not revisited


def test_reconcile_skips_fresh_orders_and_unpaid_ones(client, monkeypatch):
    from services.reconciliation import reconcile_unsettled_payments
    fresh = _book(client)  # younger than the 2-minute head start
    _patch_reconcile(monkeypatch, _FakeProvider(captured=CapturedPayment("pay_cap", fresh["price"])))
    assert reconcile_unsettled_payments() == 0
    _age_payment(fresh["bookingRef"], 5)
    _patch_reconcile(monkeypatch, _FakeProvider(captured=None))  # provider says: not paid
    assert reconcile_unsettled_payments() == 0


def test_reconcile_refunds_when_payment_found_after_expiry(client, auth_headers, monkeypatch):
    from services.reconciliation import reconcile_unsettled_payments
    b = _book(client)
    _age_payment(b["bookingRef"], 30)
    _age_booking(b["bookingRef"], 30)
    client.get(f"/api/v1/slots?sport=cricket&date={_tomorrow()}")  # sweep -> cancelled, payment expired
    fake = _FakeProvider(captured=CapturedPayment("pay_late", b["price"]))
    _patch_reconcile(monkeypatch, fake)
    assert reconcile_unsettled_payments() == 1
    assert fake.refunds == [("pay_late", b["price"])]
    assert _status(client, auth_headers, b["bookingRef"])[0] == "cancelled"


def test_reconcile_flags_amount_mismatch(client, auth_headers, monkeypatch):
    from services.reconciliation import reconcile_unsettled_payments
    b = _book(client)
    _age_payment(b["bookingRef"], 5)
    _patch_reconcile(monkeypatch, _FakeProvider(captured=CapturedPayment("pay_x", 5.0)))
    assert reconcile_unsettled_payments() == 0
    assert deps.booking_payment_repo.get_by_ref(b["bookingRef"]).status == "amount_mismatch"
    assert _status(client, auth_headers, b["bookingRef"]) == ("pending", "unpaid")


# ── scheduler endpoint ─────────────────────────────────────────────────────

def test_internal_sweep_disabled_without_token_env(client, monkeypatch):
    monkeypatch.delenv("DAZY_INTERNAL_TOKEN", raising=False)
    assert client.post("/api/v1/internal/sweep", headers={"X-Internal-Token": "x"}).status_code == 404


def test_internal_sweep_auth_and_effect(client, auth_headers, monkeypatch):
    monkeypatch.setenv("DAZY_INTERNAL_TOKEN", "s3cret-token")
    assert client.post("/api/v1/internal/sweep").status_code == 401
    assert client.post("/api/v1/internal/sweep", headers={"X-Internal-Token": "wrong"}).status_code == 401
    b = _book(client)
    _age_booking(b["bookingRef"], 30)
    r = client.post("/api/v1/internal/sweep", headers={"X-Internal-Token": "s3cret-token"})
    assert r.status_code == 200 and r.json()["expired"] == 1
    assert _status(client, auth_headers, b["bookingRef"])[0] == "cancelled"  # expired without any slot read


# ── capacity is 1 ──────────────────────────────────────────────────────────

def test_second_booking_on_same_slot_is_unavailable_not_500(client):
    s = _slot(client)
    body = {"name": "A", "contact": "9000000001", "slotIds": [s["id"]], "sportSlug": s["sportSlug"],
            "date": s["date"], "startTime": s["startTime"], "players": 1}
    assert client.post("/api/v1/bookings", json=body).status_code == 201
    r = client.post("/api/v1/bookings", json={**body, "contact": "9000000002"})
    assert r.status_code == 409 and "unavailable" in r.json()["detail"].lower()
    again = [x for x in client.get(f"/api/v1/slots?sport={s['sportSlug']}&date={s['date']}").json() if x["id"] == s["id"]][0]
    assert again["available"] is False
