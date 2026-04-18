"""Piper TTS provider — fast local synthesis with voices for Hindi,
Tamil, Telugu, Bengali, Marathi, and many more. Apache/MIT-licensed.

Install:
    pip install piper-tts onnxruntime

Download a voice (one-off):
    # e.g. Hindi pratham (medium quality)
    python -m piper.download_voices hi_IN-pratham-medium

Voice files live under `~/.local/share/piper/` (Linux) or equivalent.
Set PIPER_VOICE to the voice name (e.g. "hi_IN-pratham-medium").
"""
from __future__ import annotations

import io
import logging
import wave

from app.config import PIPER_DATA_DIR, PIPER_VOICE

logger = logging.getLogger(__name__)


class PiperProvider:
    name = "piper"
    sample_rate = 22050  # typical piper output; actual rate is read from the voice config

    # Map generic language codes -> default Piper voice. Override with PIPER_VOICE.
    DEFAULT_VOICES = {
        "en":    "en_US-amy-medium",
        "hi":    "hi_IN-pratham-medium",
        "es":    "es_ES-davefx-medium",
        "fr":    "fr_FR-siwis-medium",
        "de":    "de_DE-thorsten-medium",
        "zh":    "zh_CN-huayan-medium",
        "it":    "it_IT-paola-medium",
        "pt-br": "pt_BR-faber-medium",
    }

    def __init__(self):
        try:
            from piper import PiperVoice  # type: ignore
        except ImportError as e:
            raise ImportError(
                "Install piper-tts + onnxruntime for the Piper TTS provider:\n"
                "  pip install piper-tts onnxruntime"
            ) from e
        self._PiperVoice = PiperVoice
        self._voices: dict[str, object] = {}

    def _resolve_voice(self, language: str | None, voice: str | None) -> str:
        if voice:
            return voice
        lang_key = (language or "en").lower()
        return self.DEFAULT_VOICES.get(lang_key, PIPER_VOICE or "en_US-amy-medium")

    def _load(self, voice_name: str):
        cached = self._voices.get(voice_name)
        if cached is not None:
            return cached
        # Look for <voice_name>.onnx in PIPER_DATA_DIR.
        from pathlib import Path
        base = Path(PIPER_DATA_DIR).expanduser() if PIPER_DATA_DIR else None
        candidates = []
        if base:
            candidates.append(base / f"{voice_name}.onnx")
        import sys
        if sys.platform.startswith("linux"):
            candidates.append(Path.home() / ".local/share/piper" / f"{voice_name}.onnx")
        candidates.append(Path.cwd() / f"{voice_name}.onnx")
        onnx = next((p for p in candidates if p.exists()), None)
        if onnx is None:
            raise FileNotFoundError(
                f"Piper voice '{voice_name}' not found. Download with:\n"
                f"  python -m piper.download_voices {voice_name}\n"
                f"Or set PIPER_DATA_DIR to a directory containing {voice_name}.onnx."
            )
        voice = self._PiperVoice.load(str(onnx))
        self._voices[voice_name] = voice
        return voice

    def synthesize(self, text: str, voice: str | None = None, speed: float | None = None,
                   language: str | None = None) -> bytes:
        voice_name = self._resolve_voice(language, voice)
        piper_voice = self._load(voice_name)
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            piper_voice.synthesize(text, wf)
        return buf.getvalue()
