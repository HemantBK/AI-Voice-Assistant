import base64
import logging
import json
from fastapi import APIRouter, UploadFile, File, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from app.services import stt_service, llm_service, tts_service

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Pipeline"])


@router.post("/api/pipeline")
async def voice_pipeline(audio: UploadFile = File(...)):
    """
    Full voice pipeline: Audio -> Text -> AI Response -> Speech Audio.
    Returns transcript, AI response text, and base64-encoded audio.
    """
    try:
        # Step 1: Speech-to-Text
        audio_bytes = await audio.read()
        stt_result = stt_service.transcribe(audio_bytes)
        transcript = stt_result["text"]

        if not transcript:
            return JSONResponse(content={
                "transcript": "",
                "response": "I didn't catch that. Could you try again?",
                "audio": None,
            })

        # Step 2: LLM Response
        ai_response = llm_service.chat(transcript)

        # Step 3: Text-to-Speech
        tts_audio = tts_service.synthesize(ai_response)
        audio_b64 = base64.b64encode(tts_audio).decode("utf-8")

        return JSONResponse(content={
            "transcript": transcript,
            "response": ai_response,
            "audio": audio_b64,
        })

    except Exception as e:
        logger.error(f"Pipeline error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.websocket("/ws/voice")
async def voice_websocket(websocket: WebSocket):
    """
    WebSocket for real-time voice conversation.

    Client sends: {"type": "audio", "data": "<base64-audio>"}
    Server sends:
      - {"type": "transcript", "text": "..."}
      - {"type": "response", "text": "..."}
      - {"type": "audio", "data": "<base64-audio>"}
      - {"type": "error", "message": "..."}
    """
    await websocket.accept()
    conversation_history = []

    try:
        while True:
            raw = await websocket.receive_text()
            message = json.loads(raw)

            if message.get("type") == "audio":
                audio_bytes = base64.b64decode(message["data"])

                # Step 1: STT
                stt_result = stt_service.transcribe(audio_bytes)
                transcript = stt_result["text"]

                await websocket.send_json({
                    "type": "transcript",
                    "text": transcript,
                })

                if not transcript:
                    continue

                # Step 2: LLM
                conversation_history.append({"role": "user", "content": transcript})
                ai_response = llm_service.chat(transcript, conversation_history)
                conversation_history.append({"role": "assistant", "content": ai_response})

                # Keep history manageable (last 20 messages)
                if len(conversation_history) > 20:
                    conversation_history = conversation_history[-20:]

                await websocket.send_json({
                    "type": "response",
                    "text": ai_response,
                })

                # Step 3: TTS
                tts_audio = tts_service.synthesize(ai_response)
                audio_b64 = base64.b64encode(tts_audio).decode("utf-8")

                await websocket.send_json({
                    "type": "audio",
                    "data": audio_b64,
                })

            elif message.get("type") == "clear_history":
                conversation_history = []
                await websocket.send_json({"type": "history_cleared"})

    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        try:
            await websocket.send_json({"type": "error", "message": str(e)})
        except Exception:
            pass
