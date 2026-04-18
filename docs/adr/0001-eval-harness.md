# ADR 0001 — Eval harness & baseline metrics

- Status: Accepted
- Date: 2026-04-17
- Deciders: project lead
- Supersedes: —

## Context

Before we start the pivot to a local-first, low-latency, multilingual voice
assistant (Phases A–F), we have zero objective numbers for the current build.
"Feels faster" and "seems more accurate" are not acceptable evidence for
engineering decisions — every subsequent phase needs a measurable delta.

We also need the measurement infrastructure in place *first* because:

1. Swapping Groq → Ollama (Phase A) will regress latency and we must quantify it.
2. Streaming changes (Phase B) claim sub-second latency, which is only
   meaningful against a baseline.
3. Adding languages (Phase C) and voice cloning (Phase D) change output quality,
   which needs automatic scoring to avoid subjective drift.

## Decision

Adopt a lightweight, dependency-free eval harness under `eval/`:

- **`eval/lib/metrics.py`** — WER (Levenshtein on word tokens), keyword-hit for
  LLM answers, percentile stats (p50/p95/p99). Zero external deps — the whole
  point is that evals work even when the install is broken.
- **Runners**
  - `eval_llm.py` — golden Q&A with keyword-hit scoring
  - `eval_stt.py` — WER over a manifest of audio fixtures
  - `eval_tts.py` — synth latency + real-time-factor; can emit STT fixtures
    so the harness is self-bootstrapping (no copyrighted audio required)
  - `eval_latency.py` — black-box wall-clock against `/api/pipeline`, reads
    per-stage timings from response headers
  - `baseline.py` — orchestrator, writes a single combined JSON
- **Backend instrumentation** — a `TimingMiddleware` + `stage(name)` context
  manager in `app/core/timing.py`. Emits `X-Stage-*-Ms` and `X-Total-Ms`
  response headers and a structured log line. The latency runner depends on
  those headers — no OpenTelemetry needed for Phase 0.
- **Results** — `eval/results/<kind>-<timestamp>.json` plus
  `<kind>-latest.json` (gitignored; only kept locally for diffs).

## Alternatives considered

- **Ragas / DeepEval / TruLens** — overkill; designed for RAG, heavy deps,
  require LLM-as-judge (means an API key and cost). Reject for now; revisit
  when RAG is actually on the roadmap.
- **OpenTelemetry from day 1** — correct long-term but premature. We don't
  have infra to send spans anywhere yet. Response headers + logs are enough
  for Phase 0 and the migration to OTEL in Phase 3 is mechanical.
- **No harness; eyeball changes** — rejected. Every phase claim would be
  unverifiable.

## Consequences

Positive:
- Every future PR can include a before/after delta.
- Phase A (Ollama swap) becomes a measurable decision, not a vibes-based one.
- The harness doubles as a smoke test for the backend.

Negative / accepted tradeoffs:
- Keyword-hit scoring is coarse. It rewards presence, not correctness, and
  can be gamed by verbose answers. We will upgrade to LLM-as-judge or
  semantic similarity in Phase 3 alongside observability work.
- TTS round-trip to generate STT fixtures gives optimistic WER (clean audio,
  no background noise, no accents). We accept this for the baseline and will
  add real-speech fixtures in Phase C when we add languages.
- Baseline is machine-dependent (CPU, RAM). Results are only comparable on
  the same host; we log `env_snapshot()` with every run to make that explicit.

## Follow-ups

- Phase 3: migrate the timing middleware to OpenTelemetry spans.
- Phase 3: add LLM-as-judge for answer faithfulness/correctness.
- Phase C: add real human-recorded fixtures for Hindi/Tamil/Telugu.
- CI: wire `baseline.py` to run on PRs and block regressions > N%.
