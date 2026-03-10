from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(password: str):
    password = password[:72]  # FIX: bcrypt hard limit is 72 bytes
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str):
    plain_password = plain_password[:72]  # FIX: must match truncation used during hashing
    return pwd_context.verify(plain_password, hashed_password)