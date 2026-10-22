"""DB-backed sliding-window rate limiter (survives restarts, shared across instances),
plus client-IP resolution that cannot be spoofed via X-Forwarded-For."""
import os
import time

from fastapi import HTTPException, Request, status

from errors import ApiError
from sqlalchemy import delete, func, select

from db import _session
from db_models import RateLimitEventRow


def client_ip(req: Request) -> str:
    """Real client IP. DAZY_PROXY_HOPS = number of trusted reverse proxies in front of the
    API (Render alone = 1; Cloudflare in front of Render = 2; 0 = none, use the socket peer).
    Each trusted proxy appends the address it saw to X-Forwarded-For, so the Nth entry from
    the RIGHT is the client; anything a client prepends sits to the left and is ignored."""
    peer = req.client.host if req.client else "unknown"
    try:
        hops = int(os.environ.get("DAZY_PROXY_HOPS", "0"))
    except ValueError:
        hops = 0
    if hops <= 0:
        return peer
    parts = [p.strip() for p in req.headers.get("x-forwarded-for", "").split(",") if p.strip()]
    if len(parts) >= hops:
        return parts[-hops]
    return peer


def _limit_scale() -> int:
    """DAZY_RATE_LIMIT_SCALE multiplies every limit. Only for E2E suites that hammer one IP;
    production refuses to boot unless it is 1 (see config_guard.py)."""
    try:
        return max(1, int(os.environ.get("DAZY_RATE_LIMIT_SCALE", "1")))
    except ValueError:
        return 1


class SlidingWindowLimiter:
    def __init__(self, name: str, limit: int = 10, window_seconds: int = 60):
        self._name = name
        self._limit = limit
        self._window = window_seconds

    def _key(self, key: str) -> str:
        return f"{self._name}:{key}"

    def check(self, key: str, message: str = "Too many attempts. Try again later.") -> None:
        """Count one attempt for `key`; raise 429 when over the limit."""
        now = time.time()
        k = self._key(key)
        with _session() as s:
            s.execute(delete(RateLimitEventRow).where(RateLimitEventRow.key == k, RateLimitEventRow.ts <= now - self._window))
            used = s.scalar(select(func.count()).select_from(RateLimitEventRow).where(RateLimitEventRow.key == k))
            if used >= self._limit * _limit_scale():
                raise ApiError(status.HTTP_429_TOO_MANY_REQUESTS, message, "rate_limited")
            s.add(RateLimitEventRow(key=k, ts=now))

    def is_blocked(self, key: str) -> bool:
        """Whether `key` is at its limit, without counting an attempt (for lockouts)."""
        cutoff = time.time() - self._window
        with _session() as s:
            used = s.scalar(select(func.count()).select_from(RateLimitEventRow).where(
                RateLimitEventRow.key == self._key(key), RateLimitEventRow.ts > cutoff))
            return used >= self._limit * _limit_scale()

    def hit(self, key: str) -> None:
        with _session() as s:
            s.add(RateLimitEventRow(key=self._key(key), ts=time.time()))

    def reset(self, key: str) -> None:
        with _session() as s:
            s.execute(delete(RateLimitEventRow).where(RateLimitEventRow.key == self._key(key)))

    def clear(self) -> None:
        with _session() as s:
            s.execute(delete(RateLimitEventRow).where(RateLimitEventRow.key.like(f"{self._name}:%")))


admin_login_limiter = SlidingWindowLimiter("admin_login", 10, 60)
cashier_login_limiter = SlidingWindowLimiter("cashier_login", 10, 60)
# Per-username lockout for kiosk PINs: only FAILED attempts are recorded (see routes/cafe/auth.py).
cashier_pin_lockout = SlidingWindowLimiter("cashier_pin_fail", 5, 15 * 60)
booking_lookup_limiter = SlidingWindowLimiter("booking_lookup", 10, 60)
booking_create_limiter = SlidingWindowLimiter("booking_create_ip", 10, 600)
booking_create_contact_limiter = SlidingWindowLimiter("booking_create_contact", 5, 3600)
payment_verify_limiter = SlidingWindowLimiter("payment_verify", 20, 60)
enquiry_limiter = SlidingWindowLimiter("enquiry", 5, 600)
preorder_limiter = SlidingWindowLimiter("preorder", 10, 600)
otp_request_limiter = SlidingWindowLimiter("otp_request", 5, 600)
otp_verify_limiter = SlidingWindowLimiter("otp_verify", 10, 600)

ALL_LIMITERS = [
    admin_login_limiter, cashier_login_limiter, cashier_pin_lockout, booking_lookup_limiter,
    booking_create_limiter, booking_create_contact_limiter, payment_verify_limiter,
    enquiry_limiter, preorder_limiter, otp_request_limiter, otp_verify_limiter,
]


def clear_all_limiters() -> None:
    for lim in ALL_LIMITERS:
        lim.clear()
