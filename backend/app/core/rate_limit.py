"""In-memory token-bucket rate limiter for HTTP endpoints. Per-client
(identified by the API key if present, else remote IP). Not suitable for
multi-process deployments — swap in Redis for that."""
from __future__ import annotations

import time
from collections import defaultdict
from threading import Lock

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.config import RATE_LIMIT_CAPACITY, RATE_LIMIT_PER_MINUTE


class _Bucket:
    __slots__ = ("tokens", "updated")

    def __init__(self, capacity: float):
        self.tokens = float(capacity)
        self.updated = time.monotonic()


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app):
        super().__init__(app)
        self._buckets: dict[str, _Bucket] = defaultdict(lambda: _Bucket(RATE_LIMIT_CAPACITY))
        self._lock = Lock()
        self._refill_per_sec = RATE_LIMIT_PER_MINUTE / 60.0
        self._capacity = RATE_LIMIT_CAPACITY

    def _key(self, request: Request) -> str:
        return request.headers.get("x-api-key") or (request.client.host if request.client else "anon")

    def _take(self, key: str) -> bool:
        now = time.monotonic()
        with self._lock:
            b = self._buckets[key]
            b.tokens = min(self._capacity, b.tokens + self._refill_per_sec * (now - b.updated))
            b.updated = now
            if b.tokens < 1.0:
                return False
            b.tokens -= 1.0
            return True

    async def dispatch(self, request: Request, call_next):
        if RATE_LIMIT_PER_MINUTE <= 0:
            return await call_next(request)
        if self._take(self._key(request)):
            return await call_next(request)
        return JSONResponse(
            status_code=429,
            content={"detail": "rate limit exceeded"},
            headers={"retry-after": "60"},
        )
