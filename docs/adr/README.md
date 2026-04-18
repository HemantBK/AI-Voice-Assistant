# Architecture Decision Records

Each ADR is a short, dated record of a single architectural decision. We use the
[MADR](https://adr.github.io/madr/) style.

Numbering is 4-digit, zero-padded, monotonically increasing. Do not renumber.

## Index
- [0001 — Eval harness & baseline metrics](0001-eval-harness.md)
- [0002 — LLM provider abstraction & Ollama backend](0002-llm-provider-abstraction.md)

Phase design docs (under `docs/design/`):
- phase-b-streaming-pipeline.md (overall plan)
- phase-b1-notes.md (VAD endpointing)
- phase-b2-notes.md (sentence-level TTS streaming)
- phase-b3-notes.md (streaming LLM tokens)
- phase-b4-notes.md (continuous mic + server VAD)
- phase-b5-notes.md (barge-in + cancellation)
- phase-0.5-notes.md (audio hygiene)
- phase-c-notes.md (TTS providers + Indic)
- phase-d-notes.md (voice cloning scaffold)
- phase-e-notes.md (ARM64 edge build)
- phase-f-notes.md (hardening essentials)
