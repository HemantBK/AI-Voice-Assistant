# Phase E — Edge (Raspberry Pi 5) (ship notes)

Goal: run the whole stack on a Pi 5 8 GB with no external services.
Self-contained, LAN-only, for people who want a literal private-box
voice assistant.

## Status: SCAFFOLD, not validated

Honest statement: Phase E cannot be "done" from a dev machine alone. It
requires:

- A Raspberry Pi 5 (ideally 8 GB) with 64-bit OS.
- Flashing, benchmarking, picking the right model sizes.
- Tuning quantization + thread counts on that specific chip.
- A USB mic or HAT (browser approach still works if the Pi just hosts).

What ships in this phase is the groundwork so you can get from "I just
plugged in my Pi" to "the app boots" without fighting the Docker build.

## What shipped

- `backend/Dockerfile.arm64` — ARM64 image recipe. Uses PyTorch CPU
  wheels from pytorch.org's index (the default PyPI wheels sometimes lag
  for aarch64). Clean multi-line comments document exactly why each
  dep is there.

## What you do on the Pi

1. Flash 64-bit Raspberry Pi OS (Bookworm or later).
2. `sudo apt-get install docker.io docker-compose-plugin`.
3. `git clone` this repo onto the Pi.
4. **Pick smaller models.** Set these in `backend/.env`:
   ```
   LLM_PROVIDER=ollama
   OLLAMA_MODEL=qwen2.5:3b            # or llama3.2:1b for very tight RAM
   WHISPER_MODEL_SIZE=tiny            # or base if your input is clean
   WHISPER_DEVICE=cpu
   TTS_PROVIDER=piper                 # lighter than Kokoro on ARM
   PIPER_VOICE=en_US-amy-medium
   ```
5. `docker compose up` — on ARM this will use `backend/Dockerfile` by
   default; for an explicit ARM path run `docker compose build backend
   --build-arg DOCKERFILE=Dockerfile.arm64` (add the argument to the
   compose service once you've decided on the final layout).
6. First boot pulls the Ollama model (takes a while on a Pi's SD card).

## Expected performance (rough, not measured on this repo)

| Model / Stage           | Pi 5 8GB (CPU, int8) | Desktop CPU baseline |
|-------------------------|---------------------|----------------------|
| STT (Whisper tiny, 3 s) | 300–600 ms          | 100–200 ms           |
| LLM (qwen2.5:3b, 1st)   | 800–1500 ms         | 300–700 ms           |
| LLM (qwen2.5:3b, tok/s) | 3–6                 | 10–25                |
| TTS (Piper)             | 300–600 ms / sentence | 100–250 ms         |

These are approximations from public reports. Your mileage will vary
with ambient temperature (the Pi thermal-throttles), whether you have a
fan, and what else is running.

## Known open work

- **ARM CI build** — add a `linux/arm64` matrix to the GitHub Actions
  workflow (Phase F). Currently builds are x86 only.
- **Model pull size** — qwen2.5:3b is ~2 GB. SD-card installs should
  point Ollama at a USB SSD via `OLLAMA_MODELS=/mnt/ssd/ollama` for
  decent read speed.
- **Audio I/O from Pi directly** — if you don't have a browser, you
  want a native client using portaudio + same WS protocol. Not shipped.
- **Wake word** — relevant on Pi; not implemented.

## Rollback

Ignore the ARM Dockerfile. The x86 path is unchanged.
