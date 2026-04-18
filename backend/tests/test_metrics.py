from pathlib import Path
import sys

# Bring the eval package onto sys.path (it lives at repo root/eval).
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from eval.lib.metrics import keyword_hit, latency_stats, normalize, word_error_rate


def test_normalize_strips_punct():
    assert normalize("Hello, World!") == "hello world"


def test_wer_identical():
    assert word_error_rate("the quick brown fox", "the quick brown fox") == 0.0


def test_wer_one_sub():
    assert word_error_rate("the quick brown fox", "the slow brown fox") == 0.25


def test_wer_empty():
    assert word_error_rate("", "") == 0.0
    assert word_error_rate("a b c", "") == 1.0


def test_keyword_hit():
    assert keyword_hit("The capital of France is Paris.", ["Paris"]) is True
    assert keyword_hit("I don't know", ["Paris"]) is False
    assert keyword_hit("anything", []) is True


def test_latency_stats_percentiles():
    s = latency_stats([100, 200, 300, 400, 500])
    assert s.p50_ms == 300.0
    assert s.min_ms == 100.0
    assert s.max_ms == 500.0
