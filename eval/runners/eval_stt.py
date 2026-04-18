"""STT baseline eval: WER against manifest of audio fixtures."""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from eval.lib import backend_path  # noqa: F401
from eval.lib.metrics import latency_stats, word_error_rate
from eval.lib.reporter import env_snapshot, print_kv, print_table, write_result


MANIFEST = Path(__file__).resolve().parent.parent / "datasets" / "stt" / "manifest.json"


def run() -> dict:
    from app.services import stt_service
    from app.config import WHISPER_MODEL_SIZE, WHISPER_DEVICE

    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    samples = manifest.get("samples", [])
    base_dir = MANIFEST.parent

    results = []
    wers = []
    latencies = []

    for s in samples:
        audio_path = (base_dir / s["audio"]).resolve()
        if not audio_path.exists():
            results.append({"id": s["id"], "ok": False, "error": f"missing audio: {audio_path}"})
            continue
        audio_bytes = audio_path.read_bytes()
        t0 = time.perf_counter()
        try:
            out = stt_service.transcribe(audio_bytes)
            elapsed_ms = (time.perf_counter() - t0) * 1000
            hyp = out.get("text", "")
            wer = word_error_rate(s["reference"], hyp)
            wers.append(wer)
            latencies.append(elapsed_ms)
            results.append({
                "id": s["id"],
                "language": s.get("language"),
                "reference": s["reference"],
                "hypothesis": hyp,
                "wer": round(wer, 4),
                "latency_ms": round(elapsed_ms, 2),
                "audio_duration_s": out.get("audio_duration_s"),
                "speech_duration_s": out.get("speech_duration_s"),
                "vad_trimmed_ms": out.get("vad_trimmed_ms"),
                "vad_enabled": out.get("vad_enabled"),
                "ok": True,
            })
        except Exception as e:
            elapsed_ms = (time.perf_counter() - t0) * 1000
            results.append({"id": s["id"], "ok": False, "error": str(e), "latency_ms": round(elapsed_ms, 2)})

    stats = latency_stats(latencies)
    mean_wer = sum(wers) / len(wers) if wers else None

    trim_values = [r["vad_trimmed_ms"] for r in results if r.get("vad_trimmed_ms") is not None]
    mean_trim_ms = (sum(trim_values) / len(trim_values)) if trim_values else None

    payload = {
        "env": env_snapshot(),
        "whisper_model": WHISPER_MODEL_SIZE,
        "whisper_device": WHISPER_DEVICE,
        "total": len(results),
        "mean_wer": round(mean_wer, 4) if mean_wer is not None else None,
        "mean_vad_trimmed_ms": round(mean_trim_ms, 2) if mean_trim_ms is not None else None,
        "latency_ms": stats.as_dict(),
        "results": results,
    }

    if results:
        print_table(
            "STT results",
            ["id", "wer", "latency_ms", "ok"],
            [[r["id"], r.get("wer", "-"), r.get("latency_ms", "-"), r["ok"]] for r in results],
        )
    print_kv("STT summary", [
        ("whisper model", WHISPER_MODEL_SIZE),
        ("device", WHISPER_DEVICE),
        ("samples", len(results)),
        ("mean WER", f"{mean_wer:.4f}" if mean_wer is not None else "no successful samples"),
        ("mean VAD trimmed", f"{mean_trim_ms:.0f} ms" if mean_trim_ms is not None else "n/a"),
        ("latency p50", f"{stats.p50_ms} ms"),
        ("latency p95", f"{stats.p95_ms} ms"),
    ])
    if not samples:
        print("\n(no fixtures listed in manifest.json — see eval/datasets/stt/README.md)")
    return payload


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--save", action="store_true")
    args = ap.parse_args()
    payload = run()
    if args.save:
        path = write_result("stt", payload)
        print(f"\nSaved -> {path}")


if __name__ == "__main__":
    main()
