"""Cloudflare Turnstile verification (bot check on public write endpoints).

TURNSTILE_SECRET unset => checks are skipped (local dev / tests). Production refuses to boot
without it (see config_guard.py). Cloudflare publishes always-pass/always-fail test secrets
for development: https://developers.cloudflare.com/turnstile/troubleshooting/testing/"""
import json
import logging
import os
import urllib.parse
import urllib.request

from fastapi import HTTPException

from errors import ApiError

logger = logging.getLogger(__name__)

_VERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"


def turnstile_disabled() -> bool:
    """Explicit opt-out (DAZY_TURNSTILE_DISABLED=1): checks are skipped even if a secret is set and the
    production guard stops requiring one. Remove the variable to turn the checks back on."""
    return os.environ.get("DAZY_TURNSTILE_DISABLED", "").strip().lower() in ("1", "true", "yes", "on")


def turnstile_enabled() -> bool:
    return bool(os.environ.get("TURNSTILE_SECRET")) and not turnstile_disabled()


def _siteverify(secret: str, token: str, ip: str | None) -> bool:
    data = {"secret": secret, "response": token}
    if ip and ip != "unknown":
        data["remoteip"] = ip
    req = urllib.request.Request(_VERIFY_URL, data=urllib.parse.urlencode(data).encode(), method="POST")
    try:
        with urllib.request.urlopen(req, timeout=8) as resp:
            return bool(json.loads(resp.read()).get("success"))
    except Exception:
        # Fail closed: if Cloudflare is unreachable we cannot prove the caller is human.
        logger.exception("Turnstile siteverify failed")
        return False


def require_turnstile(token: str | None, ip: str | None) -> None:
    """Raise 400 unless the Turnstile token verifies. No-op when Turnstile is not configured."""
    secret = os.environ.get("TURNSTILE_SECRET")
    if not secret or turnstile_disabled():
        return
    if not token or not _siteverify(secret, token, ip):
        raise ApiError(400, "Please complete the verification challenge and try again.", "verification_required")
