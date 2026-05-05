import os
import random
import time
import secrets
import smtplib
import logging
import socket
import base64
import requests
from datetime import datetime, timedelta, timezone
from email.mime.text import MIMEText

from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Form
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import text, func
from pydantic import BaseModel
from jose import JWTError, jwt

from backend.config import settings
from backend.database.database import SessionLocal, engine
from backend.database.models import Base, User, UserProfile, Conversation, Message, FAQ, FailedQuery, AuditLog, SystemSetting, PasswordResetToken, Announcement
from backend.security.security import hash_password, verify_password
from backend.services.auth_service import create_access_token
from backend.services.chatbot_service import generate_reply_with_source, get_intent_guided_suggestions
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


def _apply_user_schema_compatibility(db: Session) -> None:
    """Keep auth working on legacy databases that used users.hash instead of users.hashed_password."""
    dialect = db.bind.dialect.name if db.bind else ""
    if dialect != "postgresql":
        return

    # Ensure new column exists.
    db.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS hashed_password VARCHAR"))

    legacy_hash_exists = db.execute(
        text(
            """
            SELECT 1
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = 'users'
              AND column_name = 'hash'
            LIMIT 1
            """
        )
    ).first() is not None

    if legacy_hash_exists:
        db.execute(
            text(
                """
                UPDATE users
                SET hashed_password = hash
                WHERE hashed_password IS NULL
                  AND hash IS NOT NULL
                """
            )
        )
    db.commit()


@app.on_event("startup")
def initialize_database() -> None:
    try:
        Base.metadata.create_all(bind=engine)
        with SessionLocal() as db:
            _apply_user_schema_compatibility(db)
            _normalize_faq_activation(db)
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
    if _normalize_role_value(user.role) != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


def get_main_admin(db: Session) -> User | None:
    """Main admin is the oldest admin account by ID."""
    users = db.query(User).order_by(User.id.asc()).all()
    for user in users:
        if _normalize_role_value(user.role) == "admin":
            return user
    return None


# ================================================================
#  REQUEST MODELS
# ================================================================
class RegisterRequest(BaseModel):
    full_name: str
    email: str
    password: str

class ChatRequest(BaseModel):
    message: str
    conversation_id: int | None = None
    language: str | None = "auto"


class DeleteMessagesRequest(BaseModel):
    message_ids: list[int]


class MessageFeedbackRequest(BaseModel):
    sentiment: str
    reason: str | None = None

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


class AnnouncementCreateRequest(BaseModel):
    title: str
    message: str
    is_active: bool = True


class AnnouncementUpdateRequest(BaseModel):
    title: str | None = None
    message: str | None = None
    is_active: bool | None = None


def _normalize_role_value(role_value: str | None) -> str:
    return (role_value or "user").strip().lower()


def _is_llm_enabled() -> bool:
    return bool(settings.ENABLE_LLM or settings.GROQ_API_KEY or settings.GEMINI_API_KEY or settings.OPENAI_API_KEY)


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


def _serialize_profile(profile: UserProfile | None, user: User) -> dict:
    profile = profile or UserProfile()
    return {
        "display_name": profile.display_name or user.username,
        "phone": profile.phone or "",
        "department": profile.department or "",
        "semester": profile.semester or "",
        "year": profile.year or "",
        "roll_number": profile.roll_number or "",
        "location": profile.location or "",
        "linkedin": profile.linkedin or "",
        "website": profile.website or "",
        "bio": profile.bio or "",
        "photo_data": profile.photo_data or "",
        "photo_mime": profile.photo_mime or "",
        "email": user.email,
        "username": user.username,
    }


def _parse_feedback_value(raw_feedback: str | None) -> dict | None:
    value = (raw_feedback or "").strip()
    if not value:
        return None

    parts = value.split("|", 1)
    sentiment = parts[0].strip().lower()
    reason = parts[1].strip() if len(parts) > 1 else ""
    if sentiment not in {"up", "down"}:
        return None

    return {
        "sentiment": sentiment,
        "reason": reason,
    }


def _serialize_announcement(announcement: Announcement) -> dict:
    return {
        "id": announcement.id,
        "title": announcement.title,
        "message": announcement.message,
        "is_active": bool(announcement.is_active),
        "created_by_id": announcement.created_by_id,
        "created_at": announcement.created_at.isoformat() if announcement.created_at else None,
        "updated_at": announcement.updated_at.isoformat() if announcement.updated_at else None,
    }


def _build_profile_personalization(profile: UserProfile | None, query_text: str) -> str:
    if not profile:
        return ""

    profile_bits = []
    if profile.department:
        profile_bits.append(f"Department: {profile.department}")
    if profile.semester:
        profile_bits.append(f"Semester: {profile.semester}")
    if profile.year:
        profile_bits.append(f"Year: {profile.year}")

    if not profile_bits:
        return ""

    lowered_query = (query_text or "").lower()
    relevant_hints = ["fee", "fees", "exam", "timetable", "syllabus", "placement", "admission"]
    if not any(hint in lowered_query for hint in relevant_hints):
        return ""

    return f"Based on your profile ({', '.join(profile_bits)}):"


def _serialize_admin_user(user: User) -> dict:
    profile_data = _serialize_profile(getattr(user, "profile", None), user)
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "role": _normalize_role_value(user.role),
        "is_active": bool(user.is_active),
        "profile": profile_data,
    }


def _normalize_faq_activation(db: Session) -> None:
    try:
        db.query(FAQ).filter(FAQ.is_active.is_(None)).update({FAQ.is_active: True}, synchronize_session=False)
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("Legacy FAQ activation normalization failed")


def _ensure_profile(db: Session, user: User) -> UserProfile:
    profile = db.query(UserProfile).filter(UserProfile.user_id == user.id).first()
    if profile:
        return profile

    profile = UserProfile(user_id=user.id, display_name=user.username)
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return profile


# ================================================================
#  EMAIL HELPER
# ================================================================
def send_email(to: str, subject: str, body: str):
    """Send email via Resend API (preferred) or Gmail SMTP fallback."""
    
    # Try Resend API first (works everywhere, including Render without port blocking)
    resend_api_key = (settings.RESEND_API_KEY or "").strip().strip('"').strip("'")
    if resend_api_key.lower().startswith("bearer "):
        resend_api_key = resend_api_key[7:].strip()

    if resend_api_key:
        resend_from = settings.RESEND_FROM_EMAIL or "onboarding@resend.dev"
        try:
            response = requests.post(
                "https://api.resend.com/emails",
                headers={"Authorization": f"Bearer {resend_api_key}"},
                json={
                    "from": resend_from,
                    "to": to,
                    "subject": subject,
                    "text": body
                },
                timeout=10
            )
            if response.status_code in (200, 201):
                return
            resend_error = (response.text or "").strip()
            logger.warning(f"Resend API error: {response.status_code} - {resend_error}")
            raise HTTPException(
                status_code=502,
                detail=f"Resend email error ({response.status_code}). Verify RESEND_API_KEY and RESEND_FROM_EMAIL. {resend_error}"
            )
        except HTTPException:
            raise
        except Exception as err:
            logger.exception("Resend API request failed")
            raise HTTPException(
                status_code=502,
                detail=f"Resend request failed: {err}"
            )
    
    # Fall back to SMTP if Resend unavailable or failed
    if not GMAIL_ADDRESS or not GMAIL_APP_PASSWORD:
        raise HTTPException(
            status_code=500,
            detail="Email service not configured. Contact admin."
        )

    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = GMAIL_ADDRESS
    msg["To"] = to

    # Try both common Gmail SMTP paths
    send_attempts: list[tuple[str, int]] = [("ssl", 465), ("starttls", 587)]
    smtp_timeout_seconds = 8
    errors: list[str] = []

    for mode, port in send_attempts:
        try:
            if mode == "ssl":
                with smtplib.SMTP_SSL("smtp.gmail.com", port, timeout=smtp_timeout_seconds) as server:
                    server.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
                    server.send_message(msg)
            else:
                with smtplib.SMTP("smtp.gmail.com", port, timeout=smtp_timeout_seconds) as server:
                    server.ehlo()
                    server.starttls()
                    server.ehlo()
                    server.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
                    server.send_message(msg)
            return
        except (socket.timeout, TimeoutError):
            errors.append(f"{mode}:{port}: timeout")
        except OSError as err:
            errors.append(f"{mode}:{port}: os_error={err}")
            if "network is unreachable" in str(err).lower() or getattr(err, "errno", None) == 101:
                break
        except smtplib.SMTPException as err:
            errors.append(f"{mode}:{port}: smtp_error={err}")
        except Exception as err:
            errors.append(f"{mode}:{port}: unexpected={err}")

    error_text = " | ".join(errors)
    lower_error_text = error_text.lower()
    if "network is unreachable" in lower_error_text or "errno 101" in lower_error_text:
        raise HTTPException(
            status_code=503,
            detail="SMTP network blocked. Add RESEND_API_KEY to .env for email service."
        )
    if "timeout" in lower_error_text:
        raise HTTPException(status_code=504, detail="Email server timeout. Please try again.")
    raise HTTPException(status_code=500, detail=f"Email error: {error_text}")


# ================================================================
#  OTP — SEND
# ================================================================
@app.post("/auth/send-otp")
def send_otp(data: OtpRequest, db: Session = Depends(get_db)):
    email = data.email.strip().lower()

    if db.query(User).filter(func.lower(User.email) == email).first():
        raise HTTPException(status_code=400, detail="Email already registered. Please login.")

    otp = str(random.randint(100000, 999999))
    otp_store[email] = {
        "otp":        otp,
        "expires_at": time.time() + 300,   # 5 minutes
        "verified":   False
    }

    send_email(
        to      = email,
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
    email = data.email.strip().lower()
    record = otp_store.get(email)

    if not record:
        raise HTTPException(status_code=400, detail="No OTP found. Please request a new one.")

    if time.time() > record["expires_at"]:
        otp_store.pop(email, None)
        raise HTTPException(status_code=400, detail="OTP has expired. Please request a new one.")

    if record["otp"] != data.otp.strip():
        raise HTTPException(status_code=400, detail="Incorrect OTP. Please try again.")

    otp_store[email]["verified"] = True
    return {"message": "OTP verified"}


@app.get("/auth/registration-mode")
def registration_mode():
    """Expose registration mode so frontend can switch between OTP and direct signup."""
    return {"otp_required": bool(settings.REQUIRE_REGISTRATION_OTP)}


# ================================================================
#  REGISTER
# ================================================================
@app.post("/auth/register")
def register(data: RegisterRequest, db: Session = Depends(get_db)):
    email = data.email.strip().lower()

    if db.query(User).filter(func.lower(User.email) == email).first():
        raise HTTPException(status_code=400, detail="User already exists")

    if settings.REQUIRE_REGISTRATION_OTP:
        otp_record = otp_store.get(email)
        if not otp_record:
            raise HTTPException(status_code=400, detail="Please request OTP first")
        if time.time() > otp_record["expires_at"]:
            otp_store.pop(email, None)
            raise HTTPException(status_code=400, detail="OTP has expired. Please request a new one.")
        if not otp_record.get("verified"):
            raise HTTPException(status_code=400, detail="Please verify OTP before registration")

    if len(data.password.encode("utf-8")) > 72:
        raise HTTPException(status_code=400, detail="Password too long (max 72 bytes)")
    
    user = User(
        username        = data.full_name,
        email           = email,
        hashed_password = hash_password(data.password),
        role            = "user"
    )
    db.add(user)
    db.commit()

    # Consume OTP after successful account creation when OTP mode is enabled.
    if settings.REQUIRE_REGISTRATION_OTP:
        otp_store.pop(email, None)

    return {"message": "Registered successfully"}


# ================================================================
#  LOGIN
# ================================================================
@app.post("/auth/login")
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    login_id = form_data.username.strip()
    login_id_lower = login_id.lower()

    # Step 1: Find user
    user = db.query(User).filter(
        (func.lower(User.email) == login_id_lower) |
        (func.lower(User.username) == login_id_lower)
    ).first()

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
    normalized_role = _normalize_role_value(user.role)

    return {
        "access_token": token,
        "token_type": "bearer",
        "role": normalized_role,
        "username": user.username,
        "redirect_to": "/admin_ui.html" if normalized_role == "admin" else "/chat_ui.html",
    }


@app.get("/auth/me")
def auth_me(user: User = Depends(get_current_user)):
    """Return authenticated user profile for frontend role checks."""
    return {
        "email": user.email,
        "username": user.username,
        "role": _normalize_role_value(user.role),
        "is_active": user.is_active,
    }


@app.get("/profile/me")
def get_my_profile(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    profile = db.query(UserProfile).filter(UserProfile.user_id == user.id).first()
    if not profile:
        profile = _ensure_profile(db, user)
    return _serialize_profile(profile, user)


@app.put("/profile/me")
def update_my_profile(
    display_name: str | None = Form(default=None),
    phone: str | None = Form(default=None),
    department: str | None = Form(default=None),
    semester: str | None = Form(default=None),
    year: str | None = Form(default=None),
    roll_number: str | None = Form(default=None),
    location: str | None = Form(default=None),
    linkedin: str | None = Form(default=None),
    website: str | None = Form(default=None),
    bio: str | None = Form(default=None),
    profile_photo: UploadFile | None = File(default=None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    profile = _ensure_profile(db, user)

    profile.display_name = display_name.strip() if display_name else profile.display_name
    profile.phone = phone.strip() if phone else profile.phone
    profile.department = department.strip() if department else profile.department
    profile.semester = semester.strip() if semester else profile.semester
    profile.year = year.strip() if year else profile.year
    profile.roll_number = roll_number.strip() if roll_number else profile.roll_number
    profile.location = location.strip() if location else profile.location
    profile.linkedin = linkedin.strip() if linkedin else profile.linkedin
    profile.website = website.strip() if website else profile.website
    profile.bio = bio.strip() if bio else profile.bio

    if profile_photo and profile_photo.filename:
        content = profile_photo.file.read()
        encoded_photo = base64.b64encode(content).decode("utf-8")
        mime_type = profile_photo.content_type or "image/jpeg"
        profile.photo_data = f"data:{mime_type};base64,{encoded_photo}"
        profile.photo_mime = mime_type

    db.add(profile)
    db.commit()
    db.refresh(profile)
    return _serialize_profile(profile, user)


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
    expires = datetime.now(timezone.utc) + timedelta(minutes=RESET_TOKEN_EXPIRE_MINS)

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

    now_utc = datetime.now(timezone.utc)
    expires_at = record.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)

    if now_utc > expires_at:
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

    conversation = None
    if request.conversation_id:
        conversation = db.query(Conversation).filter(
            Conversation.id == request.conversation_id,
            Conversation.user_id == user.id
        ).first()

    if not conversation:
        conversation = Conversation(user_id=user.id)
        db.add(conversation)
        db.commit()
        db.refresh(conversation)

    user_message = Message(conversation_id=conversation.id, role="user", content=request.message)
    db.add(user_message)
    db.commit()
    db.refresh(user_message)

    recent_messages = (
        db.query(Message)
        .filter(Message.conversation_id == conversation.id)
        .order_by(Message.timestamp.desc())
        .limit(8)
        .all()
    )
    conversation_history = [
        {"role": msg.role, "content": msg.content}
        for msg in reversed(recent_messages)
    ]

    profile_context_parts = []
    profile = getattr(user, "profile", None)
    language_pref = (request.language or "auto").strip().lower()
    if profile:
        if profile.display_name:
            profile_context_parts.append(f"name: {profile.display_name}")
        if profile.department:
            profile_context_parts.append(f"department: {profile.department}")
        if profile.semester:
            profile_context_parts.append(f"semester: {profile.semester}")
        if profile.year:
            profile_context_parts.append(f"year: {profile.year}")

    if language_pref in {"en", "hi"}:
        profile_context_parts.append(
            f"preferred_language: {'hindi' if language_pref == 'hi' else 'english'}"
        )

    user_context = "; ".join(profile_context_parts)

    reply, reply_source = generate_reply_with_source(
        db,
        request.message,
        conversation_history=conversation_history,
        user_context=user_context,
    )

    personalization_line = _build_profile_personalization(profile, request.message)
    if personalization_line and reply_source in {"structured", "faq", "semantic"}:
        reply = f"{personalization_line}\n{reply}"
    
    # Categorize the response
    category = categorize_response(request.message)
    
    # Generate follow-up suggestions from deterministic intent map first.
    suggestions = get_intent_guided_suggestions(request.message)
    if reply_source == "groq":
        try:
            from backend.services.ai_service import generate_follow_up_suggestions
            ai_suggestions = generate_follow_up_suggestions("", request.message, reply)
            suggestions = (ai_suggestions + suggestions)[:3]
        except Exception:
            pass

    bot_message = Message(conversation_id=conversation.id, role="bot", content=reply)
    db.add(bot_message)
    db.commit()
    db.refresh(bot_message)

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
        "suggestions": suggestions[:3],
        "source": reply_source,
    }
    
    if _normalize_role_value(user.role) == "admin":
        response["debug"] = {
            "source": reply_source,
            "category": category
        }

    response["conversation_id"] = str(conversation.id)
    response["user_message_id"] = user_message.id
    response["bot_message_id"] = bot_message.id
    
    return response


@app.post("/chat/messages/{message_id}/feedback")
def submit_message_feedback(
    message_id: int,
    payload: MessageFeedbackRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    sentiment = (payload.sentiment or "").strip().lower()
    if sentiment not in {"up", "down"}:
        raise HTTPException(status_code=400, detail="sentiment must be 'up' or 'down'")

    reason = (payload.reason or "").strip()
    if len(reason) > 120:
        raise HTTPException(status_code=400, detail="reason is too long")

    message = (
        db.query(Message)
        .join(Conversation, Conversation.id == Message.conversation_id)
        .filter(
            Message.id == message_id,
            Message.role == "bot",
            Conversation.user_id == user.id,
        )
        .first()
    )
    if not message:
        raise HTTPException(status_code=404, detail="Message not found")

    message.feedback = f"{sentiment}|{reason}" if reason else sentiment
    db.add(message)
    db.commit()

    return {
        "message": "Feedback saved",
        "feedback": _parse_feedback_value(message.feedback),
    }


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
                    "id": msg.id,
                    "role": msg.role,
                    "text": msg.content,
                    "timestamp": msg.timestamp.isoformat(),
                    "feedback": _parse_feedback_value(msg.feedback),
                }
                for msg in messages
            ]
        })
    
    return result


@app.delete("/chat/conversations/{conversation_id}")
def delete_chat_conversation(
    conversation_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    conversation = db.query(Conversation).filter(
        Conversation.id == conversation_id,
        Conversation.user_id == user.id,
    ).first()
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    db.query(Message).filter(Message.conversation_id == conversation.id).delete(synchronize_session=False)
    db.delete(conversation)
    db.commit()

    return {"message": "Conversation deleted successfully"}


@app.delete("/chat/conversations/{conversation_id}/messages")
def delete_chat_messages(
    conversation_id: int,
    payload: DeleteMessagesRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    message_ids = [mid for mid in (payload.message_ids or []) if isinstance(mid, int)]
    if not message_ids:
        raise HTTPException(status_code=400, detail="No message IDs provided")

    conversation = db.query(Conversation).filter(
        Conversation.id == conversation_id,
        Conversation.user_id == user.id,
    ).first()
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    deleted_count = db.query(Message).filter(
        Message.conversation_id == conversation.id,
        Message.id.in_(message_ids),
    ).delete(synchronize_session=False)
    db.commit()

    return {"message": "Messages deleted successfully", "deleted_count": deleted_count}


# ================================================================
#  ADMIN — DASHBOARD STATS
# ================================================================
@app.get("/admin/dashboard")
def dashboard(db: Session = Depends(get_db), admin: User = Depends(get_admin)):
    bot_messages = db.query(Message).filter(Message.role == "bot").all()
    feedback_entries = [m for m in bot_messages if (m.feedback or "").strip()]

    positive_feedback = 0
    negative_feedback = 0
    reason_counter: dict[str, int] = {}
    fallback_count = 0
    for message in bot_messages:
        content_lower = (message.content or "").lower()
        if any(token in content_lower for token in ["i don't have", "not available", "sorry"]):
            fallback_count += 1

        parsed = _parse_feedback_value(message.feedback)
        if not parsed:
            continue
        if parsed["sentiment"] == "up":
            positive_feedback += 1
        elif parsed["sentiment"] == "down":
            negative_feedback += 1
            reason_value = (parsed.get("reason") or "unspecified").strip().lower() or "unspecified"
            reason_counter[reason_value] = reason_counter.get(reason_value, 0) + 1

    top_negative_reasons = [
        {"reason": reason, "count": count}
        for reason, count in sorted(reason_counter.items(), key=lambda item: item[1], reverse=True)[:5]
    ]

    total_bot_messages = len(bot_messages)
    fallback_rate = round((fallback_count / total_bot_messages) * 100, 2) if total_bot_messages else 0.0

    return {
        "total_faqs":          db.query(FAQ).count(),
        "active_faqs":         db.query(FAQ).filter(FAQ.is_active == True).count(),
        "total_conversations": db.query(Conversation).count(),
        "failed_queries":      db.query(FailedQuery).count(),
        "feedback_total":      len(feedback_entries),
        "feedback_positive":   positive_feedback,
        "feedback_negative":   negative_feedback,
        "top_negative_reasons": top_negative_reasons,
        "fallback_rate":       fallback_rate,
    }


@app.get("/announcements/active")
def get_active_announcement(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    announcement = (
        db.query(Announcement)
        .filter(Announcement.is_active == True)
        .order_by(Announcement.updated_at.desc(), Announcement.id.desc())
        .first()
    )
    if not announcement:
        return {"announcement": None}

    return {"announcement": _serialize_announcement(announcement)}


@app.get("/admin/announcements")
def get_admin_announcements(db: Session = Depends(get_db), admin: User = Depends(get_admin)):
    announcements = db.query(Announcement).order_by(Announcement.updated_at.desc(), Announcement.id.desc()).limit(20).all()
    return [_serialize_announcement(item) for item in announcements]


@app.post("/admin/announcements")
def create_admin_announcement(
    payload: AnnouncementCreateRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(get_admin),
):
    title = (payload.title or "").strip()
    message = (payload.message or "").strip()
    if not title or not message:
        raise HTTPException(status_code=400, detail="title and message are required")

    if payload.is_active:
        db.query(Announcement).filter(Announcement.is_active == True).update({Announcement.is_active: False}, synchronize_session=False)

    announcement = Announcement(
        title=title,
        message=message,
        is_active=payload.is_active,
        created_by_id=admin.id,
    )
    db.add(announcement)
    db.commit()
    db.refresh(announcement)

    db.add(AuditLog(user_email=admin.email, action=f"Posted announcement: {title[:60]}"))
    db.commit()

    return _serialize_announcement(announcement)


@app.patch("/admin/announcements/{announcement_id}")
def update_admin_announcement(
    announcement_id: int,
    payload: AnnouncementUpdateRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(get_admin),
):
    announcement = db.query(Announcement).filter(Announcement.id == announcement_id).first()
    if not announcement:
        raise HTTPException(status_code=404, detail="Announcement not found")

    if payload.title is not None:
        title = payload.title.strip()
        if not title:
            raise HTTPException(status_code=400, detail="title cannot be empty")
        announcement.title = title

    if payload.message is not None:
        message = payload.message.strip()
        if not message:
            raise HTTPException(status_code=400, detail="message cannot be empty")
        announcement.message = message

    if payload.is_active is not None:
        if payload.is_active:
            db.query(Announcement).filter(
                Announcement.id != announcement.id,
                Announcement.is_active == True,
            ).update({Announcement.is_active: False}, synchronize_session=False)
        announcement.is_active = payload.is_active

    db.add(announcement)
    db.commit()
    db.refresh(announcement)

    db.add(AuditLog(user_email=admin.email, action=f"Updated announcement #{announcement.id}"))
    db.commit()

    return _serialize_announcement(announcement)


@app.delete("/admin/announcements/{announcement_id}")
def delete_admin_announcement(
    announcement_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(get_admin),
):
    announcement = db.query(Announcement).filter(Announcement.id == announcement_id).first()
    if not announcement:
        raise HTTPException(status_code=404, detail="Announcement not found")

    title = announcement.title or f"#{announcement.id}"
    db.delete(announcement)
    db.commit()

    db.add(AuditLog(user_email=admin.email, action=f"Deleted announcement: {title[:60]}"))
    db.commit()

    return {"message": "Announcement deleted successfully", "deleted_id": announcement_id}


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
        "enabled": _is_llm_enabled(),
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
    if hasattr(FAQ, "is_active"):
        create_kwargs["is_active"] = True

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
    users = db.query(User).options(joinedload(User.profile)).order_by(User.id).all()
    return [_serialize_admin_user(user) for user in users]


@app.patch("/admin/users/{user_id}/role")
def update_user_role(
    user_id: int,
    data: RoleUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(get_admin)
):
    target_role = _normalize_role_value(data.role)
    if target_role not in ["admin", "user"]:
        raise HTTPException(status_code=400, detail="Role must be 'admin' or 'user'")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    main_admin = get_main_admin(db)
    is_actor_main = bool(main_admin and admin.id == main_admin.id)
    is_target_main = bool(main_admin and user.id == main_admin.id)

    if is_target_main and not is_actor_main and target_role != "admin":
        raise HTTPException(status_code=403, detail="Only main admin can change main admin role")

    # Main admin can demote other admins. Non-main admins cannot demote other admins.
    if _normalize_role_value(user.role) == "admin" and target_role == "user" and admin.id != user.id and not is_actor_main:
        raise HTTPException(status_code=403, detail="Only main admin can remove another admin role")

    old_role  = _normalize_role_value(user.role)
    user.role = target_role
    db.commit()

    db.add(AuditLog(
        user_email = admin.email,
        action     = f"Changed role of {user.email} from {old_role} to {target_role}"
    ))
    db.commit()

    return {"message": f"Role updated to {target_role}"}


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
    if _normalize_role_value(user.role) == "admin" and data.is_active is False and admin.id != user.id and not is_actor_main:
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
#  ADMIN MESSAGING
# ================================================================
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


@app.post("/admin/messages/send")
def send_admin_message(
    data: SendMessageRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(get_admin)
):
    """Admin sends a message to a user"""
    recipient = db.query(User).filter(User.id == data.recipient_id).first()
    if not recipient:
        raise HTTPException(status_code=404, detail="User not found")

    message = AdminMessage(
        sender_id=admin.id,
        recipient_id=data.recipient_id,
        content=data.content,
        is_read=False,
    )

    db.add(message)
    db.commit()
    db.refresh(message)

    return MessageResponse.from_orm(message)


@app.get("/admin/messages/users")
def get_message_users(
    db: Session = Depends(get_db),
    admin: User = Depends(get_admin)
):
    """Get list of all users with message history for admin"""
    all_users = db.query(User).filter(User.role == "user", User.is_active == True).all()

    user_list = []
    for user in all_users:
        last_message = db.query(AdminMessage).filter(
            AdminMessage.recipient_id == user.id,
            AdminMessage.sender_id == admin.id,
        ).order_by(AdminMessage.created_at.desc()).first()

        user_list.append({
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "display_name": user.profile.display_name if user.profile else user.username,
            "last_message": last_message.content[:50] if last_message else None,
            "last_message_time": last_message.created_at if last_message else None,
        })

    return sorted(user_list, key=lambda x: x['last_message_time'] or datetime.min, reverse=True)


@app.get("/admin/messages/user/{user_id}")
def get_user_messages(
    user_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(get_admin)
):
    """Get all messages between admin and a specific user"""
    messages = db.query(AdminMessage).filter(
        AdminMessage.recipient_id == user_id,
        AdminMessage.sender_id == admin.id,
    ).order_by(AdminMessage.created_at.asc()).all()

    return [MessageResponse.from_orm(msg) for msg in messages]


# ================================================================
#  USER MESSAGING
# ================================================================
class ContactAdminRequest(BaseModel):
    subject: str
    message: str


@app.get("/api/messages/admin")
def get_admin_messages(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """User gets all messages from admin"""
    messages = db.query(AdminMessage).filter(
        AdminMessage.recipient_id == current_user.id
    ).order_by(AdminMessage.created_at.desc()).all()

    return [MessageResponse.from_orm(msg) for msg in messages]


@app.post("/api/messages/contact-admin")
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
        is_read=False,
    )

    db.add(message)
    db.commit()
    db.refresh(message)

    return {
        "success": True,
        "message": "Your message has been sent to the admin",
        "message_id": message.id,
    }


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

@app.get("/health")
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


@app.get("/")
def health():
    return {"status": "ok"}

# Mount static files BEFORE the root mount (more specific routes first)
app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "../static")), name="files")

# Must be LAST — serves all remaining page templates
app.mount("/templates", StaticFiles(directory=TEMPLATES_DIR), name="templates")




