from __future__ import annotations

import logging
from typing import Iterator

from app.config import GROQ_API_KEY, GROQ_MODEL, LLM_MAX_TOKENS, LLM_TEMPERATURE

logger = logging.getLogger(__name__)


class GroqProvider:
    name = "groq"

    def __init__(self):
        if not GROQ_API_KEY:
            raise ValueError("GROQ_API_KEY is not set. Get a free key at https://console.groq.com")
        from groq import Groq
        self._client = Groq(api_key=GROQ_API_KEY)
        self.model = GROQ_MODEL

    def chat(self, messages: list[dict]) -> str:
        completion = self._client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=LLM_TEMPERATURE,
            max_tokens=LLM_MAX_TOKENS,
        )
        return completion.choices[0].message.content

    def chat_stream(self, messages: list[dict]) -> Iterator[str]:
        stream = self._client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=LLM_TEMPERATURE,
            max_tokens=LLM_MAX_TOKENS,
            stream=True,
        )
        for chunk in stream:
            delta = chunk.choices[0].delta.content
            if delta:
                yield delta
