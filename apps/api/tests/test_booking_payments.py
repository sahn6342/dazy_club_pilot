"""
Booking online prepay (Detailed-Roadmap.md Phase 3). Uses the noop payment
provider (default DAZY_PAYMENT_PROVIDER) so the full pending -> pay -> confirm
flow is exercised without real gateway credentials.
"""
import json
from datetime import date, timedelta

import deps
from db_models import BookingRow
from db import _session


def _tomorrow():
    return (date.today() + timedelta(days=1)).isoformat()


def _get_available_slot(client, sport="cricket"):
    r = client.get(f"/api/v1/slots?sport={sport}&date={_tomorrow()}")
    slots = [s for s in r.json() if s["available"]]
    assert slots, f"No available slot for {sport}"
    return slots[0]


def _book(client, slot, **overrides):
    payload = {
        "name": "Jane Doe", "contact": "9876543210",
        "slotId": slot["id"], "sportSlug": slot["sportSlug"],
        "date": slot["date"], "startTime": slot["startTime"], "players": 2,
    }
    payload.update(overrides)
    r = client.post("/api/v1/bookings", json=payload)
    assert r.status_code == 201, r.text
    return r.json()


def _backdate_booking(booking_ref: str, minutes_ago: int):
    """Simulate an old pending booking without waiting for the real timeout."""
    from datetime import datetime, timezone
    stale = (datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)).isoformat()
    with _session() as s:
        s.query(BookingRow).filter(BookingRow.bookingRef == booking_ref).update({"createdAt": stale})


# ── Priced booking creates a pending hold + checkout order ─────────────────

def test_priced_booking_pending_with_checkout_order(client):
    slot = _get_available_slot(client)
    result = _book(client, slot)
    assert result["status"] == "pending"
    assert result["paymentRequired"] is True
    assert result["checkout"]["provider"] == "noop"
    assert result["checkout"]["providerOrderId"].startswith("noop_order_")


def test_free_booking_confirms_immediately_no_payment(client, auth_headers):
    """A 100%-off promo zeroes the price -> no payment step needed."""
    r = client.post("/api/v1/admin/promos", json={
        "code": "FREE100", "kind": "percent", "value": 100, "active": True,
    }, headers=auth_headers)
    assert r.status_code == 201, r.text

    slot = _get_available_slot(client)
    result = _book(client, slot, promoCode="FREE100")
    assert result["status"] == "confirmed"
    assert result["paymentRequired"] is False
    assert "checkout" not in result

    admin_list = client.get("/api/v1/admin/bookings", headers=auth_headers).json()
    booking = next(b for b in admin_list if b["bookingRef"] == result["bookingRef"])
    assert booking["paymentStatus"] == "paid"


# ── Payment verify (client callback) ────────────────────────────────────────

def test_payment_verify_confirms_booking(client, auth_headers):
    slot = _get_available_slot(client)
    result = _book(client, slot)
    ref = result["bookingRef"]
    order_id = result["checkout"]["providerOrderId"]

    r = client.post(f"/api/v1/bookings/{ref}/payment/verify", json={
        "providerOrderId": order_id, "providerPaymentId": "noop_pay_test123",
    })
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "confirmed"

    admin_list = client.get("/api/v1/admin/bookings", headers=auth_headers).json()
    booking = next(b for b in admin_list if b["bookingRef"] == ref)
    assert booking["status"] == "confirmed"
    assert booking["paymentStatus"] == "paid"


def test_payment_verify_idempotent(client):
    slot = _get_available_slot(client)
    result = _book(client, slot)
    ref = result["bookingRef"]
    body = {"providerOrderId": result["checkout"]["providerOrderId"], "providerPaymentId": "noop_pay_abc"}

    r1 = client.post(f"/api/v1/bookings/{ref}/payment/verify", json=body)
    assert r1.status_code == 200
    r2 = client.post(f"/api/v1/bookings/{ref}/payment/verify", json=body)
    assert r2.status_code == 200
    assert r2.json() == {"status": "confirmed", "paymentStatus": "paid"}


def test_payment_verify_unknown_ref_404(client):
    r = client.post("/api/v1/bookings/NOSUCHREF/payment/verify", json={
        "providerOrderId": "noop_order_x", "providerPaymentId": "noop_pay_x",
    })
    assert r.status_code == 404


# ── Webhook (source of truth) ───────────────────────────────────────────────

def test_webhook_confirms_booking(client, auth_headers):
    slot = _get_available_slot(client)
    result = _book(client, slot)
    ref = result["bookingRef"]
    order_id = result["checkout"]["providerOrderId"]

    r = client.post("/api/v1/payments/razorpay/webhook", content=json.dumps({
        "providerOrderId": order_id, "providerPaymentId": "noop_pay_webhook1",
    }))
    assert r.status_code == 200, r.text

    admin_list = client.get("/api/v1/admin/bookings", headers=auth_headers).json()
    booking = next(b for b in admin_list if b["bookingRef"] == ref)
    assert booking["status"] == "confirmed"
    assert booking["paymentStatus"] == "paid"


def test_webhook_idempotent_on_redelivery(client):
    slot = _get_available_slot(client)
    result = _book(client, slot)
    order_id = result["checkout"]["providerOrderId"]
    body = json.dumps({"providerOrderId": order_id, "providerPaymentId": "noop_pay_dup"})

    r1 = client.post("/api/v1/payments/razorpay/webhook", content=body)
    assert r1.status_code == 200
    r2 = client.post("/api/v1/payments/razorpay/webhook", content=body)  # gateway redelivery
    assert r2.status_code == 200


def test_webhook_unknown_order_404(client):
    r = client.post("/api/v1/payments/razorpay/webhook", content=json.dumps({
        "providerOrderId": "noop_order_never_created", "providerPaymentId": "x",
    }))
    assert r.status_code == 404


def test_webhook_malformed_body_400(client):
    r = client.post("/api/v1/payments/razorpay/webhook", content="not json")
    assert r.status_code == 400


# ── Timeout sweep: unpaid pending holds expire and free the slot ──────────

def test_stale_pending_booking_expires_and_frees_slot(client):
    slot = _get_available_slot(client)
    result = _book(client, slot)
    ref = result["bookingRef"]

    # Confirm the hold currently blocks the slot.
    slots_now = client.get(f"/api/v1/slots?sport={slot['sportSlug']}&date={slot['date']}").json()
    same_slot = next(s for s in slots_now if s["id"] == slot["id"])
    assert same_slot["available"] is False

    _backdate_booking(ref, minutes_ago=20)  # older than the 15-minute timeout

    # Any availability read sweeps stale pending bookings.
    slots_after = client.get(f"/api/v1/slots?sport={slot['sportSlug']}&date={slot['date']}").json()
    same_slot_after = next(s for s in slots_after if s["id"] == slot["id"])
    assert same_slot_after["available"] is True


def test_recent_pending_booking_not_swept(client):
    """A hold within the timeout window still blocks re-booking (sanity check
    that the sweep only catches genuinely stale holds)."""
    slot = _get_available_slot(client)
    _book(client, slot)  # createdAt = now, well within the 15-minute window

    slots_now = client.get(f"/api/v1/slots?sport={slot['sportSlug']}&date={slot['date']}").json()
    same_slot = next(s for s in slots_now if s["id"] == slot["id"])
    assert same_slot["available"] is False


def test_no_double_book_while_pending_hold_active(client):
    slot = _get_available_slot(client)
    _book(client, slot)  # first hold, unpaid, still within timeout

    r = client.post("/api/v1/bookings", json={
        "name": "Second Customer", "contact": "9111111111",
        "slotId": slot["id"], "sportSlug": slot["sportSlug"],
        "date": slot["date"], "startTime": slot["startTime"], "players": 1,
    })
    assert r.status_code in (404, 409)  # slot no longer available / booking conflict


# ── Refund ───────────────────────────────────────────────────────────────

def test_refund_paid_booking_frees_slot(client, auth_headers):
    slot = _get_available_slot(client)
    result = _book(client, slot)
    ref = result["bookingRef"]
    client.post(f"/api/v1/bookings/{ref}/payment/verify", json={
        "providerOrderId": result["checkout"]["providerOrderId"], "providerPaymentId": "noop_pay_refundme",
    })

    admin_list = client.get("/api/v1/admin/bookings", headers=auth_headers).json()
    booking_id = next(b for b in admin_list if b["bookingRef"] == ref)["id"]

    r = client.post(f"/api/v1/admin/bookings/{booking_id}/refund", json={}, headers=auth_headers)
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "refunded"

    admin_list2 = client.get("/api/v1/admin/bookings", headers=auth_headers).json()
    booking2 = next(b for b in admin_list2 if b["bookingRef"] == ref)
    assert booking2["paymentStatus"] == "refunded"
    assert booking2["status"] == "cancelled"

    slots_after = client.get(f"/api/v1/slots?sport={slot['sportSlug']}&date={slot['date']}").json()
    same_slot = next(s for s in slots_after if s["id"] == slot["id"])
    assert same_slot["available"] is True


def test_refund_rejects_unpaid_booking(client, auth_headers):
    slot = _get_available_slot(client)
    result = _book(client, slot)  # still pending/unpaid — never verified
    ref = result["bookingRef"]

    admin_list = client.get("/api/v1/admin/bookings", headers=auth_headers).json()
    booking_id = next(b for b in admin_list if b["bookingRef"] == ref)["id"]

    r = client.post(f"/api/v1/admin/bookings/{booking_id}/refund", json={}, headers=auth_headers)
    assert r.status_code == 409


def test_refund_requires_admin_auth(client):
    r = client.post("/api/v1/admin/bookings/some-id/refund", json={})
    assert r.status_code in (401, 403)
