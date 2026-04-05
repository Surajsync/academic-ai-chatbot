import os
import random
import time
import secrets
import smtplib
import logging
from datetime import datetime, timedelta
from email.mime.text import MIMEText

from fastapi import FastAPI, Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from sqlalchemy import text
from pydantic import BaseModel
from jose import JWTError, jwt

from backend.config import settings
from backend.database.database import SessionLocal, engine
from backend.database.models import Base, User, Conversation, Message, FAQ, FailedQuery, AuditLog, SystemSetting, PasswordResetToken
from backend.security.security import hash_password, verify_password
from backend.services.auth_service import create_access_token
from backend.services.chatbot_service import generate_reply_with_source
from backend.services.ai_service import categorize_response, generate_follow_up_suggestions
from backend.routes import chat_routes

# ================================================================
#  APP INIT
# ================================================================
# print("CREATING TABLES...")
# Base.metadata.drop_all(bind=engine)
# Base.metadata.create_all(bind=engine)

app = FastAPI(title="REC Bijnor Academic AI")

logger = logging.getLogger(__name__)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes from separate modules
app.include_router(chat_routes.router)


@app.on_event("startup")
def initialize_database() -> None:
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("Database schema initialized")
    except Exception:
        # Do not block server startup; this keeps the process listening on PORT.
        logger.exception("Database schema initialization failed during startup")

# ================================================================
#  CONFIG  ← Edit these before running
# ================================================================
SECRET_KEY = settings.SECRET_KEY
ALGORITHM = settings.JWT_ALGORITHM

GMAIL_ADDRESS = settings.GMAIL_ADDRESS
GMAIL_APP_PASSWORD = settings.GMAIL_APP_PASSWORD
RESET_TOKEN_EXPIRE_MINS = settings.RESET_TOKEN_EXPIRE_MINS
APP_BASE_URL = settings.APP_BASE_URL

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

# In-memory OTP store  { email: { otp, expires_at, verified } }
otp_store: dict = {}


# ================================================================
#  DATABASE
# ================================================================
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


print("Database initialized...")
# ================================================================
#  AUTH HELPERS
# ================================================================
def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if not email:
            raise HTTPException(status_code=401, detail="Invalid token")
        user = db.query(User).filter(User.email == email).first()
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        if not user.is_active:
            raise HTTPException(status_code=403, detail="Your account is blocked. Contact admin.")
        return user
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")


def get_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


def get_main_admin(db: Session) -> User | None:
    """Main admin is the oldest admin account by ID."""
    return db.query(User).filter(User.role == "admin").order_by(User.id.asc()).first()


# ================================================================
#  REQUEST MODELS
# ================================================================
class RegisterRequest(BaseModel):
    full_name: str
    email: str
    password: str

class ChatRequest(BaseModel):
    message: str

class OtpRequest(BaseModel):
    email: str

class OtpVerify(BaseModel):
    email: str
    otp: str

class ForgotRequest(BaseModel):
    email: str

class ResetRequest(BaseModel):
    token: str
    new_password: str

class RoleUpdate(BaseModel):
    role: str

class UserStatusUpdate(BaseModel):
    is_active: bool

class FaqCreate(BaseModel):
    keyword: str
    response: str


def _faq_keyword_value(faq: FAQ) -> str:
    return (getattr(faq, "keyword", None) or getattr(faq, "keywords", None) or getattr(faq, "question", None) or "").strip()


def _faq_response_value(faq: FAQ) -> str:
    return (getattr(faq, "response", None) or getattr(faq, "answer", None) or "").strip()


def _serialize_faq(faq: FAQ) -> dict:
    return {
        "id": faq.id,
        "keyword": _faq_keyword_value(faq),
        "response": _faq_response_value(faq),
        "is_active": bool(getattr(faq, "is_active", True)),
    }


# ================================================================
#  EMAIL HELPER
# ================================================================
def send_email(to: str, subject: str, body: str):
    """Send email via Gmail SMTP. Raises HTTPException on failure."""
    try:
        if not GMAIL_ADDRESS or not GMAIL_APP_PASSWORD:
            raise HTTPException(status_code=500, detail="Email credentials are not configured")

        msg = MIMEText(body)
        msg["Subject"] = subject
        msg["From"]    = GMAIL_ADDRESS
        msg["To"]      = to
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
            server.send_message(msg)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Email error: {str(e)}")


# ================================================================
#  OTP — SEND
# ================================================================
@app.post("/auth/send-otp")
def send_otp(data: OtpRequest, db: Session = Depends(get_db)):
    if db.query(User).filter(User.email == data.email).first():
        raise HTTPException(status_code=400, detail="Email already registered. Please login.")

    otp = str(random.randint(100000, 999999))
    otp_store[data.email] = {
        "otp":        otp,
        "expires_at": time.time() + 300,   # 5 minutes
        "verified":   False
    }

    send_email(
        to      = data.email,
        subject = "Your OTP — REC Bijnor Academic AI",
        body    = f"""Hello!

Your OTP for REC Bijnor Academic AI registration is:

    {otp}

This OTP is valid for 5 minutes. Do not share it with anyone.

— REC Bijnor Academic AI
"""
    )
    return {"message": "OTP sent successfully"}


# ================================================================
#  OTP — VERIFY
# ================================================================
@app.post("/auth/verify-otp")
def verify_otp(data: OtpVerify):
    record = otp_store.get(data.email)

    if not record:
        raise HTTPException(status_code=400, detail="No OTP found. Please request a new one.")

    if time.time() > record["expires_at"]:
        otp_store.pop(data.email, None)
        raise HTTPException(status_code=400, detail="OTP has expired. Please request a new one.")

    if record["otp"] != data.otp.strip():
        raise HTTPException(status_code=400, detail="Incorrect OTP. Please try again.")

    otp_store[data.email]["verified"] = True
    return {"message": "OTP verified"}


# ================================================================
#  REGISTER
# ================================================================
@app.post("/auth/register")
def register(data: RegisterRequest, db: Session = Depends(get_db)):
    if db.query(User).filter(User.email == data.email).first():
        raise HTTPException(status_code=400, detail="User already exists")
    if len(data.password.encode("utf-8")) > 72:
        raise HTTPException(status_code=400, detail="Password too long (max 72 bytes)")
    
    user = User(
        username        = data.full_name,
        email           = data.email,
        hashed_password = hash_password(data.password),
        role            = "user"
    )
    db.add(user)
    db.commit()
    return {"message": "Registered successfully"}


# ================================================================
#  LOGIN
# ================================================================
@app.post("/auth/login")
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):

    # Step 1: Find user
    user = db.query(User).filter(User.email == form_data.username).first()

    # Step 2: Check user exists
    if not user:
        raise HTTPException(status_code=401, detail="Invalid email or password")

    # Step 3: Verify password (ONLY ONCE)
    password_valid = verify_password(form_data.password, user.hashed_password)

    if not password_valid:
        raise HTTPException(status_code=401, detail="Invalid email or password")

    # Step 4: Check active
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Your account is blocked")

    # Step 5: Generate token
    token = create_access_token({"sub": user.email})

    return {
        "access_token": token,
        "token_type": "bearer",
        "role": user.role,
        "username": user.username
    }


# ================================================================
#  FORGOT PASSWORD — sends reset link to email
# ================================================================
@app.post("/auth/forgot-password")
def forgot_password(data: ForgotRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == data.email).first()

    # Never reveal whether email exists
    if not user:
        return {"message": "If this email is registered, a reset link has been sent."}

    token   = secrets.token_urlsafe(32)
    expires = datetime.utcnow() + timedelta(minutes=RESET_TOKEN_EXPIRE_MINS)

    db.add(PasswordResetToken(email=data.email, token=token, expires_at=expires))
    db.commit()

    reset_link = f"{APP_BASE_URL}/reset_password.html?token={token}"

    send_email(
        to      = data.email,
        subject = "Password Reset — REC Bijnor Academic AI",
        body    = f"""Hello {user.username},

You requested a password reset for your REC Bijnor Academic AI account.

Click the link below to reset your password (valid for {RESET_TOKEN_EXPIRE_MINS} minutes):

{reset_link}

If you did not request this, please ignore this email.

— REC Bijnor Academic AI
"""
    )
    return {"message": "If this email is registered, a reset link has been sent."}


# ================================================================
#  RESET PASSWORD — sets new password using token
# ================================================================
@app.post("/auth/reset-password")
def reset_password(data: ResetRequest, db: Session = Depends(get_db)):
    record = db.query(PasswordResetToken).filter(
        PasswordResetToken.token == data.token,
        PasswordResetToken.used  == False
    ).first()

    if not record:
        raise HTTPException(status_code=400, detail="Invalid or already used reset link.")

    if datetime.utcnow() > record.expires_at:
        raise HTTPException(status_code=400, detail="Reset link has expired. Please request a new one.")

    user = db.query(User).filter(User.email == record.email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")

    user.hashed_password = hash_password(data.new_password)
    record.used          = True
    db.commit()

    return {"message": "Password reset successfully. You can now login."}


# ================================================================
#  CHATBOT
# ================================================================
@app.post("/chat")
def chat(request: ChatRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    setting = db.query(SystemSetting).first()
    if setting and setting.maintenance_mode:
        return {"reply": "System is under maintenance. Please try later."}

    conversation = Conversation(user_id=user.id)
    db.add(conversation)
    db.commit()
    db.refresh(conversation)

    db.add(Message(conversation_id=conversation.id, role="user", content=request.message))
    db.commit()

    reply, reply_source = generate_reply_with_source(db, request.message)
    
    # Categorize the response
    category = categorize_response(request.message)
    
    # Generate follow-up suggestions (only if AI response was successful)
    suggestions = []
    if reply_source == "groq":
        try:
            from backend.services.ai_service import generate_follow_up_suggestions
            suggestions = generate_follow_up_suggestions("", request.message, reply)
        except Exception:
            pass

    db.add(Message(conversation_id=conversation.id, role="bot", content=reply))
    db.commit()

    # Track unanswered questions
    if "sorry" in reply.lower() or "not available" in reply.lower() or "don't have" in reply.lower():
        fq = db.query(FailedQuery).filter(FailedQuery.query_text == request.message).first()
        if fq:
            fq.frequency += 1
        else:
            db.add(FailedQuery(query_text=request.message))
        db.commit()

    response = {
        "reply": reply,
        "category": category,
        "suggestions": suggestions[:3]
    }
    
    if user.role == "admin":
        response["debug"] = {
            "source": reply_source,
            "category": category
        }
    
    return response


# ================================================================
#  GET CONVERSATION HISTORY
# ================================================================
@app.get("/chat/history")
def get_chat_history(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Fetch all conversations and messages for the current user"""
    conversations = db.query(Conversation).filter(Conversation.user_id == user.id).order_by(Conversation.created_at.desc()).all()
    
    result = []
    for conv in conversations:
        messages = db.query(Message).filter(Message.conversation_id == conv.id).order_by(Message.timestamp.asc()).all()
        
        # Extract conversation title from first user message
        title = "New Chat"
        if messages:
            for msg in messages:
                if msg.role == "user":
                    title = msg.content[:50]  # First 50 chars of first user message
                    break
        
        result.append({
            "id": str(conv.id),
            "title": title,
            "created_at": conv.created_at.isoformat(),
            "messages": [
                {
                    "role": msg.role,
                    "text": msg.content,
                    "timestamp": msg.timestamp.isoformat()
                }
                for msg in messages
            ]
        })
    
    return result


# ================================================================
#  ADMIN — DASHBOARD STATS
# ================================================================
@app.get("/admin/dashboard")
def dashboard(db: Session = Depends(get_db), admin: User = Depends(get_admin)):
    return {
        "total_faqs":          db.query(FAQ).count(),
        "active_faqs":         db.query(FAQ).filter(FAQ.is_active == True).count(),
        "total_conversations": db.query(Conversation).count(),
        "failed_queries":      db.query(FailedQuery).count()
    }


@app.get("/admin/ai-status")
def ai_status(admin: User = Depends(get_admin)):
    """Admin-only endpoint to quickly verify AI layer configuration."""
    if settings.GROQ_API_KEY:
        provider = "groq"
        model = settings.GROQ_MODEL
    elif settings.GEMINI_API_KEY:
        provider = "gemini"
        model = settings.GEMINI_MODEL
    elif settings.OPENAI_API_KEY:
        provider = "openai"
        model = settings.LLM_MODEL
    else:
        provider = "none"
        model = "n/a"

    return {
        "enabled": settings.ENABLE_LLM,
        "provider": provider,
        "model": model,
        "api_key_configured": bool(settings.GROQ_API_KEY or settings.GEMINI_API_KEY or settings.OPENAI_API_KEY),
    }


# ================================================================
#  ADMIN — FAQs
# ================================================================
@app.get("/admin/faqs")
def get_faqs(db: Session = Depends(get_db), admin: User = Depends(get_admin)):
    faqs = db.query(FAQ).order_by(FAQ.id).all()
    return [_serialize_faq(faq) for faq in faqs]


@app.post("/admin/faqs")
def add_faq(data: FaqCreate, db: Session = Depends(get_db), admin: User = Depends(get_admin)):
    create_kwargs: dict = {}

    if hasattr(FAQ, "keyword"):
        create_kwargs["keyword"] = data.keyword
    if hasattr(FAQ, "keywords"):
        create_kwargs["keywords"] = data.keyword
    if hasattr(FAQ, "question"):
        create_kwargs["question"] = data.keyword

    if hasattr(FAQ, "response"):
        create_kwargs["response"] = data.response
    if hasattr(FAQ, "answer"):
        create_kwargs["answer"] = data.response

    faq = FAQ(**create_kwargs)
    db.add(faq)
    db.commit()

    db.add(AuditLog(user_email=admin.email, action=f"Added FAQ: {data.keyword[:60]}"))
    db.commit()

    return {"message": "FAQ added"}


@app.delete("/admin/faqs/{faq_id}")
def delete_faq(faq_id: int, db: Session = Depends(get_db), admin: User = Depends(get_admin)):
    faq = db.query(FAQ).filter(FAQ.id == faq_id).first()
    if not faq:
        raise HTTPException(status_code=404, detail="FAQ not found")

    keyword_preview = _faq_keyword_value(faq)[:60]
    db.delete(faq)
    db.commit()

    # ── Resequence IDs — no gaps after delete ─────────────────────
    remaining = db.query(FAQ).order_by(FAQ.id).all()
    for new_id, row in enumerate(remaining, start=1):
        if row.id != new_id:
            db.execute(text(f"UPDATE faqs SET id = {new_id} WHERE id = {row.id}"))
    db.commit()

    # Reset PostgreSQL sequence so next INSERT continues from correct number
    db.execute(text(
        "SELECT setval('faqs_id_seq', COALESCE((SELECT MAX(id) FROM faqs), 0) + 1, false)"
    ))
    db.commit()
    # ──────────────────────────────────────────────────────────────

    db.add(AuditLog(
        user_email = admin.email,
        action     = f"Deleted FAQ '{keyword_preview}' (was id={faq_id}) — IDs resequenced"
    ))
    db.commit()

    return {"message": "Deleted and IDs resequenced"}


# ================================================================
#  ADMIN — FAILED QUERIES
# ================================================================
@app.get("/admin/failed")
def failed_queries(db: Session = Depends(get_db), admin: User = Depends(get_admin)):
    return db.query(FailedQuery).order_by(FailedQuery.frequency.desc()).all()


# ================================================================
#  ADMIN — AUDIT LOGS
# ================================================================
@app.delete("/admin/failed/{query_id}")
def delete_failed_query(query_id: int, db: Session = Depends(get_db), admin: User = Depends(get_admin)):
    """Delete a failed query by ID"""
    query = db.query(FailedQuery).filter(FailedQuery.id == query_id).first()
    if not query:
        raise HTTPException(status_code=404, detail="Failed query not found")
    db.delete(query)
    db.commit()
    return {"message": "Failed query deleted successfully"}


# ================================================================
#  ADMIN — AUDIT LOGS
# ================================================================
@app.get("/admin/audit")
def audit_logs(db: Session = Depends(get_db), admin: User = Depends(get_admin)):
    return db.query(AuditLog).order_by(AuditLog.timestamp.desc()).limit(50).all()


# ================================================================
#  ADMIN — USER MANAGEMENT
# ================================================================
@app.get("/admin/users")
def get_users(db: Session = Depends(get_db), admin: User = Depends(get_admin)):
    return db.query(User).order_by(User.id).all()


@app.patch("/admin/users/{user_id}/role")
def update_user_role(
    user_id: int,
    data: RoleUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(get_admin)
):
    if data.role not in ["admin", "user"]:
        raise HTTPException(status_code=400, detail="Role must be 'admin' or 'user'")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    main_admin = get_main_admin(db)
    is_actor_main = bool(main_admin and admin.id == main_admin.id)
    is_target_main = bool(main_admin and user.id == main_admin.id)

    if is_target_main and not is_actor_main and data.role != "admin":
        raise HTTPException(status_code=403, detail="Only main admin can change main admin role")

    # Main admin can demote other admins. Non-main admins cannot demote other admins.
    if user.role == "admin" and data.role == "user" and admin.id != user.id and not is_actor_main:
        raise HTTPException(status_code=403, detail="Only main admin can remove another admin role")

    old_role  = user.role
    user.role = data.role
    db.commit()

    db.add(AuditLog(
        user_email = admin.email,
        action     = f"Changed role of {user.email} from {old_role} to {data.role}"
    ))
    db.commit()

    return {"message": f"Role updated to {data.role}"}


@app.patch("/admin/users/{user_id}/status")
def update_user_status(
    user_id: int,
    data: UserStatusUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(get_admin)
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    main_admin = get_main_admin(db)
    is_actor_main = bool(main_admin and admin.id == main_admin.id)
    is_target_main = bool(main_admin and user.id == main_admin.id)

    if is_target_main and admin.id != user.id and data.is_active is False:
        raise HTTPException(status_code=403, detail="Only main admin can block main admin account")

    # Main admin can block admin accounts. Non-main admins cannot block other admins.
    if user.role == "admin" and data.is_active is False and admin.id != user.id and not is_actor_main:
        raise HTTPException(status_code=403, detail="Only main admin can block admin accounts")

    if admin.id == user.id and data.is_active is False:
        raise HTTPException(status_code=400, detail="You cannot block your own account")

    previous_status = user.is_active
    user.is_active = data.is_active
    db.commit()

    action = "Unblocked" if data.is_active else "Blocked"
    db.add(AuditLog(
        user_email=admin.email,
        action=f"{action} user {user.email} (active: {previous_status} -> {data.is_active})"
    ))
    db.commit()

    return {"message": f"User {'unblocked' if data.is_active else 'blocked'} successfully"}


# ================================================================
#  STATIC FILES
#  IMPORTANT: Explicit routes must come BEFORE app.mount()
# ================================================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATES_DIR = os.path.join(BASE_DIR, "../templates")


def template_file(name: str) -> str:
    return os.path.join(TEMPLATES_DIR, name)


@app.get("/")
def home():
    return FileResponse(template_file("auth_ui.html"))

@app.get("/")
def health():
    return {"status": "ok", "service": "rec-bijnor-academic-ai"}

@app.get("/auth_ui.html")
def auth_page():
    return FileResponse(template_file("auth_ui.html"))


@app.get("/chat_ui.html")
def chat_page():
    return FileResponse(template_file("chat_ui.html"))


@app.get("/admin_ui.html")
def admin_page():
    return FileResponse(template_file("admin_ui.html"))


@app.get("/reset_password.html")
def reset_password_page():
    return FileResponse(template_file("reset_password.html"))


@app.get("/healthz")
def healthz():
    return {"status": "ok", "service": "rec-bijnor-academic-ai"}

# Mount static files BEFORE the root mount (more specific routes first)
app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "../static")), name="files")

# Must be LAST — serves all remaining page templates
app.mount("/templates", StaticFiles(directory=TEMPLATES_DIR), name="templates")