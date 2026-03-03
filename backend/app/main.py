import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import stt, chat, tts, pipeline

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

app = FastAPI(
    title="AI Voice Assistant API",
    description="Free AI Voice Assistant - STT (Faster-Whisper) + LLM (Groq) + TTS (Kokoro)",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(stt.router)
app.include_router(chat.router)
app.include_router(tts.router)
app.include_router(pipeline.router)


@app.get("/")
async def root():
    return {
        "name": "AI Voice Assistant API",
        "status": "running",
        "docs": "/docs",
        "endpoints": {
            "stt": "POST /api/stt/transcribe",
            "chat": "POST /api/chat/",
            "tts": "POST /api/tts/synthesize",
            "pipeline": "POST /api/pipeline",
            "websocket": "WS /ws/voice",
        },
    }


@app.get("/health")
async def health():
    return {"status": "healthy"}
