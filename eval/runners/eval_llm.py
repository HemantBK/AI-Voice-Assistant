"""LLM baseline eval: golden Q&A, keyword-hit scoring, latency per question."""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from eval.lib import backend_path  # noqa: F401  (mutates sys.path)
from eval.lib.metrics import keyword_hit, latency_stats
from eval.lib.reporter import env_snapshot, print_kv, print_table, write_result


DATASET = Path(__file__).resolve().parent.parent / "datasets" / "llm" / "golden_qa.jsonl"


def load_golden() -> list[dict]:
    items = []
    for line in DATASET.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            items.append(json.loads(line))
    return items


def run(limit: int | None = None) -> dict:
    from app.services import llm_service
    from app.config import LLM_MODEL

    items = load_golden()
    if limit is not None:
        items = items[:limit]

    results = []
    latencies = []
    hits = 0
    scorable = 0

    for item in items:
        t0 = time.perf_counter()
        try:
            answer = llm_service.chat(item["prompt"])
            elapsed_ms = (time.perf_counter() - t0) * 1000
            ok = True
            error = None
        except Exception as e:
            elapsed_ms = (time.perf_counter() - t0) * 1000
            answer = ""
            ok = False
            error = str(e)

        keywords = item.get("must_contain") or []
        passed = keyword_hit(answer, keywords) if keywords else None
        if keywords and ok:
            scorable += 1
            if passed:
                hits += 1

        latencies.append(elapsed_ms)
        results.append({
            "id": item["id"],
            "category": item.get("category"),
            "prompt": item["prompt"],
            "answer": answer,
            "must_contain": keywords,
            "passed": passed,
            "ok": ok,
            "error": error,
            "latency_ms": round(elapsed_ms, 2),
        })

    stats = latency_stats(latencies)
    accuracy = (hits / scorable) if scorable else None

    payload = {
        "env": env_snapshot(),
        "model": LLM_MODEL,
        "total": len(results),
        "scorable": scorable,
        "hits": hits,
        "accuracy": accuracy,
        "latency_ms": stats.as_dict(),
        "results": results,
    }

    print_table(
        "LLM results",
        ["id", "category", "passed", "latency_ms"],
        [[r["id"], r["category"], r["passed"], r["latency_ms"]] for r in results],
    )
    print_kv("LLM summary", [
        ("model", LLM_MODEL),
        ("total", len(results)),
        ("keyword accuracy", f"{hits}/{scorable}" + (f"  ({accuracy:.1%})" if accuracy is not None else "")),
        ("latency p50", f"{stats.p50_ms} ms"),
        ("latency p95", f"{stats.p95_ms} ms"),
        ("latency mean", f"{stats.mean_ms} ms"),
    ])
    return payload


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--save", action="store_true", help="write JSON to eval/results/")
    args = ap.parse_args()
    payload = run(limit=args.limit)
    if args.save:
        path = write_result("llm", payload)
        print(f"\nSaved -> {path}")


if __name__ == "__main__":
    main()
