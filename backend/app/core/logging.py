"""Structured JSON logging. Enabled when LOG_FORMAT=json. Otherwise falls
back to the default human-readable formatter."""
from __future__ import annotations

import json
import logging
import sys


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for key in ("turn_id", "request_id", "stage"):
            val = getattr(record, key, None)
            if val is not None:
                payload[key] = val
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def configure(format_mode: str, level: str = "INFO") -> None:
    handler = logging.StreamHandler(sys.stdout)
    if format_mode == "json":
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
        ))
    root = logging.getLogger()
    # Reset handlers in case uvicorn set its own.
    root.handlers = [handler]
    root.setLevel(getattr(logging, level.upper(), logging.INFO))
