"""Workstream F: notification outbox, retries with backoff, manual resend, WhatsApp/SMS templates and the
provider adapters. Everything runs against fakes and mocked HTTP: no vendor account is involved."""
import io
import json
import logging
import smtplib
import socket
import urllib.error
import uuid
from datetime import date, datetime, timedelta, timezone

import pytest

import deps
import services.notification_service as ns
from integrations.notifications.base import NotificationResult
from integrations.notifications.email_smtp import SmtpEmailNotificationProvider
from integrations.notifications.sms_msg91 import Msg91SmsProvider
from integrations.notifications.whatsapp_cloud import WhatsAppCloudProvider
from services import notification_templates as tpl

T0 = datetime.now(timezone.utc)  # reset by the `clock` fixture; the retry logic compares against real row timestamps


class Chan:
    """A fake provider that records calls and plays back queued results."""
    def __init__(self, name="fake", results=None):
        self.name, self.results, self.send_calls, self.template_calls = name, list(results or []), [], []
        self.during = None   # callback run while the provider is "sending"

    def _next(self):
        return self.results.pop(0) if self.results else NotificationResult(status="sent", detail="msg-1")

    def send(self, to, subject, body):
        self.send_calls.append((to, subject, body))
        if self.during:
            self.during()
        r = self._next()
        if isinstance(r, Exception):
            raise r
        return r

    def send_template(self, to, event, params, subject, body):
        self.template_calls.append((to, event, params, subject, body))
        if self.during:
            self.during()
        r = self._next()
        if isinstance(r, Exception):
            raise r
        return r


def OK(ref="wamid-1"):
    return NotificationResult(status="sent", detail=ref)


def TRANSIENT(msg="HTTP 503"):
    return NotificationResult(status="failed", detail=msg, retryable=True)


def PERMANENT(msg="HTTP 400 bad number"):
    return NotificationResult(status="failed", detail=msg, retryable=False)


@pytest.fixture
def fakes(monkeypatch):
    f = {"email": Chan("email_fake"), "sms": Chan("sms_fake"), "whatsapp": Chan("wa_fake")}
    monkeypatch.setattr(ns, "notification_provider", f["email"])
    monkeypatch.setattr(ns, "sms_provider", f["sms"])
    monkeypatch.setattr(ns, "whatsapp_provider", f["whatsapp"])
    return f


@pytest.fixture
def clock(monkeypatch):
    global T0
    T0 = datetime.now(timezone.utc)
    state = {"now": T0}
    monkeypatch.setattr(ns, "_now", lambda: state["now"])
    return state


def _send(channel="sms", ref_id=None, event="booking_refunded", provider=None, to="9876543210"):  # refunded: always still relevant
    ref_id = ref_id or str(uuid.uuid4())
    ns.send_and_log("booking", ref_id, channel, to, "Subject", "Body text", provider=provider, event=event, params=["Jane", "AB12CD34"])
    return next(r for r in deps.notification_repo.query(ref_id=ref_id)[0])


def _row(row_id):
    return deps.notification_repo.get(row_id)[0]


# ── outbox basics ──────────────────────────────────────────────────────────

def test_a_sent_message_is_stored_with_everything_needed_to_send_it_again(fakes):
    fakes["sms"].results = [OK("sms-77")]
    row = _send("sms", event="booking_confirmed")
    assert (row.status, row.attempts, row.event, row.provider, row.providerRef) == ("sent", 1, "booking_confirmed", "sms_fake", "sms-77")
    stored = json.loads(deps.notification_repo.get(row.id)[1])
    assert stored == {"subject": "Subject", "body": "Body text", "params": ["Jane", "AB12CD34"]}
    assert row.lastAttemptAt and row.nextAttemptAt is None


def test_the_row_exists_before_the_provider_is_called(fakes):
    seen = {}
    fakes["sms"].during = lambda: seen.update(rows=[r.status for r in deps.notification_repo.query()[0]])
    _send("sms")
    assert seen["rows"] == ["sending"]  # a crash mid-send would leave a trace, not nothing


def test_email_uses_send_and_phone_channels_use_templates(fakes):
    _send("email", to="a@example.com", event="booking_confirmed")
    _send("whatsapp", event="booking_confirmed")
    assert len(fakes["email"].send_calls) == 1 and fakes["email"].template_calls == []
    assert fakes["whatsapp"].template_calls[0][:3] == ("9876543210", "booking_confirmed", ["Jane", "AB12CD34"])


def test_a_skipped_message_is_recorded_and_never_retried(fakes, clock):
    fakes["whatsapp"].results = [NotificationResult(status="skipped", detail="No WhatsApp template configured")]
    row = _send("whatsapp")
    assert row.status == "skipped" and "template" in row.errorMessage
    clock["now"] = T0 + timedelta(hours=2)
    assert ns.retry_due_notifications()["attempted"] == 0


def test_otp_rows_have_no_payload_and_cannot_be_resent():
    row = deps.notification_repo.record("otp", "hash", "whatsapp", "9876543210", "failed", "boom")
    assert deps.notification_repo.get(row.id)[1] is None
    assert row.resendable is False
    assert deps.notification_repo.claim_for_resend(row.id) is False


# ── failure classification and backoff ─────────────────────────────────────

def test_a_permanent_failure_is_final_immediately(fakes):
    fakes["sms"].results = [PERMANENT()]
    row = _send("sms")
    assert (row.status, row.attempts, row.nextAttemptAt) == ("failed", 1, None) and "bad number" in row.errorMessage


def test_a_transient_failure_is_queued_two_minutes_out(fakes, clock):
    fakes["sms"].results = [TRANSIENT()]
    row = _send("sms")
    assert row.status == "retrying" and row.attempts == 1
    assert datetime.fromisoformat(row.nextAttemptAt) == T0 + timedelta(minutes=2)


def test_a_provider_that_raises_is_treated_as_transient(fakes):
    fakes["sms"].results = [RuntimeError("socket exploded")]
    row = _send("sms")
    assert row.status == "retrying" and "socket exploded" in row.errorMessage


def test_full_retry_ladder_two_minutes_then_ten_then_give_up(fakes, clock):
    fakes["sms"].results = [TRANSIENT("attempt 1"), TRANSIENT("attempt 2"), TRANSIENT("attempt 3")]
    row = _send("sms")                                            # attempt 1 fails -> retry at +2 min
    assert ns.retry_due_notifications()["attempted"] == 0         # not due yet
    clock["now"] = T0 + timedelta(minutes=3)
    out = ns.retry_due_notifications()                            # attempt 2 fails -> retry at +10 min
    assert (out["attempted"], out["retrying"]) == (1, 1)
    r2 = _row(row.id)
    assert r2.attempts == 2 and datetime.fromisoformat(r2.nextAttemptAt) == clock["now"] + timedelta(minutes=10)
    clock["now"] += timedelta(minutes=5)
    assert ns.retry_due_notifications()["attempted"] == 0         # still waiting
    clock["now"] += timedelta(minutes=6)
    out = ns.retry_due_notifications()                            # attempt 3 fails -> final
    assert (out["attempted"], out["failed"]) == (1, 1)
    r3 = _row(row.id)
    assert (r3.status, r3.attempts, r3.nextAttemptAt) == ("failed", 3, None) and "attempt 3" in r3.errorMessage
    clock["now"] += timedelta(hours=1)
    assert ns.retry_due_notifications()["attempted"] == 0         # never again on its own
    assert len(fakes["sms"].template_calls) == 3


def test_a_retry_that_succeeds_clears_the_error(fakes, clock):
    fakes["whatsapp"].results = [TRANSIENT(), OK("wamid-late")]
    row = _send("whatsapp")
    clock["now"] = T0 + timedelta(minutes=3)
    assert ns.retry_due_notifications()["sent"] == 1
    done = _row(row.id)
    assert (done.status, done.attempts, done.providerRef, done.errorMessage) == ("sent", 2, "wamid-late", None)


def test_a_retry_that_turns_permanent_stops_early(fakes, clock):
    fakes["sms"].results = [TRANSIENT(), PERMANENT("number invalid")]
    row = _send("sms")
    clock["now"] = T0 + timedelta(minutes=3)
    ns.retry_due_notifications()
    assert (_row(row.id).status, _row(row.id).attempts) == ("failed", 2)


# ── relevance and age ──────────────────────────────────────────────────────

def _tomorrow():
    return (date.today() + timedelta(days=1)).isoformat()


def _book(client):
    slot = [s for s in client.get(f"/api/v1/slots?sport=cricket&date={_tomorrow()}").json() if s["available"]][0]
    r = client.post("/api/v1/bookings", json={"name": "Jane", "contact": "9876543210", "slotIds": [slot["id"]], "sportSlug": "cricket",
                                              "date": slot["date"], "startTime": slot["startTime"], "players": 1})
    assert r.status_code == 201, r.text
    return r.json()


def _admin_id(client, auth_headers, ref):
    items = client.get("/api/v1/admin/bookings?limit=100", headers=auth_headers).json()["items"]
    return next(b["id"] for b in items if b["bookingRef"] == ref)


def _queue_retry(fakes, clock, event, booking_id, channel="sms"):
    fakes[channel].results = [TRANSIENT()]
    row = _send(channel, ref_id=booking_id, event=event)
    clock["now"] = T0 + timedelta(minutes=3)
    return row


def test_a_payment_reminder_is_dropped_once_the_booking_is_paid(client, auth_headers, fakes, clock):
    b = _book(client)
    bid = _admin_id(client, auth_headers, b["bookingRef"])
    row = _queue_retry(fakes, clock, "booking_pending", bid)
    client.post(f"/api/v1/bookings/{b['bookingRef']}/payment/verify", json={
        "providerOrderId": b["checkout"]["providerOrderId"], "providerPaymentId": "noop_pay_x"})
    fakes["sms"].template_calls.clear()
    assert ns.retry_due_notifications()["skipped"] == 1
    r = _row(row.id)
    assert r.status == "skipped" and "no longer relevant" in r.errorMessage and fakes["sms"].template_calls == []


def test_a_pending_reminder_still_goes_out_while_the_booking_is_pending(client, auth_headers, fakes, clock):
    b = _book(client)
    row = _queue_retry(fakes, clock, "booking_pending", _admin_id(client, auth_headers, b["bookingRef"]))
    assert ns.retry_due_notifications()["sent"] == 1 and _row(row.id).status == "sent"


def test_a_confirmation_is_dropped_if_the_booking_was_cancelled_meanwhile(client, auth_headers, fakes, clock):
    b = _book(client)
    bid = _admin_id(client, auth_headers, b["bookingRef"])
    row = _queue_retry(fakes, clock, "booking_confirmed", bid)
    client.patch(f"/api/v1/admin/bookings/{bid}", json={"status": "cancelled"}, headers=auth_headers)
    ns.retry_due_notifications()
    assert _row(row.id).status == "skipped"


def test_a_refund_notice_is_always_still_true(fakes, clock):
    row = _queue_retry(fakes, clock, "booking_refunded", "booking-id-that-is-gone")
    assert ns.retry_due_notifications()["sent"] == 1 and _row(row.id).status == "sent"


def test_a_booking_that_no_longer_exists_makes_a_reminder_moot(fakes, clock):
    row = _queue_retry(fakes, clock, "booking_confirmed", "no-such-booking")
    ns.retry_due_notifications()
    assert "no longer exists" in _row(row.id).errorMessage


def test_messages_older_than_a_day_are_abandoned(fakes, clock):
    row = _queue_retry(fakes, clock, "booking_refunded", "b1")
    clock["now"] = datetime.now(timezone.utc) + timedelta(hours=25)
    out = ns.retry_due_notifications()
    assert out["failed"] == 1 and "older than 24 h" in _row(row.id).errorMessage


# ── claiming and crash recovery ────────────────────────────────────────────

def test_claiming_is_atomic_two_sweeps_cannot_take_the_same_retry(fakes, clock):
    fakes["sms"].results = [TRANSIENT()]
    row = _send("sms")
    now = (T0 + timedelta(minutes=3)).isoformat()
    first = deps.notification_repo.claim_due(now)
    second = deps.notification_repo.claim_due(now)
    assert [c.id for c in first] == [row.id] and second == []
    assert first[0].attempts == 2 and _row(row.id).status == "sending"


def test_rescue_requeues_only_stuck_rows_that_have_a_payload(fakes, clock):
    repo = deps.notification_repo
    stuck = repo.create_attempt("booking", "r1", "sms", "9876543210", "booking_confirmed", "{}", "p")
    fresh = repo.create_attempt("booking", "r2", "sms", "9876543210", "booking_confirmed", "{}", "p")
    from db import _session
    from db_models import NotificationMessageRow
    old = (datetime.now(timezone.utc) - timedelta(minutes=30)).isoformat()
    with _session() as s:
        s.query(NotificationMessageRow).filter(NotificationMessageRow.id == stuck).update({"last_attempt_at": old})
        s.add(NotificationMessageRow(id="otp-stuck", refType="otp", refId="h", channel="sms", recipient="x", status="sending",
                                     createdAt=old, last_attempt_at=old))
    assert repo.rescue_stuck((datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat()) == 1
    assert _row(stuck).status == "retrying" and _row(fresh).status == "sending" and _row("otp-stuck").status == "sending"


def test_sweep_rescues_then_retries_in_one_go(fakes, clock):
    from db import _session
    from db_models import NotificationMessageRow
    stuck = deps.notification_repo.create_attempt("booking", "r1", "sms", "9876543210", "booking_refunded",
                                                  json.dumps({"subject": "s", "body": "b", "params": []}), "p")
    with _session() as s:
        s.query(NotificationMessageRow).filter(NotificationMessageRow.id == stuck).update(
            {"last_attempt_at": (T0 - timedelta(minutes=30)).isoformat()})
    clock["now"] = T0 + timedelta(minutes=1)
    out = ns.retry_due_notifications()
    assert out["rescued"] == 1 and out["sent"] == 1 and _row(stuck).status == "sent"


# ── manual resend ──────────────────────────────────────────────────────────

def test_admin_can_resend_a_failed_message(client, auth_headers, fakes):
    fakes["whatsapp"].results = [PERMANENT("131026 undeliverable")]
    row = _send("whatsapp")
    assert row.status == "failed" and row.resendable is True
    fakes["whatsapp"].results = [OK("wamid-manual")]
    r = client.post(f"/api/v1/admin/notifications/{row.id}/resend", headers=auth_headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert (body["status"], body["attempts"], body["providerRef"]) == ("sent", 2, "wamid-manual")
    audit_row = deps.audit_repo.query(action="notification.resend")[0][0]
    d = json.loads(audit_row.detail)
    assert d["outcome"] == "sent" and d["recipient"] == "98****3210" and audit_row.actor == "admin"


def test_a_failed_manual_resend_is_reported_not_requeued(client, auth_headers, fakes):
    fakes["sms"].results = [PERMANENT("first"), TRANSIENT("gateway down")]
    row = _send("sms")
    r = client.post(f"/api/v1/admin/notifications/{row.id}/resend", headers=auth_headers).json()
    assert r["status"] == "failed" and "gateway down" in r["errorMessage"] and r["nextAttemptAt"] is None


def test_resend_ignores_relevance_because_a_human_decided(client, auth_headers, fakes):
    fakes["sms"].results = [PERMANENT()]
    row = _send("sms", ref_id="gone-booking", event="booking_confirmed")
    assert client.post(f"/api/v1/admin/notifications/{row.id}/resend", headers=auth_headers).json()["status"] == "sent"


def test_resend_is_refused_for_sent_unknown_and_payloadless_rows(client, auth_headers, fakes):
    sent = _send("sms")
    assert sent.status == "sent"
    assert client.post(f"/api/v1/admin/notifications/{sent.id}/resend", headers=auth_headers).status_code == 409
    assert client.post("/api/v1/admin/notifications/nope/resend", headers=auth_headers).status_code == 404
    otp = deps.notification_repo.record("otp", "h", "sms", "x", "failed", "boom")
    assert client.post(f"/api/v1/admin/notifications/{otp.id}/resend", headers=auth_headers).status_code == 409


def test_resend_needs_an_admin(client, fakes):
    row = _send("sms")
    client.cookies.clear()
    assert client.post(f"/api/v1/admin/notifications/{row.id}/resend").status_code == 401


# ── the admin log ──────────────────────────────────────────────────────────

def test_log_filters_pagination_and_no_message_bodies(client, auth_headers, fakes):
    fakes["sms"].results = [PERMANENT(), OK(), TRANSIENT()]
    _send("sms"), _send("sms"), _send("sms")
    fakes["whatsapp"].results = [OK()]
    _send("whatsapp")
    base = "/api/v1/admin/notifications"
    all_ = client.get(f"{base}?limit=200", headers=auth_headers)
    assert all_.headers["x-total-count"] == "4" and len(all_.json()) == 4
    assert {r["status"] for r in all_.json()} == {"failed", "sent", "retrying"}
    assert len(client.get(f"{base}?status=failed", headers=auth_headers).json()) == 1
    assert len(client.get(f"{base}?channel=whatsapp", headers=auth_headers).json()) == 1
    page = client.get(f"{base}?limit=2&offset=2", headers=auth_headers)
    assert len(page.json()) == 2 and page.headers["x-total-count"] == "4"
    leaked = json.dumps(all_.json())
    assert "Body text" not in leaked and "payload" not in leaked and "Jane" not in leaked


# ── scheduler integration ──────────────────────────────────────────────────

def test_the_sweep_endpoint_runs_retries(client, fakes, monkeypatch):
    monkeypatch.setenv("DAZY_INTERNAL_TOKEN", "sweep-tok")
    fakes["sms"].results = [TRANSIENT()]
    row = _send("sms")
    from db import _session
    from db_models import NotificationMessageRow
    with _session() as s:
        s.query(NotificationMessageRow).filter(NotificationMessageRow.id == row.id).update(
            {"next_attempt_at": (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()})
    r = client.post("/api/v1/internal/sweep", headers={"X-Internal-Token": "sweep-tok"})
    assert r.status_code == 200 and r.json()["notifications"]["sent"] == 1
    assert _row(row.id).status == "sent"


# ── per-event routing ──────────────────────────────────────────────────────

class _B:
    id, bookingRef, name, sportSlug, date = "bid-1", "AB12CD34", "Jane", "cricket", "2030-02-03"
    startTime, endTime, price, party_size = "06:00", "07:00", 1200.0, 2
    status, deleted_at = "confirmed", None


def _booking(**kw):
    b = _B()
    b.email, b.contact = kw.get("email"), kw.get("contact", "9876543210")
    return b


def _run(fakes, monkeypatch, booking, fn, *args, **kw):
    monkeypatch.setattr(ns, "_primary", lambda ref: booking)
    fn("AB12CD34", *args, **kw)


def test_confirmation_goes_to_every_channel_the_contact_supports(fakes, monkeypatch):
    _run(fakes, monkeypatch, _booking(email="jane@example.com"), ns.notify_booking_confirmed)
    assert len(fakes["email"].send_calls) == 1
    assert fakes["sms"].template_calls[0][1:3] == ("booking_confirmed", ["Jane", "AB12CD34", "Cricket", "2030-02-03", "06:00-07:00"])
    assert fakes["whatsapp"].template_calls[0][1] == "booking_confirmed"


def test_a_phone_only_contact_gets_sms_and_whatsapp_but_no_email(fakes, monkeypatch):
    _run(fakes, monkeypatch, _booking(), ns.notify_booking_confirmed)
    assert fakes["email"].send_calls == [] and len(fakes["sms"].template_calls) == 1 and len(fakes["whatsapp"].template_calls) == 1


def test_an_email_contact_gets_only_email(fakes, monkeypatch):
    _run(fakes, monkeypatch, _booking(email="a@example.com", contact="a@example.com"), ns.notify_booking_confirmed)
    assert len(fakes["email"].send_calls) == 1 and fakes["sms"].template_calls == [] and fakes["whatsapp"].template_calls == []


def test_the_payment_reminder_skips_whatsapp(fakes, monkeypatch):
    _run(fakes, monkeypatch, _booking(email="jane@example.com"), ns.notify_booking_payment_pending)
    assert len(fakes["email"].send_calls) == 1 and len(fakes["sms"].template_calls) == 1 and fakes["whatsapp"].template_calls == []
    assert fakes["sms"].template_calls[0][2][2] == "Rs. 1200.00" and "my-bookings?ref=AB12CD34" in fakes["sms"].template_calls[0][2][3]


def test_confirmation_is_deduplicated_per_channel(fakes, monkeypatch):
    b = _booking(email="jane@example.com")
    _run(fakes, monkeypatch, b, ns.notify_booking_confirmed)
    _run(fakes, monkeypatch, b, ns.notify_booking_confirmed)
    assert len(fakes["email"].send_calls) == len(fakes["sms"].template_calls) == len(fakes["whatsapp"].template_calls) == 1


def test_a_failed_channel_does_not_stop_the_others(fakes, monkeypatch):
    fakes["sms"].results = [PERMANENT()]
    _run(fakes, monkeypatch, _booking(email="jane@example.com"), ns.notify_booking_confirmed)
    assert len(fakes["email"].send_calls) == 1 and len(fakes["whatsapp"].template_calls) == 1
    statuses = {r.channel: r.status for r in deps.notification_repo.query()[0]}
    assert statuses == {"email": "sent", "sms": "failed", "whatsapp": "sent"}


def test_refund_and_cancel_templates(fakes, monkeypatch):
    b = _booking()
    _run(fakes, monkeypatch, b, ns.notify_booking_cancelled)
    _run(fakes, monkeypatch, b, ns.notify_booking_refunded, amount=600.0, cancelled=False, partial=True)
    events = [c[1:3] for c in fakes["whatsapp"].template_calls]
    assert events[0] == ("booking_cancelled", ["Jane", "AB12CD34", "2030-02-03"])
    assert events[1] == ("booking_refunded", ["Jane", "AB12CD34", "Rs. 600.00", "still active"])


def test_template_params_contract():
    b = _booking()
    assert tpl.template_params("booking_refunded", b, amount=None, cancelled=True)[2:] == ["Rs. 1200.00", "cancelled"]
    assert tpl.template_params("something_else", b) == []


# ── WhatsApp Cloud adapter (mocked HTTP) ───────────────────────────────────

class _Resp:
    def __init__(self, body):
        self._b = body

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def read(self):
        return json.dumps(self._b).encode()


def _http_error(code, body=None):
    return urllib.error.HTTPError("https://x", code, "err", {}, io.BytesIO(json.dumps(body or {}).encode()))


def _wa(monkeypatch, urlopen, **env):
    for k, v in {"WHATSAPP_CLOUD_TOKEN": "tok", "WHATSAPP_CLOUD_PHONE_ID": "99",
                 "WHATSAPP_TEMPLATE_BOOKING_CONFIRMED": "dazy_booking_confirmed", **env}.items():
        monkeypatch.setenv(k, v)
    import urllib.request
    monkeypatch.setattr(urllib.request, "urlopen", urlopen)
    return WhatsAppCloudProvider()


def test_whatsapp_template_request_shape(monkeypatch):
    seen = {}

    def fake(req, timeout=0):
        seen["body"], seen["url"] = json.loads(req.data), req.full_url
        return _Resp({"messages": [{"id": "wamid.9"}]})

    r = _wa(monkeypatch, fake).send_template("9876543210", "booking_confirmed", ["Jane", "AB12", "Cricket", "2030-02-03", "06:00-07:00"], "s", "b")
    assert r.status == "sent" and r.detail == "wamid.9" and seen["url"].endswith("/99/messages")
    t = seen["body"]["template"]
    assert seen["body"]["to"] == "919876543210" and t["name"] == "dazy_booking_confirmed" and t["language"]["code"] == "en"
    assert [p["text"] for p in t["components"][0]["parameters"]] == ["Jane", "AB12", "Cricket", "2030-02-03", "06:00-07:00"]


def test_whatsapp_event_without_a_template_is_skipped_without_any_request(monkeypatch):
    def forbidden(*a, **k):
        raise AssertionError("must not call WhatsApp without an approved template")
    r = _wa(monkeypatch, forbidden).send_template("9876543210", "booking_cancelled", ["a"], "s", "b")
    assert r.status == "skipped" and "WHATSAPP_TEMPLATE_BOOKING_CANCELLED" in r.detail
    assert _wa(monkeypatch, forbidden).send_template("a@b.com", "booking_confirmed", [], "s", "b").status == "skipped"


@pytest.mark.parametrize("error,retryable", [
    (_http_error(500), True), (_http_error(503), True), (_http_error(429), True),
    (_http_error(400, {"error": {"code": 131056}}), True),      # pair rate limit: back off
    (_http_error(400, {"error": {"code": 130429}}), True),
    (_http_error(400, {"error": {"code": 131026}}), False),     # not a WhatsApp user
    (_http_error(400, {"error": {"code": 132001}}), False),     # template does not exist
    (_http_error(401, {"error": {"code": 190}}), False),        # bad token
    (socket.timeout("timed out"), True), (urllib.error.URLError("dns"), True),
])
def test_whatsapp_failures_are_classified(monkeypatch, error, retryable):
    def fake(req, timeout=0):
        raise error
    r = _wa(monkeypatch, fake).send_template("9876543210", "booking_confirmed", ["a"], "s", "b")
    assert r.status == "failed" and r.retryable is retryable


def test_whatsapp_misconfiguration_is_permanent(monkeypatch):
    monkeypatch.delenv("WHATSAPP_CLOUD_TOKEN", raising=False)
    monkeypatch.setenv("WHATSAPP_TEMPLATE_BOOKING_CONFIRMED", "t")
    r = WhatsAppCloudProvider().send_template("9876543210", "booking_confirmed", [], "s", "b")
    assert r.status == "failed" and r.retryable is False


# ── MSG91 adapter (mocked HTTP) ────────────────────────────────────────────

def _sms(monkeypatch, urlopen, **env):
    for k, v in {"MSG91_AUTH_KEY": "authkey-1", "MSG91_TEMPLATE_BOOKING_CONFIRMED": "tpl-conf", "MSG91_TEMPLATE_OTP": "tpl-otp", **env}.items():
        monkeypatch.setenv(k, v)
    import urllib.request
    monkeypatch.setattr(urllib.request, "urlopen", urlopen)
    return Msg91SmsProvider()


def test_msg91_flow_request_shape(monkeypatch):
    seen = {}

    def fake(req, timeout=0):
        seen.update(body=json.loads(req.data), headers={k.lower(): v for k, v in req.header_items()}, url=req.full_url)
        return _Resp({"type": "success", "message": "req-123"})

    r = _sms(monkeypatch, fake).send_template("9876543210", "booking_confirmed", ["Jane", "AB12", "Cricket", "2030-02-03", "06:00-07:00"], "s", "b")
    assert (r.status, r.detail) == ("sent", "req-123")
    assert seen["url"] == "https://control.msg91.com/api/v5/flow" and seen["headers"]["authkey"] == "authkey-1"
    assert seen["body"]["template_id"] == "tpl-conf"
    assert seen["body"]["recipients"] == [{"mobiles": "919876543210", "var1": "Jane", "var2": "AB12", "var3": "Cricket",
                                           "var4": "2030-02-03", "var5": "06:00-07:00"}]


def test_msg91_event_without_a_template_is_skipped_and_free_text_is_impossible(monkeypatch):
    def forbidden(*a, **k):
        raise AssertionError("no request expected")
    p = _sms(monkeypatch, forbidden)
    assert p.send_template("9876543210", "booking_cancelled", [], "s", "b").status == "skipped"
    assert p.send("9876543210", "s", "free text").status == "skipped"
    assert p.send_template("a@b.com", "booking_confirmed", [], "s", "b").status == "skipped"


@pytest.mark.parametrize("error,retryable", [(_http_error(500), True), (_http_error(429), True), (_http_error(401), False),
                                             (socket.timeout("t"), True)])
def test_msg91_failures_are_classified(monkeypatch, error, retryable):
    def fake(req, timeout=0):
        raise error
    r = _sms(monkeypatch, fake).send_template("9876543210", "booking_confirmed", ["a"], "s", "b")
    assert r.status == "failed" and r.retryable is retryable


def test_msg91_error_inside_a_200_is_a_permanent_failure(monkeypatch):
    r = _sms(monkeypatch, lambda req, timeout=0: _Resp({"type": "error", "message": "Template ID is invalid"})).send_template(
        "9876543210", "booking_confirmed", ["a"], "s", "b")
    assert r.status == "failed" and r.retryable is False and "Template ID is invalid" in r.detail


def test_msg91_otp_and_misconfiguration(monkeypatch):
    seen = {}

    def fake(req, timeout=0):
        seen["body"] = json.loads(req.data)
        return _Resp({"type": "success", "message": "otp-1"})
    p = _sms(monkeypatch, fake)
    assert p.send_otp("9876543210", "482913").status == "sent"
    assert seen["body"]["template_id"] == "tpl-otp" and seen["body"]["recipients"][0]["var1"] == "482913"
    monkeypatch.delenv("MSG91_AUTH_KEY")
    assert Msg91SmsProvider().send_template("9876543210", "booking_confirmed", [], "s", "b").retryable is False
    monkeypatch.setenv("MSG91_AUTH_KEY", "k")
    monkeypatch.delenv("MSG91_TEMPLATE_OTP")
    assert Msg91SmsProvider().send_otp("9876543210", "1").status == "failed"


def test_factory_selects_msg91(monkeypatch):
    from integrations.notifications.factory import get_sms_provider
    monkeypatch.setenv("DAZY_NOTIFY_SMS_PROVIDER", "msg91")
    assert get_sms_provider().name == "msg91"
    monkeypatch.delenv("DAZY_NOTIFY_SMS_PROVIDER")
    assert get_sms_provider().name == "sms_stub"


# ── SMTP classification ────────────────────────────────────────────────────

@pytest.mark.parametrize("exc,retryable", [
    (smtplib.SMTPRecipientsRefused({"a@b.c": (550, b"no such user")}), False),
    (smtplib.SMTPServerDisconnected("gone"), True),
    (smtplib.SMTPConnectError(421, "busy"), True),
    (ConnectionRefusedError("refused"), True),
    (socket.timeout("timed out"), True),
    (smtplib.SMTPDataError(451, "try later"), True),
    (smtplib.SMTPDataError(554, "rejected"), False),
    (smtplib.SMTPAuthenticationError(535, b"bad creds"), False),
    (ValueError("weird"), False),
])
def test_smtp_failures_are_classified(monkeypatch, exc, retryable):
    for k, v in {"SMTP_HOST": "smtp.invalid", "SMTP_USER": "u", "SMTP_PASSWORD": "p"}.items():
        monkeypatch.setenv(k, v)

    class Boom:
        def __init__(self, *a, **k):
            raise exc
    monkeypatch.setattr(smtplib, "SMTP", Boom)
    r = SmtpEmailNotificationProvider().send("a@example.com", "s", "b")
    assert r.status == "failed" and r.retryable is retryable


def test_smtp_missing_configuration_is_permanent(monkeypatch):
    for k in ("SMTP_HOST", "SMTP_USER", "SMTP_PASSWORD"):
        monkeypatch.delenv(k, raising=False)
    assert SmtpEmailNotificationProvider().send("a@example.com", "s", "b").retryable is False


# ── delivery status and warnings ───────────────────────────────────────────

def test_production_warns_about_every_channel_that_will_not_deliver(monkeypatch):
    for k in ("RENDER", "DAZY_ENV"):
        monkeypatch.delenv(k, raising=False)
    assert ns.delivery_status()["warnings"] == []          # development: stubs are expected
    monkeypatch.setenv("RENDER", "true")
    from integrations.notifications.console import ConsoleNotificationProvider
    from integrations.notifications.sms_stub import SmsStubProvider
    from integrations.notifications.whatsapp_stub import WhatsAppStubProvider
    monkeypatch.setattr(ns, "notification_provider", ConsoleNotificationProvider())
    monkeypatch.setattr(ns, "sms_provider", SmsStubProvider())
    monkeypatch.setattr(ns, "whatsapp_provider", WhatsAppStubProvider())
    warnings = ns.delivery_status()["warnings"]
    assert len(warnings) == 3 and any("SMS" in w for w in warnings) and any("WhatsApp" in w for w in warnings) and any("Email" in w for w in warnings)


def test_real_providers_in_production_raise_no_warnings(monkeypatch):
    monkeypatch.setenv("RENDER", "true")
    monkeypatch.setattr(ns, "notification_provider", Chan("email"))
    monkeypatch.setattr(ns, "sms_provider", Chan("msg91"))
    monkeypatch.setattr(ns, "whatsapp_provider", Chan("whatsapp_cloud"))
    assert ns.delivery_status()["warnings"] == []


def test_readiness_reports_providers_and_the_retry_queue(client, fakes):
    fakes["sms"].results = [TRANSIENT()]
    _send("sms")
    body = client.get("/api/v1/health/ready").json()
    assert body["notifications"]["providers"] == {"email": "email_fake", "sms": "sms_fake", "whatsapp": "wa_fake"}
    assert body["notifications"]["queue"]["retrying"] == 1


def test_a_broken_status_lookup_never_turns_readiness_into_a_503(client, monkeypatch):
    import routes.health as h
    monkeypatch.setattr(h, "delivery_status", lambda: (_ for _ in ()).throw(RuntimeError("boom")))
    r = client.get("/api/v1/health/ready")
    assert r.status_code == 200 and r.json()["notifications"]["warnings"] == ["delivery status unavailable"]


# ── schema ─────────────────────────────────────────────────────────────────

def test_outbox_columns_and_indexes_exist():
    from sqlalchemy import text
    from db import _session
    with _session() as s:
        cols = {r[1]: r for r in s.execute(text("PRAGMA table_info(notification_messages)")).all()}
        assert {"event", "payload", "provider", "provider_ref", "attempts", "last_attempt_at", "next_attempt_at"} <= set(cols)
        assert cols["attempts"][4] in ("1", "'1'")  # server default for pre-existing rows
        idx = {r[1] for r in s.execute(text("PRAGMA index_list(notification_messages)")).all()}
        assert {"ix_notification_messages_status", "ix_notification_messages_next_attempt_at"} <= idx
