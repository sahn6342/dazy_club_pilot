"""Error reporting (Sentry) and the sweep heartbeat shown on /health/ready.

Sentry is OFF unless SENTRY_DSN is set, and when on it is configured to leak as little as possible:
no default PII, no request bodies, no local variables, no cookies/auth headers/query strings, and
emails, phone numbers and JWTs are masked in every string that does get through."""
import logging
import os
import re
import time
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_PHONE = re.compile(r"(?<!\d)(?:\+?91[\s-]?)?[6-9]\d{9}(?!\d)")
_JWT = re.compile(r"eyJ[\w-]{8,}\.[\w-]{8,}\.[\w-]{8,}")
_SENSITIVE_HEADERS = {
    "authorization", "cookie", "set-cookie", "x-otp-token", "x-internal-token", "x-razorpay-signature",
    "x-forwarded-for", "x-real-ip", "cf-connecting-ip",
}


def redact_text(text: str) -> str:
    return _JWT.sub("[jwt]", _EMAIL.sub("[email]", _PHONE.sub("[phone]", text)))


def _redact(value, depth=0):
    if depth > 6:
        return value
    if isinstance(value, str):
        return redact_text(value)
    if isinstance(value, dict):
        return {k: _redact(v, depth + 1) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_redact(v, depth + 1) for v in value]
    return value


def scrub_event(event: dict, hint=None) -> dict:
    """Sentry before_send: strip what we never want to leave the server, mask what remains."""
    req = event.get("request")
    if isinstance(req, dict):
        for drop in ("cookies", "data", "query_string", "env"):
            req.pop(drop, None)
        if isinstance(req.get("url"), str):
            req["url"] = req["url"].split("?", 1)[0]
        headers = req.get("headers")
        if isinstance(headers, dict):
            req["headers"] = {k: v for k, v in headers.items() if k.lower() not in _SENSITIVE_HEADERS}
    event.pop("user", None)
    for key in ("message", "logentry", "exception", "extra", "breadcrumbs", "contexts", "tags", "transaction"):
        if key in event:
            event[key] = _redact(event[key])
    return event


_sentry_active = False


def init_sentry(transport=None) -> bool:
    """Start Sentry if SENTRY_DSN is set. Returns whether it is active. `transport` is for tests."""
    global _sentry_active
    dsn = os.environ.get("SENTRY_DSN")
    if not dsn:
        return False
    import sentry_sdk
    from sentry_sdk.integrations.logging import LoggingIntegration

    try:
        rate = float(os.environ.get("SENTRY_TRACES_SAMPLE_RATE", "0") or 0)
    except ValueError:
        rate = 0.0
    kwargs = {"transport": transport} if transport is not None else {}
    sentry_sdk.init(
        dsn=dsn,
        environment=os.environ.get("SENTRY_ENV") or os.environ.get("DAZY_ENV") or "development",
        release=os.environ.get("SENTRY_RELEASE") or os.environ.get("RENDER_GIT_COMMIT") or None,
        send_default_pii=False,
        include_local_variables=False,   # locals routinely hold names, phones, tokens
        max_request_body_size="never",
        traces_sample_rate=max(0.0, min(rate, 1.0)),
        before_send=scrub_event,
        before_send_transaction=scrub_event,
        # Our exception handler logs unhandled errors with ERROR; the SDK already reports the exception itself,
        # so ERROR logs must not create a second event.
        integrations=[LoggingIntegration(level=logging.INFO, event_level=None)],
        **kwargs,
    )
    _sentry_active = True
    return True


def tag_request(request_id: str) -> None:
    """Attach the request id to whatever Sentry reports for this request (no-op without Sentry)."""
    if _sentry_active:
        import sentry_sdk
        sentry_sdk.set_tag("request_id", request_id)


# ── sweep heartbeat ──────────────────────────────────────────────────────────

_last_sweep: dict | None = None


def record_sweep(expired: int, reconciled: int) -> None:
    global _last_sweep
    _last_sweep = {"at": time.time(), "expired": expired, "reconciled": reconciled}


def sweep_status() -> dict:
    """What /health/ready shows about the scheduler. Process-local: it resets when the API restarts,
    and `lastRunAt` is null until the first sweep after a start."""
    configured = bool(os.environ.get("DAZY_INTERNAL_TOKEN"))
    if _last_sweep is None:
        return {"cronConfigured": configured, "lastRunAt": None, "ageSeconds": None}
    return {
        "cronConfigured": configured,
        "lastRunAt": datetime.fromtimestamp(_last_sweep["at"], tz=timezone.utc).isoformat(timespec="seconds"),
        "ageSeconds": int(time.time() - _last_sweep["at"]),
        "expired": _last_sweep["expired"], "reconciled": _last_sweep["reconciled"],
    }
