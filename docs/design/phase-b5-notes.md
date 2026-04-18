# Phase B.5 — Barge-in + turn cancellation (ship notes)

Goal: the user can interrupt the assistant. Click the mic (or start
speaking in continuous mode) while audio is playing → playback stops
within ~50 ms, in-flight LLM/TTS is cancelled server-side, the new turn
runs immediately.

## What shipped

**Backend**
- `backend/app/streaming/turn_manager.py` — `TurnManager` wraps one
  in-flight turn per WS. `start(coro)` cancels any running turn first; a
  new turn waits for the previous to unwind cleanly before starting.
- `backend/app/routers/pipeline.py`:
  - Holds a `TurnManager` per connection.
  - New client message `{"type": "barge_in"}` → cancels the in-flight
    turn, sends `{"type": "cancelled", "reason": "barge_in"}`.
  - In continuous mode, `speech_start` events during a busy turn also
    trigger cancellation + `cancelled` emit.
  - `clear_history` also cancels any in-flight turn.
  - Finalizer `await turns.cancel()` on disconnect prevents orphaned
    Ollama streams.

**Frontend**
- `frontend/src/audio/clientVad.js` — `EnergyVad`: RMS-energy VAD with
  a hold window. Reserved for continuous-mode barge-in — not wired into
  the UI yet (push-to-talk is fine without it).
- `frontend/src/services/voiceWsClient.js` — adds `bargeIn()`.
- `frontend/src/components/VoiceAssistant.jsx`:
  - Clicking the mic while `status === "speaking"` stops the player
    locally and sends `barge_in` to the server.
  - Listens for `cancelled` events; stops player, returns to `idle`.

## The cancellation contract

When barge-in fires, four things must happen fast, in order:

1. **Client stops audio** (`player.stop()`). Zero network delay — audio
   halts within one animation frame.
2. **Client sends `barge_in`** over WS. One round-trip.
3. **Server cancels the current task.** `TurnManager.cancel()` issues
   `Task.cancel()` which unwinds the running `_run_turn`. The async
   `async_iter_sync` loop raises `CancelledError` and exits.
4. **Server emits `cancelled`.** Client can show a visual acknowledgement.

Measured locally, steps 1+2 total ~50 ms (one WS frame); server task
cancel is essentially instant since we only cancel *between* awaits.

## Caveats that still leak

- **The Ollama HTTP stream keeps running.** When we cancel the async
  iteration, the producer thread inside `async_iter_sync` is still
  pulling tokens from the generator. The generator holds an open HTTP
  connection to Ollama that won't close until the body ends. In practice
  that's at most 1–2 seconds of wasted tokens. A proper fix calls
  `gen.close()` from the consumer side, which raises `GeneratorExit` in
  the producer; that's a separate follow-up.
- **TTS synth in progress.** A sentence currently being synthesized
  (inside `asyncio.to_thread(tts_service.synthesize, ...)`) will finish
  its call before yielding to the cancellation. Kokoro is fast so this
  is ≤ 1 s of extra compute; not audible because the client already stopped.
- **Continuous-mode barge-in is server-triggered only.** The client VAD
  (`EnergyVad`) is written but not wired. Wiring it saves ~1 WS RTT but
  requires running VAD during playback, which needs care with the speaker
  bleed-through case. Deferred — push-to-talk click gives us the primitive.

## Smoke test (API)

```bash
cd backend && python run.py
```

Open two terminals. Terminal 1: run a long-reply turn via a WS client.
Terminal 2: ~1 s in, send `{"type": "barge_in"}` on the same WS. You
should see a `cancelled` event and the server log `turn cancelled`.

## Known behavior to expect in the UI

- Click mic while assistant is speaking → silence, status returns to
  `idle`, no new message bubble.
- Click mic immediately after stopping assistant → starts a new
  recording (no double-click needed).
- Clear chat during playback → same effect plus history wiped.

## Rollback

Revert the B.5 commit. Backend falls back to B.4 behavior (turns can
overlap on a single connection). No schema changes.
