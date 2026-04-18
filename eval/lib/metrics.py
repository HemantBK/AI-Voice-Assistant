"""Metric primitives for the eval harness. Zero external dependencies."""
from __future__ import annotations

import re
import statistics
from dataclasses import dataclass


_PUNCT_RE = re.compile(r"[^\w\s']")


def normalize(text: str) -> str:
    text = text.lower().strip()
    text = _PUNCT_RE.sub(" ", text)
    return " ".join(text.split())


def word_error_rate(reference: str, hypothesis: str) -> float:
    """WER via token-level Levenshtein distance. Returns 0.0 on empty reference+hypothesis."""
    ref = normalize(reference).split()
    hyp = normalize(hypothesis).split()
    n, m = len(ref), len(hyp)
    if n == 0:
        return 0.0 if m == 0 else 1.0
    prev = list(range(m + 1))
    curr = [0] * (m + 1)
    for i in range(1, n + 1):
        curr[0] = i
        for j in range(1, m + 1):
            if ref[i - 1] == hyp[j - 1]:
                curr[j] = prev[j - 1]
            else:
                curr[j] = 1 + min(prev[j], curr[j - 1], prev[j - 1])
        prev, curr = curr, prev
    return prev[m] / n


def keyword_hit(answer: str, must_contain: list[str]) -> bool:
    norm = normalize(answer)
    return all(normalize(k) in norm for k in must_contain)


@dataclass
class LatencyStats:
    count: int
    mean_ms: float
    p50_ms: float
    p95_ms: float
    p99_ms: float
    min_ms: float
    max_ms: float

    def as_dict(self) -> dict:
        return self.__dict__.copy()


def latency_stats(samples_ms: list[float]) -> LatencyStats:
    if not samples_ms:
        return LatencyStats(0, 0, 0, 0, 0, 0, 0)
    sorted_s = sorted(samples_ms)

    def pct(p: float) -> float:
        if len(sorted_s) == 1:
            return sorted_s[0]
        k = (len(sorted_s) - 1) * p
        f = int(k)
        c = min(f + 1, len(sorted_s) - 1)
        return sorted_s[f] + (sorted_s[c] - sorted_s[f]) * (k - f)

    return LatencyStats(
        count=len(samples_ms),
        mean_ms=round(statistics.fmean(samples_ms), 2),
        p50_ms=round(pct(0.50), 2),
        p95_ms=round(pct(0.95), 2),
        p99_ms=round(pct(0.99), 2),
        min_ms=round(min(samples_ms), 2),
        max_ms=round(max(samples_ms), 2),
    )
