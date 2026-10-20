"""Structured logging: one JSON object per line in production (what Render/Datadog/Loki ingest and
what `jq` can filter), readable text locally. Every line carries the request id of the request that
produced it, so a customer's "my booking failed at 14:03" becomes one grep.

DAZY_LOG_FORMAT=json|text (default: json in production, text otherwise) and DAZY_LOG_LEVEL (default INFO).
Only the standard library: this module is imported first and must never fail."""
import contextvars
import json
import logging
import os
import re
import sys
from datetime import datetime, timezone

# Set per request by the request-context middleware; "-" outside a request (startup, cron, scripts).
request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="-")

_SENSITIVE_KEYS = re.compile(r"pass|secret|token|authorization|cookie|signature|otp|pin\b|credential", re.I)
_LOGRECORD_FIELDS = set(logging.LogRecord("", 0, "", 0, "", (), None).__dict__) | {"message", "asctime", "request_id", "taskName"}


def _is_production() -> bool:
    return os.environ.get("DAZY_ENV", "").lower() == "production" or bool(os.environ.get("RENDER"))


def mask_contact(value: str | None) -> str:
    """'jane.doe@example.com' -> 'j***@example.com'; '9876543210' -> '98****3210'. For logs only."""
    if not value:
        return ""
    if "@" in value:
        local, _, domain = value.partition("@")
        return f"{local[:1]}***@{domain}"
    digits = value.strip()
    return f"{digits[:2]}{'*' * max(len(digits) - 6, 2)}{digits[-4:]}" if len(digits) >= 8 else "***"


class RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if not getattr(record, "request_id", None):
            record.request_id = request_id_var.get()
        return True


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        out = {
            "ts": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
            "request_id": getattr(record, "request_id", None) or request_id_var.get(),
        }
        for key, value in record.__dict__.items():  # fields passed via logger.info(..., extra={...})
            if key in _LOGRECORD_FIELDS or key.startswith("_"):
                continue
            out[key] = "[redacted]" if _SENSITIVE_KEYS.search(key) else value
        if record.exc_info:
            out["exc"] = self.formatException(record.exc_info)
        return json.dumps(out, default=str, ensure_ascii=False)


class _DropAsgiTraceback(logging.Filter):
    """uvicorn logs 'Exception in ASGI application' for every 500 with no request id; our exception
    handler already logged the same traceback with one."""
    def filter(self, record: logging.LogRecord) -> bool:
        return not str(record.msg).startswith("Exception in ASGI application")


def configure_logging() -> None:
    """Idempotent. Replaces the root handlers (including uvicorn's own) with one stdout handler."""
    fmt = os.environ.get("DAZY_LOG_FORMAT", "").lower() or ("json" if _is_production() else "text")
    handler = logging.StreamHandler(sys.stdout)
    handler.addFilter(RequestIdFilter())
    handler.setFormatter(
        JsonFormatter() if fmt == "json"
        else logging.Formatter("%(asctime)s %(levelname)s [%(request_id)s] %(name)s: %(message)s")
    )
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(os.environ.get("DAZY_LOG_LEVEL", "INFO").upper())
    for name in ("uvicorn", "uvicorn.error"):
        lg = logging.getLogger(name)
        lg.handlers[:] = []
        lg.propagate = True
    logging.getLogger("uvicorn.error").addFilter(_DropAsgiTraceback())
    access = logging.getLogger("uvicorn.access")  # replaced by our own access line with request id and timing
    access.handlers[:] = []
    access.propagate = False
