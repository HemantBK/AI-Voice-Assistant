# STT fixtures

Drop `.wav` (or `.mp3`, `.webm`) files in this directory and list them in `manifest.json`.

Format:
```json
{
  "samples": [
    {
      "id": "hello-en",
      "audio": "hello-en.wav",
      "reference": "Hello, how are you today?",
      "language": "en"
    }
  ]
}
```

Two ways to populate fixtures:

1. **Record yourself** — phone voice memo, export as WAV/mp3, transcribe manually.
2. **TTS round-trip** — run `python eval/runners/eval_tts.py --emit-stt-fixtures` (see that runner). Synthesizes known text and drops it here. Baseline WER on TTS-generated speech is optimistic but free and reproducible.

Do not commit large or sensitive audio files. `.wav`/`.mp3` in this directory are gitignored by default.
