from fastapi import APIRouter, UploadFile, File, HTTPException
from app.services import stt_service

router = APIRouter(prefix="/api/stt", tags=["Speech-to-Text"])


@router.post("/transcribe")
async def transcribe_audio(audio: UploadFile = File(...)):
    """Transcribe an audio file to text."""
    try:
        audio_bytes = await audio.read()
        result = stt_service.transcribe(audio_bytes)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
