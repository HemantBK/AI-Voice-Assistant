"""Report helpers: console tables + JSON writes."""
from __future__ import annotations

import json
import platform
import socket
import sys
from datetime import datetime, timezone
from pathlib import Path


RESULTS_DIR = Path(__file__).resolve().parent.parent / "results"


def env_snapshot() -> dict:
    return {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "hostname": socket.gethostname(),
        "platform": platform.platform(),
        "python": sys.version.split()[0],
    }


def write_result(name: str, payload: dict) -> Path:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = RESULTS_DIR / f"{name}-{stamp}.json"
    path.write_text(json.dumps(payload, indent=2))
    latest = RESULTS_DIR / f"{name}-latest.json"
    latest.write_text(json.dumps(payload, indent=2))
    return path


def print_kv(title: str, rows: list[tuple[str, object]]) -> None:
    width = max((len(k) for k, _ in rows), default=0)
    print(f"\n=== {title} ===")
    for k, v in rows:
        print(f"  {k.ljust(width)}  {v}")


def print_table(title: str, headers: list[str], rows: list[list[object]]) -> None:
    widths = [len(h) for h in headers]
    str_rows = [[str(c) for c in r] for r in rows]
    for r in str_rows:
        for i, cell in enumerate(r):
            widths[i] = max(widths[i], len(cell))
    print(f"\n=== {title} ===")
    line = "  ".join(h.ljust(widths[i]) for i, h in enumerate(headers))
    print(line)
    print("-" * len(line))
    for r in str_rows:
        print("  ".join(r[i].ljust(widths[i]) for i in range(len(headers))))
