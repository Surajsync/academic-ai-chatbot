from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel
from backend.utils.helpers import get_db
from backend.services.chatbot_service import get_response

router = APIRouter(prefix="/api", tags=["chat"])


class ChatRequest(BaseModel):
    message: str


@router.post("/chat")
def chat(data: ChatRequest):
    result = get_response(data.message)
    
    return {
        "user_message": data.message,
        "bot_reply": result.get("answer"),
        "type": result.get("type")
    }

