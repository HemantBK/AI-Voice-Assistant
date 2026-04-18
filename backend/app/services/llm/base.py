from __future__ import annotations

from typing import Iterator, Protocol


class LLMProvider(Protocol):
    name: str
    model: str

    def chat(self, messages: list[dict]) -> str: ...

    def chat_stream(self, messages: list[dict]) -> Iterator[str]: ...
