"""Public LLM API. Routes to the active provider (groq or ollama) selected by
LLM_PROVIDER. The chat / chat_stream signatures are unchanged from earlier
versions so routers don't need updating."""
from __future__ import annotations

import logging
from typing import Iterator

from app.config import SYSTEM_PROMPT
from app.services.llm import get_provider

logger = logging.getLogger(__name__)


def _build_messages(user_message: str, history: list[dict] | None) -> list[dict]:
    messages: list[dict] = [{"role": "system", "content": SYSTEM_PROMPT}]
    if history:
        messages.extend(history)
    messages.append({"role": "user", "content": user_message})
    return messages


def chat(user_message: str, conversation_history: list[dict] | None = None) -> str:
    provider = get_provider()
    messages = _build_messages(user_message, conversation_history)
    logger.info(f"[{provider.name}:{provider.model}] -> {user_message[:80]!r}")
    response = provider.chat(messages)
    logger.info(f"[{provider.name}] <- {response[:80]!r}")
    return response


def chat_stream(user_message: str, conversation_history: list[dict] | None = None) -> Iterator[str]:
    provider = get_provider()
    messages = _build_messages(user_message, conversation_history)
    yield from provider.chat_stream(messages)
