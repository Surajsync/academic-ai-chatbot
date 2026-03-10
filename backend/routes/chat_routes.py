from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel

from utils.helpers import get_db
from services.chatbot_service import generate_reply

router = APIRouter()


class ChatRequest(BaseModel):
    message: str


@router.post("/chat")
def chat(data: ChatRequest, db: Session = Depends(get_db)):

    reply = generate_reply(db, data.message)

    return {
        "user_message": data.message,
        "bot_reply": reply
    }