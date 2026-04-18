# Phase B.4 — Continuous mic + server VAD endpointing (ship notes)

Goal: user doesn't press a button to start/stop. The app listens
continuously; Silero VAD on the server detects when the user stops
speaking and triggers the turn automatically.

## What shipped

**Backend**
- `backend/app/streaming/vad.py` — `FrameVad` class. Ingests 20 ms PCM16
  frames, runs Silero VAD (onnx), emits `speech_start` / `speech_end`
  events. Buffers a 200 ms pre-speech pad so the first syllable isn't
  clipped. Lazy-imports `silero-vad` so the backend still boots without it
  installed (only `continuous=1` connections fail).
- `backend/app/streaming/wav.py` — `pcm16_to_wav` byte writer. Wraps the
  VAD-accumulated PCM so the existing `stt_service.transcribe(bytes)` just
  works.
- `backend/app/routers/pipeline.py` — refactored into `_run_turn(...)` and
  a per-connection dispatcher. New query param `?continuous=1` enables
  frame-mode. New message types: `audio_frame`, `end_of_turn`.
- `backend/requirements.txt` — adds `silero-vad>=5.1` (MIT).

**Frontend**
- `frontend/public/recorder-worklet.js` — `AudioWorkletProcessor` that
  downsamples 48 kHz → 16 kHz mono PCM16 on the audio thread and posts
  20 ms frames to the main thread. Nearest-neighbor downsample (no
  anti-alias) is intentionally simple — see "Known gaps".
- `frontend/src/audio/microphoneStream.js` — `MicrophoneStream` wraps the
  `getUserMedia` + `AudioContext` + worklet plumbing. Applies browser
  built-in echo cancellation / noise suppression / AGC.

**Not wired into the UI yet** (intentional — see below).

## Why the UI isn't switched over

The UI is still in push-to-talk mode. Switching the main assistant to
`continuous=1` by default requires UX decisions I can't make for you:

- Barge-in handling during TTS (that's B.5).
- What does "mute" look like? A software toggle? A hardware key?
- Privacy: a hot mic is always listening. Mandatory visual indicator.
- Wake word — Phase I-haven't-written-yet, but pairs naturally with B.4.

So B.4 ships the plumbing. Two options to wire it:

1. Add a "hands-free" toggle on the UI. In that mode, open WS with
   `?stream=1&continuous=1`, start `MicrophoneStream`, post each frame as
   `{type: "audio_frame", pcm16_b64: ...}`. Display a VAD indicator from
   the `{type: "vad"}` events.
2. Wait for B.5 so barge-in lands at the same time as continuous mic
   (the two features are painful apart).

I recommend option 2. For now, continuous mode is an API, not a UI.

## Manual smoke test (API only)

```bash
pip install silero-vad
cd backend && python run.py
```

Then a one-line node/python client can push synthetic frames. Example
(using websockets + numpy to push 2 seconds of speech + 1 second silence):

```python
import asyncio, base64, json, numpy as np, wave
from websockets.asyncio.client import connect

async def main():
    with wave.open("eval/datasets/stt/tts-roundtrip-00.wav", "rb") as wf:
        pcm = wf.readframes(wf.getnframes())
        rate = wf.getframerate()
    assert rate == 24000 or rate == 16000, f"resample first: rate={rate}"
    # naive: assumes 16k mono; if not, resample with scipy before use.
    frame_size = 320 * 2  # 20ms @ 16kHz, 2 bytes/sample
    async with connect("ws://127.0.0.1:8000/ws/voice?stream=1&continuous=1") as ws:
        for i in range(0, len(pcm), frame_size):
            frame = pcm[i:i+frame_size]
            if len(frame) < frame_size:
                frame += b"\x00" * (frame_size - len(frame))
            await ws.send(json.dumps({"type": "audio_frame", "pcm16_b64": base64.b64encode(frame).decode()}))
            await asyncio.sleep(0.02)
        # 1s of silence to trigger endpoint
        silence = b"\x00" * frame_size
        for _ in range(50):
            await ws.send(json.dumps({"type": "audio_frame", "pcm16_b64": base64.b64encode(silence).decode()}))
            await asyncio.sleep(0.02)
        while True:
            print(await ws.recv())

asyncio.run(main())
```

## Known gaps we're accepting

- **No UI yet.** See above.
- **No barge-in.** Still possible to trigger a new turn while the previous
  is speaking; currently that produces stacked replies. B.5 fixes this.
- **Nearest-neighbor downsample in the worklet.** Higher-quality resample
  (Kaiser filter) would go in Phase 0.5. For English speech on a clean mic
  the difference is small; for music or noisy audio it would matter.
- **No AEC between TTS output and mic input.** Browser AEC handles most
  speaker bleed, but in the open-speaker case you can self-interrupt.
  True AEC (Speex or WebRTC) is Phase 0.5 work.
- **VAD runs on the event loop executor thread.** Per-frame inference
  adds ~1–3 ms on CPU. For 1 concurrent user, fine. For many, move to a
  dedicated process or batch-VAD.
- **No concurrency control.** If two `speech_end` events fire close
  together, two `_run_turn`s run concurrently on one socket. B.5 will add
  a single-in-flight-turn lock.

## Rollback

- Clients can stop sending `continuous=1`; server behavior is unchanged.
- Legacy `audio` path still works in all modes.
