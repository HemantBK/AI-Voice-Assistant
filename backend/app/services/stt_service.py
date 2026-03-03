import io
import logging
from faster_whisper import WhisperModel
from app.config import WHISPER_MODEL_SIZE, WHISPER_DEVICE

logger = logging.getLogger(__name__)

_model = None


def get_model():
    global _model
    if _model is None:
        logger.info(f"Loading Whisper model: {WHISPER_MODEL_SIZE} on {WHISPER_DEVICE}")
        _model = WhisperModel(
            WHISPER_MODEL_SIZE,
            device=WHISPER_DEVICE,
            compute_type="int8" if WHISPER_DEVICE == "cpu" else "float16",
        )
        logger.info("Whisper model loaded")
    return _model


def transcribe(audio_bytes: bytes) -> dict:
    """Transcribe audio bytes to text using Faster-Whisper."""
    model = get_model()

    audio_file = io.BytesIO(audio_bytes)
    segments, info = model.transcribe(audio_file, beam_size=5)

    text_parts = []
    for segment in segments:
        text_parts.append(segment.text)

    transcript = " ".join(text_parts).strip()

    return {
        "text": transcript,
        "language": info.language,
        "language_probability": round(info.language_probability, 3),
    }
