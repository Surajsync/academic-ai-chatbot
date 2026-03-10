# ================================================================
#  REC Bijnor Academic AI  —  Main Application
#  Run from:  chatbot_project/backend/
#  Command:   uvicorn app:app --reload
# ================================================================

import random
import time
import secrets
import smtplib
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

from database.database import SessionLocal, engine
from database.models import Base, User, Conversation, Message, FAQ, FailedQuery, AuditLog, SystemSetting, PasswordResetToken
from security.security import hash_password, verify_password
from services.auth_service import create_access_token
from services.chatbot_service import generate_reply


# ================================================================
#  APP INIT
# ================================================================
Base.metadata.create_all(bind=engine)

app = FastAPI(title="REC Bijnor Academic AI")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ================================================================
#  CONFIG  ← Edit these before running
# ================================================================
SECRET_KEY   = "secret_key_for_jwt_token_generation"
ALGORITHM    = "HS256"

GMAIL_ADDRESS           = "suraj.it.22061@recb.ac.in"  
GMAIL_APP_PASSWORD      = "udru lmqy wdpz jjcs"  
RESET_TOKEN_EXPIRE_MINS = 15
APP_BASE_URL            = "http://127.0.0.1:8000"       # ← change to LAN IP for mobile testing

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
        return user
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")


def get_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


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

class FaqCreate(BaseModel):
    keyword: str
    response: str


# ================================================================
#  EMAIL HELPER
# ================================================================
def send_email(to: str, subject: str, body: str):
    """Send email via Gmail SMTP. Raises HTTPException on failure."""
    try:
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
    user = db.query(User).filter(User.email == form_data.username).first()

    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    token = create_access_token({"sub": user.email})
    return {
        "access_token": token,
        "token_type":   "bearer",
        "role":         user.role,
        "username":     user.username
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

    reply = generate_reply(db, request.message)

    db.add(Message(conversation_id=conversation.id, role="bot", content=reply))
    db.commit()

    # Track unanswered questions
    if "Sorry" in reply:
        fq = db.query(FailedQuery).filter(FailedQuery.query_text == request.message).first()
        if fq:
            fq.frequency += 1
        else:
            db.add(FailedQuery(query_text=request.message))
        db.commit()

    return {"reply": reply}


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


# ================================================================
#  ADMIN — FAQs
# ================================================================
@app.get("/admin/faqs")
def get_faqs(db: Session = Depends(get_db), admin: User = Depends(get_admin)):
    return db.query(FAQ).order_by(FAQ.id).all()


@app.post("/admin/faqs")
def add_faq(data: FaqCreate, db: Session = Depends(get_db), admin: User = Depends(get_admin)):
    faq = FAQ(keyword=data.keyword, response=data.response)
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

    keyword_preview = faq.keyword[:60]
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

    old_role  = user.role
    user.role = data.role
    db.commit()

    db.add(AuditLog(
        user_email = admin.email,
        action     = f"Changed role of {user.email} from {old_role} to {data.role}"
    ))
    db.commit()

    return {"message": f"Role updated to {data.role}"}


# ================================================================
#  STATIC FILES
#  IMPORTANT: Explicit routes must come BEFORE app.mount()
# ================================================================
@app.get("/logo.png")
def serve_logo():
    return FileResponse("../assests/logo.png")

@app.get("/")
def home():
    return FileResponse("../templates/auth_ui.html")

@app.get("/auth_ui.html")
def auth_ui_html():
    return FileResponse("../templates/auth_ui.html")

@app.get("/admin_ui.html")
def admin_ui_html():
    return FileResponse("../templates/admin_ui.html")

@app.get("/chat_ui.html")
def chat_ui_html():
    return FileResponse("../templates/chat_ui.html")

@app.get("/reset_password.html")
def reset_password_html():
    return FileResponse("../templates/reset_password.html")

# Must be LAST — serves all remaining static assets
app.mount("/", StaticFiles(directory="../templates"), name="static")