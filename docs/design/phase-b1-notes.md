# Phase B.1 — Server-side VAD endpointing (ship notes)

Slice of the Phase B plan: add VAD-based silence trimming *before* Whisper
decodes, without changing the request/response protocol.

## What shipped

- `backend/app/config.py` — `WHISPER_VAD_FILTER` (default **true**) plus
  tunables: `min_silence_ms`, `min_speech_ms`, `speech_pad_ms`, `threshold`.
- `backend/app/services/stt_service.py` — passes `vad_filter` and
  `vad_parameters` to `WhisperModel.transcribe()`. Returns
  `audio_duration_s`, `speech_duration_s`, `vad_trimmed_ms`, `vad_enabled`
  in the STT result dict.
- `eval/runners/eval_stt.py` — records and summarizes `vad_trimmed_ms`.
- `backend/.env.example` — documents the new knobs.

Nothing in the router layer, WS protocol, or frontend changed.

## How to A/B

With the backend running, transcribe the same manifest twice:

```bash
# A: VAD on (default)
python -m eval.runners.eval_stt --save

# B: VAD off
WHISPER_VAD_FILTER=false python -m eval.runners.eval_stt --save
```

Then diff the two newest `eval/results/stt-*.json`. Two things to check:

1. **STT latency delta.** `latency_ms.mean` / `p50` / `p95` should drop on
   inputs with meaningful silence. No-op on clean TTS-roundtrip fixtures
   (they're already silence-free).
2. **Hallucination delta.** If `mean_wer` *also* drops with VAD on, that is
   silence hallucination being suppressed — a common Whisper failure on
   padded audio. This is a bigger deal than the latency win.

End-to-end latency (`eval_latency.py`) should show the same pattern on the
`stt` stage header.

## Honest caveats

- TTS-roundtrip fixtures have near-zero silence, so `vad_trimmed_ms` will
  read ~0 and this looks like a no-op. Record a real sample (e.g. 1s of
  silence + "hello" + 1s of silence) to see the effect.
- `vad_filter=True` adds ~30–80 ms of Silero inference on very short inputs
  where there's nothing to trim. On short clips VAD can be *net negative*.
  The default threshold is conservative for this reason; tune if you see
  regressions on your hardware.
- This slice does nothing for the LLM or TTS stages, which dominate total
  latency. Sentence-level TTS streaming (B.2) is where the user-perceived
  win actually comes from.

## Follow-ups unlocked

- B.4 (continuous mic capture) will want the same VAD logic applied to
  incoming WS frames, not a buffered file. When we build that module at
  `backend/app/streaming/vad.py` we will lift the parameter defaults from
  here so behavior stays consistent.
- `vad_trimmed_ms` is now a first-class metric; future regressions in VAD
  behavior will be visible in `eval/results/stt-*.json`.
