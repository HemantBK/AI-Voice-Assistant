# Phase 0.5 — Audio hygiene (ship notes)

Goal: make sure we're not sending garbage audio into Whisper or the VAD.
Kept deliberately minimal because most of what this phase would normally
cover is already handled by the browser.

## What shipped

- `backend/app/audio/resample.py` — three server-side helpers:
  - `resample_linear(pcm16, src, dst)` — linear-interpolation resampler
    for PCM16 mono. numpy if present, pure-Python fallback. Used by the
    B.4 frame path if the client ever posts frames at a non-16k rate.
  - `remove_dc_offset(pcm16)` — subtracts the mean.
  - `peak_normalize(pcm16, target_peak=0.95)` — attenuate-only normalize.
- `backend/app/audio/__init__.py` (package marker).

## What the browser already does for us

When the frontend opens the mic we pass:

```js
navigator.mediaDevices.getUserMedia({
  audio: {
    echoCancellation: true,
    noiseSuppression: true,
    autoGainControl: true,
  },
});
```

That gives us Chrome's implementation of:
- **AEC** (WebRTC acoustic echo cancellation) — the speaker-bleed case
  that would otherwise cause self-interruption during TTS.
- **Noise suppression** — not RNNoise, but a steady-state suppressor
  that handles HVAC, fan noise, keyboard clack reasonably.
- **AGC** — levels the mic volume so the user can lean in/back without
  surprising the STT.

For the current scope (desktop browsers on localhost), this is
sufficient. We keep the server-side helpers for when we get audio that
*didn't* come from `getUserMedia` — Raspberry Pi direct mic capture
(Phase E), native mobile clients, or uploaded files.

## What we explicitly did NOT build

- **RNNoise / Speex DSP on the server.** Both require native deps that
  complicate install. Empirically the browser AEC+NS is close enough
  that the model-output quality delta is small. Revisit if users report
  poor STT on specific hardware.
- **Server-side AEC.** Only relevant if the server has both mic and
  speaker (Pi/embedded). Deferred to Phase E when we have hardware.
- **High-quality resampler (Kaiser / polyphase).** The nearest-neighbor
  downsample in `recorder-worklet.js` is acceptable for speech; a good
  resampler is a dependency (scipy or a C lib) and the quality win is
  not audible on 48k→16k of speech. If we go wideband TTS (48k out) or
  music, we upgrade.

## Success criteria

If after this phase the STT WER on a real human recording is still worse
than on the TTS round-trip fixture by >> 5 points, the problem is not
hygiene — it's that the TTS-roundtrip fixture set is unrealistic. Add
real samples; do not chase it with more DSP.

## Rollback

None required — all additions are new files, no behavior change.
