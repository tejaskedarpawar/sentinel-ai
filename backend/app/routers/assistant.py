"""
SOC Assistant Router for Sentinel AI.
Endpoint: POST /api/assistant/chat
"""
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.assistant.chat import chat_with_assistant

router = APIRouter(prefix="/api/assistant", tags=["assistant"])


class ChatRequest(BaseModel):
    message: str
    history: list[dict] | None = None
    mode: str | None = None  # optional "ollama" | "fallback"


class ToolUsage(BaseModel):
    name: str
    args: dict
    rows: int


class ChatResponse(BaseModel):
    answer: str
    tools_used: list[ToolUsage]
    mode: str  # "ollama" | "fallback"


@router.post("/chat", response_model=ChatResponse)
def post_chat(req: ChatRequest, db: Session = Depends(get_db)):
    """
    SOC Security Assistant Chat endpoint.
    Answers analyst questions strictly via whitelisted, typed read-only query functions.
    Supported modes: 'ollama' with native function calling, or deterministic 'fallback' intent router.
    """
    result = chat_with_assistant(db, message=req.message, history=req.history, force_mode=req.mode)
    return result

