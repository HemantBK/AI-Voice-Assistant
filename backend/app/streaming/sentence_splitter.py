"""Sentence-level splitter for streaming TTS.

For Phase B.2 we receive a full LLM response and split it into sentences so
each can be synthesized and streamed independently. The splitter is
intentionally naive — it prefers emitting *something* early over perfect
abbreviation handling. Edge cases we knowingly get wrong (and log):

- "Dr. Smith said..." → may emit "Dr." as its own sentence
- "3.14" → may split mid-number
- Trailing prose without a period → held back as tail; flushed by flush().

For token-level streaming (Phase B.3), use `IncrementalSentenceSplitter`:
feed tokens as they arrive, receive sentences when boundaries appear.
"""
from __future__ import annotations

import re
from typing import Iterator


_SENTENCE_END = re.compile(r"([.!?])(\s+|$)")


def split_sentences(text: str, min_chars: int = 8) -> list[str]:
    """Split a complete string into sentence-ish fragments.

    `min_chars` guards against emitting single-character splits ("A.", "!").
    Fragments shorter than `min_chars` are appended to the previous fragment
    rather than emitted on their own.
    """
    text = text.strip()
    if not text:
        return []

    parts: list[str] = []
    i = 0
    for match in _SENTENCE_END.finditer(text):
        end = match.end()
        candidate = text[i:end].strip()
        if not candidate:
            continue
        if parts and len(candidate) < min_chars:
            parts[-1] = parts[-1] + " " + candidate
        else:
            parts.append(candidate)
        i = end

    tail = text[i:].strip()
    if tail:
        if parts and len(tail) < min_chars:
            parts[-1] = parts[-1] + " " + tail
        else:
            parts.append(tail)

    return parts


class IncrementalSentenceSplitter:
    """Token-level splitter used by Phase B.3 streaming LLM.

    Usage:
        splitter = IncrementalSentenceSplitter()
        for token in llm_stream:
            for sentence in splitter.push(token):
                yield sentence
        for sentence in splitter.flush():
            yield sentence
    """

    def __init__(self, min_chars: int = 8):
        self._buf = ""
        self._min_chars = min_chars

    def push(self, token: str) -> Iterator[str]:
        self._buf += token
        while True:
            match = _SENTENCE_END.search(self._buf)
            if not match:
                return
            end = match.end()
            candidate = self._buf[:end].strip()
            self._buf = self._buf[end:]
            if len(candidate) >= self._min_chars:
                yield candidate
            else:
                self._buf = candidate + " " + self._buf

    def flush(self) -> Iterator[str]:
        tail = self._buf.strip()
        self._buf = ""
        if tail:
            yield tail
