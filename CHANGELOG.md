# Changelog

All notable changes to this project are documented here. Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versions follow [SemVer](https://semver.org/). Each entry also links the phase design doc under `docs/design/`.

## [Unreleased]

Placeholder for the next release. Contributors: add your entry here.

---

## Phase F — Hardening essentials

See [phase-f-notes](docs/design/phase-f-notes.md).

**Added**
- `APIKeyMiddleware` (`backend/app/core/auth.py`) — opt-in via `API_KEY`; constant-time comparison.
- `RateLimitMiddleware` (`backend/app/core/rate_limit.py`) — token bucket per-key / per-IP.
- Structured JSON logging via `LOG_FORMAT=json` (`backend/app/core/logging.py`).
- `/ready` liveness/readiness endpoint.
- `backend/pyproject.toml` — pytest + ruff config.
- `backend/tests/` — unit tests for sentence splitter, metrics, turn manager.
- `.github/workflows/ci.yml` — Python 3.11/3.12 matrix, eslint, pytest, eval self-test.

**Changed**
- CORS now driven by `ALLOWED_ORIGINS` env var (was hardcoded `*`).
- Middleware chain order: CORS → APIKey → Rate-limit → Timing.

---

## Phase E — Edge (ARM64 Pi 5) scaffold

See [phase-e-notes](docs/design/phase-e-notes.md).

**Added**
- `backend/Dockerfile.arm64` — ARM64 build recipe with PyTorch CPU wheels.

**Status:** scaffold only — needs physical hardware to validate.

---

## Phase D' — Voice cloning (OpenVoice v2) scaffold

See [phase-d-notes](docs/design/phase-d-notes.md).

**Added**
- `backend/app/services/tts/openvoice_provider.py` — provider scaffold.
- `TTS_PROVIDER=openvoice` option in the factory.
- `frontend/src/components/ConsentGate.jsx` — blocking consent modal.
- `frontend/src/services/consent.js` — localStorage-backed consent state.
- Env knobs: `OPENVOICE_CHECKPOINT_DIR`, `OPENVOICE_REFERENCE_WAV`, `OPENVOICE_BASE_SPEAKER`.

**Status:** scaffold only — checkpoint download, enrollment, and watermarking strategy are user-side setup.

---

## Phase C — TTS provider abstraction + multilingual

See [phase-c-notes](docs/design/phase-c-notes.md).

**Added**
- `backend/app/services/tts/` package: `base.py`, `kokoro_provider.py`, `piper_provider.py`, `factory.py`.
- Env knobs: `TTS_PROVIDER`, `PIPER_VOICE`, `PIPER_DATA_DIR`.
- Default voice mapping for English, Hindi, Spanish, French, German, Chinese, Italian, pt-BR.

**Changed**
- `tts_service.synthesize()` signature gains optional `language: str | None`.
- Kokoro provider now supports `en`, `en-gb`, `ja`, `zh` via lazy per-language pipelines.

---

## Phase 0.5 — Audio hygiene

See [phase-0.5-notes](docs/design/phase-0.5-notes.md).

**Added**
- `backend/app/audio/resample.py` — linear PCM16 resample, DC-offset removal, peak normalize.

**Rationale:** server-side fallbacks. Browser `getUserMedia` with AEC/NS/AGC handles the common case.

---

## Phase B.5 — Barge-in and turn cancellation

See [phase-b5-notes](docs/design/phase-b5-notes.md).

**Added**
- `backend/app/streaming/turn_manager.py` — single in-flight turn per WS with graceful cancel.
- `{"type":"barge_in"}` client message and `{"type":"cancelled"}` server response.
- `frontend/src/audio/clientVad.js` — RMS-energy VAD for client-side barge-in (not yet UI-wired).
- `VoiceWsClient.bargeIn()`.

**Changed**
- Clicking the mic while `status === "speaking"` stops playback + sends barge-in.
- Continuous-mode `speech_start` during a busy turn triggers cancel + emits `cancelled`.

---

## Phase B.4 — Continuous mic + server VAD

See [phase-b4-notes](docs/design/phase-b4-notes.md).

**Added**
- `backend/app/streaming/vad.py` — `FrameVad` wrapping Silero VAD (onnx).
- `backend/app/streaming/wav.py` — PCM16 → WAV byte writer.
- `frontend/public/recorder-worklet.js` — AudioWorklet for 48k→16k PCM16 frames.
- `frontend/src/audio/microphoneStream.js` — mic capture with browser AEC/NS/AGC.
- `?continuous=1` query param; `audio_frame` and `end_of_turn` message types.
- `silero-vad>=5.1` dependency (lazy-imported).

**Status:** API plumbing only. UI switchover deferred to B.4-UI follow-up.

---

## Phase B.3 — Streaming LLM tokens → sentence splitter → TTS

See [phase-b3-notes](docs/design/phase-b3-notes.md).

**Added**
- `backend/app/streaming/async_stream.py` — `async_iter_sync` bridges blocking LLM generators into asyncio.
- `{"type":"llm_delta","delta":"..."}` token events.
- `first_llm_delta_ms` metric in `eval_streaming.py`.

**Changed**
- `/ws/voice?stream=1` now streams LLM tokens; each complete sentence is synthesized and sent as it forms.
- Frontend `VoiceAssistant` renders live typing from `llm_delta` and reconciles on `response`.

---

## Phase B.2 — Sentence-level TTS streaming

See [phase-b2-notes](docs/design/phase-b2-notes.md).

**Added**
- `backend/app/streaming/sentence_splitter.py` — `split_sentences` and `IncrementalSentenceSplitter`.
- `backend/app/routers/pipeline.py` — `?stream=1` WS mode with `tts_chunk` / `tts_end` events.
- `frontend/src/audio/streamingPlayer.js` — gapless sequenced playback; `stop()` primitive for barge-in.
- `frontend/src/services/voiceWsClient.js` — streaming WS wrapper.
- `eval/runners/eval_streaming.py` — measures `first_audio_byte_ms`.

**Changed**
- Frontend replaces REST `/api/pipeline` with the streaming WS flow (REST endpoint still available as fallback).

---

## Phase B.1 — Whisper VAD endpointing

See [phase-b1-notes](docs/design/phase-b1-notes.md).

**Added**
- `WHISPER_VAD_FILTER` (default true) + tunables `WHISPER_VAD_MIN_SILENCE_MS`, `MIN_SPEECH_MS`, `SPEECH_PAD_MS`, `THRESHOLD`.
- `stt_service.transcribe` now returns `audio_duration_s`, `speech_duration_s`, `vad_trimmed_ms`.
- `eval_stt.py` surfaces `mean_vad_trimmed_ms`.

---

## Phase A — Ollama LLM provider (local-first default)

See [ADR 0002](docs/adr/0002-llm-provider-abstraction.md).

**Added**
- `backend/app/services/llm/` package: `base.py` Protocol, `groq_provider.py`, `ollama_provider.py`, `factory.py`.
- `LLM_PROVIDER` env switch; default flipped to `ollama` in `.env.example`.
- Ollama + `ollama-pull` services in `docker-compose.yml`.
- `qwen2.5:3b` default model (Apache-2.0).

**Changed**
- `llm_service.py` reduced to a thin façade. Router code unchanged.
- README reframed around local-first pitch.

---

## Phase 0 — Eval harness + baseline metrics

See [ADR 0001](docs/adr/0001-eval-harness.md).

**Added**
- `eval/lib/metrics.py` — zero-dep WER, keyword-hit, p50/p95/p99.
- `eval/runners/` — `eval_llm.py`, `eval_stt.py`, `eval_tts.py`, `eval_latency.py`, `baseline.py`.
- `eval/datasets/llm/golden_qa.jsonl` — 20-item curated set across 9 categories.
- `backend/app/core/timing.py` — `TimingMiddleware` + `stage()` context manager emitting `X-Stage-*-Ms` and `X-Total-Ms` response headers.
- `docs/adr/README.md`, `docs/design-doc-template.md`.

---

## Initial project

Scaffolded baseline voice assistant (STT + LLM + TTS + WebSocket) by the original author.
