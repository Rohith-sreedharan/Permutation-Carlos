from fastapi import APIRouter, HTTPException, status, Depends
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime, timezone
import bcrypt

from db.mongo import db


class UserRegistration(BaseModel):
    email: EmailStr
    password: str
    username: Optional[str]


router = APIRouter(prefix="/api", tags=["auth"])


def hash_password(password: str) -> str:
    """Hash password using bcrypt directly."""
    # Bcrypt has a 72-byte limit, truncate if necessary
    password_bytes = password.encode('utf-8')[:72]
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password_bytes, salt)
    return hashed.decode('utf-8')


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify password against bcrypt hash."""
    # Bcrypt has a 72-byte limit, truncate if necessary
    password_bytes = plain_password.encode('utf-8')[:72]
    hashed_bytes = hashed_password.encode('utf-8')
    return bcrypt.checkpw(password_bytes, hashed_bytes)


@router.post("/auth/register")
def register_user(payload: UserRegistration):
    users = db["users"]
    existing = users.find_one({"email": payload.email})
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User already exists")

    now = datetime.now(timezone.utc).isoformat()
    user_doc = {
        "email": payload.email,
        "username": payload.username or payload.email.split("@")[0],
        "hashed_password": hash_password(payload.password),  # Use bcrypt
        "created_at": now,
    }

    res = users.insert_one(user_doc)
    return {"status": "ok", "user_id": str(res.inserted_id), "email": payload.email}


@router.post("/token")
def token(form_data: OAuth2PasswordRequestForm = Depends()):
    users = db["users"]
    user = users.find_one({"email": form_data.username})
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    # Check both old field name (password_hash) and new field name (hashed_password)
    stored_hash = user.get("hashed_password") or user.get("password_hash")
    if not stored_hash:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    
    # Verify password using bcrypt
    if not verify_password(form_data.password, stored_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    # Simple token for development: not a JWT, just a placeholder string
    token_value = f"user:{str(user.get('_id'))}"
    return {"access_token": token_value, "token_type": "bearer"}
