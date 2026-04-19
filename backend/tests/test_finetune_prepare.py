"""Unit tests for finetune/prepare_dataset.py. Runs with no GPU and no
training deps — only stdlib + pytest."""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest


def _load_module():
    """Load finetune/prepare_dataset.py as a module without importing `finetune`
    as a package (it has no __init__.py, which is deliberate)."""
    root = Path(__file__).resolve().parents[2]
    spec = importlib.util.spec_from_file_location(
        "prepare_dataset", root / "finetune" / "prepare_dataset.py"
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules["prepare_dataset"] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def pd():
    return _load_module()


@pytest.fixture
def tmp_jsonl(tmp_path):
    def _write(rows):
        p = tmp_path / "in.jsonl"
        with p.open("w", encoding="utf-8") as f:
            for r in rows:
                f.write(json.dumps(r) + "\n")
        return p
    return _write


# --- validate_row ----------------------------------------------------------

def test_validate_row_happy(pd):
    ok, _ = pd.validate_row({"messages": [
        {"role": "user", "content": "hi"},
        {"role": "assistant", "content": "hello"},
    ]})
    assert ok


def test_validate_row_with_system(pd):
    ok, _ = pd.validate_row({"messages": [
        {"role": "system", "content": "be terse"},
        {"role": "user", "content": "hi"},
        {"role": "assistant", "content": "hi"},
    ]})
    assert ok


def test_validate_row_missing_messages(pd):
    ok, why = pd.validate_row({})
    assert not ok and "messages" in why


def test_validate_row_too_few_turns(pd):
    ok, why = pd.validate_row({"messages": [{"role": "user", "content": "hi"}]})
    assert not ok


def test_validate_row_empty_content(pd):
    ok, _ = pd.validate_row({"messages": [
        {"role": "user", "content": "   "},
        {"role": "assistant", "content": "hi"},
    ]})
    assert not ok


def test_validate_row_invalid_role(pd):
    ok, _ = pd.validate_row({"messages": [
        {"role": "user", "content": "hi"},
        {"role": "bot", "content": "hi"},
    ]})
    assert not ok


def test_validate_row_must_end_with_assistant(pd):
    ok, why = pd.validate_row({"messages": [
        {"role": "user", "content": "hi"},
        {"role": "assistant", "content": "hi"},
        {"role": "user", "content": "again"},
    ]})
    assert not ok and "assistant" in why


# --- load_jsonl ------------------------------------------------------------

def test_load_jsonl_skips_bad_rows_but_loads_good(pd, tmp_jsonl, caplog):
    p = tmp_jsonl([
        {"messages": [{"role": "user", "content": "q"}, {"role": "assistant", "content": "a"}]},
        {"oops": "no messages"},
        {"messages": [{"role": "user", "content": "q2"}, {"role": "assistant", "content": "a2"}]},
    ])
    rows = pd.load_jsonl(p)
    assert len(rows) == 2


def test_load_jsonl_handles_blank_and_comment_lines(pd, tmp_path):
    p = tmp_path / "in.jsonl"
    p.write_text(
        '\n\n// comment line\n'
        + json.dumps({"messages": [
            {"role": "user", "content": "q"},
            {"role": "assistant", "content": "a"},
        ]}) + "\n",
        encoding="utf-8",
    )
    assert len(pd.load_jsonl(p)) == 1


# --- split_dataset --------------------------------------------------------

def test_split_dataset_respects_fraction(pd):
    rows = [{"id": i} for i in range(10)]
    train, ev = pd.split_dataset(rows, 0.2, seed=42)
    assert len(train) == 8 and len(ev) == 2


def test_split_dataset_is_deterministic(pd):
    rows = [{"id": i} for i in range(20)]
    t1, e1 = pd.split_dataset(rows, 0.25, seed=123)
    t2, e2 = pd.split_dataset(rows, 0.25, seed=123)
    assert t1 == t2 and e1 == e2


def test_split_dataset_rejects_zero_fraction(pd):
    with pytest.raises(ValueError):
        pd.split_dataset([{"id": 0}, {"id": 1}], 0.0, seed=0)


def test_split_dataset_rejects_zero_train(pd):
    # eval_frac=1.0 would leave 0 training rows
    with pytest.raises(ValueError):
        pd.split_dataset([{"id": 0}, {"id": 1}], 0.999, seed=0)


# --- example dataset sanity -----------------------------------------------

def test_example_dataset_parses(pd):
    root = Path(__file__).resolve().parents[2]
    path = root / "finetune" / "dataset_example.jsonl"
    rows = pd.load_jsonl(path)
    assert len(rows) >= 20, f"example dataset too small: {len(rows)}"
    # every row must validate
    for r in rows:
        ok, why = pd.validate_row(r)
        assert ok, f"row invalid: {why} | {r}"
