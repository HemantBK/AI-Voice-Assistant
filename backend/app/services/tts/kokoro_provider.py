from __future__ import annotations

import io
import logging

import numpy as np
import soundfile as sf

from app.config import KOKORO_SPEED, KOKORO_VOICE

logger = logging.getLogger(__name__)


class KokoroProvider:
    """English-first TTS. Fast, high quality, 82 M params."""
    name = "kokoro"
    sample_rate = 24000

    # Kokoro language codes. Subset here covers the currently-packaged voices;
    # see https://github.com/hexgrad/kokoro for the full registry.
    LANG_CODES = {
        "en": "a",      # American English
        "en-gb": "b",   # British English
        "ja": "j",
        "zh": "z",
    }

    def __init__(self):
        from kokoro import KPipeline
        # Lazy-load per language to avoid bringing up every voice at boot.
        self._pipelines: dict[str, KPipeline] = {}

    def _pipeline(self, language: str | None):
        code = self.LANG_CODES.get((language or "en").lower(), "a")
        pipe = self._pipelines.get(code)
        if pipe is None:
            from kokoro import KPipeline
            logger.info("Loading Kokoro pipeline for lang_code=%s", code)
            pipe = KPipeline(lang_code=code)
            self._pipelines[code] = pipe
        return pipe

    def synthesize(self, text: str, voice: str | None = None, speed: float | None = None,
                   language: str | None = None) -> bytes:
        pipe = self._pipeline(language)
        voice = voice or KOKORO_VOICE
        speed = speed or KOKORO_SPEED
        audio_chunks = []
        for _, _, audio in pipe(text, voice=voice, speed=speed):
            if audio is not None:
                audio_chunks.append(audio)
        if not audio_chunks:
            raise ValueError("TTS produced no audio output")
        full_audio = np.concatenate(audio_chunks)
        buf = io.BytesIO()
        sf.write(buf, full_audio, self.sample_rate, format="WAV")
        buf.seek(0)
        return buf.read()
