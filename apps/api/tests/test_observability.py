"""Workstream G: JSON logs with request ids, /health/ready, Sentry scrubbing, quiet notification stubs,
and the Cloudflare cron worker's own test suite."""
import json
import logging
import os
import shutil
import subprocess
import time
import uuid

import pytest
from starlette.testclient import TestClient

import deps
import observability
import routes.health as health_routes
from logging_config import (
    JsonFormatter, RequestIdFilter, _DropAsgiTraceback, configure_logging, mask_contact, request_id_var,
)
from main import app
from observability import init_sentry, record_sweep, redact_text, scrub_event, sweep_status

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


@pytest.fixture
def restore_logging():
    root = logging.getLogger()
    saved = (root.handlers[:], root.level, [(n, logging.getLogger(n).handlers[:], logging.getLogger(n).propagate)
                                            for n in ("uvicorn", "uvicorn.error", "uvicorn.access")])
    yield
    root.handlers[:] = saved[0]
    root.setLevel(saved[1])
    for name, handlers, propagate in saved[2]:
        lg = logging.getLogger(name)
        lg.handlers[:] = handlers
        lg.propagate = propagate
        lg.filters.clear()


def _record(msg="hello", level=logging.INFO, **extra):
    rec = logging.LogRecord("test.logger", level, __file__, 1, msg, (), None)
    for k, v in extra.items():
        setattr(rec, k, v)
    return rec


# ── JSON formatter and logging setup ───────────────────────────────────────

def test_json_lines_have_the_standard_fields_and_the_request_id():
    token = request_id_var.set("req-123456")
    try:
        line = JsonFormatter().format(_record("booking created", ref="AB12CD34", amount=1200.5))
    finally:
        request_id_var.reset(token)
    data = json.loads(line)
    assert data["msg"] == "booking created" and data["level"] == "INFO" and data["logger"] == "test.logger"
    assert data["request_id"] == "req-123456" and data["ref"] == "AB12CD34" and data["amount"] == 1200.5
    assert data["ts"].endswith("+00:00") and "T" in data["ts"]
    assert "\n" not in line  # one object per line


def test_request_id_defaults_to_a_dash_outside_a_request():
    assert json.loads(JsonFormatter().format(_record()))["request_id"] == "-"


def test_sensitive_extras_are_redacted_but_messages_with_unicode_survive():
    data = json.loads(JsonFormatter().format(_record("नमस्ते ₹100", password="hunter2", api_token="abc", otp_code="123456",
                                                      authorization="Bearer x", note="fine")))
    assert data["msg"] == "नमस्ते ₹100" and data["note"] == "fine"
    for key in ("password", "api_token", "otp_code", "authorization"):
        assert data[key] == "[redacted]"


def test_exceptions_are_included_as_a_field():
    try:
        raise ValueError("kaboom")
    except ValueError:
        import sys
        rec = logging.LogRecord("x", logging.ERROR, __file__, 1, "failed", (), sys.exc_info())
    data = json.loads(JsonFormatter().format(rec))
    assert "ValueError: kaboom" in data["exc"] and "Traceback" in data["exc"]


def test_filter_stamps_records_with_the_current_request_id():
    rec = _record()
    token = request_id_var.set("abc-request")
    try:
        RequestIdFilter().filter(rec)
    finally:
        request_id_var.reset(token)
    assert rec.request_id == "abc-request"


def test_configure_logging_picks_format_and_level_from_the_environment(monkeypatch, restore_logging):
    monkeypatch.delenv("RENDER", raising=False)
    monkeypatch.delenv("DAZY_ENV", raising=False)
    monkeypatch.delenv("DAZY_LOG_FORMAT", raising=False)
    configure_logging()
    root = logging.getLogger()
    assert len(root.handlers) == 1 and not isinstance(root.handlers[0].formatter, JsonFormatter)  # text locally

    monkeypatch.setenv("RENDER", "true")
    configure_logging()
    assert isinstance(root.handlers[0].formatter, JsonFormatter)  # JSON in production

    monkeypatch.setenv("DAZY_LOG_FORMAT", "text")
    monkeypatch.setenv("DAZY_LOG_LEVEL", "warning")
    configure_logging()
    assert not isinstance(root.handlers[0].formatter, JsonFormatter) and root.level == logging.WARNING
    assert len(root.handlers) == 1  # idempotent: no duplicate handlers


def test_uvicorn_loggers_are_routed_through_ours(restore_logging):
    configure_logging()
    assert logging.getLogger("uvicorn.error").propagate is True and logging.getLogger("uvicorn.error").handlers == []
    assert logging.getLogger("uvicorn.access").propagate is False  # we write our own access line


def test_duplicate_asgi_tracebacks_are_dropped():
    f = _DropAsgiTraceback()
    assert f.filter(_record("Exception in ASGI application\n")) is False
    assert f.filter(_record("Application startup complete.")) is True


@pytest.mark.parametrize("raw,masked", [
    ("jane.doe@example.com", "j***@example.com"), ("9876543210", "98****3210"), ("12345", "***"), ("", ""), (None, ""),
])
def test_mask_contact(raw, masked):
    assert mask_contact(raw) == masked


# ── request id middleware and access log ───────────────────────────────────

def test_every_response_carries_a_request_id(client):
    r = client.get("/api/v1/venue")
    assert len(r.headers["x-request-id"]) == 32 and int(r.headers["x-request-id"], 16) >= 0
    assert client.get("/api/v1/venue").headers["x-request-id"] != r.headers["x-request-id"]


def test_a_sane_client_request_id_is_kept_and_a_bad_one_replaced(client):
    assert client.get("/api/v1/venue", headers={"X-Request-ID": "cron-1234-abcd"}).headers["x-request-id"] == "cron-1234-abcd"
    for bad in ("short", "has spaces in it!!", "x" * 100, "<script>alert(1)</script>"):
        got = client.get("/api/v1/venue", headers={"X-Request-ID": bad}).headers["x-request-id"]
        assert got != bad and len(got) == 32


def test_access_line_has_method_path_status_duration_ip_and_request_id(client, caplog):
    with caplog.at_level(logging.INFO, logger="access"):
        r = client.get("/api/v1/venue", headers={"X-Request-ID": "trace-0001-xyz"})
    rec = next(x for x in caplog.records if x.name == "access" and x.path == "/api/v1/venue")
    assert (rec.method, rec.status, rec.request_id) == ("GET", 200, "trace-0001-xyz")
    assert rec.duration_ms >= 0 and rec.ip and r.status_code == 200


def test_query_strings_never_reach_the_logs(client, caplog):
    with caplog.at_level(logging.DEBUG):
        client.get("/api/v1/bookings/lookup?ref=NOPE1234&contact=9876543210")
    # (the httpx test client logs the URLs it requests; that is the client, not the server)
    text = "\n".join(f"{r.getMessage()} {getattr(r, 'path', '')}" for r in caplog.records if not r.name.startswith("httpx"))
    assert "9876543210" not in text and "NOPE1234" not in text
    assert any(getattr(r, "path", None) == "/api/v1/bookings/lookup" for r in caplog.records)


def test_health_checks_do_not_spam_the_info_log(client, caplog):
    with caplog.at_level(logging.INFO, logger="access"):
        client.get("/api/v1/health")
        client.get("/api/v1/health/ready")
    assert not [r for r in caplog.records if r.name == "access" and r.path.startswith("/api/v1/health")]
    with caplog.at_level(logging.DEBUG, logger="access"):
        client.get("/api/v1/health")
    assert [r for r in caplog.records if r.name == "access" and r.levelno == logging.DEBUG]


def test_failed_requests_are_logged_with_their_status(client, caplog):
    with caplog.at_level(logging.INFO, logger="access"):
        client.get("/api/v1/admin/me")  # 401
    assert next(r for r in caplog.records if r.name == "access" and r.path == "/api/v1/admin/me").status == 401


@pytest.fixture
def boom_route():
    async def boom():
        raise RuntimeError("secret internal detail jane@example.com")
    app.add_api_route("/__boom", boom)
    yield "/__boom"
    app.router.routes[:] = [r for r in app.router.routes if getattr(r, "path", None) != "/__boom"]
    app.middleware_stack = None


def test_unhandled_errors_return_a_generic_body_with_the_request_id_and_are_logged_with_it(boom_route, caplog):
    app.middleware_stack = None
    c = TestClient(app, raise_server_exceptions=False)
    with caplog.at_level(logging.INFO):
        r = c.get(boom_route, headers={"X-Request-ID": "trace-boom-001"})
    assert r.status_code == 500
    assert r.json() == {"detail": "Internal server error.", "requestId": "trace-boom-001"}
    assert r.headers["x-request-id"] == "trace-boom-001"
    assert "secret internal detail" not in r.text  # nothing leaks to the client
    err = next(x for x in caplog.records if x.levelno == logging.ERROR and "Unhandled error" in x.getMessage())
    assert err.request_id == "trace-boom-001" and err.exc_info and "secret internal detail" in str(err.exc_info[1])
    assert next(x for x in caplog.records if x.name == "access" and x.path == boom_route).status == 500


# ── /health and /health/ready ──────────────────────────────────────────────

def test_liveness_never_touches_the_database(client, monkeypatch):
    def boom(*a, **k):
        raise AssertionError("liveness must not query the database")
    monkeypatch.setattr(health_routes, "_session", boom)
    assert client.get("/api/v1/health").status_code == 200


def test_ready_reports_database_and_migration_state(client):
    r = client.get("/api/v1/health/ready")
    body = r.json()
    assert r.status_code == 200 and body["status"] == "ok" and body["db"] == "ok" and body["migrated"] is True
    assert body["revision"] == body["head"] and body["revision"]
    assert set(body["sweep"]) >= {"cronConfigured", "lastRunAt", "ageSeconds"}


def test_ready_is_503_without_leaking_when_the_database_is_down(client, monkeypatch, caplog):
    def down(*a, **k):
        raise RuntimeError("connection to server at 10.0.0.5 failed: password authentication failed for user bob")
    monkeypatch.setattr(health_routes, "_session", down)
    with caplog.at_level(logging.ERROR):
        r = client.get("/api/v1/health/ready")
    assert r.status_code == 503 and r.json() == {"status": "degraded", "db": "error"}
    assert "10.0.0.5" not in r.text and "bob" not in r.text
    assert any("database unavailable" in x.getMessage() for x in caplog.records)  # detail goes to the log only


def test_ready_is_503_when_the_schema_is_behind_the_code(client, monkeypatch):
    monkeypatch.setattr(health_routes, "_migration_head", lambda: "zzzzzzzzzzzz")
    r = client.get("/api/v1/health/ready")
    body = r.json()
    assert r.status_code == 503 and body["status"] == "degraded" and body["migrated"] is False and body["db"] == "ok"


def test_ready_shows_when_the_scheduler_last_ran(client, monkeypatch):
    monkeypatch.setattr(observability, "_last_sweep", None)
    monkeypatch.setenv("DAZY_INTERNAL_TOKEN", "tok-for-test")
    assert client.get("/api/v1/health/ready").json()["sweep"] == {"cronConfigured": True, "lastRunAt": None, "ageSeconds": None}
    assert client.post("/api/v1/internal/sweep", headers={"X-Internal-Token": "tok-for-test"}).status_code == 200
    sweep = client.get("/api/v1/health/ready").json()["sweep"]
    assert sweep["lastRunAt"] and 0 <= sweep["ageSeconds"] < 5 and sweep["expired"] == 0 and sweep["reconciled"] == 0


def test_sweep_status_ages(monkeypatch):
    monkeypatch.setattr(observability, "_last_sweep", {"at": time.time() - 90, "expired": 3, "reconciled": 1})
    s = sweep_status()
    assert 89 <= s["ageSeconds"] <= 92 and s["expired"] == 3


# ── Sentry ────────────────────────────────────────────────────────────────

def test_sentry_is_off_without_a_dsn(monkeypatch):
    monkeypatch.delenv("SENTRY_DSN", raising=False)
    assert init_sentry() is False


@pytest.mark.parametrize("raw,expect", [
    ("mail jane.doe@example.com now", "mail [email] now"),
    ("call 9876543210 or +919876543210", "call [phone] or [phone]"),
    ("token eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJhZG1pbiJ9.abcdefghijk end", "token [jwt] end"),
    ("nothing sensitive: booking AB12CD34 for Rs. 1200", "nothing sensitive: booking AB12CD34 for Rs. 1200"),
    ("order 12345678901234 id", "order 12345678901234 id"),   # long digit runs are not phone numbers
])
def test_redact_text(raw, expect):
    assert redact_text(raw) == expect


def test_scrub_event_strips_request_data_headers_user_and_masks_strings():
    event = {
        "request": {
            "url": "https://api.example.com/api/v1/bookings/lookup?ref=AB&contact=9876543210",
            "query_string": "ref=AB&contact=9876543210", "cookies": {"dazy_admin": "eyJ.x.y"},
            "data": {"contact": "9876543210", "name": "Jane"}, "env": {"REMOTE_ADDR": "1.2.3.4"},
            "headers": {"Authorization": "Bearer x", "Cookie": "dazy_admin=1", "X-OTP-Token": "t", "X-Razorpay-Signature": "s",
                        "X-Forwarded-For": "1.2.3.4", "User-Agent": "pytest", "Content-Type": "application/json"},
        },
        "user": {"id": "1", "email": "jane@example.com", "ip_address": "1.2.3.4"},
        "message": "failed for jane@example.com",
        "exception": {"values": [{"type": "ValueError", "value": "bad contact 9876543210"}]},
        "breadcrumbs": {"values": [{"message": "GET /x?contact=9876543210 by jane@example.com"}]},
        "tags": {"request_id": "trace-1"},
    }
    out = scrub_event(event)
    req = out["request"]
    assert req["url"] == "https://api.example.com/api/v1/bookings/lookup"
    assert not ({"query_string", "cookies", "data", "env"} & set(req))
    assert set(req["headers"]) == {"User-Agent", "Content-Type"}
    assert "user" not in out
    blob = json.dumps(out)
    assert "jane@example.com" not in blob and "9876543210" not in blob
    assert out["tags"]["request_id"] == "trace-1"
    assert out["exception"]["values"][0]["type"] == "ValueError"


def test_scrub_event_tolerates_sparse_events():
    assert scrub_event({}) == {}
    assert scrub_event({"request": {}, "user": None}) == {"request": {}}


class _Collector:
    """A Sentry transport that keeps events in memory instead of sending them."""
    def __new__(cls):
        from sentry_sdk.transport import Transport

        class T(Transport):
            def __init__(self):
                super().__init__()
                self.events = []

            def capture_envelope(self, envelope):
                for item in envelope.items:
                    if item.headers.get("type") == "event":
                        self.events.append(item.payload.json)

        return T()


def test_sentry_reports_one_scrubbed_event_per_unhandled_error(boom_route, monkeypatch):
    import sentry_sdk
    monkeypatch.setenv("SENTRY_DSN", "https://publickey@o0.ingest.invalid/1")
    monkeypatch.setenv("SENTRY_ENV", "test-env")
    monkeypatch.setenv("SENTRY_RELEASE", "abc123")
    transport = _Collector()
    try:
        assert init_sentry(transport=transport) is True
        app.middleware_stack = None  # rebuild so the SDK's ASGI/Starlette integration wraps this app
        c = TestClient(app, raise_server_exceptions=False)
        r = c.get(boom_route + "?contact=9876543210",
                  headers={"X-Request-ID": "trace-sentry-01", "Authorization": "Bearer abc", "Cookie": "dazy_admin=zzz"})
        assert r.status_code == 500
        sentry_sdk.flush()
        events = transport.events
        assert len(events) == 1, [e.get("message") or e.get("exception") for e in events]  # no duplicate from the ERROR log
        ev = events[0]
        assert ev["environment"] == "test-env" and ev["release"] == "abc123"
        assert ev["tags"]["request_id"] == "trace-sentry-01"
        blob = json.dumps(ev)
        for secret in ("9876543210", "jane@example.com", "Bearer abc", "dazy_admin=zzz"):
            assert secret not in blob, secret
        assert "user" not in ev
        frames = [f for v in ev["exception"]["values"] for f in v["stacktrace"]["frames"]]
        assert frames and all("vars" not in f for f in frames)  # no local variables
    finally:
        sentry_sdk.get_client().close()
        sentry_sdk.init(dsn="")  # a disabled client (dsn=None would re-read SENTRY_DSN from the environment)
        observability._sentry_active = False
        app.middleware_stack = None


def test_trace_sample_rate_is_clamped_and_defaults_to_off(monkeypatch):
    import sentry_sdk
    monkeypatch.setenv("SENTRY_DSN", "https://publickey@o0.ingest.invalid/1")
    try:
        monkeypatch.setenv("SENTRY_TRACES_SAMPLE_RATE", "5")
        init_sentry(transport=_Collector())
        assert sentry_sdk.get_client().options["traces_sample_rate"] == 1.0
        monkeypatch.setenv("SENTRY_TRACES_SAMPLE_RATE", "garbage")
        init_sentry(transport=_Collector())
        assert sentry_sdk.get_client().options["traces_sample_rate"] == 0.0
        opts = sentry_sdk.get_client().options
        assert opts["send_default_pii"] is False and opts["include_local_variables"] is False
    finally:
        sentry_sdk.get_client().close()
        sentry_sdk.init(dsn="")
        observability._sentry_active = False


# ── notification stubs no longer print, and stay quiet in production ───────

def test_stubs_log_in_development_and_hide_bodies_in_production(caplog, monkeypatch):
    from integrations.notifications.console import ConsoleNotificationProvider
    from integrations.notifications.sms_stub import SmsStubProvider
    from integrations.notifications.whatsapp_stub import WhatsAppStubProvider
    monkeypatch.delenv("RENDER", raising=False)
    monkeypatch.delenv("DAZY_ENV", raising=False)
    with caplog.at_level(logging.INFO):
        for p in (ConsoleNotificationProvider(), SmsStubProvider(), WhatsAppStubProvider()):
            assert p.send("9876543210", "Code", "Your code is 482913").status == "sent"
    assert "482913" in caplog.text  # developers need to see the OTP

    caplog.clear()
    monkeypatch.setenv("RENDER", "true")
    with caplog.at_level(logging.INFO):
        for p in (ConsoleNotificationProvider(), SmsStubProvider(), WhatsAppStubProvider()):
            assert p.send("9876543210", "Code", "Your code is 482913").status == "sent"
    assert "482913" not in caplog.text and "9876543210" not in caplog.text  # neither the code nor the number
    assert "98****3210" in caplog.text and "NOT delivered" in caplog.text


def test_no_print_calls_remain_in_runtime_code():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    offenders = []
    for base in ("integrations", "services", "routes", "repositories"):
        for dirpath, _, files in os.walk(os.path.join(root, base)):
            for f in files:
                if f.endswith(".py") and "print(" in open(os.path.join(dirpath, f), encoding="utf-8").read().replace("window.print()", ""):
                    offenders.append(os.path.join(base, f))
    assert offenders == []


# ── the Cloudflare cron worker's own tests ─────────────────────────────────

@pytest.mark.skipif(not shutil.which("node"), reason="node is not installed")
def test_cron_worker_unit_tests_pass():
    r = subprocess.run(["node", "--test", "src/"], cwd=os.path.join(REPO, "infra", "cron-worker"),
                       capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "fail 0" in r.stdout


def test_worker_config_matches_the_api_it_calls():
    cfg = open(os.path.join(REPO, "infra", "cron-worker", "wrangler.toml"), encoding="utf-8").read()
    assert 'crons = ["*/5 * * * *"]' in cfg and "workers_dev = false" in cfg
    src = open(os.path.join(REPO, "infra", "cron-worker", "src", "index.js"), encoding="utf-8").read()
    assert "/internal/sweep" in src and "/health/ready" in src and "X-Internal-Token" in src
