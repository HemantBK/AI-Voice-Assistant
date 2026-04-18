# Phase B.3 — Streaming LLM tokens → sentence splitter → TTS (ship notes)

Goal: the LLM and TTS now overlap in time. Tokens stream from the provider;
each completed sentence is synthesized and emitted while the LLM is still
generating the next one. User perceives the assistant "thinking out loud"
rather than pausing for full generation before speaking.

## What shipped

**Backend**
- `backend/app/streaming/async_stream.py` — `async_iter_sync(gen_factory)`.
  Bridges a blocking sync generator (Ollama / Groq streaming SDKs) onto the
  asyncio event loop via an `asyncio.Queue` and `call_soon_threadsafe`.
  Self-test: first token arrives in ~125 ms against a 50 ms/token fake
  generator (vs. ~250 ms that full buffering would give).
- `backend/app/routers/pipeline.py` — streaming branch rewritten:
  - Calls `llm_service.chat_stream()` (already available) and wraps it with
    `async_iter_sync`.
  - Each token is emitted as `{type: "llm_delta", delta: "<token>"}` to the
    client for live-typing UX.
  - Tokens also feed an `IncrementalSentenceSplitter` (built in B.2). When
    a sentence boundary appears, the sentence is synthesized and emitted as
    a `tts_chunk` while the LLM keeps generating.
  - After the stream ends, `splitter.flush()` emits the tail sentence.
  - A final `{type: "response", text: "<full text>"}` and `tts_end` close
    the turn. History is appended once with the full text.

**Frontend**
- `VoiceAssistant.jsx` — new `llm_delta` handler appends to the last
  assistant message if it's marked `streaming: true`, else pushes a new
  streaming-tagged bubble. `response` reconciles the final text and clears
  the `streaming` flag.

**Eval**
- `eval/runners/eval_streaming.py` — new metric **`first_llm_delta_ms`**
  (time from send to first LLM token). Useful to separate "LLM is slow"
  from "TTS is slow" when reading results.

## What "sub-second perceived latency" requires

Three things must all be true on the test box:

1. `first_llm_delta_ms` is small — a 3B model on CPU does ~5–30 tok/s;
   first-token is usually ≤ 500 ms on warm Ollama.
2. The first sentence is short enough that TTS synth finishes quickly.
3. Network + WS round-trip is negligible (true on localhost).

`first_audio_byte_ms` ≈ `first_llm_delta_ms` + first-sentence-length /
tok-per-sec + TTS time for the first sentence. B.3 doesn't change (1) or
(3); it shortens (2) by removing the "wait for the full response" barrier.

## A/B recipe

Bring up the server with `LLM_PROVIDER=ollama`, then:

```bash
# Baseline: B.2 (sentence-level TTS, LLM still one-shot)
# -> You don't actually have this now; B.3 replaces the streaming branch.
#    To compare, git checkout the B.2 commit, run eval, stash results,
#    come back to B.3, run eval again.
git log --oneline | head              # find B.2 and B.3 commits
git checkout <B.2-commit>
python -m eval.runners.eval_streaming \
  --url 'ws://127.0.0.1:8000/ws/voice?stream=1' \
  --fixture eval/datasets/stt/tts-roundtrip-00.wav \
  --runs 10 --save
git checkout main
python -m eval.runners.eval_streaming \
  --url 'ws://127.0.0.1:8000/ws/voice?stream=1' \
  --fixture eval/datasets/stt/tts-roundtrip-00.wav \
  --runs 10 --save

diff <(jq .stats.first_audio_byte_ms eval/results/streaming-*B2*.json) \
     <(jq .stats.first_audio_byte_ms eval/results/streaming-*B3*.json)
```

Expected win: `first_audio_byte_ms` drops by roughly
`(time_for_full_response - time_for_first_sentence)` because the first
sentence no longer waits for the rest of the response to generate. On a 3B
CPU Ollama path producing a 120-token reply across 3 sentences, that's
commonly a 1000–3000 ms improvement.

## Manual browser test checklist

Please verify before moving on:

- [ ] Ask "Tell me a 3-sentence story about a robot." The assistant text
      bubble fills in word-by-word (llm_delta streaming) while audio starts
      playing after the first sentence boundary. Bubble text finishes
      slightly ahead of the audio because LLM finishes before TTS does.
- [ ] Ask something short ("Hi."). Single sentence — no regression vs B.2.
- [ ] Ask for a long reply ("List 10 fun facts about space"). Audio starts
      after sentence 1; gaps between sentences should be small (depends on
      Kokoro RTF on your box).
- [ ] Silence in → empty transcript → no `llm_delta`, no tts_chunk, no
      crash; status returns to `idle`.
- [ ] Clear chat mid-stream — player stops, no zombie audio, next turn
      works cleanly.

## Known gaps we're accepting in this slice

- **No barge-in yet.** Clicking mic during playback still doesn't cancel
  the current LLM/TTS stream. Fixed in B.5.
- **Producer thread leaks on disconnect.** If the WS client disconnects
  mid-generation, the Ollama stream generator keeps running until it
  returns (short replies: fine; long replies: small waste). Fixed in B.5
  via `gen.close()`.
- **WS message rate.** We emit one `llm_delta` per token — on a fast
  provider that's 30–100 msgs/s. Fine on localhost; may want batching
  (100–200 ms windows) over WAN. Revisit if it matters.
- **Sentence splitter abbreviations.** "Dr. Smith" may split early. We
  accepted this in B.2 and haven't improved it.

## Rollback

Revert the B.3 commit. The streaming branch falls back to B.2 behavior
(one-shot LLM + sentence-level TTS). Non-streaming path is untouched.
