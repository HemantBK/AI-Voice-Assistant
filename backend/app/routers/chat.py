from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.services import llm_service

router = APIRouter(prefix="/api/chat", tags=["Chat"])


class ChatRequest(BaseModel):
    message: str
    conversation_history: list[dict] | None = None


class ChatResponse(BaseModel):
    response: str


@router.post("/", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """Send a text message and get an AI response."""
    try:
        response = llm_service.chat(request.message, request.conversation_history)
        return ChatResponse(response=response)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
