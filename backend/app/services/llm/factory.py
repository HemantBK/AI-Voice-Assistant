from __future__ import annotations

import logging

from app.config import LLM_PROVIDER
from app.services.llm.base import LLMProvider

logger = logging.getLogger(__name__)

_provider: LLMProvider | None = None


def get_provider() -> LLMProvider:
    global _provider
    if _provider is not None:
        return _provider

    if LLM_PROVIDER == "ollama":
        from app.services.llm.ollama_provider import OllamaProvider
        _provider = OllamaProvider()
    elif LLM_PROVIDER == "groq":
        from app.services.llm.groq_provider import GroqProvider
        _provider = GroqProvider()
    else:
        raise ValueError(
            f"Unknown LLM_PROVIDER={LLM_PROVIDER!r}. Expected 'groq' or 'ollama'."
        )

    logger.info(f"LLM provider: {_provider.name} (model={_provider.model})")
    return _provider
