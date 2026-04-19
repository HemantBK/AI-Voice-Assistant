"""LLM-as-judge scoring for the eval harness.

We ask a stronger / different LLM to rate each Q&A pair on three dimensions
and return a strict JSON verdict. A second judge can run in parallel to
quantify agreement — if two independent judges don't agree, the metric
itself is noise.

Rubric is in eval/datasets/llm/rubric.md for human review. The RUBRIC
constant below is the verbatim prompt given to the judge.

Design choices:
  - Temperature 0.0 for reproducibility.
  - Reuses the project's LLM providers for the judge (Ollama or Groq) —
    no new dep, no new API key flow.
  - Judge failures are per-item; a bad parse on one Q/A does not fail the
    whole run. Failed items get ok=False + error in the JSON.
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from typing import Callable

logger = logging.getLogger(__name__)


RUBRIC = """You are an evaluator grading a voice assistant's reply.

Rate the assistant's ANSWER to the QUESTION on three dimensions. Each is an
integer 1-5 (higher is better).

  CORRECTNESS (1-5): Is the answer factually accurate?
    5 = fully correct and specific
    4 = correct with minor omission
    3 = partially correct or vague
    2 = mostly wrong or misleading
    1 = completely wrong

  RELEVANCE (1-5): Does the answer address the question that was asked?
    5 = directly and fully addresses the question
    3 = partial; drifts or only touches part
    1 = unrelated

  CONCISENESS (1-5): Appropriate length for a spoken reply (<= 3 sentences)?
    5 = crisp, <= 2 sentences, no filler
    3 = acceptable, slightly long, some filler
    1 = rambling, multiple paragraphs, multiple ideas

Return ONLY a single JSON object, no prose, no code fence:
{"correctness": <int>, "relevance": <int>, "conciseness": <int>, "rationale": "<one short sentence>"}
"""


ChatFn = Callable[[list[dict]], str]


@dataclass
class JudgeScore:
    correctness: int
    relevance: int
    conciseness: int
    rationale: str = ""
    ok: bool = True
    error: str | None = None

    @property
    def mean(self) -> float:
        if not self.ok:
            return 0.0
        return (self.correctness + self.relevance + self.conciseness) / 3.0

    def as_dict(self) -> dict:
        return {
            "correctness": self.correctness,
            "relevance": self.relevance,
            "conciseness": self.conciseness,
            "mean": round(self.mean, 2),
            "rationale": self.rationale,
            "ok": self.ok,
            "error": self.error,
        }


class Judge:
    """LLM-as-judge wrapping a callable `chat(messages) -> str`."""

    def __init__(self, name: str, model: str, chat_fn: ChatFn):
        self.name = name
        self.model = model
        self._chat = chat_fn

    def score(self, question: str, answer: str) -> JudgeScore:
        if not answer or not answer.strip():
            return JudgeScore(0, 0, 0, ok=False, error="empty answer")
        messages = [
            {"role": "system", "content": RUBRIC},
            {"role": "user", "content": f"QUESTION:\n{question}\n\nANSWER:\n{answer}\n\nReturn JSON only."},
        ]
        try:
            raw = self._chat(messages)
        except Exception as e:
            return JudgeScore(0, 0, 0, ok=False, error=f"judge call failed: {e}")
        try:
            obj = extract_json(raw)
            return JudgeScore(
                correctness=_validate_score(obj, "correctness"),
                relevance=_validate_score(obj, "relevance"),
                conciseness=_validate_score(obj, "conciseness"),
                rationale=str(obj.get("rationale", ""))[:280],
            )
        except Exception as e:
            logger.warning("judge %s/%s parse failed: %s | raw=%r", self.name, self.model, e, raw[:200])
            return JudgeScore(0, 0, 0, ok=False, error=str(e))


def extract_json(raw: str) -> dict:
    """Pull the first JSON object out of a possibly-fenced LLM reply."""
    if not raw:
        raise ValueError("empty judge output")
    s = raw.strip()
    s = re.sub(r"^```(?:json)?\s*", "", s)
    s = re.sub(r"\s*```\s*$", "", s)
    # Prefer a JSON object at the start if present
    if s.startswith("{"):
        # balance-aware find of matching closing brace
        depth = 0
        for i, ch in enumerate(s):
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return json.loads(s[: i + 1])
    m = re.search(r"\{.*\}", s, flags=re.DOTALL)
    if not m:
        raise ValueError(f"no JSON object in output: {raw[:160]!r}")
    return json.loads(m.group(0))


def _validate_score(obj: dict, key: str) -> int:
    if key not in obj:
        raise ValueError(f"missing key {key!r}")
    v = obj[key]
    if isinstance(v, str):
        v = int(v.strip())
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        raise ValueError(f"{key}: expected int, got {type(v).__name__}")
    v = int(v)
    if not 1 <= v <= 5:
        raise ValueError(f"{key}={v} out of range 1..5")
    return v


def pair_agreement(a: JudgeScore, b: JudgeScore) -> dict:
    """Per-item agreement between two judges."""
    if not (a.ok and b.ok):
        return {"ok": False}
    dims = ("correctness", "relevance", "conciseness")
    diffs = [abs(getattr(a, d) - getattr(b, d)) for d in dims]
    return {
        "ok": True,
        "exact_match": all(d == 0 for d in diffs),
        "within_1": all(d <= 1 for d in diffs),
        "mean_abs_diff": round(sum(diffs) / len(diffs), 2),
    }


# -----------------------------------------------------------------------------
# Factories — reuse the project's providers so no new auth flow is needed.
# -----------------------------------------------------------------------------


def make_ollama_judge(model: str = "qwen2.5:7b", host: str | None = None) -> Judge:
    """Build a judge backed by a local Ollama daemon.

    Default model is qwen2.5:7b — stronger than the 3B typically used for the
    voice replies so the judge isn't grading its own work. Lower temperature
    is forced to 0 regardless of app defaults.
    """
    from ollama import Client
    from app.config import OLLAMA_HOST

    client = Client(host=host or OLLAMA_HOST)

    def chat(messages: list[dict]) -> str:
        resp = client.chat(
            model=model,
            messages=messages,
            options={"temperature": 0.0, "num_predict": 200},
        )
        return resp["message"]["content"]

    return Judge("ollama", model, chat)


def make_groq_judge(model: str = "llama-3.3-70b-versatile") -> Judge:
    """Build a judge backed by Groq's API. Requires GROQ_API_KEY."""
    from groq import Groq
    from app.config import GROQ_API_KEY

    if not GROQ_API_KEY:
        raise ValueError("GROQ_API_KEY is not set; cannot build Groq judge")

    client = Groq(api_key=GROQ_API_KEY)

    def chat(messages: list[dict]) -> str:
        r = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=0.0,
            max_tokens=200,
        )
        return r.choices[0].message.content or ""

    return Judge("groq", model, chat)


def make_judge(spec: str | None) -> Judge | None:
    """Parse a judge spec like 'ollama', 'ollama:qwen2.5:7b', 'groq',
    'groq:llama-3.1-70b-versatile'. Returns None for None/'none'/''."""
    if not spec or spec.lower() == "none":
        return None
    if ":" in spec:
        backend, model = spec.split(":", 1)
    else:
        backend, model = spec, None
    backend = backend.lower().strip()
    if backend == "ollama":
        return make_ollama_judge(model or "qwen2.5:7b")
    if backend == "groq":
        return make_groq_judge(model or "llama-3.3-70b-versatile")
    raise ValueError(f"unknown judge backend {backend!r}; expected 'ollama' or 'groq'")
