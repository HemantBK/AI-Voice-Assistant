"""Run the full baseline: LLM + TTS (+ emits STT fixtures) + STT. Writes a
combined JSON under eval/results/. Latency eval is run separately because it
requires the backend server to be up; see README."""
from __future__ import annotations

import argparse
from pathlib import Path

from eval.lib import backend_path  # noqa: F401
from eval.lib.reporter import env_snapshot, print_kv, write_result
from eval.runners import eval_llm, eval_stt, eval_tts


def run(skip: list[str]) -> dict:
    skip_set = set(skip)
    payload = {"env": env_snapshot(), "skipped": sorted(skip_set)}

    if "llm" not in skip_set:
        print("\n### Running LLM eval ###")
        payload["llm"] = eval_llm.run()

    if "tts" not in skip_set:
        print("\n### Running TTS eval (emits STT fixtures) ###")
        payload["tts"] = eval_tts.run(emit_stt_fixtures=True)

    if "stt" not in skip_set:
        print("\n### Running STT eval ###")
        payload["stt"] = eval_stt.run()

    return payload


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip", nargs="*", default=[], choices=["llm", "stt", "tts"],
                    help="skip specific stages")
    ap.add_argument("--no-save", action="store_true")
    args = ap.parse_args()
    payload = run(skip=args.skip)

    summary = [("stages run", ", ".join(k for k in ["llm", "tts", "stt"] if k in payload))]
    if "llm" in payload and payload["llm"].get("accuracy") is not None:
        summary.append(("LLM accuracy", f"{payload['llm']['accuracy']:.1%}"))
    if "tts" in payload and payload["tts"].get("mean_rtf") is not None:
        summary.append(("TTS mean RTF", f"{payload['tts']['mean_rtf']:.3f}"))
    if "stt" in payload and payload["stt"].get("mean_wer") is not None:
        summary.append(("STT mean WER", f"{payload['stt']['mean_wer']:.4f}"))
    print_kv("Baseline summary", summary)

    if not args.no_save:
        path = write_result("baseline", payload)
        print(f"\nSaved -> {path}")


if __name__ == "__main__":
    main()
