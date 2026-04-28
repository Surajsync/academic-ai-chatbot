from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from datetime import datetime

from backend.utils.helpers import get_db, get_current_user
from backend.database.models import FAQ, Conversation, FailedQuery, User, AdminMessage

router = APIRouter()


# ================= PYDANTIC MODELS FOR VALIDATION =================
class SendMessageRequest(BaseModel):
    recipient_id: int
    content: str


class MessageResponse(BaseModel):
    id: int
    sender_id: int
    recipient_id: int
    content: str
    is_read: bool
    created_at: datetime

    class Config:
        from_attributes = True


# ================= DASHBOARD =================
@router.get("/admin/dashboard")
def dashboard(db: Session = Depends(get_db)):

    total_faqs = db.query(FAQ).count()
    active_faqs = db.query(FAQ).filter(FAQ.is_active == True).count()
    total_conversations = db.query(Conversation).count()
    failed_queries = db.query(FailedQuery).count()

    return {
        "total_faqs": total_faqs,
        "active_faqs": active_faqs,
        "total_conversations": total_conversations,
        "failed_queries": failed_queries
    }


@router.get("/admin/faqs")
def get_faqs(db: Session = Depends(get_db)):
    return db.query(FAQ).all()


# ================= ADMIN MESSAGING =================
@router.post("/admin/messages/send")
def send_message(
    data: SendMessageRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Admin sends a message to a user"""
    
    # Verify sender is admin
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Only admins can send messages")
    
    # Verify recipient exists
    recipient = db.query(User).filter(User.id == data.recipient_id).first()
    if not recipient:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Create and save message
    message = AdminMessage(
        sender_id=current_user.id,
        recipient_id=data.recipient_id,
        content=data.content,
        is_read=False
    )
    
    db.add(message)
    db.commit()
    db.refresh(message)
    
    return MessageResponse.from_orm(message)


@router.get("/admin/messages/users")
def get_message_users(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get list of all users with message history for admin"""
    
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Only admins can view messages")
    
    # Get all unique users who have received messages from this admin
    users_with_messages = db.query(User).join(
        AdminMessage, (AdminMessage.recipient_id == User.id)
    ).filter(
        AdminMessage.sender_id == current_user.id
    ).distinct().all()
    
    # Also get all active users (for composing new messages)
    all_users = db.query(User).filter(User.role == "user", User.is_active == True).all()
    
    user_list = []
    for user in all_users:
        last_message = db.query(AdminMessage).filter(
            AdminMessage.recipient_id == user.id,
            AdminMessage.sender_id == current_user.id
        ).order_by(AdminMessage.created_at.desc()).first()
        
        user_list.append({
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "display_name": user.profile.display_name if user.profile else user.username,
            "last_message": last_message.content[:50] if last_message else None,
            "last_message_time": last_message.created_at if last_message else None
        })
    
    return sorted(user_list, key=lambda x: x['last_message_time'] or datetime.min, reverse=True)


@router.get("/admin/messages/user/{user_id}")
def get_user_messages(
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all messages between admin and a specific user"""
    
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Only admins can view messages")
    
    messages = db.query(AdminMessage).filter(
        AdminMessage.recipient_id == user_id,
        AdminMessage.sender_id == current_user.id
    ).order_by(AdminMessage.created_at.asc()).all()
    
    return [MessageResponse.from_orm(msg) for msg in messages]


@router.post("/admin/messages/mark-read/{message_id}")
def mark_message_read(
    message_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Mark a message as read"""
    
    message = db.query(AdminMessage).filter(AdminMessage.id == message_id).first()
    if not message:
        raise HTTPException(status_code=404, detail="Message not found")
    
    message.is_read = True
    db.commit()
    db.refresh(message)
    
    return MessageResponse.from_orm(message)