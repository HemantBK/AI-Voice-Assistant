"""Streaming WS eval: opens a connection to /ws/voice?stream=1, sends a
fixture audio file, records timestamps for:
  - transcript event
  - response (full LLM text) event
  - first tts_chunk event  <-- first_audio_byte_ms, the headline metric
  - tts_end event

Run N times, aggregate p50/p95/p99. Requires the backend to be running.
"""
from __future__ import annotations

import argparse
import asyncio
import base64
import json
import time
from pathlib import Path
from urllib.parse import urlparse

try:
    from websockets.asyncio.client import connect
except ImportError:
    from websockets import connect  # older websockets versions

from eval.lib.metrics import latency_stats
from eval.lib.reporter import env_snapshot, print_kv, print_table, write_result


async def _run_one(ws_url: str, fixture: Path, timeout: float) -> dict:
    audio_b64 = base64.b64encode(fixture.read_bytes()).decode("utf-8")
    timings: dict[str, float | None] = {
        "transcript_ms": None,
        "first_llm_delta_ms": None,
        "response_ms": None,
        "first_audio_byte_ms": None,
        "tts_end_ms": None,
    }
    chunks = 0
    t0 = time.perf_counter()

    async with connect(ws_url, open_timeout=timeout) as ws:
        await ws.send(json.dumps({"type": "audio", "data": audio_b64}))
        while True:
            raw = await asyncio.wait_for(ws.recv(), timeout=timeout)
            now_ms = (time.perf_counter() - t0) * 1000
            msg = json.loads(raw)
            mtype = msg.get("type")
            if mtype == "transcript" and timings["transcript_ms"] is None:
                timings["transcript_ms"] = now_ms
            elif mtype == "llm_delta" and timings["first_llm_delta_ms"] is None:
                timings["first_llm_delta_ms"] = now_ms
            elif mtype == "response" and timings["response_ms"] is None:
                timings["response_ms"] = now_ms
            elif mtype in ("tts_chunk", "audio"):
                chunks += 1
                if timings["first_audio_byte_ms"] is None:
                    timings["first_audio_byte_ms"] = now_ms
                if mtype == "audio":  # legacy non-streaming path fires once and is done
                    timings["tts_end_ms"] = now_ms
                    break
            elif mtype == "tts_end":
                timings["tts_end_ms"] = now_ms
                break
            elif mtype == "error":
                raise RuntimeError(msg.get("message", "ws error"))

    return {**timings, "chunks": chunks}


async def _main(url: str, fixture: Path, runs: int, warmup: int, timeout: float) -> dict:
    parsed = urlparse(url)
    if parsed.scheme not in ("ws", "wss"):
        raise ValueError(f"URL must be ws:// or wss://, got {url}")

    for _ in range(warmup):
        await _run_one(url, fixture, timeout)

    samples = []
    for i in range(runs):
        samples.append(await _run_one(url, fixture, timeout))

    def col(name):
        return [s[name] for s in samples if s.get(name) is not None]

    metric_keys = ("transcript_ms", "first_llm_delta_ms", "response_ms",
                   "first_audio_byte_ms", "tts_end_ms")
    stats = {k: latency_stats(col(k)).as_dict() for k in metric_keys}

    payload = {
        "env": env_snapshot(),
        "url": url,
        "fixture": str(fixture),
        "warmup": warmup,
        "runs": runs,
        "stats": stats,
        "samples": samples,
    }

    print_table(
        "Per-run (ms)",
        ["run", "transcript", "first_llm_tok", "response", "first_audio", "tts_end", "chunks"],
        [[
            i + 1,
            round(s.get("transcript_ms") or 0, 2),
            round(s.get("first_llm_delta_ms") or 0, 2),
            round(s.get("response_ms") or 0, 2),
            round(s.get("first_audio_byte_ms") or 0, 2),
            round(s.get("tts_end_ms") or 0, 2),
            s.get("chunks", 0),
        ] for i, s in enumerate(samples)],
    )
    for name in metric_keys:
        s = stats[name]
        print_kv(f"{name}", [
            ("p50", f"{s['p50_ms']} ms"),
            ("p95", f"{s['p95_ms']} ms"),
            ("mean", f"{s['mean_ms']} ms"),
        ])
    return payload


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="ws://127.0.0.1:8000/ws/voice?stream=1")
    ap.add_argument("--fixture", type=Path, required=True,
                    help="path to a .wav file; use eval_tts.py --emit-stt-fixtures to create one")
    ap.add_argument("--runs", type=int, default=10)
    ap.add_argument("--warmup", type=int, default=1)
    ap.add_argument("--timeout", type=float, default=60.0)
    ap.add_argument("--save", action="store_true")
    args = ap.parse_args()
    payload = asyncio.run(_main(args.url, args.fixture, args.runs, args.warmup, args.timeout))
    if args.save:
        path = write_result("streaming", payload)
        print(f"\nSaved -> {path}")


if __name__ == "__main__":
    main()
