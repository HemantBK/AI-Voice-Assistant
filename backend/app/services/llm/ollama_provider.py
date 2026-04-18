from __future__ import annotations

import logging
from typing import Iterator

from app.config import LLM_MAX_TOKENS, LLM_TEMPERATURE, OLLAMA_HOST, OLLAMA_MODEL

logger = logging.getLogger(__name__)


class OllamaProvider:
    name = "ollama"

    def __init__(self):
        try:
            from ollama import Client
        except ImportError as e:
            raise ImportError(
                "The 'ollama' package is required for the local provider. "
                "Install it with: pip install ollama"
            ) from e
        self._client = Client(host=OLLAMA_HOST)
        self.model = OLLAMA_MODEL
        self._options = {
            "temperature": LLM_TEMPERATURE,
            "num_predict": LLM_MAX_TOKENS,
        }

    def chat(self, messages: list[dict]) -> str:
        try:
            resp = self._client.chat(model=self.model, messages=messages, options=self._options)
        except Exception as e:
            raise RuntimeError(
                f"Ollama call failed against {OLLAMA_HOST} (model={self.model}). "
                f"Is the daemon running and the model pulled? "
                f"Run: `ollama pull {self.model}`. Underlying error: {e}"
            ) from e
        return resp["message"]["content"]

    def chat_stream(self, messages: list[dict]) -> Iterator[str]:
        try:
            stream = self._client.chat(
                model=self.model, messages=messages, options=self._options, stream=True
            )
        except Exception as e:
            raise RuntimeError(
                f"Ollama stream call failed against {OLLAMA_HOST} (model={self.model}): {e}"
            ) from e
        for chunk in stream:
            delta = chunk.get("message", {}).get("content")
            if delta:
                yield delta
