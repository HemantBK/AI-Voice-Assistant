# Eval harness

Baseline metrics for the voice assistant. Run before and after every change so
we can prove improvement instead of claiming it.

What it measures today:

| Kind    | Metric                                       | How                                             |
|---------|----------------------------------------------|-------------------------------------------------|
| LLM     | keyword-hit accuracy, latency                | golden Q&A (`datasets/llm/golden_qa.jsonl`)     |
| LLM     | judge scores (correctness / relevance / conciseness) + 2-judge agreement | `--judge ollama` / `--judge groq` (see below)   |
| STT     | WER per sample, latency                      | manifest of audio fixtures + reference text     |
| TTS     | latency, real-time factor (RTF)              | synth each prompt, measure time / audio length  |
| E2E     | wall + per-stage latency                     | POST `/api/pipeline`, read `X-Stage-*-Ms`       |
| E2E     | first_llm_delta_ms / first_audio_byte_ms     | WS streaming runner                             |

All outputs land in `eval/results/` as timestamped JSON plus a `*-latest.json`.
Gitignored.

## Setup

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate         # Windows (bash: source .venv/Scripts/activate)
pip install -r requirements.txt
cp .env.example .env            # fill in GROQ_API_KEY if evaluating the current cloud LLM
```

The LLM/STT/TTS runners import `app.services.*` directly, so they need the
backend deps installed, but **no server needs to be running** for those three.
Only the latency runner hits a live server.

## Run it

From the project root (`AI Voice assitant project`):

```bash
# Full baseline (LLM + TTS + STT) — writes combined JSON
python -m eval.runners.baseline --save=false   # prints table
python -m eval.runners.baseline                 # also writes results/baseline-*.json

# One kind at a time
python -m eval.runners.eval_llm --save
python -m eval.runners.eval_tts --emit-stt-fixtures --save   # seeds STT fixtures
python -m eval.runners.eval_stt --save

# LLM-as-judge (local, free — uses qwen2.5:7b via Ollama)
python -m eval.runners.eval_llm --judge ollama --save

# Two-judge cross-check (reports inter-rater agreement)
python -m eval.runners.eval_llm \
    --judge  ollama:qwen2.5:7b \
    --judge2 groq:llama-3.3-70b-versatile \
    --save

# E2E latency (requires server running: `cd backend && python run.py`)
python -m eval.runners.eval_latency \
    --fixture eval/datasets/stt/tts-roundtrip-00.wav \
    --runs 10 --warmup 1 --save
```

## Bootstrapping STT fixtures

The repo ships with **no audio files**. Two options:

1. **Self-bootstrap (zero effort, optimistic numbers):**
   ```bash
   python -m eval.runners.eval_tts --emit-stt-fixtures
   ```
   Each prompt in `datasets/tts/prompts.txt` is synthesized and appended to
   `datasets/stt/manifest.json`. This measures STT on clean TTS audio — a
   ceiling, not a realistic WER.

2. **Record real samples (realistic numbers):**
   - Drop `.wav`/`.mp3` files in `datasets/stt/`.
   - Append entries to `manifest.json`. See `datasets/stt/README.md`.

## Reading the output

- **LLM accuracy** — `hits / scorable`. `scorable` excludes conversational
  prompts with empty `must_contain`, so chit-chat doesn't skew the score.
- **Judge mean** — average of the judge's correctness/relevance/conciseness
  scores across all items. Each dimension is 1–5 per [`rubric.md`](datasets/llm/rubric.md).
- **within-1 agreement** — fraction of items where two judges scored
  within 1 point on every dimension. Below ~80% the metric is noise.
- **WER** — 0.0 is perfect; 1.0 is "all words wrong". Lower is better.
- **RTF** — `synth_time / audio_time`. <1.0 means faster than real-time.
- **Stage latency** — parsed from `X-Stage-stt-Ms`, `X-Stage-llm-Ms`,
  `X-Stage-tts-Ms` on the pipeline response.

## Design rationale

See [`docs/adr/0001-eval-harness.md`](../docs/adr/0001-eval-harness.md) for why
we built this before anything else and what we deliberately did *not* include.
