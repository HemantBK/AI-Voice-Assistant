from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import (
    ALLOWED_ORIGINS,
    LOG_FORMAT,
    LOG_LEVEL,
    OTEL_ENABLED,
    OTEL_EXPORTER_OTLP_ENDPOINT,
    OTEL_SAMPLE_RATE,
    OTEL_SERVICE_NAME,
)
from app.core import tracing
from app.core.auth import APIKeyMiddleware
from app.core.logging import configure as configure_logging
from app.core.rate_limit import RateLimitMiddleware
from app.core.timing import TimingMiddleware
from app.routers import chat, pipeline, stt, tts

configure_logging(LOG_FORMAT, LOG_LEVEL)

# Configure OpenTelemetry before app creation so FastAPI auto-instrumentation
# sees a tracer provider. Safe no-op when OTEL_ENABLED=false.
if OTEL_ENABLED:
    tracing.configure(
        service_name=OTEL_SERVICE_NAME,
        endpoint=OTEL_EXPORTER_OTLP_ENDPOINT,
        sample_rate=OTEL_SAMPLE_RATE,
    )

app = FastAPI(
    title="AI Voice Assistant API",
    description="Local-first voice assistant — STT + LLM + TTS, streaming over WebSocket.",
    version="1.0.0",
)

if OTEL_ENABLED:
    tracing.instrument_fastapi(app)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*", "x-api-key"],
)
app.add_middleware(APIKeyMiddleware)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(TimingMiddleware)

app.include_router(stt.router)
app.include_router(chat.router)
app.include_router(tts.router)
app.include_router(pipeline.router)


@app.get("/")
async def root():
    return {
        "name": "AI Voice Assistant API",
        "status": "running",
        "docs": "/docs",
        "endpoints": {
            "stt": "POST /api/stt/transcribe",
            "chat": "POST /api/chat/",
            "tts": "POST /api/tts/synthesize",
            "pipeline": "POST /api/pipeline",
            "websocket": "WS /ws/voice (?stream=1&continuous=1 optional)",
        },
    }


@app.get("/health")
async def health():
    return {"status": "healthy"}


@app.get("/ready")
async def ready():
    # Lightweight readiness check. Real checks (provider reachability,
    # model availability) are in the followups list.
    return {"status": "ready"}
