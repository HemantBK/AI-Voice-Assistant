from __future__ import annotations

from typing import Protocol


class TTSProvider(Protocol):
    name: str

    def synthesize(self, text: str, voice: str | None = None, speed: float | None = None,
                   language: str | None = None) -> bytes: ...
