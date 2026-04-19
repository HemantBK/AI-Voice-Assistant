"""Unit tests for eval/lib/judge.py. Exercises JSON extraction, validation,
and the Judge.score() flow with a fake chat function so we don't hit any
real LLM."""
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from eval.lib.judge import (  # noqa: E402
    Judge,
    JudgeScore,
    extract_json,
    make_judge,
    pair_agreement,
)


# --- extract_json -----------------------------------------------------------

def test_extract_json_plain():
    obj = extract_json('{"correctness": 5, "relevance": 4, "conciseness": 5}')
    assert obj["correctness"] == 5


def test_extract_json_code_fence():
    raw = '```json\n{"correctness": 3, "relevance": 3, "conciseness": 3, "rationale": "meh"}\n```'
    obj = extract_json(raw)
    assert obj["rationale"] == "meh"


def test_extract_json_with_prefix_and_suffix():
    raw = 'Here is my verdict:\n{"correctness": 4, "relevance": 5, "conciseness": 4}\nHope that helps.'
    obj = extract_json(raw)
    assert obj["relevance"] == 5


def test_extract_json_nested_braces_in_string():
    # Balance-aware parser must not trip on braces inside strings.
    raw = '{"correctness": 5, "relevance": 5, "conciseness": 5, "rationale": "uses a {format} token"}'
    obj = extract_json(raw)
    assert obj["rationale"] == "uses a {format} token"


def test_extract_json_empty_raises():
    with pytest.raises(ValueError):
        extract_json("")


def test_extract_json_no_object_raises():
    with pytest.raises(ValueError):
        extract_json("no json here at all")


# --- Judge.score -----------------------------------------------------------

def _fake_chat(reply: str):
    return lambda messages: reply


def test_judge_score_happy_path():
    j = Judge("fake", "m", _fake_chat('{"correctness": 5, "relevance": 4, "conciseness": 5, "rationale": "solid"}'))
    s = j.score("What is 2+2?", "4")
    assert s.ok and s.correctness == 5 and s.relevance == 4 and s.conciseness == 5
    assert s.rationale == "solid"
    assert round(s.mean, 2) == round((5 + 4 + 5) / 3, 2)


def test_judge_score_handles_string_numbers():
    j = Judge("fake", "m", _fake_chat('{"correctness": "4", "relevance": "4", "conciseness": "4"}'))
    s = j.score("Q", "A")
    assert s.ok and s.correctness == 4


def test_judge_score_out_of_range():
    j = Judge("fake", "m", _fake_chat('{"correctness": 9, "relevance": 3, "conciseness": 3}'))
    s = j.score("Q", "A")
    assert not s.ok and "out of range" in (s.error or "")


def test_judge_score_empty_answer_short_circuits():
    called = []
    def chat(_messages):
        called.append(1)
        return "{}"
    j = Judge("fake", "m", chat)
    s = j.score("Q", "   ")
    assert not s.ok and s.error == "empty answer"
    assert called == []


def test_judge_score_chat_raises():
    def boom(_):
        raise RuntimeError("network down")
    s = Judge("fake", "m", boom).score("Q", "A")
    assert not s.ok and "network down" in (s.error or "")


def test_judge_score_bad_json_marks_error_but_does_not_raise():
    j = Judge("fake", "m", _fake_chat("not json at all"))
    s = j.score("Q", "A")
    assert not s.ok and s.error


# --- pair_agreement --------------------------------------------------------

def test_pair_agreement_exact():
    a = JudgeScore(4, 4, 4)
    b = JudgeScore(4, 4, 4)
    agree = pair_agreement(a, b)
    assert agree["exact_match"] and agree["within_1"] and agree["mean_abs_diff"] == 0


def test_pair_agreement_within_1():
    a = JudgeScore(5, 4, 3)
    b = JudgeScore(4, 4, 4)
    agree = pair_agreement(a, b)
    assert not agree["exact_match"] and agree["within_1"]
    assert agree["mean_abs_diff"] == round((1 + 0 + 1) / 3, 2)


def test_pair_agreement_disagree():
    a = JudgeScore(5, 5, 5)
    b = JudgeScore(1, 1, 1)
    agree = pair_agreement(a, b)
    assert not agree["within_1"]


def test_pair_agreement_one_errored():
    a = JudgeScore(0, 0, 0, ok=False, error="x")
    b = JudgeScore(4, 4, 4)
    assert pair_agreement(a, b) == {"ok": False}


# --- make_judge ------------------------------------------------------------

def test_make_judge_none():
    assert make_judge(None) is None
    assert make_judge("") is None
    assert make_judge("none") is None


def test_make_judge_bad_backend():
    with pytest.raises(ValueError):
        make_judge("vertex")
