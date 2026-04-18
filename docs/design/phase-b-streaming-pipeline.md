# Design Doc: Phase B — Streaming pipeline & barge-in

| Field        | Value                              |
|--------------|------------------------------------|
| Status       | Draft                              |
| Author(s)    | project lead                       |
| Reviewers    | —                                  |
| Date created | 2026-04-17                         |
| Last updated | 2026-04-17                         |
| Phase        | B — Streaming + sub-second latency |

## 1. Context

Today the pipeline is request/response: the user releases the mic, the entire
`audio → STT → LLM → TTS` chain runs sequentially, then a single WAV blob is
returned and played. Wall-clock latency on a `qwen2.5:3b` CPU box is roughly:

- STT (≈3 s utterance, faster-whisper base, int8 CPU): ~600–1200 ms
- LLM (Ollama, ~120 tokens, 3B model on CPU): ~2000–6000 ms
- TTS (Kokoro, ~120 tokens): ~800–2000 ms
- **Total: 3.4 – 9.2 s before the first audio byte plays.**

Even on Groq the TTS step still blocks for ~1 s. Every commercial voice
assistant achieves sub-second perceived latency by **overlapping** these
stages and **streaming** to the speaker. We are far from that today.

## 2. Goals

- **First-audio-byte latency p50 ≤ 1000 ms, p95 ≤ 1500 ms** on Ollama path
  (CPU, qwen2.5:3b). Stretch target: ≤ 700 ms p50.
- **Barge-in**: if the user starts speaking during TTS playback, audio output
  stops within ≤ 100 ms.
- **No regression** on the existing `/api/pipeline` REST endpoint (kept for
  benchmarks and clients that don't want streaming).
- **Eval-harness-measurable**: a new runner reports first-audio-byte latency,
  per-stage start/end timestamps, and barge-in cancel latency.

## 3. Non-goals

- Multi-user concurrency tuning (single user is the design target for v1).
- Replacing Whisper with a streaming-native model (whisper-streaming, RTC).
  We will keep faster-whisper and use VAD-bounded chunks; revisit in Phase C.
- Speaker diarization, wake-word, persistent memory — separate phases.
- Mobile or native app. Web only.

## 4. Requirements

Functional:
- Continuous mic capture from the browser, streamed to the server.
- Server-side VAD detects speech end and triggers STT (no manual stop button
  required, but the existing button still works as an override).
- LLM tokens stream from provider, are split into sentences, and each
  sentence is synthesized + streamed to the client as soon as it's ready.
- Client plays incoming audio sentences in order, gaplessly.
- If VAD detects new user speech during playback, the client stops audio
  immediately and signals the server to cancel the in-flight LLM/TTS.

Non-functional:
- All transport over a single WebSocket connection (existing `/ws/voice`).
- Audio in: 16 kHz mono PCM16 frames, 20 ms each (320 samples).
- Audio out: 24 kHz PCM16 frames or Opus (decision below). Server emits frames
  ≤ 200 ms each so playback can start without buffering.
- Backpressure: client must be able to drop pending TTS frames on barge-in.

## 5. Proposal

### 5.1 Wire format (extends existing `/ws/voice`)

Client → server (one of):
```
{"type": "audio_frame",   "pcm16_b64": "..."}        # 20 ms PCM16 mono @ 16 kHz
{"type": "barge_in"}                                  # client started speaking; cancel current turn
{"type": "end_of_turn"}                               # manual stop (mic button)
{"type": "clear_history"}
```

Server → client:
```
{"type": "vad",        "speaking": true|false}
{"type": "transcript", "text": "...", "is_final": false|true}
{"type": "llm_delta",  "text": "..."}                 # raw token chunks (optional, for transcript UI)
{"type": "tts_chunk",  "seq": 0, "pcm16_b64": "...", "sample_rate": 24000}
{"type": "tts_end",    "seq": 12}                     # last chunk for this turn
{"type": "cancelled",  "reason": "barge_in"}
{"type": "error",      "message": "..."}
```

Audio format: PCM16 little-endian, mono. Opus compression deferred — adds
encode/decode latency and a codec dep; revisit if bandwidth becomes an issue.

### 5.2 Server pipeline

```
audio_frame ─┐                    ┌─ tts_chunk seq=0 ─┐
audio_frame ─┤                    ├─ tts_chunk seq=1 ─┤  WS to client
audio_frame ─┴─▶ VAD ─▶ STT ─▶ LLM ─sentence─▶ TTS ──┴─ tts_end ─────┘
                  │                  │                ▲
                  └─ "vad" event     └─ "llm_delta"   │
                                                       │
   barge_in / end_of_turn ───▶ asyncio.Task.cancel() ──┘  cancels LLM + TTS
```

Implementation:
- A `TurnManager` per WS connection holds the current `asyncio.Task` for the
  LLM-and-TTS coroutine. `barge_in` calls `.cancel()` and emits `cancelled`.
- `silero_vad` (ONNX, MIT, ~2 MB) runs on the server in a thread executor.
  Frame-by-frame; fires `speech_end` after ≥ 300 ms of trailing silence.
- STT receives the buffered speech segment and runs once. (Streaming STT is
  Phase B.4; Phase B.1–B.3 keeps STT one-shot at end-of-speech.)
- LLM streams via `provider.chat_stream()` (already implemented). A
  `SentenceSplitter` accumulates tokens and yields whole sentences on
  `[.!?]\s` or every N characters.
- TTS calls `tts_service.synthesize(sentence)` per sentence, splits the WAV
  into PCM frames, streams them. (Per-sentence Kokoro calls are well under
  the per-token budget; full-streaming TTS is Phase B.5.)

### 5.3 Client pipeline

- Replace `MediaRecorder` (which only flushes at stop) with an `AudioWorklet`
  that downsamples to 16 kHz mono PCM16 and posts 20 ms frames.
- An `AudioPlayer` maintains a `seq`-ordered queue of `AudioBufferSourceNode`s,
  scheduled back-to-back via `AudioContext.currentTime`. Stop method cancels
  all pending sources — barge-in.
- Client-side VAD (Silero ONNX in WASM, ~2 MB) detects local speech onset
  during playback and emits `barge_in` immediately. (Without client VAD,
  barge-in latency is bounded by network RTT.)
- UI shows transcript live (`is_final` toggle), assistant text live as
  `llm_delta` arrives, plays audio as `tts_chunk` arrives.

### 5.4 File layout (delta)

```
backend/app/
    streaming/
        __init__.py
        vad.py                # SileroVAD wrapper, frame-in / event-out
        sentence_splitter.py  # tokens-in, sentences-out
        turn_manager.py       # per-connection state, cancellation
    routers/
        pipeline.py           # /ws/voice gets a v2 protocol path
frontend/src/
    audio/
        recorder-worklet.js   # AudioWorkletProcessor: 48k → 16k PCM16
        player.js             # gapless seq-ordered playback
        vad-client.js         # Silero ONNX in WASM
    hooks/
        useStreamingVoice.js  # replaces useAudioRecorder for streaming UI
eval/
    runners/
        eval_streaming.py     # first-audio-byte latency, barge-in latency
```

## 6. Alternatives considered

- **Server-Sent Events instead of WebSocket.** SSE is one-way; we need
  client→server audio frames continuously. Reject.
- **WebRTC instead of WebSocket.** Lower latency, native jitter buffer, NAT
  traversal. But: ICE/STUN setup, much more complex, server side needs
  aiortc. WS + PCM frames is good enough for the localhost / LAN target of
  Phase B; revisit for Phase E (edge / public deployment).
- **whisper-streaming / RealtimeSTT (true streaming STT).** True overlap
  with user speech, lower end-to-end latency. But: experimental, more model
  state to manage, harder to debug. Keep one-shot STT at end-of-speech for
  Phase B.1–B.3; promote to streaming in B.4 once the harness is in place.
- **Streaming TTS at sub-sentence level.** Kokoro doesn't support true
  token-level streaming. Sentence-level streaming captures most of the win
  (~80%) without forking Kokoro. Revisit when Piper is added in Phase C
  (Piper supports streaming natively).
- **Run VAD on the client only.** Saves CPU on the server, but means the
  server cannot reject silent or runaway frames. We do *both*: client VAD
  drives barge-in (latency-critical), server VAD drives end-of-turn
  detection (quality-critical).

## 7. Risks & mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|-----------|
| AudioWorklet sample-rate mismatch (browser is 48k, model wants 16k) | high | breaks STT | downsample in worklet, unit-test the worklet output offline |
| Sentence splitter cuts mid-abbreviation ("Dr." "U.S.") | medium | choppy TTS | start naive, allow N-token min before splitting, log cases |
| Cancellation races: LLM finishes between barge-in and cancel | medium | wasted compute | guard `tts_chunk` emit with `task.cancelled()` check before send |
| Silero VAD WASM size on cold load | medium | slow first paint | lazy-load after first user gesture, cache in service worker |
| Ollama keeps generating after cancel (subprocess) | high | wasted CPU | call client.abort if available; otherwise accept until upstream fix |
| Barge-in false positives from speaker bleed-through | medium | self-interruption | run VAD on the *input* mic only; AEC out of scope (see Phase 0.5) |

## 8. Rollout plan

Slice incrementally. Each slice is independently mergeable and measurable:

- **B.1 — Server-side VAD endpointing on existing pipeline.** No streaming
  yet; just trim leading/trailing silence and measure the latency win.
  Eval: rerun `eval_latency.py`, expect 100–300 ms STT savings.
- **B.2 — Sentence-level TTS streaming over WS.** New WS protocol
  `tts_chunk` / `tts_end`. LLM still one-shot. Biggest single perceived-
  latency win because user hears the first sentence while later sentences
  synthesize. Eval: new `eval_streaming.py` reports `first_audio_byte_ms`.
- **B.3 — Streaming LLM into the sentence splitter.** LLM and TTS now
  overlap. Eval: same runner, `first_audio_byte_ms` should drop again.
- **B.4 — Continuous mic capture + server VAD trigger (no manual stop).**
  AudioWorklet on the client; mic button becomes "wake/sleep" not "PTT".
- **B.5 — Barge-in.** Client VAD, immediate playback stop, server task
  cancel. Eval: `barge_in_latency_ms` p95 ≤ 100 ms.

Stop after any slice if the numbers say it's good enough.

## 9. Rollback plan

Each slice is its own commit / branch. Revert the commit. The legacy
`/api/pipeline` POST endpoint is *not* removed in Phase B — it remains the
fallback path and the eval baseline, so rollback is "switch the frontend
back to calling the REST endpoint."

## 10. Observability

- Extend `TimingMiddleware` (ADR 0001) with WS-aware spans:
  `ws.audio_frames_received`, `vad.speech_start`, `vad.speech_end`,
  `stt.start/end`, `llm.first_token`, `llm.last_token`, `tts.chunk[seq]`,
  `client.first_audio_play` (reported back via a `metrics` WS event).
- Structured log per turn: `{turn_id, stage, t_ms_relative, total_ms}`.
- New eval runner emits a CSV of timestamps for offline analysis.

## 11. Security & privacy

- Mic stream is high-volume PII. Reaffirm `LLM_PROVIDER=ollama` default — no
  audio leaves the box.
- `/ws/voice` currently has no auth (open issue from the audit). Out of
  scope for Phase B; tracked in Phase 4 (security hardening). Add a TODO and
  a CORS-tight origin check.
- Document audio retention: zero by default. Server holds frames in memory
  for the duration of one turn only.

## 12. Success metrics

Baseline (Phase A, captured before B.1 lands):
- `first_audio_byte_ms` p50 / p95: __ / __
- `total_pipeline_ms` p50 / p95: __ / __

Targets after B.5:
- `first_audio_byte_ms` p50 ≤ 1000, p95 ≤ 1500
- `barge_in_latency_ms` p95 ≤ 100
- LLM accuracy on `golden_qa.jsonl` unchanged (no regression)
- WER on STT manifest unchanged

All three measured by the eval harness; no claim ships without numbers.

## 13. Open questions

- Should client VAD be Silero (2 MB ONNX) or the simpler WebRTC VAD (built
  into browsers, less accurate)? Bench in B.5.
- How do we handle the "user trails off" case where VAD never fires?
  Probably a hard-cap timeout (e.g. 8 s of single utterance → force STT).
- Do we want to emit `llm_delta` to the client at all, or only the
  synthesized audio? Showing live transcript helps perceived speed but adds
  UI complexity. Decide in B.3.

## 14. Appendix

- ADR 0001 (eval harness) — required for measuring every slice.
- ADR 0002 (provider abstraction) — Ollama is the default streaming target.
- Silero VAD: https://github.com/snakers4/silero-vad
- Kokoro: behavior on per-sentence calls — verify warm cache cost is small.
