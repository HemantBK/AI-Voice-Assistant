# LLM-as-judge rubric

This is the human-readable version of the prompt the judge model sees.
Kept in source for transparency: when the judge scores your assistant,
you can audit the exact criteria it used.

The machine-readable version lives in `eval/lib/judge.py` as the
`RUBRIC` constant. Keep this file and that string in sync.

## What is being scored

For every golden Q&A pair, the judge sees:
- `QUESTION`  — the prompt sent to the voice assistant
- `ANSWER`    — the assistant's reply

It returns three integer scores (1–5) and a one-sentence rationale.

## The three dimensions

### Correctness (1–5)

Is the answer factually accurate?

| Score | Meaning |
|---|---|
| 5 | Fully correct and specific |
| 4 | Correct with minor omission |
| 3 | Partially correct or vague |
| 2 | Mostly wrong or misleading |
| 1 | Completely wrong |

### Relevance (1–5)

Does the answer address the question that was actually asked?

| Score | Meaning |
|---|---|
| 5 | Directly and fully addresses it |
| 3 | Partial; drifts or only touches part |
| 1 | Unrelated |

### Conciseness (1–5)

Appropriate length for a *spoken* reply (≤ 3 sentences per the system
prompt)?

| Score | Meaning |
|---|---|
| 5 | Crisp, ≤ 2 sentences, no filler |
| 3 | Acceptable, slightly long, some filler |
| 1 | Rambling, multiple paragraphs, multiple ideas |

## Output format

The judge is instructed to return strict JSON:

```json
{"correctness": 4, "relevance": 5, "conciseness": 3, "rationale": "Correct but slightly long for voice."}
```

No prose, no code fence, no chain-of-thought. Failures to parse are
caught per-item and marked `ok: false`.

## Honest limitations of LLM-as-judge

- **Self-preference.** A judge tends to prefer its own family of models.
  Mitigate by running two judges from different families (e.g.
  `ollama:qwen2.5:7b` + `groq:llama-3.3-70b`) and reporting agreement.
- **Length bias.** Judges tend to reward longer, more-confident answers
  on the correctness dimension even when shorter ones are truthful.
  The rubric explicitly penalizes length via the conciseness dimension.
- **Position / verbosity bias** from the prompt wording itself. The
  rubric asks for "one short sentence" rationale to reduce CoT effects.
- **Consistency over time.** Judge model updates can shift absolute
  scores. Treat scores as *relative within a run*, not as a stable
  benchmark across months.

## What success looks like

- Mean score improves as you ship better prompts / models / retrieval.
- Two-judge agreement (`within_1` rate) stays above ~80% — below that,
  your metric is too noisy to trust.
- Rationales spot-check as sensible (read 5 random ones after each run).
