"""Compare base model vs fine-tuned model on the golden Q&A set + judge rubric.

Runs the LLM eval twice — once against each Ollama model — and produces a
single combined JSON with side-by-side scores and a summary table.

Typical use (after finishing Phase G.3 training + `ollama create voice-assistant-ft`):

    python -m eval.runners.eval_llm_compare \\
        --base qwen2.5:3b \\
        --finetuned voice-assistant-ft \\
        --judge ollama --save

The runner flips `OLLAMA_MODEL` via environment for each half so we don't need
per-call plumbing in the LLM provider.
"""
from __future__ import annotations

import argparse
import importlib
import os
from pathlib import Path

from eval.lib import backend_path  # noqa: F401  (mutates sys.path)
from eval.lib.reporter import env_snapshot, print_kv, write_result


def _run_with_model(model: str, judge_spec: str | None, judge2_spec: str | None,
                    limit: int | None) -> dict:
    os.environ["OLLAMA_MODEL"] = model
    os.environ["LLM_PROVIDER"] = "ollama"
    # Force a full reload so the factory singleton picks up the new model.
    for name in ("app.config", "app.services.llm", "app.services.llm.factory",
                 "app.services.llm.ollama_provider", "app.services.llm_service"):
        if name in importlib.sys.modules:
            importlib.reload(importlib.sys.modules[name])
    from eval.runners import eval_llm  # imported here so reloads above take effect
    importlib.reload(eval_llm)
    return eval_llm.run(limit=limit, judge_spec=judge_spec, judge2_spec=judge2_spec)


def _delta(a: float | None, b: float | None) -> str:
    if a is None or b is None:
        return "—"
    diff = b - a
    sign = "+" if diff >= 0 else ""
    return f"{sign}{diff:.3f}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True, help="Ollama model tag for the base model (e.g. qwen2.5:3b)")
    ap.add_argument("--finetuned", required=True, help="Ollama model tag for the fine-tuned model")
    ap.add_argument("--judge", default="ollama", help="judge spec, same format as eval_llm --judge")
    ap.add_argument("--judge2", default=None)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--save", action="store_true")
    args = ap.parse_args()

    print(f"\n=== BASE: {args.base} ===")
    base_result = _run_with_model(args.base, args.judge, args.judge2, args.limit)

    print(f"\n=== FINETUNED: {args.finetuned} ===")
    ft_result = _run_with_model(args.finetuned, args.judge, args.judge2, args.limit)

    payload = {
        "env": env_snapshot(),
        "base_model": args.base,
        "finetuned_model": args.finetuned,
        "base": base_result,
        "finetuned": ft_result,
    }

    rows = [
        ("keyword accuracy (base)", f"{base_result['hits']}/{base_result['scorable']}"),
        ("keyword accuracy (ft)",   f"{ft_result['hits']}/{ft_result['scorable']}"),
    ]
    if base_result.get("judge_summary") and ft_result.get("judge_summary"):
        bj = base_result["judge_summary"]
        fj = ft_result["judge_summary"]
        rows += [
            ("judge correctness (base / ft / Δ)",
             f"{bj['mean_correctness']} / {fj['mean_correctness']} / {_delta(bj['mean_correctness'], fj['mean_correctness'])}"),
            ("judge relevance    (base / ft / Δ)",
             f"{bj['mean_relevance']} / {fj['mean_relevance']} / {_delta(bj['mean_relevance'], fj['mean_relevance'])}"),
            ("judge conciseness  (base / ft / Δ)",
             f"{bj['mean_conciseness']} / {fj['mean_conciseness']} / {_delta(bj['mean_conciseness'], fj['mean_conciseness'])}"),
            ("judge overall      (base / ft / Δ)",
             f"{bj['mean_overall']} / {fj['mean_overall']} / {_delta(bj['mean_overall'], fj['mean_overall'])}"),
        ]
    rows += [
        ("latency p50 (base / ft)",
         f"{base_result['latency_ms']['p50_ms']} / {ft_result['latency_ms']['p50_ms']} ms"),
        ("latency p95 (base / ft)",
         f"{base_result['latency_ms']['p95_ms']} / {ft_result['latency_ms']['p95_ms']} ms"),
    ]
    print_kv("Base vs Fine-tuned", rows)

    if args.save:
        path = write_result("llm_compare", payload)
        print(f"\nSaved -> {path}")


if __name__ == "__main__":
    main()
