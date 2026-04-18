"""Public TTS API. Delegates to the active provider (kokoro | piper) selected
by TTS_PROVIDER. Signature preserved for router backward compatibility."""
from __future__ import annotations

import logging

from app.services.tts import get_provider

logger = logging.getLogger(__name__)

SAMPLE_RATE = 24000  # nominal; actual per-provider rate is encoded in the returned WAV


def synthesize(text: str, voice: str | None = None, speed: float | None = None,
               language: str | None = None) -> bytes:
    """Text -> WAV bytes. `language` is used for provider-level voice
    selection (e.g. pick a Hindi voice for Piper)."""
    provider = get_provider()
    return provider.synthesize(text, voice=voice, speed=speed, language=language)
