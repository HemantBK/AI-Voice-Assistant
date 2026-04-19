# Phase G.2 — OpenTelemetry tracing + Jaeger (ship notes)

Goal: replace (actually, *augment*) the response-header timing with
proper OTel spans, exported via OTLP/HTTP to any compliant backend.
Ship with a Jaeger-all-in-one overlay so there's a zero-account local
path; leave the door open for Grafana Cloud / Tempo / Honeycomb.

## What shipped

**Backend**
- `backend/app/core/tracing.py`
  - `configure(service_name, endpoint, sample_rate)` — idempotent setup.
    Lazy-imports the OTel SDK; if missing, logs a warning and returns
    `False`. The backend still runs.
  - `get_tracer()` — returns a tracer or `None` (hot-path safe).
  - `instrument_fastapi(app)` — wraps HTTP routes in auto-spans.
  - `_install_inmemory_tracer()` / `_uninstall_tracer_for_tests()` —
    idempotent test helpers (OTel forbids replacing a TracerProvider
    mid-process, so we clear an in-memory exporter between tests).
- `backend/app/core/timing.py` — `stage()` now yields the active OTel
  span (or `None`). Header bucket behavior unchanged → the eval harness
  still reads `X-Stage-*-Ms` and `X-Total-Ms`.
- `backend/app/routers/pipeline.py` — `_run_turn` is fully wrapped in a
  `voice.turn` parent span with attributes like `voice.streaming`,
  `voice.transcript_chars`, `voice.response_chars`, `voice.tts_chunks`.
  Each stage span (`pipeline.stt`, `pipeline.llm_stream`, `pipeline.tts`)
  carries per-stage attributes: language, VAD trim, streaming flag,
  audio bytes, sentence length, seq.
- `backend/app/main.py` — calls `tracing.configure()` before app
  creation (so FastAPI auto-instrumentation picks it up) and installs
  `FastAPIInstrumentor` when OTel is enabled.
- `backend/app/config.py` + `.env.example` — `OTEL_ENABLED`,
  `OTEL_SERVICE_NAME`, `OTEL_EXPORTER_OTLP_ENDPOINT`, `OTEL_SAMPLE_RATE`.
- `backend/requirements.txt` — adds `opentelemetry-api`,
  `opentelemetry-sdk`, `opentelemetry-exporter-otlp-proto-http`,
  `opentelemetry-instrumentation-fastapi`.

**Infra**
- `docker-compose.observability.yml` — Jaeger all-in-one service +
  backend env overrides (`OTEL_ENABLED=true`,
  `OTEL_EXPORTER_OTLP_ENDPOINT=http://jaeger:4318`).
- Jaeger UI at `http://localhost:16686`.

**Tests**
- `backend/tests/test_tracing.py` — 6 unit tests using
  `InMemorySpanExporter`:
  - stage yields span when tracing on
  - stage yields None when tracing off
  - header bucket still fills regardless of tracing
  - exception propagation ends the span cleanly
  - nested stages produce parent-child spans
  - configure is idempotent
- Full suite: 38/38 passing.

## Running it

Zero-account local stack:

```bash
docker compose -f docker-compose.yml -f docker-compose.observability.yml up
# wait for Jaeger healthcheck
# open http://localhost:16686 → pick service "voice-assistant-backend"
# make a voice turn via the frontend → see the trace waterfall
```

Native (no Docker):

```bash
# terminal 1 — Jaeger
docker run --rm --name jaeger \
  -e COLLECTOR_OTLP_ENABLED=true \
  -p 16686:16686 -p 4318:4318 \
  jaegertracing/all-in-one:1.57

# terminal 2 — backend with OTel on
cd backend
OTEL_ENABLED=true \
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318 \
  python run.py
```

## What the trace waterfall tells you

A single voice turn produces:

```
voice.turn                    <-- total turn duration
├── pipeline.stt              <-- Whisper time (attributes: language, VAD trim)
├── pipeline.llm_stream       <-- from first request to last token
│   ├── pipeline.tts          <-- sentence 1 synth
│   ├── pipeline.tts          <-- sentence 2 synth
│   └── ...
└── (tail) pipeline.tts       <-- trailing sentence after flush()
```

The gap between `pipeline.stt`'s end and `pipeline.llm_stream`'s first
token is your LLM TTFT. The gap between the first TTS chunk's end and
the next one is your streaming headroom. These gaps are the data you
use to prove the streaming design (see ARCHITECTURE.md's gantt).

## Switching to Grafana Cloud / Tempo / Honeycomb / Datadog

Any OTLP/HTTP endpoint works. Example for Grafana Cloud free tier:

```bash
OTEL_EXPORTER_OTLP_ENDPOINT=https://otlp-gateway-<zone>.grafana.net/otlp
OTEL_EXPORTER_OTLP_HEADERS="Authorization=Basic <your-grafana-token>"
OTEL_ENABLED=true
```

(The current `tracing.configure()` takes an endpoint; for headers-based
auth add `os.getenv("OTEL_EXPORTER_OTLP_HEADERS")` handling if you need
managed backends — one-liner extension, not done here.)

## Known limitations

- **WebSocket auto-instrumentation is thin.** FastAPIInstrumentor wraps
  HTTP routes but WebSocket messages aren't per-message-instrumented
  upstream. We add manual `voice.turn` spans per turn to compensate.
- **Span-provider is process-global.** Once `configure()` runs you
  can't swap providers without restarting. Documented; tests handle it.
- **No metrics yet.** This slice adds traces only. Adding a
  `MeterProvider` + a `Counter`/`Histogram` for tokens-per-second and
  audio-bytes-per-turn is a small follow-up.
- **No log-trace correlation.** The `LOG_FORMAT=json` structured logs
  don't yet carry the active `trace_id`. Add
  `opentelemetry-instrumentation-logging` + attach span context to log
  records — ~10 LOC follow-up.
- **Header-based auth** for managed backends isn't wired (see above).

## Rollback

Set `OTEL_ENABLED=false` (the default). Backend drops tracing and keeps
the `X-Stage-*-Ms` headers. No schema change, no data migration.

## Follow-ups worth doing next

- Log-trace correlation (trace_id in every JSON log line).
- Meter SDK + custom metrics (`voice.turn.duration_ms`,
  `tts.rtf`, `llm.tokens_per_sec`).
- Span event for `barge_in` cancellations so they show up in the
  waterfall.
- Grafana dashboard JSON committed to `docs/observability/` so anyone
  importing into a fresh Grafana instance gets the same charts.
