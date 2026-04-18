import io
import logging

from faster_whisper import WhisperModel

from app.config import (
    WHISPER_DEVICE,
    WHISPER_MODEL_SIZE,
    WHISPER_VAD_FILTER,
    WHISPER_VAD_MIN_SILENCE_MS,
    WHISPER_VAD_MIN_SPEECH_MS,
    WHISPER_VAD_SPEECH_PAD_MS,
    WHISPER_VAD_THRESHOLD,
)

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


def _vad_parameters() -> dict:
    return {
        "threshold": WHISPER_VAD_THRESHOLD,
        "min_silence_duration_ms": WHISPER_VAD_MIN_SILENCE_MS,
        "min_speech_duration_ms": WHISPER_VAD_MIN_SPEECH_MS,
        "speech_pad_ms": WHISPER_VAD_SPEECH_PAD_MS,
    }


def transcribe(audio_bytes: bytes) -> dict:
    """Transcribe audio bytes. With VAD filtering enabled (default), silent
    regions are skipped before decoding, which both reduces STT compute and
    prevents Whisper hallucinations on silence."""
    model = get_model()

    audio_file = io.BytesIO(audio_bytes)
    segments, info = model.transcribe(
        audio_file,
        beam_size=5,
        vad_filter=WHISPER_VAD_FILTER,
        vad_parameters=_vad_parameters() if WHISPER_VAD_FILTER else None,
    )

    text_parts = [s.text for s in segments]
    transcript = " ".join(text_parts).strip()

    audio_duration_s = float(getattr(info, "duration", 0.0) or 0.0)
    speech_duration_s = float(getattr(info, "duration_after_vad", audio_duration_s) or audio_duration_s)
    trimmed_ms = max(0.0, (audio_duration_s - speech_duration_s) * 1000.0)

    if WHISPER_VAD_FILTER and audio_duration_s > 0:
        logger.info(
            "stt.vad trimmed=%.0fms audio=%.2fs speech=%.2fs ratio=%.2f",
            trimmed_ms, audio_duration_s, speech_duration_s,
            speech_duration_s / audio_duration_s if audio_duration_s else 0.0,
        )

    return {
        "text": transcript,
        "language": info.language,
        "language_probability": round(info.language_probability, 3),
        "audio_duration_s": round(audio_duration_s, 3),
        "speech_duration_s": round(speech_duration_s, 3),
        "vad_trimmed_ms": round(trimmed_ms, 2),
        "vad_enabled": WHISPER_VAD_FILTER,
    }
