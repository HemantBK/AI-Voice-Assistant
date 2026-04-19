"""Per-stage timing for the voice pipeline.

`stage()` is a lightweight context manager that records named stage
durations. It has two behaviors running in parallel:

  1. HTTP response headers: `X-Stage-<name>-Ms` + `X-Total-Ms`. These
     are what the eval harness reads. Always on.
  2. OpenTelemetry spans: when tracing is configured (Phase G.2), the
     same stage boundaries become child spans with their durations.
     The context manager `yield`s the span object (or None) so callers
     can attach attributes like `llm.model` or `stt.audio_duration_s`.

Backwards compatibility: `with stage("x"):` keeps working; the yielded
value is new but optional.
"""
from __future__ import annotations

import contextvars
import json
import logging
import time
from contextlib import contextmanager
from typing import Any, Iterator

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.tracing import get_tracer


logger = logging.getLogger("timing")

_current: contextvars.ContextVar[dict[str, float] | None] = contextvars.ContextVar(
    "stage_timings", default=None
)


@contextmanager
def stage(name: str) -> Iterator[Any]:
    """Time a named stage.

    Yields the OTel span (if tracing is on) or None. Either way the stage's
    elapsed ms lands on the current request's header bucket.

    Usage:
        with stage("stt") as span:
            result = stt_service.transcribe(audio)
            if span is not None:
                span.set_attribute("stt.audio_duration_s", result["audio_duration_s"])
    """
    bucket = _current.get()
    t0 = time.perf_counter()
    tracer = get_tracer()
    if tracer is not None:
        # start_as_current_span is a CM; use it explicitly so we can also
        # bookkeep header timings in the finally block.
        span_cm = tracer.start_as_current_span(f"pipeline.{name}")
        span = span_cm.__enter__()
        try:
            yield span
            span_cm.__exit__(None, None, None)
        except BaseException as e:
            span_cm.__exit__(type(e), e, e.__traceback__)
            raise
        finally:
            elapsed_ms = (time.perf_counter() - t0) * 1000
            if bucket is not None:
                bucket[name] = round(bucket.get(name, 0.0) + elapsed_ms, 2)
    else:
        try:
            yield None
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
