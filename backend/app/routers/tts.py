from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel
from app.services import tts_service

router = APIRouter(prefix="/api/tts", tags=["Text-to-Speech"])


class TTSRequest(BaseModel):
    text: str
    voice: str | None = None
    speed: float | None = None


@router.post("/synthesize")
async def synthesize_speech(request: TTSRequest):
    """Convert text to speech audio (returns WAV)."""
    try:
        audio_bytes = tts_service.synthesize(request.text, request.voice, request.speed)
        return Response(content=audio_bytes, media_type="audio/wav")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
