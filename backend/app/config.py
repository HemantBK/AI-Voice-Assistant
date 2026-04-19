import os
from dotenv import load_dotenv

load_dotenv()

LLM_PROVIDER = os.getenv("LLM_PROVIDER", "groq").lower()

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = os.getenv("GROQ_MODEL", os.getenv("LLM_MODEL", "llama-3.3-70b-versatile"))

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:3b")

LLM_MODEL = GROQ_MODEL if LLM_PROVIDER == "groq" else OLLAMA_MODEL
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.7"))
LLM_MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", "256"))

WHISPER_MODEL_SIZE = os.getenv("WHISPER_MODEL_SIZE", "base")
WHISPER_DEVICE = os.getenv("WHISPER_DEVICE", "cpu")
WHISPER_VAD_FILTER = os.getenv("WHISPER_VAD_FILTER", "true").lower() in ("1", "true", "yes")
WHISPER_VAD_MIN_SILENCE_MS = int(os.getenv("WHISPER_VAD_MIN_SILENCE_MS", "500"))
WHISPER_VAD_MIN_SPEECH_MS = int(os.getenv("WHISPER_VAD_MIN_SPEECH_MS", "150"))
WHISPER_VAD_SPEECH_PAD_MS = int(os.getenv("WHISPER_VAD_SPEECH_PAD_MS", "200"))
WHISPER_VAD_THRESHOLD = float(os.getenv("WHISPER_VAD_THRESHOLD", "0.5"))

TTS_PROVIDER = os.getenv("TTS_PROVIDER", "kokoro").lower()

KOKORO_VOICE = os.getenv("KOKORO_VOICE", "af_heart")
KOKORO_SPEED = float(os.getenv("KOKORO_SPEED", "1.0"))

PIPER_VOICE = os.getenv("PIPER_VOICE", "")
PIPER_DATA_DIR = os.getenv("PIPER_DATA_DIR", "")

OPENVOICE_CHECKPOINT_DIR = os.getenv("OPENVOICE_CHECKPOINT_DIR", "")
OPENVOICE_REFERENCE_WAV = os.getenv("OPENVOICE_REFERENCE_WAV", "")
OPENVOICE_BASE_SPEAKER = os.getenv("OPENVOICE_BASE_SPEAKER", "default")

SYSTEM_PROMPT = os.getenv("SYSTEM_PROMPT", (
    "You are a helpful voice assistant. Keep responses concise and conversational, "
    "ideally under 3 sentences. Be friendly and natural."
))

# -----------------------------------------------------------------------------
# Phase F — hardening knobs
# -----------------------------------------------------------------------------
def _csv(value: str) -> list[str]:
    return [v.strip() for v in value.split(",") if v.strip()]


# CORS. Default remains "*" for local dev friendliness; set explicit origins
# in production. Comma-separated list.
ALLOWED_ORIGINS = _csv(os.getenv("ALLOWED_ORIGINS", "*"))

# API key gate. Empty = auth disabled (dev). Non-empty = required on all
# non-docs endpoints and on WS handshakes.
API_KEY = os.getenv("API_KEY", "")

# Rate limit (per key if supplied, else per IP). RATE_LIMIT_PER_MINUTE<=0 disables.
RATE_LIMIT_PER_MINUTE = int(os.getenv("RATE_LIMIT_PER_MINUTE", "60"))
RATE_LIMIT_CAPACITY = int(os.getenv("RATE_LIMIT_CAPACITY", "20"))

# Logging
LOG_FORMAT = os.getenv("LOG_FORMAT", "text").lower()  # "text" | "json"
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# -----------------------------------------------------------------------------
# OpenTelemetry (Phase G.2). Off by default so the backend stays lean.
# Turn it on by setting OTEL_ENABLED=true; point at any OTLP/HTTP collector
# (Jaeger, Tempo, Grafana Cloud, Honeycomb, Datadog, ...). The included
# docker-compose.observability.yml overlay runs Jaeger locally.
# -----------------------------------------------------------------------------
OTEL_ENABLED = os.getenv("OTEL_ENABLED", "false").lower() in ("1", "true", "yes")
OTEL_SERVICE_NAME = os.getenv("OTEL_SERVICE_NAME", "voice-assistant-backend")
OTEL_EXPORTER_OTLP_ENDPOINT = os.getenv(
    "OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4318"
)
OTEL_SAMPLE_RATE = float(os.getenv("OTEL_SAMPLE_RATE", "1.0"))
