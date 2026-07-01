"""Per-key sliding-window rate limiter, shared by admin and cashier login."""
import time
from collections import defaultdict

from fastapi import HTTPException, status


class SlidingWindowLimiter:
    def __init__(self, limit: int = 10, window_seconds: int = 60):
        self._limit = limit
        self._window = window_seconds
        self._attempts: dict[str, list[float]] = defaultdict(list)

    def check(self, key: str) -> None:
        now = time.time()
        window = [t for t in self._attempts[key] if now - t < self._window]
        if len(window) >= self._limit:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many login attempts. Try again later.",
            )
        window.append(now)
        self._attempts[key] = window

    def clear(self) -> None:
        self._attempts.clear()


admin_login_limiter = SlidingWindowLimiter(limit=10, window_seconds=60)
cashier_login_limiter = SlidingWindowLimiter(limit=10, window_seconds=60)
