# Phase G.1 — LLM-as-judge evaluation (ship notes)

Goal: upgrade the LLM eval from "does keyword appear in answer" to "a
stronger LLM scores the answer on correctness / relevance / conciseness
against a published rubric." Optional second judge quantifies inter-rater
agreement so we can detect when the metric itself is noise.

## What shipped

- `eval/lib/judge.py`
  - `Judge` — thin wrapper around `chat(messages) -> str`. `score()`
    returns a `JudgeScore` dataclass with per-dimension ints + rationale.
  - `extract_json()` — balance-aware JSON extractor. Handles `json`
    code fences, leading/trailing prose, and nested braces inside strings.
  - `pair_agreement()` — per-item exact-match / within-1 / mean-abs-diff.
  - `make_judge(spec)` — parses `ollama`, `ollama:qwen2.5:7b`, `groq`,
    `groq:llama-3.3-70b-versatile`. Reuses project LLM providers so no
    new auth flow is needed.
- `eval/datasets/llm/rubric.md` — human-readable rubric kept in sync
  with the `RUBRIC` prompt constant.
- `eval/runners/eval_llm.py` — new `--judge` and `--judge2` flags. Per-
  item scores, per-judge summary, optional agreement summary. Table
  output grows columns for `j1_mean`, `j2_mean`, `within_1`.
- `backend/tests/test_judge.py` — 18 unit tests covering JSON extraction
  (plain / fenced / prefix+suffix / nested braces / empty / no-object),
  score validation (happy path, string numbers, out of range, empty
  answer short-circuit, chat exception, bad JSON), and agreement
  computation (exact / within-1 / disagree / one-errored).
- README + eval/README updated with usage + metric definitions.

## Running it

```bash
# local, free, single judge
python -m eval.runners.eval_llm --judge ollama --save

# two-judge cross-check (reports within-1 agreement)
python -m eval.runners.eval_llm \
  --judge  ollama:qwen2.5:7b \
  --judge2 groq:llama-3.3-70b-versatile \
  --save
```

## How to read the numbers

The runner reports three new things when `--judge` is set:

1. **Per-dimension means (1-5)** — correctness, relevance, conciseness.
   Use them to spot where the assistant is weak. If correctness is 4.2
   but conciseness is 2.1, you have a verbosity problem.
2. **Overall mean** — unweighted average of the three. Convenient single
   number for diffs across runs.
3. **Within-1 agreement rate** (only when `--judge2` is set) — fraction
   of items where both judges scored within 1 point on every dimension.
   Target > 80%. Below that, don't trust the absolute scores; treat
   them only as relative within one run.

## Known biases and how we partially mitigate them

| Bias | Mitigation in this slice | Residual risk |
|---|---|---|
| **Self-preference** — judge prefers its own model family | Support `--judge2` from a different family and report agreement | Still present when using one judge |
| **Length bias** — judges reward longer answers as "more correct" | Explicit conciseness dimension penalizes length | Judges may still inflate correctness on long replies |
| **Position/order bias** | Only one answer per judge call; no pairwise A/B | We skip pairwise for simplicity |
| **Chain-of-thought drift** | Rubric asks for one-sentence rationale only | Some models still produce CoT in the rationale |
| **Cross-version drift** | Pinned judge model string is recorded in results JSON | Absolute scores may drift across model updates |

See `eval/datasets/llm/rubric.md` for the full rubric + bias discussion.

## Cost / time notes

- **Ollama `qwen2.5:7b` on CPU:** 3-15 s per item. 20 items ≈ 60-300 s.
  Free, fully local.
- **Groq `llama-3.3-70b-versatile`:** ~1 s per item. 20 items ≈ 20 s.
  Free tier; rate limit is generous for eval scale.
- **Both judges together:** additive, worst case ~5 min for 20 items.

Run with `--limit 5` while iterating on rubric wording.

## What's explicitly NOT in this slice

- **Pairwise A/B scoring** (answer-from-model-A vs answer-from-model-B).
  Useful when comparing two models' outputs; not yet needed.
- **LLM-judge over retrieval context** (Ragas-style faithfulness).
  Waits until RAG lands.
- **Statistical significance tests** on score deltas (McNemar, bootstrap
  CIs). Current sample size (20 items) is too small for serious stats;
  we'd need to grow the golden set first.
- **CI integration** — the judge adds minutes to the run and needs a
  running Ollama or a Groq key, so we don't gate PRs on it yet. Design
  goal: make it a nightly cron, not a PR blocker.

## Rollback

Drop the `--judge` flag and you get the Phase-0 keyword-hit eval back,
unchanged. The judge module is isolated; deleting `eval/lib/judge.py`
and removing the three `make_judge`/`pair_agreement` imports from
`eval_llm.py` reverses the slice with zero data migration.

## Follow-ups

- Grow `golden_qa.jsonl` to 100+ items once the rubric stabilizes.
- Add per-category breakdowns (factual / reasoning / conversational
  dimensions).
- Wire a nightly GitHub Actions job that runs the judge eval against
  `main` and commits the result JSON to a `eval/results/history/` path.
- Swap to [promptfoo](https://github.com/promptfoo/promptfoo) if we
  need A/B testing infrastructure we don't want to build.
