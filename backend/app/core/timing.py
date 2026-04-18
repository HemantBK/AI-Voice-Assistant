"""Per-stage timing for the voice pipeline.

`StageTimer` is a lightweight context manager that records named stage
durations on the current request. Stages are exposed as response headers
(`X-Stage-*-Ms`) and logged as a structured JSON line so the eval harness
can parse latency without running a separate profiler.
"""
from __future__ import annotations

import contextvars
import json
import logging
import time
from contextlib import contextmanager
from typing import Iterator

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


logger = logging.getLogger("timing")

_current: contextvars.ContextVar[dict[str, float] | None] = contextvars.ContextVar(
    "stage_timings", default=None
)


@contextmanager
def stage(name: str) -> Iterator[None]:
    bucket = _current.get()
    t0 = time.perf_counter()
    try:
        yield
    finally:
        elapsed_ms = (time.perf_counter() - t0) * 1000
        if bucket is not None:
            bucket[name] = round(bucket.get(name, 0.0) + elapsed_ms, 2)


class TimingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        bucket: dict[str, float] = {}
        token = _current.set(bucket)
        t0 = time.perf_counter()
        try:
            response: Response = await call_next(request)
        finally:
            _current.reset(token)
        total_ms = round((time.perf_counter() - t0) * 1000, 2)
        response.headers["X-Total-Ms"] = str(total_ms)
        for name, ms in bucket.items():
            response.headers[f"X-Stage-{name}-Ms"] = str(ms)
        if bucket:
            logger.info(json.dumps({
                "event": "request_timing",
                "path": request.url.path,
                "method": request.method,
                "status": response.status_code,
                "total_ms": total_ms,
                "stages": bucket,
            }))
        return response
