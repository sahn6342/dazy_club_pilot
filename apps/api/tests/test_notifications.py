"""
Customer confirmation (Detailed-Roadmap.md Phase 5). Covers: a confirmed,
paid booking sends exactly one notification (free-booking auto-confirm,
payment-verify callback, and the payment webhook all funnel through the same
guarded notify_booking_confirmed call); content is assembled correctly;
a provider failure is logged but never fails the booking flow; and the
admin delivery-log endpoint.
"""
import uuid

import pytest
from starlette.testclient import TestClient

from main import app
from auth import create_access_token
from integrations.notifications.base import NotificationProvider, NotificationResult
from integrations.notifications.email_smtp import SmtpEmailNotificationProvider
import deps
import services.notification_service as notification_service

client = TestClient(app)

ADMIN_HEADERS = {"Authorization": "Bearer " + create_access_token("admin", "admin")}


def _first_available_slot(sport="badminton"):
    r = client.get(f"/api/v1/slots?sport={sport}")
    assert r.status_code == 200
    slots = [s for s in r.json() if s["available"]]
    assert slots, f"no available {sport} slot to book"
    return slots[0]


def _create_free_promo() -> str:
    code = f"FREE{uuid.uuid4().hex[:6].upper()}"
    r = client.post(
        "/api/v1/admin/promos",
        json={"code": code, "kind": "percent", "value": 100, "active": True,
              "valid_from": None, "valid_to": None, "max_uses": None, "sport_slug": None},
        headers=ADMIN_HEADERS,
    )
    assert r.status_code == 201
    return code


def _book(slot, promo_code=None, contact="9812345670"):
    body = {
        "name": "Notify Test",
        "contact": contact,
        "sportSlug": slot["sportSlug"],
        "date": slot["date"],
        "startTime": slot["startTime"],
        "slotIds": [slot["id"]],
        "players": 1,
    }
    if promo_code:
        body["promoCode"] = promo_code
    r = client.post("/api/v1/bookings", json=body)
    assert r.status_code == 201
    return r.json()


class _FakeProvider(NotificationProvider):
    name = "fake"

    def __init__(self, result=None, raises=False):
        self._result = result or NotificationResult(status="sent")
        self._raises = raises
        self.calls = []

    def send(self, to, subject, body):
        self.calls.append((to, subject, body))
        if self._raises:
            raise RuntimeError("provider exploded")
        return self._result


@pytest.fixture()
def fake_provider():
    # notification_service does `from deps import notification_provider`, so it holds its
    # own module-level binding — patch that binding directly, not deps.notification_provider.
    original = notification_service.notification_provider
    fake = _FakeProvider()
    notification_service.notification_provider = fake
    yield fake
    notification_service.notification_provider = original


# ── Fires exactly once, per confirmation path ───────────────────────────────

def test_free_booking_auto_confirm_sends_one_notification(fake_provider):
    slot = _first_available_slot()
    promo = _create_free_promo()
    booking = _book(slot, promo_code=promo)
    assert booking["status"] == "confirmed"

    assert len(fake_provider.calls) == 1
    logged = deps.notification_repo.get_all(ref_type="booking")
    assert len(logged) == 1
    assert logged[0].status == "sent"
    assert logged[0].refType == "booking"


def test_payment_verify_sends_one_notification(fake_provider):
    slot = _first_available_slot("cricket")
    booking = _book(slot)
    assert booking["paymentRequired"] is True
    assert len(fake_provider.calls) == 0  # not confirmed yet — no notification

    r = client.post(
        f"/api/v1/bookings/{booking['bookingRef']}/payment/verify",
        json={"providerOrderId": booking["checkout"]["providerOrderId"], "providerPaymentId": "pay_1"},
    )
    assert r.status_code == 200
    assert len(fake_provider.calls) == 1


def test_payment_verify_idempotent_does_not_double_notify(fake_provider):
    slot = _first_available_slot("cricket")
    booking = _book(slot)
    order_id = booking["checkout"]["providerOrderId"]

    client.post(f"/api/v1/bookings/{booking['bookingRef']}/payment/verify", json={"providerOrderId": order_id, "providerPaymentId": "pay_1"})
    r2 = client.post(f"/api/v1/bookings/{booking['bookingRef']}/payment/verify", json={"providerOrderId": order_id, "providerPaymentId": "pay_1"})
    assert r2.status_code == 200

    assert len(fake_provider.calls) == 1  # second (idempotent) call must not re-notify


def test_webhook_confirmation_sends_one_notification(fake_provider):
    slot = _first_available_slot("pickleball")
    booking = _book(slot)
    order_id = booking["checkout"]["providerOrderId"]

    import json
    body = json.dumps({"providerOrderId": order_id, "providerPaymentId": "pay_webhook_1"}).encode()
    r = client.post("/api/v1/payments/razorpay/webhook", content=body)
    assert r.status_code == 200
    assert len(fake_provider.calls) == 1


# ── Content ───────────────────────────────────────────────────────────────

def test_confirmation_content_includes_booking_details(fake_provider):
    slot = _first_available_slot("badminton")
    promo = _create_free_promo()
    booking = _book(slot, promo_code=promo)

    to, subject, body = fake_provider.calls[0]
    assert to == "9812345670"
    assert booking["bookingRef"] in subject
    assert booking["bookingRef"] in body
    assert slot["sportSlug"] in body
    assert slot["date"] in body
    assert slot["startTime"] in body


# ── Failure is logged, not fatal ────────────────────────────────────────────

def test_notification_provider_failure_does_not_fail_booking():
    original = notification_service.notification_provider
    notification_service.notification_provider = _FakeProvider(raises=True)
    try:
        slot = _first_available_slot("badminton")
        promo = _create_free_promo()
        booking = _book(slot, promo_code=promo)  # must not raise / must not 500
        assert booking["status"] == "confirmed"

        logged = deps.notification_repo.get_all(ref_type="booking")
        assert len(logged) == 1
        assert logged[0].status == "failed"
        assert "provider exploded" in (logged[0].errorMessage or "")
    finally:
        notification_service.notification_provider = original


def test_smtp_provider_skips_non_email_recipient():
    provider = SmtpEmailNotificationProvider()
    result = provider.send("9812345670", "Subject", "Body")
    assert result.status == "skipped"


def test_smtp_provider_fails_cleanly_when_unconfigured(monkeypatch):
    monkeypatch.delenv("SMTP_HOST", raising=False)
    monkeypatch.delenv("SMTP_USER", raising=False)
    monkeypatch.delenv("SMTP_PASSWORD", raising=False)
    provider = SmtpEmailNotificationProvider()
    result = provider.send("someone@example.com", "Subject", "Body")
    assert result.status == "failed"


# ── Admin delivery log ───────────────────────────────────────────────────────

def test_admin_notifications_lists_sent_messages(fake_provider):
    slot = _first_available_slot("badminton")
    promo = _create_free_promo()
    booking = _book(slot, promo_code=promo)

    r = client.get("/api/v1/admin/notifications", headers=ADMIN_HEADERS)
    assert r.status_code == 200
    body = r.json()
    assert any(n["refId"] for n in body if n["status"] == "sent")

    r2 = client.get("/api/v1/admin/notifications?refType=booking", headers=ADMIN_HEADERS)
    assert all(n["refType"] == "booking" for n in r2.json())


def test_admin_notifications_requires_admin_auth():
    r = client.get("/api/v1/admin/notifications")
    assert r.status_code in (401, 403)
