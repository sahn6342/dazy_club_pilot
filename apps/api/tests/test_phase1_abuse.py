"""Phase 1 abuse controls: Turnstile, OTP-gated booking search, pending-booking cap,
WhatsApp Cloud adapter."""
import json
import re
from datetime import date, timedelta

import pytest

import deps
import services.otp_service as otp_service
import services.turnstile as turnstile
from integrations.notifications.base import NotificationResult
from integrations.notifications.whatsapp_cloud import WhatsAppCloudProvider


def _tomorrow():
    return (date.today() + timedelta(days=1)).isoformat()


def _slots(client, sport="cricket"):
    return [s for s in client.get(f"/api/v1/slots?sport={sport}&date={_tomorrow()}").json() if s["available"]]


def _body(slot, contact="9876543210", **kw):
    return {"name": "Jane", "contact": contact, "slotIds": [slot["id"]], "sportSlug": slot["sportSlug"],
            "date": slot["date"], "startTime": slot["startTime"], "players": 1, **kw}


class _Capture:
    """Stands in for a notification provider and remembers the last code sent."""
    def __init__(self):
        self.codes = []

    def send_otp(self, to, code):
        self.codes.append((to, code))
        return NotificationResult(status="sent")


@pytest.fixture
def otp_sink(monkeypatch):
    sink = _Capture()
    monkeypatch.setattr(otp_service, "notification_provider", sink)
    monkeypatch.setattr(otp_service, "whatsapp_provider", sink)
    return sink


def _verify_flow(client, contact, sink):
    assert client.post("/api/v1/otp/request", json={"contact": contact}).status_code == 200
    code = sink.codes[-1][1]
    r = client.post("/api/v1/otp/verify", json={"contact": contact, "code": code})
    assert r.status_code == 200, r.text
    return r.json()["otpToken"]


# ── pending-booking cap ────────────────────────────────────────────────────

def test_third_unpaid_booking_for_same_contact_is_refused(client):
    s = _slots(client)
    assert client.post("/api/v1/bookings", json=_body(s[0])).status_code == 201
    assert client.post("/api/v1/bookings", json=_body(s[2])).status_code == 201
    r = client.post("/api/v1/bookings", json=_body(s[4]))
    assert r.status_code == 429 and "waiting for payment" in r.json()["detail"]
    # Another contact is unaffected.
    assert client.post("/api/v1/bookings", json=_body(s[4], contact="9111111111")).status_code == 201


def test_paid_booking_does_not_count_against_cap(client):
    s = _slots(client)
    b = client.post("/api/v1/bookings", json=_body(s[0])).json()
    client.post(f"/api/v1/bookings/{b['bookingRef']}/payment/verify",
                json={"providerOrderId": b["checkout"]["providerOrderId"], "providerPaymentId": "noop_pay_1"})
    assert client.post("/api/v1/bookings", json=_body(s[2])).status_code == 201
    assert client.post("/api/v1/bookings", json=_body(s[4])).status_code == 201


# ── OTP-gated search ───────────────────────────────────────────────────────

def test_search_requires_otp(client):
    r = client.get("/api/v1/bookings/search?contact=9876543210")
    assert r.status_code == 401 and r.json()["detail"] == "otp_required"
    assert client.get("/api/v1/bookings/search?contact=9876543210",
                      headers={"X-OTP-Token": "garbage"}).status_code == 401


def test_search_after_otp_returns_only_that_contacts_bookings(client, otp_sink):
    s = _slots(client)
    client.post("/api/v1/bookings", json=_body(s[0], contact="9876543210"))
    client.post("/api/v1/bookings", json=_body(s[2], contact="9222222222"))
    tok = _verify_flow(client, "9876543210", otp_sink)
    r = client.get("/api/v1/bookings/search?contact=9876543210", headers={"X-OTP-Token": tok})
    assert r.status_code == 200 and len(r.json()) == 1


def test_search_without_otp_lists_all_bookings_newest_first_when_disabled(client, monkeypatch):
    monkeypatch.setenv("DAZY_OTP_DISABLED", "1")
    s = _slots(client)
    refs = [client.post("/api/v1/bookings", json=_body(s[i], contact="9876543210")).json()["bookingRef"] for i in (0, 2)]
    client.post("/api/v1/bookings", json=_body(s[4], contact="9222222222"))
    r = client.get("/api/v1/bookings/search?contact=9876543210")  # no OTP token
    assert r.status_code == 200
    assert [b["bookingRef"] for b in r.json()] == refs[::-1]  # newest first, other contact's booking excluded
    assert client.get("/api/v1/bookings/search?contact=not-a-contact").status_code == 422  # still validated
    monkeypatch.delenv("DAZY_OTP_DISABLED")
    assert client.get("/api/v1/bookings/search?contact=9876543210").status_code == 401  # default is closed again


def test_search_by_contact_limit_is_a_parameter():
    import uuid
    import deps
    from datetime import datetime, timezone
    from models import BookingRecord
    contact = "9333333333"
    now = datetime.now(timezone.utc).isoformat()
    deps.booking_repo.create_many([
        BookingRecord(id=str(uuid.uuid4()), bookingRef=f"LIM{i:05d}", slotId=f"limit-test-slot-{uuid.uuid4()}", name="Lim It",
                      contact=contact, sportSlug="cricket", date="2030-01-01", startTime="06:00", endTime="07:00",
                      party_size=1, status="confirmed", createdAt=f"2030-01-01T00:00:{i:02d}+00:00")
        for i in range(12)
    ])
    assert len(deps.booking_repo.search_by_contact(contact)) == 10  # the OTP-gated search keeps its cap
    wide = deps.booking_repo.search_by_contact(contact, limit=200)
    assert len(wide) == 12 and wide[0].bookingRef == "LIM00011"  # newest first


def test_otp_token_is_bound_to_its_contact(client, otp_sink):
    tok = _verify_flow(client, "9876543210", otp_sink)
    r = client.get("/api/v1/bookings/search?contact=9222222222", headers={"X-OTP-Token": tok})
    assert r.status_code == 403


def test_email_otp_goes_to_email_and_phone_otp_to_whatsapp(client, monkeypatch):
    mail, wa = _Capture(), _Capture()
    monkeypatch.setattr(otp_service, "notification_provider", mail)
    monkeypatch.setattr(otp_service, "whatsapp_provider", wa)
    assert client.post("/api/v1/otp/request", json={"contact": "Jane@Example.com"}).json()["channel"] == "email"
    assert client.post("/api/v1/otp/request", json={"contact": "9876543210"}).json()["channel"] == "whatsapp"
    assert mail.codes[0][0] == "jane@example.com" and wa.codes[0][0] == "9876543210"
    assert re.fullmatch(r"\d{6}", mail.codes[0][1])


def test_otp_wrong_code_lockout_and_single_use(client, otp_sink):
    client.post("/api/v1/otp/request", json={"contact": "9876543210"})
    good = otp_sink.codes[-1][1]
    bad = "000000" if good != "000000" else "111111"
    for _ in range(5):
        assert client.post("/api/v1/otp/verify", json={"contact": "9876543210", "code": bad}).status_code == 400
    # After 5 wrong guesses even the right code is dead; a fresh code is needed.
    assert client.post("/api/v1/otp/verify", json={"contact": "9876543210", "code": good}).status_code == 400
    client.post("/api/v1/otp/request", json={"contact": "9876543210"})
    fresh = otp_sink.codes[-1][1]
    assert client.post("/api/v1/otp/verify", json={"contact": "9876543210", "code": fresh}).status_code == 200
    assert client.post("/api/v1/otp/verify", json={"contact": "9876543210", "code": fresh}).status_code == 400  # burnt


def test_otp_expires(client, otp_sink, monkeypatch):
    client.post("/api/v1/otp/request", json={"contact": "9876543210"})
    code = otp_sink.codes[-1][1]
    real = otp_service.time.time
    monkeypatch.setattr(otp_service.time, "time", lambda: real() + otp_service.OTP_TTL_SECONDS + 5)
    assert client.post("/api/v1/otp/verify", json={"contact": "9876543210", "code": code}).status_code == 400


def test_otp_code_is_never_stored_in_plaintext(client, otp_sink):
    client.post("/api/v1/otp/request", json={"contact": "9876543210"})
    code = otp_sink.codes[-1][1]
    from db import _session
    from db_models import OtpCodeRow, NotificationMessageRow
    with _session() as s:
        row = s.query(OtpCodeRow).one()
        assert code not in row.code_hash and len(row.code_hash) == 64
        logged = s.query(NotificationMessageRow).all()
        assert all(code not in (m.errorMessage or "") for m in logged)


def test_otp_request_validates_contact_and_is_rate_limited(client, otp_sink):
    assert client.post("/api/v1/otp/request", json={"contact": "not-a-contact"}).status_code == 422
    codes = [client.post("/api/v1/otp/request", json={"contact": "9876543210"}).status_code for _ in range(6)]
    assert codes[:5] == [200] * 5 and codes[5] == 429


# ── Turnstile ──────────────────────────────────────────────────────────────

def test_turnstile_skipped_when_unconfigured(client):
    s = _slots(client)
    assert client.post("/api/v1/bookings", json=_body(s[0])).status_code == 201


def test_turnstile_enforced_on_booking_enquiry_and_otp(client, monkeypatch):
    monkeypatch.setenv("TURNSTILE_SECRET", "secret")
    monkeypatch.setattr(turnstile, "_siteverify", lambda secret, token, ip: token == "good-token")
    s = _slots(client)
    assert client.post("/api/v1/bookings", json=_body(s[0])).status_code == 400  # missing token
    assert client.post("/api/v1/bookings", json=_body(s[0], turnstileToken="bad")).status_code == 400
    assert client.post("/api/v1/bookings", json=_body(s[0], turnstileToken="good-token")).status_code == 201

    enquiry = {"name": "A B", "contact": "9000000001", "message": "hello there"}
    assert client.post("/api/v1/contact-enquiries", json=enquiry).status_code == 400
    assert client.post("/api/v1/contact-enquiries", json={**enquiry, "turnstileToken": "good-token"}).status_code == 201

    assert client.post("/api/v1/otp/request", json={"contact": "9876543210"}).status_code == 400
    assert client.post("/api/v1/otp/request", json={"contact": "9876543210", "turnstileToken": "good-token"}).status_code == 200


def test_turnstile_can_be_disabled_explicitly(client, monkeypatch):
    monkeypatch.setenv("TURNSTILE_SECRET", "secret")
    monkeypatch.setattr(turnstile, "_siteverify", lambda secret, token, ip: False)  # would reject everything
    s = _slots(client)
    assert client.post("/api/v1/bookings", json=_body(s[0])).status_code == 400
    monkeypatch.setenv("DAZY_TURNSTILE_DISABLED", "1")
    assert turnstile.turnstile_disabled() and not turnstile.turnstile_enabled()
    assert client.post("/api/v1/bookings", json=_body(s[0])).status_code == 201
    assert client.post("/api/v1/otp/request", json={"contact": "9876543210"}).status_code == 200


def test_turnstile_fails_closed_when_cloudflare_unreachable(monkeypatch):
    import urllib.request
    monkeypatch.setenv("TURNSTILE_SECRET", "secret")

    def boom(*a, **k):
        raise OSError("network down")
    monkeypatch.setattr(urllib.request, "urlopen", boom)
    with pytest.raises(Exception) as ei:
        turnstile.require_turnstile("any-token", "1.2.3.4")
    assert getattr(ei.value, "status_code", None) == 400


# ── WhatsApp Cloud adapter (mocked transport) ──────────────────────────────

def _cloud(monkeypatch, **env):
    base = {"WHATSAPP_CLOUD_TOKEN": "tok", "WHATSAPP_CLOUD_PHONE_ID": "123", "WHATSAPP_OTP_TEMPLATE": "otp_tpl"}
    for k, v in {**base, **env}.items():
        monkeypatch.setenv(k, v)
    return WhatsAppCloudProvider()


def test_whatsapp_cloud_otp_sends_template_to_country_prefixed_number(monkeypatch):
    sent = {}

    class _Resp:
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def read(self): return json.dumps({"messages": [{"id": "wamid.1"}]}).encode()

    def fake_urlopen(req, timeout=0):
        sent["url"], sent["auth"], sent["body"] = req.full_url, req.headers["Authorization"], json.loads(req.data)
        return _Resp()

    import urllib.request
    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    res = _cloud(monkeypatch).send_otp("9876543210", "123456")
    assert res.status == "sent" and res.detail == "wamid.1"
    assert sent["url"].endswith("/123/messages") and sent["auth"] == "Bearer tok"
    assert sent["body"]["to"] == "919876543210" and sent["body"]["type"] == "template"
    assert sent["body"]["template"]["name"] == "otp_tpl"
    assert sent["body"]["template"]["components"][0]["parameters"][0]["text"] == "123456"


def test_whatsapp_cloud_reports_misconfiguration_without_raising(monkeypatch):
    monkeypatch.delenv("WHATSAPP_OTP_TEMPLATE", raising=False)
    p = WhatsAppCloudProvider.__new__(WhatsAppCloudProvider)
    p.__init__()
    assert p.send_otp("9876543210", "123456").status == "failed"
    assert _cloud(monkeypatch).send("a@b.com", "s", "b").status == "skipped"


def test_factory_selects_whatsapp_cloud(monkeypatch):
    from integrations.notifications.factory import get_whatsapp_provider
    monkeypatch.setenv("DAZY_NOTIFY_WHATSAPP_PROVIDER", "whatsapp_cloud")
    assert get_whatsapp_provider().name == "whatsapp_cloud"
    monkeypatch.delenv("DAZY_NOTIFY_WHATSAPP_PROVIDER")
    assert get_whatsapp_provider().name == "whatsapp_stub"
