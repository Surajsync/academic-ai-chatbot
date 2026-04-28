from backend.database.database import SessionLocal
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthCredential
from jose import jwt, JWTError
from backend.config import settings
from backend.database.models import User

SECRET_KEY = settings.SECRET_KEY
ALGORITHM = settings.JWT_ALGORITHM

# OAuth2 scheme for JWT
oauth2_scheme = HTTPBearer()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user(token: HTTPAuthCredential = Depends(oauth2_scheme), db = Depends(get_db)) -> User:
    """Extract and validate JWT token to get current user"""
    try:
        payload = jwt.decode(token.credentials, SECRET_KEY, algorithms=[ALGORITHM])
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
