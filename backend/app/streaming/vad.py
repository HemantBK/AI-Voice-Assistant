"""Server-side frame-level VAD for B.4. Wraps Silero VAD (MIT, ~2 MB ONNX)
to detect speech on short incoming PCM16 frames. The VAD runs once per
frame; the caller decides when enough trailing silence has been seen to
call end-of-turn.

Silero VAD is loaded lazily on first use so the backend still boots
without the `silero-vad` package installed (B.4 is opt-in).
"""
from __future__ import annotations

import logging
import threading
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)

_LOAD_LOCK = threading.Lock()
_MODEL = None


def _load_model():
    global _MODEL
    if _MODEL is not None:
        return _MODEL
    with _LOAD_LOCK:
        if _MODEL is None:
            try:
                from silero_vad import load_silero_vad
            except ImportError as e:
                raise ImportError(
                    "Install `silero-vad` for B.4 continuous mic mode: pip install silero-vad"
                ) from e
            _MODEL = load_silero_vad(onnx=True)
            logger.info("Silero VAD loaded (onnx)")
    return _MODEL


@dataclass
class VadState:
    in_speech: bool = False
    ms_in_state: float = 0.0
    last_speech_prob: float = 0.0


class FrameVad:
    """Frame-wise VAD. Feed 20 ms PCM16 frames (320 samples @ 16 kHz) in
    sequence; query `.endpoint()` to decide when the user stopped speaking.

    Default thresholds match the Phase B.1 `WHISPER_VAD_*` defaults to keep
    behavior consistent across the pipeline.
    """

    def __init__(
        self,
        sample_rate: int = 16000,
        threshold: float = 0.5,
        min_speech_ms: int = 150,
        min_silence_ms: int = 500,
        pre_speech_pad_ms: int = 200,
    ):
        self.sample_rate = sample_rate
        self.threshold = threshold
        self.min_speech_ms = min_speech_ms
        self.min_silence_ms = min_silence_ms
        self.pre_speech_pad_ms = pre_speech_pad_ms
        self._frame_ms = 20.0
        self._state = VadState()
        self._model = None
        self._pre_buffer: list[bytes] = []  # raw frames kept before speech start
        self._speech_frames: list[bytes] = []
        self._np = None

    def _ensure_model(self):
        if self._model is None:
            import numpy as np
            self._np = np
            self._model = _load_model()

    def push(self, pcm16_frame: bytes) -> Optional[str]:
        """Ingest one 20 ms frame. Returns:
          - 'speech_start' when a speech segment begins
          - 'speech_end' when speech ends (enough trailing silence)
          - None otherwise
        """
        self._ensure_model()
        import torch

        arr = self._np.frombuffer(pcm16_frame, dtype=self._np.int16).astype(self._np.float32) / 32768.0
        if arr.size == 0:
            return None
        with torch.no_grad():
            prob = float(self._model(torch.from_numpy(arr), self.sample_rate).item())
        self._state.last_speech_prob = prob
        is_speech_frame = prob >= self.threshold

        event: Optional[str] = None
        if self._state.in_speech:
            self._speech_frames.append(pcm16_frame)
            if is_speech_frame:
                self._state.ms_in_state = 0.0
            else:
                self._state.ms_in_state += self._frame_ms
                if self._state.ms_in_state >= self.min_silence_ms:
                    self._state.in_speech = False
                    self._state.ms_in_state = 0.0
                    event = "speech_end"
        else:
            self._pre_buffer.append(pcm16_frame)
            max_pre = int(self.pre_speech_pad_ms // self._frame_ms)
            if len(self._pre_buffer) > max_pre:
                self._pre_buffer = self._pre_buffer[-max_pre:]
            if is_speech_frame:
                self._state.ms_in_state += self._frame_ms
                if self._state.ms_in_state >= self.min_speech_ms:
                    self._state.in_speech = True
                    self._state.ms_in_state = 0.0
                    self._speech_frames.extend(self._pre_buffer)
                    self._pre_buffer = []
                    event = "speech_start"
            else:
                self._state.ms_in_state = 0.0

        return event

    def drain_segment(self) -> bytes:
        """Return the accumulated speech PCM16 and reset the segment buffer."""
        pcm = b"".join(self._speech_frames)
        self._speech_frames = []
        return pcm

    @property
    def in_speech(self) -> bool:
        return self._state.in_speech

    @property
    def last_prob(self) -> float:
        return self._state.last_speech_prob
