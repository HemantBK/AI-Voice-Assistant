"""LLM eval: golden Q&A, keyword-hit scoring, latency, and optional
LLM-as-judge scoring (correctness / relevance / conciseness) with optional
two-judge agreement.

Examples:
    python -m eval.runners.eval_llm
    python -m eval.runners.eval_llm --judge ollama --save
    python -m eval.runners.eval_llm --judge ollama:qwen2.5:7b --judge2 groq:llama-3.3-70b-versatile --save
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from eval.lib import backend_path  # noqa: F401  (mutates sys.path)
from eval.lib.judge import JudgeScore, make_judge, pair_agreement
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


def _mean(values: list[float]) -> float | None:
    return round(sum(values) / len(values), 3) if values else None


def _judge_summary(scores: list[JudgeScore]) -> dict:
    ok = [s for s in scores if s.ok]
    return {
        "evaluated": len(scores),
        "ok": len(ok),
        "mean_correctness": _mean([s.correctness for s in ok]),
        "mean_relevance": _mean([s.relevance for s in ok]),
        "mean_conciseness": _mean([s.conciseness for s in ok]),
        "mean_overall": _mean([s.mean for s in ok]),
    }


def run(limit: int | None = None, judge_spec: str | None = None,
        judge2_spec: str | None = None) -> dict:
    from app.services import llm_service
    from app.config import LLM_MODEL

    items = load_golden()
    if limit is not None:
        items = items[:limit]

    judge = make_judge(judge_spec)
    judge2 = make_judge(judge2_spec)

    results = []
    latencies: list[float] = []
    hits = 0
    scorable = 0
    j1_scores: list[JudgeScore] = []
    j2_scores: list[JudgeScore] = []
    agreements: list[dict] = []

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
        result: dict = {
            "id": item["id"],
            "category": item.get("category"),
            "prompt": item["prompt"],
            "answer": answer,
            "must_contain": keywords,
            "passed": passed,
            "ok": ok,
            "error": error,
            "latency_ms": round(elapsed_ms, 2),
        }

        if judge is not None and ok:
            s1 = judge.score(item["prompt"], answer)
            j1_scores.append(s1)
            result["judge"] = {
                "backend": judge.name,
                "model": judge.model,
                **s1.as_dict(),
            }
            if judge2 is not None:
                s2 = judge2.score(item["prompt"], answer)
                j2_scores.append(s2)
                result["judge2"] = {
                    "backend": judge2.name,
                    "model": judge2.model,
                    **s2.as_dict(),
                }
                agree = pair_agreement(s1, s2)
                result["judge_agreement"] = agree
                if agree.get("ok"):
                    agreements.append(agree)

        results.append(result)

    stats = latency_stats(latencies)
    accuracy = (hits / scorable) if scorable else None

    payload: dict = {
        "env": env_snapshot(),
        "model": LLM_MODEL,
        "judge": judge.name + ":" + judge.model if judge else None,
        "judge2": judge2.name + ":" + judge2.model if judge2 else None,
        "total": len(results),
        "scorable": scorable,
        "hits": hits,
        "accuracy": accuracy,
        "latency_ms": stats.as_dict(),
        "results": results,
    }
    if judge is not None:
        payload["judge_summary"] = _judge_summary(j1_scores)
    if judge2 is not None:
        payload["judge2_summary"] = _judge_summary(j2_scores)
    if judge is not None and judge2 is not None and agreements:
        payload["agreement_summary"] = {
            "items": len(agreements),
            "exact_match_rate": _mean([1.0 if a["exact_match"] else 0.0 for a in agreements]),
            "within_1_rate": _mean([1.0 if a["within_1"] else 0.0 for a in agreements]),
            "mean_abs_diff": _mean([a["mean_abs_diff"] for a in agreements]),
        }

    table_headers = ["id", "category", "passed", "latency_ms"]
    if judge is not None:
        table_headers += ["j1_mean"]
    if judge2 is not None:
        table_headers += ["j2_mean", "within_1"]
    rows = []
    for r in results:
        row = [r["id"], r["category"], r["passed"], r["latency_ms"]]
        if judge is not None:
            j = r.get("judge") or {}
            row.append(j.get("mean", "-") if j.get("ok") else "err")
        if judge2 is not None:
            j = r.get("judge2") or {}
            row.append(j.get("mean", "-") if j.get("ok") else "err")
            a = r.get("judge_agreement") or {}
            row.append("yes" if a.get("within_1") else ("no" if a.get("ok") else "-"))
        rows.append(row)
    print_table("LLM results", table_headers, rows)

    summary_rows = [
        ("model", LLM_MODEL),
        ("total", len(results)),
        ("keyword accuracy", f"{hits}/{scorable}" + (f"  ({accuracy:.1%})" if accuracy is not None else "")),
        ("latency p50", f"{stats.p50_ms} ms"),
        ("latency p95", f"{stats.p95_ms} ms"),
        ("latency mean", f"{stats.mean_ms} ms"),
    ]
    if judge is not None:
        js = payload["judge_summary"]
        summary_rows.append(("judge", f"{judge.name}:{judge.model}"))
        summary_rows.append((
            "judge mean (C/R/Cn/overall)",
            f"{js['mean_correctness']} / {js['mean_relevance']} / {js['mean_conciseness']} / {js['mean_overall']}",
        ))
    if judge2 is not None:
        js2 = payload["judge2_summary"]
        summary_rows.append(("judge2", f"{judge2.name}:{judge2.model}"))
        summary_rows.append((
            "judge2 mean (C/R/Cn/overall)",
            f"{js2['mean_correctness']} / {js2['mean_relevance']} / {js2['mean_conciseness']} / {js2['mean_overall']}",
        ))
        if "agreement_summary" in payload:
            a = payload["agreement_summary"]
            summary_rows.append(("within-1 agreement", f"{a['within_1_rate']:.1%}"))
            summary_rows.append(("exact-match agreement", f"{a['exact_match_rate']:.1%}"))
    print_kv("LLM summary", summary_rows)
    return payload


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--save", action="store_true", help="write JSON to eval/results/")
    ap.add_argument("--judge", default=None,
                    help="LLM-as-judge spec; e.g. 'ollama', 'ollama:qwen2.5:7b', 'groq'")
    ap.add_argument("--judge2", default=None,
                    help="Optional second judge for agreement; same spec format as --judge")
    args = ap.parse_args()
    payload = run(limit=args.limit, judge_spec=args.judge, judge2_spec=args.judge2)
    if args.save:
        path = write_result("llm", payload)
        print(f"\nSaved -> {path}")


if __name__ == "__main__":
    main()
