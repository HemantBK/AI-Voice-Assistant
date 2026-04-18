"""Tiny PCM16 -> WAV byte writer. Used by B.4 to wrap VAD-accumulated
speech frames into a WAV blob that the existing STT service can read."""
from __future__ import annotations

import io
import struct


def pcm16_to_wav(pcm: bytes, sample_rate: int = 16000, channels: int = 1) -> bytes:
    byte_rate = sample_rate * channels * 2
    block_align = channels * 2
    data_size = len(pcm)
    buf = io.BytesIO()
    buf.write(b"RIFF")
    buf.write(struct.pack("<I", 36 + data_size))
    buf.write(b"WAVE")
    buf.write(b"fmt ")
    buf.write(struct.pack("<IHHIIHH", 16, 1, channels, sample_rate, byte_rate, block_align, 16))
    buf.write(b"data")
    buf.write(struct.pack("<I", data_size))
    buf.write(pcm)
    return buf.getvalue()
