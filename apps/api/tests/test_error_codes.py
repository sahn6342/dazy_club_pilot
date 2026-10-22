"""Booking and payment errors carry a machine-readable `code` next to the (unchanged) `detail`, and a payment
gateway outage of any kind is a clean 503 instead of a 500."""
import logging
import socket
import urllib.error
from datetime import date, timedelta

import pytest

from errors import ApiError
from integrations.payments.razorpay import RazorpayPaymentProvider
from rate_limit import SlidingWindowLimiter
from routes import bookings as bookings_routes


def _day() -> str:
    return (date.today() + timedelta(days=1)).isoformat()


def _slots(client, sport="cricket"):
    return [s for s in client.get(f"/api/v1/slots?sport={sport}&date={_day()}").json() if s["available"]]


def _body(slot, contact="9876543210", **kw):
    return {"name": "Jane", "contact": contact, "slotIds": [slot["id"]], "sportSlug": slot["sportSlug"],
            "date": slot["date"], "startTime": slot["startTime"], "players": 1, **kw}


def _err(r):
    return r.json()["detail"], r.json().get("code")


# ── create booking ──────────────────────────────────────────────────────────

def test_unknown_slot_is_slot_not_found(client):
    s = _slots(client)[0]
    r = client.post("/api/v1/bookings", json=_body({**s, "id": "slot-court-cricket-2999-01-01-0600"}))
    assert r.status_code == 404 and _err(r) == ("Slot slot-court-cricket-2999-01-01-0600 not found.", "slot_not_found")


def test_taken_slot_is_slot_unavailable(client):
    s = _slots(client)[0]
    assert client.post("/api/v1/bookings", json=_body(s)).status_code == 201
    r = client.post("/api/v1/bookings", json=_body(s, contact="9111111111"))
    assert r.status_code == 409 and r.json()["code"] == "slot_unavailable" and "unavailable" in r.json()["detail"]


def test_non_consecutive_slots_have_a_code(client):
    s = _slots(client)
    r = client.post("/api/v1/bookings", json={**_body(s[0]), "slotIds": [s[0]["id"], s[3]["id"]]})
    assert r.status_code == 400 and r.json()["code"] == "slots_not_consecutive"


def test_pending_cap_and_promo_errors_have_codes(client):
    s = _slots(client)
    assert client.post("/api/v1/bookings", json=_body(s[0])).status_code == 201
    assert client.post("/api/v1/bookings", json=_body(s[2])).status_code == 201
    r = client.post("/api/v1/bookings", json=_body(s[4]))
    assert r.status_code == 429 and r.json()["code"] == "pending_cap"
    r = client.post("/api/v1/bookings", json=_body(s[4], contact="9222222222", promoCode="NOPE-NOT-A-CODE"))
    assert r.status_code == 400 and r.json()["code"] == "promo_invalid"


def test_turnstile_failure_has_a_code(client, monkeypatch):
    from services import turnstile
    monkeypatch.setenv("TURNSTILE_SECRET", "secret")
    monkeypatch.setattr(turnstile, "_siteverify", lambda *a: False)
    r = client.post("/api/v1/bookings", json=_body(_slots(client)[0]))
    assert r.status_code == 400 and r.json()["code"] == "verification_required"


def test_rate_limit_has_a_code():
    limiter = SlidingWindowLimiter("codes_test", limit=1, window_seconds=60)
    limiter.check("k")
    with pytest.raises(ApiError) as ei:
        limiter.check("k", "Slow down.")
    assert (ei.value.status_code, ei.value.detail, ei.value.code) == (429, "Slow down.", "rate_limited")


# ── gateway outage ──────────────────────────────────────────────────────────

class _DownGateway:
    name = "razorpay"

    def create_order(self, amount, ref):
        raise RuntimeError("Razorpay API unreachable: [Errno 11001] getaddrinfo failed")


def test_gateway_outage_is_a_503_with_a_code_is_logged_and_releases_the_promo(client, auth_headers, monkeypatch, caplog):
    monkeypatch.setattr(bookings_routes, "payment_provider", _DownGateway())
    used = lambda: next(p for p in client.get("/api/v1/admin/promos", headers=auth_headers).json() if p["code"] == "WELCOME10")["used_count"]  # noqa: E731
    before = used()
    with caplog.at_level(logging.WARNING, logger="routes.bookings"):
        r = client.post("/api/v1/bookings", json=_body(_slots(client)[0], promoCode="WELCOME10"))
    assert r.status_code == 503
    assert r.json() == {"detail": "Payment gateway unavailable — please try again.", "code": "payment_unavailable"}
    assert used() == before  # the promo use taken for this attempt was handed back
    assert any("Razorpay API unreachable" in rec.getMessage() for rec in caplog.records)  # the operator can see why
    # nothing was booked
    assert _slots(client)[0]["available"] is True


@pytest.mark.parametrize("failure", [
    urllib.error.URLError("getaddrinfo failed"),
    socket.timeout("timed out"),
    ConnectionResetError("reset by peer"),
])
def test_razorpay_network_failures_become_runtime_errors(monkeypatch, failure):
    monkeypatch.setenv("RAZORPAY_KEY_ID", "k")
    monkeypatch.setenv("RAZORPAY_KEY_SECRET", "s")

    def boom(*a, **k):
        raise failure
    monkeypatch.setattr("urllib.request.urlopen", boom)
    with pytest.raises(RuntimeError, match="unreachable"):
        RazorpayPaymentProvider().create_order(amount=100.0, ref="ABCD1234")


def test_razorpay_http_errors_still_become_runtime_errors(monkeypatch):
    import io
    monkeypatch.setenv("RAZORPAY_KEY_ID", "k")
    monkeypatch.setenv("RAZORPAY_KEY_SECRET", "s")

    def boom(*a, **k):
        raise urllib.error.HTTPError("https://api.razorpay.com", 401, "Unauthorized", {}, io.BytesIO(b'{"error":"bad keys"}'))
    monkeypatch.setattr("urllib.request.urlopen", boom)
    with pytest.raises(RuntimeError, match="Razorpay API error 401"):
        RazorpayPaymentProvider().create_order(amount=100.0, ref="ABCD1234")


# ── verify, lookup, search ──────────────────────────────────────────────────

def test_verify_lookup_and_search_errors_have_codes(client):
    r = client.post("/api/v1/bookings/NOSUCHREF/payment/verify", json={"providerOrderId": "o", "providerPaymentId": "p"})
    assert r.status_code == 404 and r.json()["code"] == "booking_not_found"

    s = _slots(client)[0]
    ref = client.post("/api/v1/bookings", json=_body(s)).json()["bookingRef"]
    r = client.get(f"/api/v1/bookings/lookup?ref={ref}&contact=0000000000")
    assert r.status_code == 404 and r.json() == {"detail": "Booking not found.", "code": "booking_not_found"}

    r = client.get("/api/v1/bookings/search?contact=9876543210")
    assert r.status_code == 401 and r.json() == {"detail": "otp_required", "code": "otp_required"}
    assert client.get("/api/v1/bookings/search?contact=nope").json()["code"] == "contact_invalid"


def test_other_errors_keep_the_default_shape(client):
    """Errors without a code (validation) are unchanged, so existing clients are unaffected."""
    r = client.post("/api/v1/bookings", json={"name": "x"})
    assert r.status_code == 422 and isinstance(r.json()["detail"], list) and "code" not in r.json()
