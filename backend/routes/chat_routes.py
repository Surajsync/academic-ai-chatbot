from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from datetime import datetime
from backend.utils.helpers import get_db, get_current_user
from backend.services.chatbot_service import get_response
from backend.database.models import AdminMessage, User

router = APIRouter(prefix="/api", tags=["chat"])


class ChatRequest(BaseModel):
    message: str


class AdminMessageResponse(BaseModel):
    id: int
    sender_id: int
    content: str
    created_at: datetime
    
    class Config:
        from_attributes = True


@router.post("/chat")
def chat(data: ChatRequest):
    result = get_response(data.message)
    
    return {
        "user_message": data.message,
        "bot_reply": result.get("answer"),
        "type": result.get("type")
    }


# ================= USER MESSAGING =================
# user-facing admin messaging endpoints removed

