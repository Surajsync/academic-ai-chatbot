from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, DateTime, Text
from sqlalchemy.orm import relationship
from datetime import datetime
from .database import Base


# ================= USERS =================

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True)
    email = Column(String(100), unique=True)
    hashed_password = Column(String)
    is_active = Column(Boolean, default=True)
    role = Column(String, default="user")  # admin, user

    conversations = relationship("Conversation", back_populates="user")


# ================= FAQ =================

class FAQ(Base):
    __tablename__ = "faqs"

    id = Column(Integer, primary_key=True, index=True)
    question = Column(Text)
    answer = Column(Text)
    keywords = Column(Text)
    embedding = Column(Text) 
    is_active = Column(Boolean, default=True)


# ================= CONVERSATIONS =================

class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="conversations")
    messages = relationship("Message", back_populates="conversation")


class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(Integer, ForeignKey("conversations.id"))
    role = Column(String)  # user / bot
    content = Column(Text)
    feedback = Column(String, nullable=True)  # 👍 / 👎
    timestamp = Column(DateTime, default=datetime.utcnow)

    conversation = relationship("Conversation", back_populates="messages")


# ================= FAILED QUERIES =================

class FailedQuery(Base):
    __tablename__ = "failed_queries"

    id = Column(Integer, primary_key=True)
    query_text = Column(Text, unique=True)
    frequency = Column(Integer, default=1)
    created_at = Column(DateTime, default=datetime.utcnow)


# ================= AUDIT LOG =================

class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True)
    user_email = Column(String)
    action = Column(Text)
    timestamp = Column(DateTime, default=datetime.utcnow)


# ================= SYSTEM SETTINGS =================

class SystemSetting(Base):
    __tablename__ = "system_settings"

    id = Column(Integer, primary_key=True)
    maintenance_mode = Column(Boolean, default=False)
    rate_limit_per_hour = Column(Integer, default=60)
    updated_at = Column(DateTime, default=datetime.utcnow)

# ================= PASSWORD RESET TOKENS =================

class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"

    id         = Column(Integer, primary_key=True)
    email      = Column(String(100), index=True)
    token      = Column(String(200), unique=True, index=True)
    expires_at = Column(DateTime)
    used       = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

#================= COLLEGE INFO =================
class Department(Base):
    __tablename__ = "departments"

    id = Column(Integer, primary_key=True)
    name = Column(String(100), unique=True)
    hod = Column(String(100))

#================= FEE STRUCTURE =================
class FeeStructure(Base):
    __tablename__ = "fee_structures"

    id = Column(Integer, primary_key=True, index=True)
    year = Column(Integer)
    amount = Column(Integer)
    branch = Column(String(50))


#================= CLUBS =================
class Club(Base):
    __tablename__ = "clubs"

    id = Column(Integer, primary_key=True)
    name = Column(String(100), unique=True)
    category = Column(String(50))
    description = Column(Text)


#================= PLACEMENTS =================
class Placement(Base):
    __tablename__ = "placements"

    id = Column(Integer, primary_key=True)
    student_name = Column(String(100))
    branch = Column(String(50))
    company_name = Column(String(100))
    package_lpa = Column(String(20), nullable=True)
    placement_year = Column(String(20))


#================= SCHOLARSHIP CELL =================
class ScholarshipCell(Base):
    __tablename__ = "scholarship_cells"

    id = Column(Integer, primary_key=True)
    name = Column(String(100))
    designation = Column(String(100))
    category = Column(String(100), nullable=True)
    contact_no = Column(String(20))
    email = Column(String(100), nullable=True)


print("FAQ MODEL LOADED")