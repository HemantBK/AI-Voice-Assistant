# Phase B.2 — Sentence-level TTS streaming (ship notes)

Goal: user hears the first sentence of the assistant's reply long before the
full response has been synthesized. Ships the new WS streaming protocol and
the client-side gapless audio player. LLM is still one-shot in this slice —
token-level streaming is B.3.

## What shipped

**Backend**
- `backend/app/streaming/sentence_splitter.py`
  - `split_sentences(text)` — naive period/?/! splitter with a min-chars merge rule
  - `IncrementalSentenceSplitter` — token-level variant, reserved for B.3
- `backend/app/routers/pipeline.py` — `/ws/voice` now accepts `?stream=1`:
  - on `stream=1`: emits a `tts_chunk` per sentence with `seq`, `text`,
    `audio` (base64 WAV), `is_final`; then a `tts_end` marker
  - on default: unchanged — single `audio` blob, backward-compatible
- Kokoro calls are wrapped in `asyncio.to_thread` so the event loop stays
  responsive while synth is running.

**Frontend**
- `frontend/src/audio/streamingPlayer.js` — `StreamingAudioPlayer`
  schedules each chunk at `max(nextStart, currentTime)` for gapless
  playback; `stop()` cancels all sources (B.5 barge-in primitive).
- `frontend/src/services/voiceWsClient.js` — `VoiceWsClient` wrapper;
  streaming on by default, legacy mode via `{ streaming: false }`.
- `frontend/src/components/VoiceAssistant.jsx` — replaces the REST pipeline
  call with the WS streaming flow. Transitions: `idle → recording →
  processing → speaking → idle` driven by WS events.

**Eval**
- `eval/runners/eval_streaming.py` — opens the WS, posts a fixture,
  records `transcript_ms`, `response_ms`, **`first_audio_byte_ms`**,
  `tts_end_ms`. Aggregates p50/p95/p99 across N runs.

## The headline metric

`first_audio_byte_ms` — milliseconds from sending the user audio to
receiving the first `tts_chunk` back. This is the single number we expect
to drop meaningfully vs. the Phase A baseline.

## How to A/B against Phase A

1. Generate a fixture (if you haven't yet):
   ```bash
   python -m eval.runners.eval_tts --emit-stt-fixtures
   ```
2. Start the backend: `cd backend && python run.py`
3. Baseline — legacy WS path (single audio blob):
   ```bash
   python -m eval.runners.eval_streaming \
     --url ws://127.0.0.1:8000/ws/voice \
     --fixture eval/datasets/stt/tts-roundtrip-00.wav \
     --runs 10 --save
   ```
4. New — streaming path:
   ```bash
   python -m eval.runners.eval_streaming \
     --url 'ws://127.0.0.1:8000/ws/voice?stream=1' \
     --fixture eval/datasets/stt/tts-roundtrip-00.wav \
     --runs 10 --save
   ```
5. Diff the two newest `eval/results/streaming-*.json`.

Expected: `first_audio_byte_ms` drops by roughly
`(total_response_length - first_sentence_length) / tts_rtf`. On a 120-token
reply split into 3 sentences, that's typically a 400–800 ms win.

## Manual test checklist (I can't run the browser)

Please run these before calling B.2 green:

- [ ] `docker compose up` (or manual start) — frontend loads at
      `http://localhost:5173`
- [ ] Mic permission prompt appears on first click
- [ ] Press mic → speak → press mic. Expect: transcript bubble appears,
      assistant bubble appears, **audio starts before the full response is
      finished** (the point of the slice). Sentences should play
      back-to-back with no gap.
- [ ] Long reply: ask "Tell me a 3-sentence story about a robot." You
      should hear the first sentence while the second is still being
      synthesized.
- [ ] Short reply: ask "Hi." Single sentence is handled (no gap mismatch).
- [ ] Empty input: press mic, stay silent, press mic. Expect `transcript`
      is empty, no crash, status returns to `idle`.
- [ ] Clear chat button: stops playback immediately, resets history.
- [ ] Reload the page mid-conversation: no zombie audio, no console errors.
- [ ] Network tab: single WS connection; per-sentence `tts_chunk` frames
      are visible.

## Known gaps we're accepting in this slice

- **LLM is still one-shot.** The biggest remaining latency floor. Fixed in
  B.3 (stream LLM tokens → feed the sentence splitter live).
- **Kokoro sentence warm-start.** Each sentence spins up the pipeline
  again. If RTF is bad on your box, consider batching 2 sentences at a time.
- **No barge-in yet.** Clicking mic while the assistant is speaking is
  blocked (`status === processing` gate lifted, but the player doesn't stop).
  Fixed in B.5.
- **No concurrency control.** If you hit mic twice fast, you can queue
  overlapping turns. Fixed in B.5 alongside barge-in (single in-flight turn).
- **WS has no auth.** Still tracked for Phase 4 (security hardening).

## Rollback

- Server: set the frontend back to `streaming: false` or just hit the REST
  `/api/pipeline` endpoint. No schema changes, no migrations.
- Full revert: `git revert` the B.2 commit — backend falls back to the
  pre-streaming WS protocol, frontend can be reverted independently.
