from __future__ import annotations

import logging

from app.config import TTS_PROVIDER
from app.services.tts.base import TTSProvider

logger = logging.getLogger(__name__)

_provider: TTSProvider | None = None


def get_provider() -> TTSProvider:
    global _provider
    if _provider is not None:
        return _provider

    name = (TTS_PROVIDER or "kokoro").lower()
    if name == "kokoro":
        from app.services.tts.kokoro_provider import KokoroProvider
        _provider = KokoroProvider()
    elif name == "piper":
        from app.services.tts.piper_provider import PiperProvider
        _provider = PiperProvider()
    elif name == "openvoice":
        from app.services.tts.openvoice_provider import OpenVoiceProvider
        _provider = OpenVoiceProvider()
    else:
        raise ValueError(f"Unknown TTS_PROVIDER={name!r}. Expected 'kokoro', 'piper', or 'openvoice'.")
    logger.info("TTS provider: %s", _provider.name)
    return _provider
