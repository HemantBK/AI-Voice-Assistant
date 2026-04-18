"""OpenVoice v2 cloning scaffold (Phase D').

NOTE — this is a SCAFFOLD. OpenVoice v2 has a non-trivial install
(torch, librosa, whisper, and a model download) and the provider API
below is written against the public OpenVoice v2 interface but has NOT
been validated in this repo. See docs/design/phase-d-notes.md for the
full setup and the consent/watermarking story.

Usage once installed + enrolled:

    TTS_PROVIDER=openvoice
    OPENVOICE_REFERENCE_WAV=/path/to/user-10s-enrollment.wav
    OPENVOICE_BASE_SPEAKER=en-default

The provider mixes a base speaker's prosody with the enrollment
speaker's timbre. Input goes through a base TTS first (Piper or
Kokoro) and is then tone-converted to the enrolled voice.
"""
from __future__ import annotations

import io
import logging
from pathlib import Path

import numpy as np
import soundfile as sf

from app.config import (
    OPENVOICE_BASE_SPEAKER,
    OPENVOICE_CHECKPOINT_DIR,
    OPENVOICE_REFERENCE_WAV,
)

logger = logging.getLogger(__name__)


class OpenVoiceProvider:
    name = "openvoice"
    sample_rate = 24000

    def __init__(self):
        try:
            # Imports are deferred so the server still boots without OpenVoice installed.
            from openvoice import se_extractor  # type: ignore
            from openvoice.api import BaseSpeakerTTS, ToneColorConverter  # type: ignore
        except ImportError as e:
            raise ImportError(
                "OpenVoice v2 is not installed. See docs/design/phase-d-notes.md"
            ) from e
        self._se_extractor = se_extractor
        self._BaseSpeakerTTS = BaseSpeakerTTS
        self._ToneColorConverter = ToneColorConverter

        ckpt = Path(OPENVOICE_CHECKPOINT_DIR).expanduser()
        if not ckpt.exists():
            raise FileNotFoundError(
                f"OPENVOICE_CHECKPOINT_DIR does not exist: {ckpt}. "
                "Download the v2 checkpoints — see docs/design/phase-d-notes.md."
            )

        ref = Path(OPENVOICE_REFERENCE_WAV).expanduser() if OPENVOICE_REFERENCE_WAV else None
        if not ref or not ref.exists():
            raise FileNotFoundError(
                "OPENVOICE_REFERENCE_WAV is not set or missing. "
                "Record a 10-second enrollment clip and point this env var at it."
            )

        base_ckpt = ckpt / "base_speakers" / "EN"
        self._base_tts = BaseSpeakerTTS(f"{base_ckpt}/config.json", device="cpu")
        self._base_tts.load_ckpt(f"{base_ckpt}/checkpoint.pth")

        conv_ckpt = ckpt / "converter"
        self._tone = ToneColorConverter(f"{conv_ckpt}/config.json", device="cpu")
        self._tone.load_ckpt(f"{conv_ckpt}/checkpoint.pth")

        self._target_se, _ = se_extractor.get_se(str(ref), self._tone, vad=True)
        self._source_se = np.load(base_ckpt / "en_default_se.npy")
        self._base_speaker = OPENVOICE_BASE_SPEAKER or "default"

    def synthesize(self, text: str, voice: str | None = None, speed: float | None = None,
                   language: str | None = None) -> bytes:
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as src_f, \
             tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as dst_f:
            src_path = src_f.name
            dst_path = dst_f.name

        try:
            self._base_tts.tts(text, src_path, speaker=self._base_speaker, language=(language or "English"), speed=(speed or 1.0))
            self._tone.convert(
                audio_src_path=src_path,
                src_se=self._source_se,
                tgt_se=self._target_se,
                output_path=dst_path,
                message="@cloned",  # simple watermark tag; real audio watermarking is a follow-up
            )
            audio, _ = sf.read(dst_path)
            buf = io.BytesIO()
            sf.write(buf, audio, self.sample_rate, format="WAV")
            buf.seek(0)
            return buf.read()
        finally:
            for p in (src_path, dst_path):
                try:
                    Path(p).unlink(missing_ok=True)
                except Exception:
                    pass
