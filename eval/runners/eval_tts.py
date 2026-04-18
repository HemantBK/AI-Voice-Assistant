"""TTS baseline eval: synth latency + real-time factor (RTF). Optionally emits
STT fixtures so STT can be evaluated on known-reference audio."""
from __future__ import annotations

import argparse
import io
import json
import time
import wave
from pathlib import Path

from eval.lib import backend_path  # noqa: F401
from eval.lib.metrics import latency_stats
from eval.lib.reporter import env_snapshot, print_kv, print_table, write_result


PROMPTS = Path(__file__).resolve().parent.parent / "datasets" / "tts" / "prompts.txt"
STT_DIR = Path(__file__).resolve().parent.parent / "datasets" / "stt"


def _wav_duration_seconds(wav_bytes: bytes) -> float:
    with wave.open(io.BytesIO(wav_bytes), "rb") as wf:
        frames = wf.getnframes()
        rate = wf.getframerate()
        return frames / float(rate) if rate else 0.0


def run(emit_stt_fixtures: bool = False) -> dict:
    from app.services import tts_service
    from app.config import KOKORO_VOICE

    prompts = [p.strip() for p in PROMPTS.read_text(encoding="utf-8").splitlines() if p.strip()]
    results = []
    latencies = []
    rtfs = []

    if emit_stt_fixtures:
        STT_DIR.mkdir(parents=True, exist_ok=True)

    fixture_samples = []

    for i, text in enumerate(prompts):
        t0 = time.perf_counter()
        try:
            audio = tts_service.synthesize(text)
            elapsed_s = time.perf_counter() - t0
            elapsed_ms = elapsed_s * 1000
            dur = _wav_duration_seconds(audio)
            rtf = (elapsed_s / dur) if dur > 0 else None
            latencies.append(elapsed_ms)
            if rtf is not None:
                rtfs.append(rtf)
            record = {
                "id": f"tts-{i:02d}",
                "text": text,
                "audio_bytes": len(audio),
                "audio_seconds": round(dur, 3),
                "latency_ms": round(elapsed_ms, 2),
                "rtf": round(rtf, 3) if rtf is not None else None,
                "ok": True,
            }
            if emit_stt_fixtures:
                fname = f"tts-roundtrip-{i:02d}.wav"
                (STT_DIR / fname).write_bytes(audio)
                fixture_samples.append({
                    "id": f"tts-roundtrip-{i:02d}",
                    "audio": fname,
                    "reference": text,
                    "language": "en",
                })
            results.append(record)
        except Exception as e:
            elapsed_ms = (time.perf_counter() - t0) * 1000
            results.append({"id": f"tts-{i:02d}", "text": text, "ok": False, "error": str(e), "latency_ms": round(elapsed_ms, 2)})

    if emit_stt_fixtures and fixture_samples:
        manifest_path = STT_DIR / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {"samples": []}
        existing_ids = {s.get("id") for s in manifest.get("samples", [])}
        for fs in fixture_samples:
            if fs["id"] not in existing_ids:
                manifest["samples"].append(fs)
        manifest_path.write_text(json.dumps(manifest, indent=2))
        print(f"\nEmitted {len(fixture_samples)} STT fixtures -> {manifest_path}")

    stats = latency_stats(latencies)
    mean_rtf = sum(rtfs) / len(rtfs) if rtfs else None

    payload = {
        "env": env_snapshot(),
        "voice": KOKORO_VOICE,
        "total": len(results),
        "mean_rtf": round(mean_rtf, 3) if mean_rtf is not None else None,
        "latency_ms": stats.as_dict(),
        "results": results,
    }

    print_table(
        "TTS results",
        ["id", "audio_s", "latency_ms", "rtf"],
        [[r["id"], r.get("audio_seconds", "-"), r.get("latency_ms", "-"), r.get("rtf", "-")] for r in results],
    )
    print_kv("TTS summary", [
        ("voice", KOKORO_VOICE),
        ("prompts", len(results)),
        ("mean RTF (synth_time / audio_time)", f"{mean_rtf:.3f}" if mean_rtf is not None else "n/a"),
        ("latency p50", f"{stats.p50_ms} ms"),
        ("latency p95", f"{stats.p95_ms} ms"),
    ])
    return payload


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--save", action="store_true")
    ap.add_argument("--emit-stt-fixtures", action="store_true",
                    help="also write each synthesized clip to eval/datasets/stt/ and append to manifest.json")
    args = ap.parse_args()
    payload = run(emit_stt_fixtures=args.emit_stt_fixtures)
    if args.save:
        path = write_result("tts", payload)
        print(f"\nSaved -> {path}")


if __name__ == "__main__":
    main()
