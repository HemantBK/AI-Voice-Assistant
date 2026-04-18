# Phase C — Multilingual + Indic (ship notes)

Goal: the assistant speaks more than English. Whisper already transcribes
99+ languages; the bottleneck is TTS. This phase adds a provider
abstraction so Kokoro and Piper can coexist, with Piper handling Hindi,
Tamil, Telugu, Bengali, Marathi, and many more.

## What shipped

**Backend — TTS provider abstraction**
- `backend/app/services/tts/base.py` — `TTSProvider` Protocol.
- `backend/app/services/tts/kokoro_provider.py` — wraps existing Kokoro;
  supports language switching between `en`, `en-gb`, `ja`, `zh` via
  Kokoro's built-in `lang_code`. Lazy per-language pipeline load.
- `backend/app/services/tts/piper_provider.py` — wraps Piper. Voice
  selection: explicit `voice`, else `DEFAULT_VOICES[language]`, else
  `PIPER_VOICE` env override. Raises a clear error pointing at
  `python -m piper.download_voices <voice>` when a voice file is missing.
- `backend/app/services/tts/factory.py` — env-driven singleton
  (`TTS_PROVIDER=kokoro|piper`).
- `backend/app/services/tts_service.py` — now a thin façade. Signature
  gains an optional `language: str | None` argument (default behavior
  unchanged).
- `backend/app/config.py` + `.env.example` — `TTS_PROVIDER`,
  `PIPER_VOICE`, `PIPER_DATA_DIR`.

**What is *not* shipped**
- Language auto-detection through the pipeline. Whisper already returns
  `info.language` in `stt_service`, but the router doesn't pass it into
  LLM / TTS yet. One-line wire-up, deferred so this slice stays a
  refactor-only commit.
- UI language selector. Out of scope here; pick it up when wiring the
  language pass-through end-to-end.
- Indic speech fixtures in `eval/datasets/stt/`. The eval harness is
  language-agnostic but our fixture set is English-only. Add real
  Hindi/Tamil/etc. recordings to exercise Phase C properly.

## Installing Piper (user action)

```bash
pip install piper-tts onnxruntime
mkdir -p ~/piper-voices
export PIPER_DATA_DIR=~/piper-voices
cd ~/piper-voices
python -m piper.download_voices hi_IN-pratham-medium    # Hindi
python -m piper.download_voices en_US-amy-medium        # English fallback
# etc. Run once per voice.
```

Then flip the provider:
```bash
TTS_PROVIDER=piper
PIPER_VOICE=hi_IN-pratham-medium
```

## Model/voice license caveats

- **Kokoro** — Apache 2.0. Use freely.
- **Piper core + most official voices** — MIT. Use freely.
- **Piper community voices** — varies; check each voice's README at
  https://github.com/rhasspy/piper/blob/master/VOICES.md before shipping
  in a product.
- **AI4Bharat Indic voices** — higher quality for Indian languages than
  most Piper voices, but licensing varies; many are research-only. Not
  integrated here; pick voice by voice if you need production rights.

## A/B recipe for TTS quality

For each language you care about:

1. Prepare 10 reference sentences (`eval/datasets/tts/prompts_<lang>.txt`).
2. Synthesize with each candidate voice.
3. Blind-rate audio (mean opinion score, 1–5) yourself or with a small
   panel. No LLM-as-judge — MOS is perceptual.
4. Measure RTF and first-chunk latency with `eval_tts.py`.

## Why no whisper-large for Indic

Small/base Whisper underperforms on Indian languages; `large-v3` is much
better but 3 GB and CPU-slow. If you need Hindi STT quality, the right
lever is `WHISPER_MODEL_SIZE=large-v3` with GPU. Out of scope here;
noted as a follow-up.

## Rollback

Set `TTS_PROVIDER=kokoro` and the behavior is identical to pre-Phase-C.
`tts_service.synthesize(text)` (without the new `language` kwarg) keeps
working.
