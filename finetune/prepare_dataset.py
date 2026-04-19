"""Validate + split a chat-format JSONL dataset for LoRA training.

Expected input per line:
    {"messages": [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}]}

Optional additional "system" role entries at the start of messages are allowed.
Lines failing validation are reported and skipped.

Outputs a HuggingFace Dataset-compatible JSONL split pair (train + eval) to the
target directory.
"""
from __future__ import annotations

import argparse
import json
import logging
import random
from pathlib import Path

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


VALID_ROLES = {"system", "user", "assistant"}


def validate_row(row: dict) -> tuple[bool, str]:
    if "messages" not in row or not isinstance(row["messages"], list):
        return False, "missing or non-list 'messages'"
    if len(row["messages"]) < 2:
        return False, "need at least user + assistant turns"
    last_role = None
    saw_user = saw_assistant = False
    for m in row["messages"]:
        if "role" not in m or "content" not in m:
            return False, "message missing role/content"
        if m["role"] not in VALID_ROLES:
            return False, f"invalid role {m['role']!r}"
        if not isinstance(m["content"], str) or not m["content"].strip():
            return False, "empty content"
        if m["role"] == "user":
            saw_user = True
        if m["role"] == "assistant":
            saw_assistant = True
        last_role = m["role"]
    if not (saw_user and saw_assistant):
        return False, "need both user and assistant turns"
    if last_role != "assistant":
        return False, "final turn must be assistant (what we train on)"
    return True, ""


def load_jsonl(path: Path) -> list[dict]:
    rows = []
    errors: list[str] = []
    for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = line.strip()
        if not line or line.startswith("//"):
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError as e:
            errors.append(f"line {i}: JSON error — {e}")
            continue
        ok, reason = validate_row(obj)
        if not ok:
            errors.append(f"line {i}: {reason}")
            continue
        rows.append(obj)
    for e in errors:
        logger.warning(e)
    logger.info("Loaded %d rows, skipped %d", len(rows), len(errors))
    return rows


def split_dataset(rows: list[dict], eval_frac: float, seed: int) -> tuple[list[dict], list[dict]]:
    if not 0.0 < eval_frac < 1.0:
        raise ValueError(f"eval_frac must be in (0, 1); got {eval_frac}")
    rng = random.Random(seed)
    shuffled = rows.copy()
    rng.shuffle(shuffled)
    split = max(1, int(round(len(shuffled) * eval_frac)))
    eval_rows = shuffled[:split]
    train_rows = shuffled[split:]
    if not train_rows:
        raise ValueError(f"eval_frac={eval_frac} left no training rows")
    return train_rows, eval_rows


def write_jsonl(rows: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", type=Path, required=True, help="source JSONL")
    ap.add_argument("--out-dir", type=Path, required=True, help="where to write train/eval splits")
    ap.add_argument("--eval-frac", type=float, default=0.1)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    rows = load_jsonl(args.input)
    if len(rows) < 8:
        logger.warning(
            "Only %d rows — LoRA needs at least ~30 for a non-trivial signal. Consider "
            "expanding dataset_example.jsonl or loading a public dataset.",
            len(rows),
        )
    train, eval_rows = split_dataset(rows, args.eval_frac, args.seed)
    write_jsonl(train, args.out_dir / "train.jsonl")
    write_jsonl(eval_rows, args.out_dir / "eval.jsonl")
    logger.info("train=%d  eval=%d  ->  %s", len(train), len(eval_rows), args.out_dir)


if __name__ == "__main__":
    main()
