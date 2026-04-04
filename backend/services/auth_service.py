from sqlalchemy.orm import Session
from backend.database.models import User
from backend.security.security import hash_password, verify_password
from jose import jwt
from datetime import datetime, timedelta
from backend.config import settings

SECRET_KEY = settings.SECRET_KEY
ALGORITHM = settings.JWT_ALGORITHM
ACCESS_TOKEN_EXPIRE_MINUTES = settings.ACCESS_TOKEN_EXPIRE_MINUTES


def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def register_user(db: Session, username: str, email: str, password: str):

    existing = db.query(User).filter(User.email == email).first()

    if existing:
        return None

    user = User(
        username=username,
        email=email,
        hashed_password=hash_password(password),
        role="user"
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    return user


def authenticate_user(db: Session, email: str, password: str):

    user = db.query(User).filter(User.email == email).first()

    if not user:
        return None

    if not verify_password(password, user.hashed_password):
        return None

    return user