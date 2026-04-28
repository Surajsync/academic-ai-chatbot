from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from datetime import datetime
from backend.utils.helpers import get_db, get_current_user
from backend.services.chatbot_service import get_response

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


class ContactAdminRequest(BaseModel):
    subject: str
    message: str


@router.post("/chat")
def chat(data: ChatRequest):
    result = get_response(data.message)
    
    return {
        "user_message": data.message,
        "bot_reply": result.get("answer"),
        "type": result.get("type")
    }


# ================= USER MESSAGING =================
@router.get("/messages/admin")
def get_admin_messages(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """User gets all messages from admin"""
    
    messages = db.query(AdminMessage).filter(
        AdminMessage.recipient_id == current_user.id
    ).order_by(AdminMessage.created_at.desc()).all()
    
    return [AdminMessageResponse.from_orm(msg) for msg in messages]


@router.post("/messages/contact-admin")
def contact_admin(
    data: ContactAdminRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """User sends a contact message to admin"""
    
    admin = db.query(User).filter(User.role == "admin").first()
    
    if not admin:
        raise HTTPException(status_code=500, detail="No admin available")
    
    message = AdminMessage(
        sender_id=current_user.id,
        recipient_id=admin.id,
        content=f"Subject: {data.subject}\n\n{data.message}",
        is_read=False
    )
    
    db.add(message)
    db.commit()
    db.refresh(message)
    
    return {
        "success": True,
        "message": "Your message has been sent to the admin",
        "message_id": message.id
    }

