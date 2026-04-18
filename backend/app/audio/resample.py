"""Audio hygiene utilities (Phase 0.5).

This module deliberately stays small: the browser's `getUserMedia` already
applies echoCancellation/noiseSuppression/AGC (configured in
MicrophoneStream), and faster-whisper handles its own decoding of arbitrary
input formats. The functions here are for server-side PCM fixups — sample
rate conversion for the VAD path, simple peak-normalization, and DC-offset
removal.

For true RNNoise / Speex AEC / WebRTC AEC we would ship a native dep;
that's deferred. See docs/design/phase-0.5-notes.md for rationale.
"""
from __future__ import annotations

import math

try:
    import numpy as np
except ImportError:  # pragma: no cover
    np = None  # type: ignore


def resample_linear(pcm16: bytes, src_rate: int, dst_rate: int) -> bytes:
    """Linear-interpolation resampler for PCM16 mono.

    Good enough for the 48k->16k STT path on clean speech; not suitable
    for audio where aliasing matters. Falls back to pure Python if numpy
    isn't available (slower but dep-free).
    """
    if src_rate == dst_rate or len(pcm16) == 0:
        return pcm16
    if np is not None:
        src = np.frombuffer(pcm16, dtype=np.int16).astype(np.float32)
        n_src = src.shape[0]
        n_dst = max(1, int(round(n_src * dst_rate / src_rate)))
        x_src = np.linspace(0.0, n_src - 1, num=n_src, dtype=np.float32)
        x_dst = np.linspace(0.0, n_src - 1, num=n_dst, dtype=np.float32)
        dst = np.interp(x_dst, x_src, src)
        return np.clip(dst, -32768, 32767).astype(np.int16).tobytes()

    # Pure-python fallback.
    import struct
    n_src = len(pcm16) // 2
    samples = struct.unpack(f"<{n_src}h", pcm16)
    n_dst = max(1, int(round(n_src * dst_rate / src_rate)))
    out = []
    for i in range(n_dst):
        t = (i * (n_src - 1)) / max(1, n_dst - 1) if n_dst > 1 else 0
        lo = int(math.floor(t))
        hi = min(n_src - 1, lo + 1)
        frac = t - lo
        v = samples[lo] * (1 - frac) + samples[hi] * frac
        out.append(max(-32768, min(32767, int(round(v)))))
    return struct.pack(f"<{len(out)}h", *out)


def remove_dc_offset(pcm16: bytes) -> bytes:
    """Subtract the mean so zero-crossing heuristics behave on biased ADCs."""
    if np is None or not pcm16:
        return pcm16
    arr = np.frombuffer(pcm16, dtype=np.int16).astype(np.int32)
    arr -= int(arr.mean())
    return np.clip(arr, -32768, 32767).astype(np.int16).tobytes()


def peak_normalize(pcm16: bytes, target_peak: float = 0.95) -> bytes:
    """Scale to a target peak amplitude (0..1 of int16 range). No-op if silent."""
    if np is None or not pcm16:
        return pcm16
    arr = np.frombuffer(pcm16, dtype=np.int16).astype(np.float32)
    peak = float(np.max(np.abs(arr)))
    if peak <= 0:
        return pcm16
    scale = (target_peak * 32767.0) / peak
    if scale >= 1.0:
        return pcm16
    out = np.clip(arr * scale, -32768, 32767).astype(np.int16)
    return out.tobytes()
