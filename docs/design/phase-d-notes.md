# Phase D' — Voice cloning via OpenVoice v2 (ship notes)

Goal: the assistant can speak in a specific person's voice after a short
enrollment recording. Uses **OpenVoice v2** (MIT-licensed) instead of
Coqui XTTS-v2 (CPML, non-commercial).

## Status: SCAFFOLD, not validated

The provider code is written against the public OpenVoice v2 API but I
have **not run it in this repo**. Shipping it as a scaffold because:

1. OpenVoice v2 has a heavy install (torch, librosa, a Whisper ckpt,
   OpenVoice's own checkpoints — several GB).
2. It needs a user-recorded enrollment audio (voice clip 6–10 s) which
   only you can provide.
3. The legal surface (consent, watermarking, jurisdiction) matters more
   than the code quality.

Treat this phase as infrastructure. Before calling it done you must:

- Install the deps and validate one synthesis round.
- Enroll a consenting speaker.
- Decide on a watermark strategy (see below).
- Enable the consent gate in the UI.

## What shipped

**Backend**
- `backend/app/services/tts/openvoice_provider.py` — `OpenVoiceProvider`
  uses OpenVoice v2's `BaseSpeakerTTS` + `ToneColorConverter` to produce
  base speech and convert it to the enrolled voice's timbre.
- `backend/app/services/tts/factory.py` — `TTS_PROVIDER=openvoice`
  option.
- `backend/app/config.py` + `.env.example` — `OPENVOICE_CHECKPOINT_DIR`,
  `OPENVOICE_REFERENCE_WAV`, `OPENVOICE_BASE_SPEAKER`.

**Frontend**
- `frontend/src/components/ConsentGate.jsx` — blocking modal with four
  clauses; consent stored in localStorage. Exports `hasConsent()` and
  `clearConsent()` helpers.
- Voice-enrollment UI **not shipped**. The simplest form is a 10-second
  recording button that posts the WAV to a new endpoint which writes it
  to `OPENVOICE_REFERENCE_WAV`. Add this once the backend path works.

## Setup (manual, one-time)

```bash
pip install git+https://github.com/myshell-ai/OpenVoice
pip install torch torchaudio librosa

# Download OpenVoice v2 checkpoints (see the repo for current URLs)
mkdir -p ~/openvoice-ckpts
# ... (download + extract into ~/openvoice-ckpts/base_speakers/EN and ~/openvoice-ckpts/converter)

export OPENVOICE_CHECKPOINT_DIR=~/openvoice-ckpts
export OPENVOICE_REFERENCE_WAV=~/my-enrollment-10s.wav
export TTS_PROVIDER=openvoice
```

Enrollment recording: 6–10 seconds, mono, quiet environment, speaker
reading a normal sentence. OpenVoice tolerates lower-quality input than
XTTS but quality of the clone correlates with quality of the reference.

## Watermarking

OpenVoice v2 doesn't watermark by default. Options:

1. **[AudioSeal](https://github.com/facebookresearch/audioseal)** (Meta,
   MIT) — imperceptible watermark survives most common transforms.
   Recommended. Add as a post-process step after `ToneColorConverter`.
2. **Perceptual metadata** — inject a tag into the WAV metadata. Trivial
   but trivially strippable. Useful only as a politeness signal.
3. **None + disclose in output** — frontend always shows "this voice is
   synthesized" in UI. Least technical effort, most user trust.

Pick one before shipping any cloned audio. My preference: #1 + #3.

## Consent flow (to wire later)

```
User clicks "Clone a voice"
  -> if !hasConsent() -> render <ConsentGate /> (blocks)
  -> else -> render <VoiceEnrollment /> (records 10s, POSTs to /api/voice/enroll)
  -> backend saves wav, updates OPENVOICE_REFERENCE_WAV on disk OR per-user
     registry; reloads the provider.
```

`/api/voice/enroll` is not in this commit. It's a ~40-line FastAPI endpoint.

## Legal checklist before shipping in any product

- [ ] ToS explicitly prohibit non-consensual clones.
- [ ] Record proof-of-consent for each enrollment (audio of speaker
      saying "I, NAME, on DATE, give permission to clone my voice for
      USE").
- [ ] US states with deepfake statutes: CA (AB 602, AB 730), TX (SB 751),
      MN, WA, VA — confirm the product complies.
- [ ] EU AI Act — cloned voice output is an Article 50 deepfake
      disclosure trigger.
- [ ] India's IT Rules 2021 — synthetic media identification obligation.
- [ ] If user-generated content: takedown / complaint process.

## Rollback

`TTS_PROVIDER=kokoro`. Behavior unchanged. OpenVoice code path is
lazy-imported so removing `openvoice` from installs does not affect the
Kokoro or Piper paths.
