from fastapi import APIRouter, HTTPException, status, Depends
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime, timezone
import hashlib

from db.mongo import db


class UserRegistration(BaseModel):
    email: EmailStr
    password: str
    username: Optional[str]


router = APIRouter(prefix="/api", tags=["auth"])


def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


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
        "password_hash": hash_password(payload.password),
        "created_at": now,
    }

    res = users.insert_one(user_doc)
    # don't return password hash
    return {"status": "ok", "user_id": str(res.inserted_id), "email": payload.email}


@router.post("/token")
def token(form_data: OAuth2PasswordRequestForm = Depends()):
    # OAuth2PasswordRequestForm uses fields: username, password
    users = db["users"]
    user = users.find_one({"email": form_data.username})
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    if user.get("password_hash") != hash_password(form_data.password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    # Simple token for development: not a JWT, just a placeholder string
    token_value = f"user:{str(user.get('_id'))}"
    return {"access_token": token_value, "token_type": "bearer"}
