import io
import logging
import numpy as np
import soundfile as sf
from kokoro import KPipeline
from app.config import KOKORO_VOICE, KOKORO_SPEED

logger = logging.getLogger(__name__)

SAMPLE_RATE = 24000
_pipeline = None


def get_pipeline():
    global _pipeline
    if _pipeline is None:
        logger.info("Loading Kokoro TTS pipeline...")
        _pipeline = KPipeline(lang_code="a")  # 'a' = American English
        logger.info("Kokoro TTS loaded")
    return _pipeline


def synthesize(text: str, voice: str | None = None, speed: float | None = None) -> bytes:
    """Convert text to speech audio (WAV bytes)."""
    pipeline = get_pipeline()

    voice = voice or KOKORO_VOICE
    speed = speed or KOKORO_SPEED

    audio_chunks = []
    for _, _, audio in pipeline(text, voice=voice, speed=speed):
        if audio is not None:
            audio_chunks.append(audio)

    if not audio_chunks:
        raise ValueError("TTS produced no audio output")

    full_audio = np.concatenate(audio_chunks)

    buffer = io.BytesIO()
    sf.write(buffer, full_audio, SAMPLE_RATE, format="WAV")
    buffer.seek(0)
    return buffer.read()
