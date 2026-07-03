"""
Self-service booking lookup/resume (growth-track F2-style, built after a real
UX bug: a pending payment was silently unrecoverable if a customer closed the
tab). Covers: pending booking resumes with the SAME checkout order (never a
second Razorpay order), confirmed booking shows details with no checkout,
wrong contact / unknown ref return a generic 404 (no enumeration), rate
limiting, and a payment-pending notification fires once at booking creation.
"""
import json

import pytest
from starlette.testclient import TestClient

from main import app
from auth import create_access_token
from rate_limit import booking_lookup_limiter
import services.notification_service as notification_service
from integrations.notifications.base import NotificationProvider, NotificationResult

client = TestClient(app)
ADMIN_HEADERS = {"Authorization": "Bearer " + create_access_token("admin", "admin")}


class _FakeProvider(NotificationProvider):
    name = "fake"

    def __init__(self):
        self.calls = []

    def send(self, to, subject, body):
        self.calls.append((to, subject, body))
        return NotificationResult(status="sent")


@pytest.fixture()
def fake_provider():
    original = notification_service.notification_provider
    fake = _FakeProvider()
    notification_service.notification_provider = fake
    yield fake
    notification_service.notification_provider = original


def _get_priced_slot(sport="cricket"):
    r = client.get(f"/api/v1/slots?sport={sport}")
    return next(s for s in r.json() if s["available"] and s["finalPrice"])


def _book(slot, contact="9812399001"):
    body = {
        "name": "Lookup Test", "contact": contact, "sportSlug": slot["sportSlug"],
        "date": slot["date"], "startTime": slot["startTime"], "slotIds": [slot["id"]], "players": 1,
    }
    r = client.post("/api/v1/bookings", json=body)
    assert r.status_code == 201
    return r.json()


def test_lookup_pending_booking_reuses_the_same_checkout_order():
    slot = _get_priced_slot()
    booking = _book(slot, contact="9812399001")

    r = client.get(f"/api/v1/bookings/lookup?ref={booking['bookingRef']}&contact=9812399001")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "pending"
    assert body["paymentRequired"] is True
    assert body["checkout"]["providerOrderId"] == booking["checkout"]["providerOrderId"]


def test_lookup_confirmed_booking_has_no_checkout():
    slot = _get_priced_slot("badminton")
    # Free it via a 100%-off promo so it auto-confirms with no payment step.
    promo_code = "LOOKUPFREE"
    client.post("/api/v1/admin/promos", json={
        "code": promo_code, "kind": "percent", "value": 100, "active": True,
        "valid_from": None, "valid_to": None, "max_uses": None, "sport_slug": None,
    }, headers=ADMIN_HEADERS)
    body_req = {
        "name": "Lookup Confirmed", "contact": "9812399002", "sportSlug": slot["sportSlug"],
        "date": slot["date"], "startTime": slot["startTime"], "slotIds": [slot["id"]], "players": 1,
        "promoCode": promo_code,
    }
    booking = client.post("/api/v1/bookings", json=body_req).json()
    assert booking["status"] == "confirmed"

    r = client.get(f"/api/v1/bookings/lookup?ref={booking['bookingRef']}&contact=9812399002")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "confirmed"
    assert body["paymentRequired"] is False
    assert body["checkout"] is None


def test_lookup_wrong_contact_returns_404():
    slot = _get_priced_slot("pickleball")
    booking = _book(slot, contact="9812399003")
    r = client.get(f"/api/v1/bookings/lookup?ref={booking['bookingRef']}&contact=0000000000")
    assert r.status_code == 404


def test_lookup_unknown_ref_returns_404():
    r = client.get("/api/v1/bookings/lookup?ref=NOSUCHREF&contact=9812399003")
    assert r.status_code == 404


def test_lookup_is_rate_limited():
    booking_lookup_limiter.clear()
    for _ in range(10):
        client.get("/api/v1/bookings/lookup?ref=X&contact=Y")
    r = client.get("/api/v1/bookings/lookup?ref=X&contact=Y")
    assert r.status_code == 429


def test_priced_booking_sends_one_payment_pending_notification(fake_provider):
    slot = _get_priced_slot("cricket")
    booking = _book(slot, contact="9812399004")

    assert len(fake_provider.calls) == 1
    to, subject, body = fake_provider.calls[0]
    assert to == "9812399004"
    assert booking["bookingRef"] in subject
    assert booking["bookingRef"] in body
    assert "/my-bookings?ref=" in body
