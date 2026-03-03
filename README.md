# AI Voice Assistant

A full-stack, real-time voice assistant built entirely with **free and open-source tools** — no credit card, no API costs, no trial expiry.

Speak naturally, get intelligent responses spoken back to you. Powered by Faster-Whisper (STT) + Groq/Llama 3.3 70B (LLM) + Kokoro (TTS).

```
 You speak         AI listens         AI thinks          AI speaks
 ┌────────┐       ┌───────────┐      ┌───────────┐      ┌──────────┐
 │  🎙️    │  ──▶  │  Faster   │ ──▶  │   Groq    │ ──▶  │  Kokoro  │
 │  User   │       │  Whisper  │      │ Llama 3.3 │      │   TTS    │
 │  Audio  │       │   (STT)   │      │   (LLM)   │      │  (Voice) │
 └────────┘       └───────────┘      └───────────┘      └──────────┘
```

---

## Table of Contents

- [Features](#features)
- [System Architecture](#system-architecture)
- [Tech Stack](#tech-stack)
- [Prerequisites](#prerequisites)
- [Quick Start](#quick-start)
- [Project Structure](#project-structure)
- [Backend Deep Dive](#backend-deep-dive)
- [Frontend Deep Dive](#frontend-deep-dive)
- [API Reference](#api-reference)
- [WebSocket Protocol](#websocket-protocol)
- [Configuration](#configuration)
- [Docker Deployment](#docker-deployment)
- [Free Cloud Deployment](#free-cloud-deployment)
- [CI/CD Pipeline](#cicd-pipeline)
- [Troubleshooting](#troubleshooting)
- [Contributing](#contributing)
- [License](#license)

---

## Features

- **Real-time voice conversation** — talk naturally, hear AI responses spoken aloud
- **Speech-to-Text** — Faster-Whisper with 99+ language support, 7.75% WER
- **LLM-powered responses** — Groq API running Llama 3.3 70B at ~80ms time-to-first-token
- **Natural text-to-speech** — Kokoro TTS, 82M params, <0.3s latency
- **WebSocket streaming** — real-time bidirectional communication
- **Conversation memory** — maintains context across turns (last 20 messages)
- **Dark-themed UI** — clean, modern React interface with status animations
- **Fully containerized** — Docker + Docker Compose for one-command deployment
- **CI/CD ready** — GitHub Actions for linting and build verification
- **100% free** — every component works without a credit card

---

## System Architecture

### High-Level Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        FRONTEND (React + Vite)                  │
│                                                                 │
│  ┌──────────────┐  ┌──────────────────┐  ┌───────────────────┐  │
│  │ Audio        │  │  VoiceAssistant  │  │   API Service     │  │
│  │ Recorder     │──│  Component       │──│   (REST + WS)     │  │
│  │ (WebM/Opus)  │  │  (Chat UI)       │  │                   │  │
│  └──────────────┘  └──────────────────┘  └────────┬──────────┘  │
│                                                    │             │
└────────────────────────────────────────────────────┼─────────────┘
                                                     │
                                          HTTP / WebSocket
                                                     │
┌────────────────────────────────────────────────────┼─────────────┐
│                     BACKEND (FastAPI + Uvicorn)     │             │
│                                                     ▼             │
│  ┌─────────────────────────────────────────────────────────────┐  │
│  │                    API Router Layer                          │  │
│  │                                                             │  │
│  │  POST /api/pipeline ──── Full voice pipeline (one-shot)     │  │
│  │  WS   /ws/voice    ──── Real-time streaming pipeline        │  │
│  │  POST /api/stt/transcribe ── Speech-to-Text only            │  │
│  │  POST /api/chat/   ──── LLM chat only                       │  │
│  │  POST /api/tts/synthesize ── Text-to-Speech only            │  │
│  └─────────┬───────────────────┬───────────────────┬───────────┘  │
│            │                   │                   │               │
│            ▼                   ▼                   ▼               │
│  ┌──────────────┐   ┌──────────────────┐   ┌──────────────┐      │
│  │  STT Service │   │   LLM Service    │   │  TTS Service │      │
│  │              │   │                  │   │              │      │
│  │ Faster-      │   │  Groq API        │   │  Kokoro      │      │
│  │ Whisper      │   │  (Llama 3.3 70B) │   │  Pipeline    │      │
│  │              │   │                  │   │              │      │
│  │ Local model  │   │  Cloud API       │   │  Local model │      │
│  │ (CPU/GPU)    │   │  (free tier)     │   │  (CPU/GPU)   │      │
│  └──────────────┘   └──────────────────┘   └──────────────┘      │
│                                                                   │
└───────────────────────────────────────────────────────────────────┘
```

### Data Flow — Full Pipeline

```
Step 1: CAPTURE
  Browser MediaRecorder API captures user speech
  ↓ Audio encoded as WebM/Opus (16kHz, mono, noise suppression)

Step 2: TRANSCRIBE (Faster-Whisper)
  Audio bytes → WhisperModel.transcribe()
  ↓ Returns: { text, language, confidence }

Step 3: THINK (Groq / Llama 3.3 70B)
  System prompt + conversation history + user transcript → Groq API
  ↓ Returns: AI response text (max 256 tokens, temperature 0.7)

Step 4: SYNTHESIZE (Kokoro TTS)
  AI response text → KPipeline() → numpy audio array
  ↓ Returns: WAV audio bytes (24kHz sample rate)

Step 5: RESPOND
  Backend sends { transcript, response, audio (base64) } to frontend
  ↓ Frontend displays text + plays audio through browser
```

### WebSocket Flow (Real-Time Mode)

```
CLIENT                              SERVER
  │                                    │
  │──── WS Connect /ws/voice ────────▶│
  │                                    │ Initialize conversation_history = []
  │                                    │
  │── {"type":"audio","data":"b64"} ──▶│
  │                                    │── STT transcribe
  │◀── {"type":"transcript","text":""} │
  │                                    │── LLM chat (with history)
  │◀── {"type":"response","text":""}  ─│
  │                                    │── TTS synthesize
  │◀── {"type":"audio","data":"b64"}  ─│
  │                                    │
  │  (repeat for each utterance)       │
  │                                    │
  │── {"type":"clear_history"} ───────▶│
  │◀── {"type":"history_cleared"} ────│
  │                                    │
  │──── WS Disconnect ───────────────▶│
```

---

## Tech Stack

| Layer | Technology | Role | Cost |
|-------|-----------|------|------|
| **Speech-to-Text** | [Faster-Whisper](https://github.com/SYSTRAN/faster-whisper) | Transcribe user speech to text | Free (MIT) |
| **LLM** | [Groq API](https://console.groq.com) + Llama 3.3 70B | Generate intelligent responses | Free tier (14,400 req/day) |
| **Text-to-Speech** | [Kokoro TTS](https://huggingface.co/hexgrad/Kokoro-82M) | Convert AI text to natural speech | Free (Apache 2.0) |
| **Backend** | [FastAPI](https://fastapi.tiangolo.com) + Uvicorn | REST API + WebSocket server | Free (MIT) |
| **Frontend** | [React](https://react.dev) + [Vite](https://vitejs.dev) | Voice UI with chat interface | Free (MIT) |
| **Containerization** | Docker + Docker Compose | Package and run the full stack | Free |
| **CI/CD** | GitHub Actions | Automated linting and builds | Free (public repos) |
| **Backend Hosting** | [HuggingFace Spaces](https://huggingface.co/spaces) | Free CPU/GPU deployment | Free (no card) |
| **Frontend Hosting** | [Vercel](https://vercel.com) | Free React app hosting + CDN | Free (no card) |

**Total cost: $0**

---

## Prerequisites

Before you start, make sure you have:

- **Python 3.11+** — [Download](https://www.python.org/downloads/)
- **Node.js 20+** — [Download](https://nodejs.org/)
- **Git** — [Download](https://git-scm.com/downloads)
- **FFmpeg** — Required by Faster-Whisper
  - Windows: `winget install ffmpeg` or download from [ffmpeg.org](https://ffmpeg.org/download.html)
  - macOS: `brew install ffmpeg`
  - Linux: `sudo apt install ffmpeg`
- **Docker** (optional, for containerized deployment) — [Download](https://www.docker.com/products/docker-desktop/)

---

## Quick Start

### 1. Clone the Repository

```bash
git clone https://github.com/YOUR_USERNAME/ai-voice-assistant.git
cd ai-voice-assistant
```

### 2. Get Your Free Groq API Key

1. Go to [console.groq.com](https://console.groq.com)
2. Sign up (no credit card required)
3. Go to **API Keys** and create a new key
4. Copy the key — you'll need it in the next step

### 3. Set Up the Backend

```bash
# Navigate to backend
cd backend

# Create environment file
cp .env.example .env

# Open .env and paste your Groq API key
# Replace "your_groq_api_key_here" with your actual key

# Create Python virtual environment
python -m venv venv

# Activate it
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Start the backend server
python run.py
```

The backend will start at **http://localhost:8000**

Visit **http://localhost:8000/docs** to see the interactive API documentation (Swagger UI).

### 4. Set Up the Frontend (New Terminal)

```bash
# Navigate to frontend
cd frontend

# Install dependencies
npm install

# Start the dev server
npm run dev
```

The frontend will start at **http://localhost:5173**

### 5. Start Talking

1. Open **http://localhost:5173** in your browser
2. Click the microphone button
3. Speak your question
4. Click the button again to stop recording
5. Wait for the AI to respond — you'll see the text AND hear the audio

---

## Project Structure

```
ai-voice-assistant/
│
├── backend/                          # Python FastAPI backend
│   ├── app/
│   │   ├── __init__.py
│   │   ├── config.py                 # Environment variable configuration
│   │   ├── main.py                   # FastAPI app entry point, CORS, routers
│   │   ├── services/
│   │   │   ├── __init__.py
│   │   │   ├── stt_service.py        # Faster-Whisper speech-to-text
│   │   │   ├── llm_service.py        # Groq API LLM integration
│   │   │   └── tts_service.py        # Kokoro text-to-speech
│   │   └── routers/
│   │       ├── __init__.py
│   │       ├── stt.py                # POST /api/stt/transcribe
│   │       ├── chat.py               # POST /api/chat/
│   │       ├── tts.py                # POST /api/tts/synthesize
│   │       └── pipeline.py           # POST /api/pipeline + WS /ws/voice
│   ├── requirements.txt              # Python dependencies
│   ├── Dockerfile                    # Backend container image
│   ├── run.py                        # Dev server quick-start script
│   ├── .env.example                  # Environment variable template
│   └── .env                          # Your actual config (git-ignored)
│
├── frontend/                         # React + Vite frontend
│   ├── src/
│   │   ├── main.jsx                  # React entry point
│   │   ├── App.jsx                   # Root component
│   │   ├── App.css                   # Full dark-theme stylesheet
│   │   ├── index.css                 # Global base styles
│   │   ├── components/
│   │   │   └── VoiceAssistant.jsx    # Main voice UI component
│   │   ├── hooks/
│   │   │   └── useAudioRecorder.js   # Browser microphone recording hook
│   │   └── services/
│   │       └── api.js                # Backend API + WebSocket + audio utils
│   ├── public/                       # Static assets
│   ├── package.json                  # Node.js dependencies
│   ├── vite.config.js                # Vite build configuration
│   ├── Dockerfile                    # Frontend container (multi-stage)
│   ├── nginx.conf                    # Production reverse proxy config
│   └── .env.example                  # Frontend env template
│
├── docker-compose.yml                # Full-stack orchestration
├── .github/
│   └── workflows/
│       └── ci.yml                    # GitHub Actions CI pipeline
├── .gitignore                        # Git ignore rules
└── README.md                         # This file
```

---

## Backend Deep Dive

### Services Layer

The backend follows a **service-oriented architecture**. Each AI capability is isolated into its own service module with lazy model loading (models are loaded on first request, not at startup).

#### STT Service (`backend/app/services/stt_service.py`)

```python
# How it works:
# 1. Loads Faster-Whisper model lazily (cached globally)
# 2. Accepts raw audio bytes (any format FFmpeg supports)
# 3. Returns transcript with language detection

transcribe(audio_bytes) → {
    "text": "Hello, how are you?",
    "language": "en",
    "language_probability": 0.98
}
```

- **Model**: Whisper `base` by default (configurable: tiny, base, small, medium, large)
- **Compute**: `int8` quantization on CPU, `float16` on GPU
- **Beam size**: 5 (balances accuracy and speed)
- **Languages**: 99+ supported automatically

#### LLM Service (`backend/app/services/llm_service.py`)

```python
# Two modes:
# 1. Standard: chat() → returns full response string
# 2. Streaming: chat_stream() → yields response chunks

chat(user_message, conversation_history) → "I'm doing great! How can I help?"
```

- **Provider**: Groq (free tier — 14,400 requests/day)
- **Model**: Llama 3.3 70B Versatile
- **Temperature**: 0.7 (natural, slightly creative)
- **Max tokens**: 256 (keeps responses concise for voice)
- **System prompt**: Configurable, defaults to friendly voice assistant

#### TTS Service (`backend/app/services/tts_service.py`)

```python
# How it works:
# 1. Loads Kokoro TTS pipeline lazily
# 2. Generates speech audio from text
# 3. Returns WAV bytes at 24kHz

synthesize(text, voice?, speed?) → bytes (WAV audio)
```

- **Model**: Kokoro 82M parameters
- **Latency**: <0.3s for typical responses
- **Sample rate**: 24,000 Hz
- **Voice**: `af_heart` (American female, configurable)
- **Speed**: 1.0x (configurable)

### Router Layer

Routers handle HTTP/WebSocket requests and delegate to services.

| Router | Endpoint | Method | Purpose |
|--------|----------|--------|---------|
| `stt.py` | `/api/stt/transcribe` | POST | Transcribe audio file |
| `chat.py` | `/api/chat/` | POST | Send text, get AI response |
| `tts.py` | `/api/tts/synthesize` | POST | Convert text to speech WAV |
| `pipeline.py` | `/api/pipeline` | POST | Full voice pipeline (audio in → audio out) |
| `pipeline.py` | `/ws/voice` | WebSocket | Real-time streaming voice conversation |

---

## Frontend Deep Dive

### VoiceAssistant Component

The main UI component manages the entire conversation lifecycle:

```
State Machine:
  idle ──(click mic)──▶ recording
  recording ──(click mic)──▶ processing
  processing ──(API response)──▶ speaking
  speaking ──(audio ends)──▶ idle
```

**Visual indicators**:
- **Idle**: Gray mic button — "Click to speak"
- **Recording**: Red pulsing button — "Listening... Click to stop"
- **Processing**: Amber button — "Thinking..."
- **Speaking**: Teal button — "Speaking..."

### useAudioRecorder Hook

Handles browser microphone access and audio capture:

- Uses `navigator.mediaDevices.getUserMedia()` for mic access
- Records as **WebM/Opus** codec (best compression for speech)
- Audio constraints: 16kHz, mono, echo cancellation, noise suppression
- Automatically releases microphone on stop
- Returns a `Blob` for upload to the backend

### API Service

Three ways to communicate with the backend:

1. **Pipeline (REST)** — single request, full round-trip
2. **Chat (REST)** — text-only conversation
3. **WebSocket** — persistent connection, real-time streaming

---

## API Reference

### `GET /`

Returns API metadata and available endpoints.

**Response:**
```json
{
  "name": "AI Voice Assistant API",
  "status": "running",
  "docs": "/docs",
  "endpoints": {
    "stt": "POST /api/stt/transcribe",
    "chat": "POST /api/chat/",
    "tts": "POST /api/tts/synthesize",
    "pipeline": "POST /api/pipeline",
    "websocket": "WS /ws/voice"
  }
}
```

### `GET /health`

Health check endpoint.

**Response:**
```json
{ "status": "healthy" }
```

### `POST /api/stt/transcribe`

Transcribe an audio file to text.

**Request:** `multipart/form-data`
| Field | Type | Description |
|-------|------|-------------|
| `audio` | File | Audio file (WAV, WebM, MP3, etc.) |

**Response:**
```json
{
  "text": "Hello, what is the weather today?",
  "language": "en",
  "language_probability": 0.985
}
```

### `POST /api/chat/`

Send a text message and get an AI response.

**Request:** `application/json`
```json
{
  "message": "What is the capital of France?",
  "conversation_history": [
    { "role": "user", "content": "Hi" },
    { "role": "assistant", "content": "Hello! How can I help?" }
  ]
}
```

**Response:**
```json
{
  "response": "The capital of France is Paris!"
}
```

### `POST /api/tts/synthesize`

Convert text to speech audio.

**Request:** `application/json`
```json
{
  "text": "Hello, how are you today?",
  "voice": "af_heart",
  "speed": 1.0
}
```

**Response:** Binary WAV audio file (`audio/wav`)

### `POST /api/pipeline`

Full voice pipeline — send audio, get transcript + AI response + spoken audio.

**Request:** `multipart/form-data`
| Field | Type | Description |
|-------|------|-------------|
| `audio` | File | Audio recording from the microphone |

**Response:**
```json
{
  "transcript": "What is machine learning?",
  "response": "Machine learning is a branch of AI where computers learn from data...",
  "audio": "UklGRi4AAABXQVZFZm10IBAAAA..."
}
```

The `audio` field contains base64-encoded WAV data. Decode and play in the browser.

---

## WebSocket Protocol

### Connect

```
ws://localhost:8000/ws/voice
```

### Client Messages

**Send audio for processing:**
```json
{
  "type": "audio",
  "data": "<base64-encoded audio bytes>"
}
```

**Clear conversation history:**
```json
{
  "type": "clear_history"
}
```

### Server Messages

**Transcript (user's speech):**
```json
{
  "type": "transcript",
  "text": "What's the weather like?"
}
```

**AI response text:**
```json
{
  "type": "response",
  "text": "I don't have access to real-time weather data..."
}
```

**AI response audio:**
```json
{
  "type": "audio",
  "data": "<base64-encoded WAV audio>"
}
```

**Error:**
```json
{
  "type": "error",
  "message": "Description of what went wrong"
}
```

**History cleared confirmation:**
```json
{
  "type": "history_cleared"
}
```

---

## Configuration

### Backend Environment Variables

Create `backend/.env` from the template:

```bash
cp backend/.env.example backend/.env
```

| Variable | Default | Description |
|----------|---------|-------------|
| `GROQ_API_KEY` | *(required)* | Free API key from [console.groq.com](https://console.groq.com) |
| `WHISPER_MODEL_SIZE` | `base` | Whisper model: `tiny`, `base`, `small`, `medium`, `large` |
| `WHISPER_DEVICE` | `cpu` | Compute device: `cpu` or `cuda` |
| `KOKORO_VOICE` | `af_heart` | TTS voice preset |
| `KOKORO_SPEED` | `1.0` | Speech speed multiplier |
| `LLM_MODEL` | `llama-3.3-70b-versatile` | Groq model name |
| `SYSTEM_PROMPT` | *(friendly assistant)* | Custom system prompt for the LLM |

**Whisper model sizes vs. accuracy/speed:**

| Model | Parameters | Disk Size | Relative Speed | WER |
|-------|-----------|-----------|----------------|-----|
| `tiny` | 39M | ~75MB | Fastest | ~12% |
| `base` | 74M | ~140MB | Fast | ~10% |
| `small` | 244M | ~460MB | Medium | ~8% |
| `medium` | 769M | ~1.5GB | Slow | ~7% |
| `large` | 1550M | ~3GB | Slowest | ~5% |

### Frontend Environment Variables

Create `frontend/.env` from the template:

```bash
cp frontend/.env.example frontend/.env
```

| Variable | Default | Description |
|----------|---------|-------------|
| `VITE_API_URL` | `http://localhost:8000` | Backend API URL |

---

## Docker Deployment

### Run with Docker Compose

```bash
# Make sure backend/.env exists with your Groq API key
cp backend/.env.example backend/.env
# Edit backend/.env and add your GROQ_API_KEY

# Build and start everything
docker compose up --build

# Or run in detached mode
docker compose up --build -d
```

This starts:
- **Backend** at http://localhost:8000
- **Frontend** at http://localhost:5173

The frontend nginx config automatically proxies `/api/*` and `/ws/*` to the backend, so everything works through port 5173.

### Stop

```bash
docker compose down
```

### Build Individual Containers

```bash
# Backend only
docker build -t voice-assistant-backend ./backend
docker run -p 8000:8000 --env-file ./backend/.env voice-assistant-backend

# Frontend only
docker build -t voice-assistant-frontend ./frontend
docker run -p 5173:80 voice-assistant-frontend
```

---

## Free Cloud Deployment

Deploy the entire project for free — no credit card required on any platform.

### Backend → Hugging Face Spaces

1. Create a free account at [huggingface.co](https://huggingface.co)
2. Create a new Space (select **Docker** as SDK)
3. Push your backend code:
   ```bash
   cd backend
   git init
   git remote add space https://huggingface.co/spaces/YOUR_USER/voice-assistant-backend
   git add .
   git commit -m "Initial deploy"
   git push space main
   ```
4. Add `GROQ_API_KEY` in Space Settings → Variables
5. Your backend will be live at `https://YOUR_USER-voice-assistant-backend.hf.space`

**ZeroGPU**: For GPU acceleration, add `@spaces.GPU` decorator to your endpoints and HuggingFace provides free H200 GPU slices.

### Frontend → Vercel

1. Push your project to GitHub
2. Go to [vercel.com](https://vercel.com) and sign in with GitHub
3. Click **Import Project** → select your repo
4. Set:
   - **Root Directory**: `frontend`
   - **Build Command**: `npm run build`
   - **Output Directory**: `dist`
5. Add environment variable:
   - `VITE_API_URL` = `https://YOUR_USER-voice-assistant-backend.hf.space`
6. Click **Deploy**

Your frontend will be live at `https://your-project.vercel.app`

### Alternative Free Hosting Options

| Platform | Best For | Free Tier |
|----------|----------|-----------|
| [Render](https://render.com) | Backend | Free web services, auto-deploy from Git |
| [Railway](https://railway.com) | Backend | $5 free credit on signup, no card |
| [Netlify](https://netlify.com) | Frontend | Free static hosting + CDN |

---

## CI/CD Pipeline

The project includes a GitHub Actions workflow (`.github/workflows/ci.yml`) that runs on every push and PR to `main`:

### Jobs

| Job | What it does |
|-----|-------------|
| `backend-lint` | Installs Python 3.11, runs `ruff check` on backend code |
| `frontend-build` | Installs Node.js 20, runs `npm ci` and `npm run build` |

### Trigger

```yaml
on:
  push:
    branches: [main]
  pull_request:
    branches: [main]
```

Both jobs run in parallel on `ubuntu-latest` for fast feedback.

---

## Troubleshooting

### "Microphone access denied"

Your browser needs permission to use the microphone.
- Click the lock icon in the address bar → allow microphone
- Make sure you're using HTTPS or `localhost` (mic requires secure context)

### "GROQ_API_KEY is not set"

1. Get a free key at [console.groq.com](https://console.groq.com)
2. Create `backend/.env` and add: `GROQ_API_KEY=your_key_here`
3. Restart the backend server

### "FFmpeg not found" or Whisper model fails to load

Faster-Whisper requires FFmpeg for audio decoding:
```bash
# Windows
winget install ffmpeg

# macOS
brew install ffmpeg

# Ubuntu/Debian
sudo apt install ffmpeg
```

### Backend starts but frontend can't connect

Make sure CORS is working:
- Backend should be at `http://localhost:8000`
- Frontend at `http://localhost:5173`
- Check `VITE_API_URL` in `frontend/.env`

### "No module named 'kokoro'"

Kokoro TTS may need additional dependencies:
```bash
pip install kokoro soundfile numpy
```

### Slow transcription

- Use `WHISPER_MODEL_SIZE=tiny` for fastest results
- If you have a GPU: set `WHISPER_DEVICE=cuda`
- Use `WHISPER_MODEL_SIZE=base` (default) for best balance

---

## Contributing

1. Fork the repository
2. Create your feature branch: `git checkout -b feature/my-feature`
3. Commit your changes: `git commit -m "Add my feature"`
4. Push to the branch: `git push origin feature/my-feature`
5. Open a Pull Request

### Development Tips

- Backend auto-reloads on file changes (via `uvicorn --reload`)
- Frontend auto-reloads via Vite HMR
- Visit `http://localhost:8000/docs` for interactive API testing
- Use the individual endpoints (`/api/stt`, `/api/chat`, `/api/tts`) for debugging each stage

---

## License

This project is open source. All tools used are free and open-source:

| Component | License |
|-----------|---------|
| Faster-Whisper | MIT |
| Kokoro TTS | Apache 2.0 |
| FastAPI | MIT |
| React | MIT |
| Vite | MIT |
| Groq API | Free tier |

---

**Built with free and open-source AI. No credit card. No API costs. Just code.**
