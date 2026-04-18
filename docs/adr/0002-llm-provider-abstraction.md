# ADR 0002 — LLM provider abstraction & Ollama (local) backend

- Status: Accepted
- Date: 2026-04-17
- Phase: A — Go fully local
- Supersedes: —

## Context

The current build calls Groq directly from `app/services/llm_service.py`. That
ties the project to a cloud API, an account/sign-up flow, and Meta's Llama
license. The project's identity (per the pivot) is **local-first, offline,
private** — the cloud LLM contradicts every line of that pitch.

We also want to compare backends with the eval harness (ADR 0001), which
requires the swap to be a runtime config toggle, not a code branch.

## Decision

Introduce a thin `LLMProvider` interface and ship two implementations:

- **GroqProvider** — wraps the existing Groq SDK call. Kept for benchmarking
  and as a fallback for low-spec hardware.
- **OllamaProvider** — talks to a local Ollama daemon on `OLLAMA_HOST`
  (default `http://localhost:11434`). Default model: `qwen2.5:3b`
  (Apache-2.0, ~2 GB, comfortably runs on 8 GB RAM CPU-only).

Selection is by the `LLM_PROVIDER` env var (`groq` | `ollama`). Default for
new installs is `ollama` to match the project identity; the `.env.example` is
updated accordingly. `llm_service.chat` and `llm_service.chat_stream` keep
their existing signatures so routers do not change.

Layout:

```
backend/app/services/
    llm_service.py            # façade — preserves the public chat / chat_stream API
    llm/
        __init__.py
        base.py               # Protocol: chat, chat_stream, name
        groq_provider.py
        ollama_provider.py
        factory.py            # get_provider() — singleton, env-driven
```

Docker Compose gains an `ollama` service (`ollama/ollama` image), a named
volume for the model cache, and an `ollama-pull` init container that pulls
`OLLAMA_MODEL` on first boot so the assistant works after a single
`docker compose up`.

## Alternatives considered

- **Replace Groq entirely (no abstraction).** Simplest but loses the
  benchmark backstop and forces every Phase-A user to install Ollama before
  the app does anything. Reject — provider switch costs ~80 LOC.
- **llama-cpp-python in-process.** No daemon, smaller ops surface. Rejected
  for Phase A: model loading happens inside the FastAPI worker, blocking the
  event loop on startup, and concurrency control is harder. Revisit for
  Phase E (edge / Pi single-process).
- **LangChain / LiteLLM.** Solves provider switching plus dozens of others
  we will never use. Heavy dep, opinionated. Reject; we have two providers,
  a Protocol is enough.

## Consequences

Positive:
- The "100% local, no API key" pitch becomes literally true once
  `LLM_PROVIDER=ollama` is the default.
- Eval harness can A/B providers by flipping one env var and re-running
  `eval_llm.py`.
- Future providers (vLLM, llama.cpp, OpenAI for parity tests) drop into
  `llm/` without router changes.

Negative / accepted tradeoffs:
- Adds a runtime dependency on a separate Ollama process (or container).
  Documented in README; the docker-compose path is one command.
- Local quality < Groq Llama 3.3 70B. Qwen2.5-3B is honest about this; the
  README will state it explicitly and direct users to larger models
  (`qwen2.5:7b`, `llama3.1:8b`) if they have the RAM.
- Ollama Python client adds one dependency (`ollama`, MIT). Acceptable —
  it's a 200-line HTTP wrapper.

## Rollout

1. Land the abstraction with `LLM_PROVIDER` defaulting to `groq` in this
   commit so existing setups don't break.
2. Run `eval_llm.py` against both providers, attach results to PR.
3. Flip default to `ollama` in a follow-up commit once numbers are recorded.

## Rollback

Revert the commits. No persisted state, no migrations.

## Success metrics

- `eval_llm.py` runs cleanly against both providers.
- Latency baseline captured for each (for the Phase B streaming work).
- README install path "I have nothing installed" → "voice reply" still works
  via docker-compose.
