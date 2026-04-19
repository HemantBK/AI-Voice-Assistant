import asyncio
import base64
import json
import logging

from fastapi import APIRouter, File, HTTPException, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse

from app.core.timing import stage
from app.core.tracing import get_tracer
from app.services import llm_service, stt_service, tts_service
from app.streaming.async_stream import async_iter_sync
from app.streaming.sentence_splitter import IncrementalSentenceSplitter
from app.streaming.turn_manager import TurnManager
from app.streaming.wav import pcm16_to_wav

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Pipeline"])


@router.post("/api/pipeline")
async def voice_pipeline(audio: UploadFile = File(...)):
    """One-shot pipeline. Kept intact for the REST eval path and non-streaming
    clients; streaming behavior lives on /ws/voice?stream=1."""
    try:
        audio_bytes = await audio.read()
        with stage("stt"):
            stt_result = stt_service.transcribe(audio_bytes)
        transcript = stt_result["text"]

        if not transcript:
            return JSONResponse(content={
                "transcript": "",
                "response": "I didn't catch that. Could you try again?",
                "audio": None,
            })

        with stage("llm"):
            ai_response = llm_service.chat(transcript)

        with stage("tts"):
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


class _NullSpanCtx:
    def __enter__(self):
        return None
    def __exit__(self, *exc):
        return False


async def _run_turn(
    websocket: WebSocket,
    audio_bytes: bytes,
    streaming: bool,
    history: list[dict],
) -> None:
    """Run a single STT->LLM->TTS turn. Appends to `history` in place.

    The whole body lives under a `voice.turn` OTel span (when tracing is
    on) with attributes recorded as each stage completes. `stage()` emits
    per-phase child spans + the X-Stage-*-Ms response headers the eval
    harness consumes.
    """
    tracer = get_tracer()
    turn_cm = tracer.start_as_current_span("voice.turn") if tracer is not None else _NullSpanCtx()

    with turn_cm as turn_span:
        if turn_span is not None:
            turn_span.set_attribute("voice.streaming", streaming)
            turn_span.set_attribute("voice.audio_bytes", len(audio_bytes))

        with stage("stt") as stt_span:
            stt_result = stt_service.transcribe(audio_bytes)
        if stt_span is not None:
            stt_span.set_attribute("stt.language", stt_result.get("language", "") or "")
            stt_span.set_attribute("stt.audio_duration_s", float(stt_result.get("audio_duration_s") or 0.0))
            stt_span.set_attribute("stt.speech_duration_s", float(stt_result.get("speech_duration_s") or 0.0))
            stt_span.set_attribute("stt.vad_trimmed_ms", float(stt_result.get("vad_trimmed_ms") or 0.0))

        transcript = stt_result["text"]
        await websocket.send_json({"type": "transcript", "text": transcript})
        if turn_span is not None:
            turn_span.set_attribute("voice.transcript_chars", len(transcript))

        if not transcript:
            if turn_span is not None:
                turn_span.set_attribute("voice.empty_transcript", True)
            return

        history.append({"role": "user", "content": transcript})
        history_snapshot = list(history)

        if not streaming:
            with stage("llm") as llm_span:
                ai_response = llm_service.chat(transcript, history_snapshot)
            if llm_span is not None:
                llm_span.set_attribute("llm.streaming", False)
                llm_span.set_attribute("llm.response_chars", len(ai_response))
            history.append({"role": "assistant", "content": ai_response})
            if len(history) > 20:
                del history[:-20]
            await websocket.send_json({"type": "response", "text": ai_response})
            with stage("tts") as tts_span:
                tts_audio = tts_service.synthesize(ai_response)
            if tts_span is not None:
                tts_span.set_attribute("tts.audio_bytes", len(tts_audio))
                tts_span.set_attribute("tts.streaming", False)
            await websocket.send_json({
                "type": "audio",
                "data": base64.b64encode(tts_audio).decode("utf-8"),
            })
            if turn_span is not None:
                turn_span.set_attribute("voice.response_chars", len(ai_response))
            return

        splitter = IncrementalSentenceSplitter()
        accumulated: list[str] = []
        seq = 0
        pending_sentences: list[str] = []

        async def emit_sentence(text: str, is_final: bool) -> None:
            nonlocal seq
            with stage("tts") as tts_span:
                chunk = await asyncio.to_thread(tts_service.synthesize, text)
            if tts_span is not None:
                tts_span.set_attribute("tts.audio_bytes", len(chunk))
                tts_span.set_attribute("tts.sentence_chars", len(text))
                tts_span.set_attribute("tts.seq", seq)
            await websocket.send_json({
                "type": "tts_chunk",
                "seq": seq,
                "text": text,
                "audio": base64.b64encode(chunk).decode("utf-8"),
                "is_final": is_final,
            })
            seq += 1

        def token_gen():
            return llm_service.chat_stream(transcript, history_snapshot)

        with stage("llm_stream") as llm_span:
            if llm_span is not None:
                llm_span.set_attribute("llm.streaming", True)
            async for token in async_iter_sync(token_gen):
                accumulated.append(token)
                await websocket.send_json({"type": "llm_delta", "delta": token})
                for sentence in splitter.push(token):
                    pending_sentences.append(sentence)
                while pending_sentences:
                    await emit_sentence(pending_sentences.pop(0), is_final=False)
            if llm_span is not None:
                llm_span.set_attribute("llm.tokens", len(accumulated))

        tail = list(splitter.flush())
        pending_sentences.extend(tail)
        for i, sentence in enumerate(pending_sentences):
            is_final = i == len(pending_sentences) - 1
            await emit_sentence(sentence, is_final=is_final)

        if seq == 0:
            fallback = "".join(accumulated).strip() or "I'm not sure how to answer that."
            await emit_sentence(fallback, is_final=True)

        full_text = "".join(accumulated).strip()
        history.append({"role": "assistant", "content": full_text})
        if len(history) > 20:
            del history[:-20]

        await websocket.send_json({"type": "response", "text": full_text})
        await websocket.send_json({"type": "tts_end", "count": seq})
        if turn_span is not None:
            turn_span.set_attribute("voice.response_chars", len(full_text))
            turn_span.set_attribute("voice.tts_chunks", seq)


@router.websocket("/ws/voice")
async def voice_websocket(websocket: WebSocket):
    """WebSocket voice pipeline.

    Query params:
      stream=1       -> B.2/B.3 streaming TTS + LLM tokens (recommended)
      continuous=1   -> B.4 continuous mic with server-side VAD endpointing

    Message types (client -> server):
      {"type": "audio",       "data": "<base64 audio blob>"}      # one-shot
      {"type": "audio_frame", "pcm16_b64": "<base64 PCM16 20ms 16kHz>"}  # B.4 stream
      {"type": "end_of_turn"}                                     # B.4 manual endpoint
      {"type": "clear_history"}

    Server -> client events are documented in docs/design/phase-b*.md.
    """
    streaming = websocket.query_params.get("stream") in ("1", "true", "yes")
    continuous = websocket.query_params.get("continuous") in ("1", "true", "yes")
    await websocket.accept()
    history: list[dict] = []
    turns = TurnManager()

    # Lazy VAD — only constructed when continuous mode is used, so the
    # backend still boots without the silero-vad package installed.
    frame_vad = None
    if continuous:
        try:
            from app.streaming.vad import FrameVad
            frame_vad = FrameVad()
        except ImportError as e:
            await websocket.send_json({"type": "error", "message": str(e)})
            await websocket.close()
            return

    try:
        while True:
            raw = await websocket.receive_text()
            message = json.loads(raw)
            mtype = message.get("type")

            if mtype == "clear_history":
                await turns.cancel()
                history.clear()
                await websocket.send_json({"type": "history_cleared"})
                continue

            if mtype == "barge_in":
                await turns.cancel()
                await websocket.send_json({"type": "cancelled", "reason": "barge_in"})
                continue

            if mtype == "audio":
                audio_bytes = base64.b64decode(message["data"])
                await turns.start(_run_turn(websocket, audio_bytes, streaming, history))
                continue

            if mtype == "audio_frame" and frame_vad is not None:
                frame = base64.b64decode(message["pcm16_b64"])
                event = frame_vad.push(frame)
                if event == "speech_start":
                    if turns.is_busy():
                        # user started talking while assistant is replying -> barge-in
                        await turns.cancel()
                        await websocket.send_json({"type": "cancelled", "reason": "barge_in"})
                    await websocket.send_json({"type": "vad", "speaking": True})
                elif event == "speech_end":
                    await websocket.send_json({"type": "vad", "speaking": False})
                    pcm = frame_vad.drain_segment()
                    if pcm:
                        wav = pcm16_to_wav(pcm, sample_rate=16000)
                        await turns.start(_run_turn(websocket, wav, streaming, history))
                continue

            if mtype == "end_of_turn" and frame_vad is not None:
                pcm = frame_vad.drain_segment()
                if pcm:
                    wav = pcm16_to_wav(pcm, sample_rate=16000)
                    await turns.start(_run_turn(websocket, wav, streaming, history))
                continue

    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        try:
            await websocket.send_json({"type": "error", "message": str(e)})
        except Exception:
            pass
    finally:
        await turns.cancel()
