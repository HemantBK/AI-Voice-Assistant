"""End-to-end latency eval: POST an audio fixture to /api/pipeline N times,
parse per-stage headers (X-Stage-*-Ms), aggregate p50/p95/p99."""
from __future__ import annotations

import argparse
import time
from pathlib import Path
from urllib.parse import urlparse

from eval.lib.metrics import latency_stats
from eval.lib.reporter import env_snapshot, print_kv, print_table, write_result


def _post_multipart(url: str, file_path: Path, timeout: float = 60.0):
    """Zero-dep multipart POST using stdlib only."""
    import uuid
    import http.client

    boundary = f"----evalboundary{uuid.uuid4().hex}"
    filename = file_path.name
    file_bytes = file_path.read_bytes()
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="audio"; filename="{filename}"\r\n'
        f"Content-Type: audio/wav\r\n\r\n"
    ).encode("utf-8") + file_bytes + f"\r\n--{boundary}--\r\n".encode("utf-8")

    parsed = urlparse(url)
    conn_cls = http.client.HTTPSConnection if parsed.scheme == "https" else http.client.HTTPConnection
    conn = conn_cls(parsed.hostname, parsed.port or (443 if parsed.scheme == "https" else 80), timeout=timeout)
    try:
        conn.request(
            "POST",
            parsed.path + (f"?{parsed.query}" if parsed.query else ""),
            body=body,
            headers={
                "Content-Type": f"multipart/form-data; boundary={boundary}",
                "Content-Length": str(len(body)),
            },
        )
        resp = conn.getresponse()
        data = resp.read()
        return resp.status, dict(resp.getheaders()), data
    finally:
        conn.close()


def run(url: str, fixture: Path, runs: int, warmup: int) -> dict:
    if not fixture.exists():
        raise FileNotFoundError(f"fixture audio not found: {fixture}")

    for _ in range(warmup):
        _post_multipart(url, fixture)

    totals = []
    stages: dict[str, list[float]] = {}
    raw = []

    for i in range(runs):
        t0 = time.perf_counter()
        status, headers, _ = _post_multipart(url, fixture)
        wall_ms = (time.perf_counter() - t0) * 1000
        server_total = float(headers.get("x-total-ms") or headers.get("X-Total-Ms") or 0.0)
        stage_ms = {}
        for k, v in headers.items():
            kl = k.lower()
            if kl.startswith("x-stage-") and kl.endswith("-ms"):
                name = kl[len("x-stage-"):-len("-ms")]
                try:
                    stage_ms[name] = float(v)
                    stages.setdefault(name, []).append(float(v))
                except ValueError:
                    pass
        totals.append(wall_ms)
        raw.append({
            "run": i + 1,
            "status": status,
            "wall_ms": round(wall_ms, 2),
            "server_total_ms": server_total,
            "stages": stage_ms,
        })

    wall_stats = latency_stats(totals)
    stage_stats = {name: latency_stats(vals).as_dict() for name, vals in stages.items()}

    payload = {
        "env": env_snapshot(),
        "url": url,
        "fixture": str(fixture),
        "warmup": warmup,
        "runs": runs,
        "wall_latency_ms": wall_stats.as_dict(),
        "stage_latency_ms": stage_stats,
        "raw": raw,
    }

    print_table(
        "Per-run",
        ["run", "status", "wall_ms", "server_total_ms", "stt", "llm", "tts"],
        [[
            r["run"],
            r["status"],
            r["wall_ms"],
            r["server_total_ms"],
            r["stages"].get("stt", "-"),
            r["stages"].get("llm", "-"),
            r["stages"].get("tts", "-"),
        ] for r in raw],
    )
    print_kv("Wall latency (client-observed)", [
        ("p50", f"{wall_stats.p50_ms} ms"),
        ("p95", f"{wall_stats.p95_ms} ms"),
        ("p99", f"{wall_stats.p99_ms} ms"),
        ("mean", f"{wall_stats.mean_ms} ms"),
    ])
    for name, st in stage_stats.items():
        print_kv(f"Stage '{name}' latency", [
            ("p50", f"{st['p50_ms']} ms"),
            ("p95", f"{st['p95_ms']} ms"),
            ("mean", f"{st['mean_ms']} ms"),
        ])
    return payload


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://127.0.0.1:8000/api/pipeline")
    ap.add_argument("--fixture", type=Path, required=True,
                    help="path to a .wav file; use eval_tts.py --emit-stt-fixtures to create one")
    ap.add_argument("--runs", type=int, default=10)
    ap.add_argument("--warmup", type=int, default=1)
    ap.add_argument("--save", action="store_true")
    args = ap.parse_args()
    payload = run(args.url, args.fixture, args.runs, args.warmup)
    if args.save:
        path = write_result("latency", payload)
        print(f"\nSaved -> {path}")


if __name__ == "__main__":
    main()
