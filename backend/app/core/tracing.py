"""OpenTelemetry setup for the backend (Phase G.2).

Design goals:
  - Opt-in. The backend runs fine with `OTEL_ENABLED=false` (default) and
    zero OTel packages installed — all imports are lazy and guarded.
  - Standard OTLP/HTTP exporter so it works with Jaeger, Tempo, Grafana
    Cloud, Honeycomb, Datadog, and anything else that speaks OTLP.
  - Span attributes follow the conventions that make traces actually
    useful: service name, per-stage pipeline spans, model + provider
    names, durations derived from the existing `stage()` helper.

The public surface is small:
  - `configure()` — call once at startup.
  - `get_tracer()` — returns a tracer or None (None means tracing is off).

Callers (such as `stage()` in timing.py) check for None and no-op when
tracing is disabled, so the hot path has no mandatory dependency on this
module.
"""
from __future__ import annotations

import logging
import threading
from typing import Any

logger = logging.getLogger(__name__)

_tracer: Any = None
_configured: bool = False
_lock = threading.Lock()


def configure(
    service_name: str,
    endpoint: str,
    sample_rate: float = 1.0,
) -> bool:
    """Configure OpenTelemetry once. Returns True if tracing is now active,
    False if deps are missing or configuration failed (non-fatal)."""
    global _tracer, _configured
    with _lock:
        if _configured:
            return _tracer is not None
        _configured = True  # do not retry

        try:
            from opentelemetry import trace
            from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
                OTLPSpanExporter,
            )
            from opentelemetry.sdk.resources import Resource
            from opentelemetry.sdk.trace import TracerProvider
            from opentelemetry.sdk.trace.export import BatchSpanProcessor
            from opentelemetry.sdk.trace.sampling import (
                ParentBased,
                TraceIdRatioBased,
            )
        except ImportError as e:
            logger.warning(
                "OpenTelemetry SDK not installed; tracing disabled (%s). "
                "Install with: pip install -r backend/requirements.txt",
                e,
            )
            return False

        try:
            resource = Resource.create({"service.name": service_name})
            if 0.0 < sample_rate < 1.0:
                sampler = ParentBased(root=TraceIdRatioBased(sample_rate))
                provider = TracerProvider(resource=resource, sampler=sampler)
            else:
                provider = TracerProvider(resource=resource)
            exporter = OTLPSpanExporter(endpoint=f"{endpoint.rstrip('/')}/v1/traces")
            provider.add_span_processor(BatchSpanProcessor(exporter))
            trace.set_tracer_provider(provider)
            _tracer = trace.get_tracer(service_name)
            logger.info(
                "OpenTelemetry tracing enabled: service=%s endpoint=%s sample_rate=%s",
                service_name,
                endpoint,
                sample_rate,
            )
            return True
        except Exception as e:
            logger.exception("OpenTelemetry setup failed; tracing disabled: %s", e)
            _tracer = None
            return False


def get_tracer() -> Any:
    """Return the configured tracer, or None if tracing is off. Callers
    should treat None as "no-op"."""
    return _tracer


def instrument_fastapi(app: Any) -> None:
    """Install FastAPI auto-instrumentation. Safe to call when tracing is
    off — returns silently."""
    if _tracer is None:
        return
    try:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
    except ImportError:
        logger.warning("opentelemetry-instrumentation-fastapi not installed; skipping auto HTTP spans")
        return
    try:
        FastAPIInstrumentor.instrument_app(app)
        logger.info("FastAPI OTel auto-instrumentation installed")
    except Exception as e:
        logger.warning("FastAPIInstrumentor failed: %s", e)


# ---------------------------------------------------------------------------
# Test helpers (kept in the module so tests don't bypass the configure guard).
# ---------------------------------------------------------------------------


def _reset_for_tests() -> None:
    global _tracer, _configured
    with _lock:
        _tracer = None
        _configured = False


_test_exporter: Any = None


def _install_inmemory_tracer() -> Any:
    """Install an in-memory exporter + tracer for unit tests. Idempotent:
    OTel's TracerProvider can only be set once per process, so subsequent
    calls reuse the existing provider and just return the cached exporter.
    The caller should clear it (`exporter.clear()`) between tests."""
    global _tracer, _configured, _test_exporter
    from opentelemetry import trace
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
        InMemorySpanExporter,
    )

    if _test_exporter is not None:
        # Provider already installed; just reset our module-level flags so
        # tests see a consistent state, and hand back the same exporter.
        _test_exporter.clear()
        _tracer = trace.get_tracer("test")
        _configured = True
        return _test_exporter

    resource = Resource.create({"service.name": "test"})
    provider = TracerProvider(resource=resource)
    exporter = InMemorySpanExporter()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    trace.set_tracer_provider(provider)
    _tracer = trace.get_tracer("test")
    _configured = True
    _test_exporter = exporter
    return exporter


def _uninstall_tracer_for_tests() -> None:
    """Drop the local reference to the tracer so `get_tracer() -> None`
    simulates OTel-off mode, without touching the process-global provider."""
    global _tracer, _configured
    _tracer = None
    _configured = False
