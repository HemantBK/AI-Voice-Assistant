"""Unit tests for OTel tracing + timing integration.

Uses an in-memory span exporter — no network, no collector required.
Tests that `stage()` emits both X-Stage headers AND OTel spans when
tracing is on, and is a no-op on tracing when off.
"""
from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest

# Ensure backend/ is on sys.path (tests run from repo root)
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


@pytest.fixture
def tracing_on():
    """Install (or reuse) the in-memory exporter. OTel's TracerProvider
    can only be set once per process, so the helper is idempotent — it
    clears previously emitted spans and hands back the cached exporter."""
    from app.core import tracing as tracing_mod
    exporter = tracing_mod._install_inmemory_tracer()
    yield exporter
    exporter.clear()


@pytest.fixture
def tracing_off():
    from app.core import tracing as tracing_mod
    tracing_mod._uninstall_tracer_for_tests()
    yield
    tracing_mod._uninstall_tracer_for_tests()


def test_stage_yields_span_when_tracing_on(tracing_on):
    from app.core.timing import stage

    with stage("demo") as span:
        assert span is not None
        span.set_attribute("demo.value", 42)

    spans = tracing_on.get_finished_spans()
    assert len(spans) == 1
    s = spans[0]
    assert s.name == "pipeline.demo"
    assert s.attributes.get("demo.value") == 42


def test_stage_yields_none_when_tracing_off(tracing_off):
    from app.core.timing import stage

    with stage("demo") as span:
        assert span is None  # no-op when tracing is off


def test_stage_records_header_bucket_regardless_of_tracing(tracing_on):
    """Headers (the eval harness contract) must keep working even when
    tracing is on. They use a ContextVar bucket set up by TimingMiddleware
    — here we simulate that bucket directly."""
    from app.core import timing
    from app.core.timing import stage

    bucket: dict[str, float] = {}
    token = timing._current.set(bucket)
    try:
        with stage("stt"):
            pass
        with stage("tts"):
            pass
    finally:
        timing._current.reset(token)

    assert set(bucket.keys()) == {"stt", "tts"}
    for ms in bucket.values():
        assert ms >= 0.0


def test_stage_propagates_exception_and_still_finishes_span(tracing_on):
    from app.core.timing import stage

    class BoomError(RuntimeError):
        pass

    with pytest.raises(BoomError):
        with stage("unsafe"):
            raise BoomError("kaboom")

    spans = tracing_on.get_finished_spans()
    assert len(spans) == 1
    assert spans[0].name == "pipeline.unsafe"
    # Span ended (has end_time) even though the block raised
    assert spans[0].end_time is not None


def test_nested_stages_produce_parent_child_spans(tracing_on):
    from app.core.timing import stage

    with stage("outer"):
        with stage("inner"):
            pass

    spans = {s.name: s for s in tracing_on.get_finished_spans()}
    assert "pipeline.outer" in spans
    assert "pipeline.inner" in spans
    inner = spans["pipeline.inner"]
    outer = spans["pipeline.outer"]
    assert inner.parent is not None
    assert inner.parent.span_id == outer.context.span_id


def test_configure_is_idempotent(tracing_on):
    """Calling configure() after install doesn't blow up or replace state."""
    from app.core import tracing as tracing_mod

    # configure() short-circuits because _configured is already True
    result = tracing_mod.configure("whatever", "http://nope:4318")
    # Either True (already configured and tracer is set) or silent no-op
    assert result in (True, False)
    # Regardless, the tracer remains valid and stage() still works
    from app.core.timing import stage
    with stage("after-reconfigure"):
        pass
    assert any(
        s.name == "pipeline.after-reconfigure"
        for s in tracing_on.get_finished_spans()
    )
