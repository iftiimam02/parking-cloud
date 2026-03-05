import os
from datetime import datetime, timedelta

from jose import jwt, JWTError
from passlib.context import CryptContext
from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer

JWT_SECRET = os.getenv("JWT_SECRET", "devsecret")
ALGO = "HS256"
ACCESS_TOKEN_MINUTES = 60 * 24  # 24h

# Use PBKDF2 instead of bcrypt (works reliably on Windows/Python 3.13)
pwd = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")
oauth2 = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

def hash_pw(p: str) -> str:
    # Optional: basic password length sanity
    if len(p) < 4:
        raise HTTPException(status_code=400, detail="Password too short.")
    return pwd.hash(p)

def verify_pw(p: str, h: str) -> bool:
    return pwd.verify(p, h)

def create_token(user_id: int) -> str:
    exp = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_MINUTES)
    return jwt.encode({"sub": str(user_id), "exp": exp}, JWT_SECRET, algorithm=ALGO)

def get_user_id_from_token(token: str = Depends(oauth2)) -> int:
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[ALGO])
        return int(payload["sub"])
    except (JWTError, KeyError, ValueError):
        raise HTTPException(status_code=401, detail="Invalid token")