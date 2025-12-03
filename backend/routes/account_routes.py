from fastapi import APIRouter, HTTPException, status, Header
from typing import Optional, Dict, Any
from bson import ObjectId
from db.mongo import db

router = APIRouter(prefix="/api/account", tags=["account"])


def _get_user_id_from_auth(authorization: Optional[str]) -> str:
    if not authorization:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing Authorization header")
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != 'bearer':
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid Authorization header")
    token = parts[1]
    # dev token format: "user:<id>"
    if not token.startswith('user:'):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token format")
    return token.split(':', 1)[1]


def _find_user_by_id(id_str: str) -> Optional[Dict[str, Any]]:
    try:
        oid = ObjectId(id_str)
    except Exception:
        return None
    return db['users'].find_one({"_id": oid})


@router.get("/profile")
def get_profile(Authorization: Optional[str] = Header(None)):
    user_id = _get_user_id_from_auth(Authorization)
    user = _find_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    profile = {
        "id": str(user.get("_id")),
        "email": user.get("email"),
        "username": user.get("username"),
        "avatarUrl": user.get("avatarUrl") or f"https://i.pravatar.cc/150?u={user.get('email')}",
        "created_at": user.get("created_at"),
        "score": user.get("score", 0),
        "streaks": user.get("streaks", 0),
        "tier": user.get("tier", "starter")
    }
    return {"profile": profile}


@router.get("/wallet")
def get_wallet(Authorization: Optional[str] = Header(None)):
    user_id = _get_user_id_from_auth(Authorization)
    user = _find_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    # Wallet fields stored on user doc under `wallet` or create defaults
    wallet = user.get("wallet", {
        "balance": 0.0,
        "currency": "USD",
        "transactions": [],
    })

    # Normalize transaction IDs to strings
    txs = []
    for t in wallet.get("transactions", []):
        tx = dict(t)
        if tx.get("_id"):
            tx["id"] = str(tx.pop("_id"))
        txs.append(tx)
    wallet["transactions"] = txs

    return {"wallet": wallet}


@router.get("/settings")
def get_settings(Authorization: Optional[str] = Header(None)):
    user_id = _get_user_id_from_auth(Authorization)
    user = _find_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    settings = user.get("settings", {
        "email_notifications": True,
        "sms_notifications": False,
        "theme": "dark",
    })
    return {"settings": settings}


@router.get("/subscription")
def get_subscription(user_id: str):
    """Legacy endpoint for backward compatibility - redirects to /api/subscription/status"""
    try:
        user = _find_user_by_id(user_id)
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        
        return {
            "tier": user.get("tier", "starter"),
            "tier_level": user.get("tier", "starter"),  # Legacy field
            "status": "active"
        }
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.put("/settings")
def update_settings(payload: Dict[str, Any], Authorization: Optional[str] = Header(None)):
    user_id = _get_user_id_from_auth(Authorization)
    try:
        oid = ObjectId(user_id)
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid user id in token")

    # Only allow updating settings subdocument
    update = {"$set": {f"settings.{k}": v for k, v in payload.items()}}
    db['users'].update_one({"_id": oid}, update)
    user = db['users'].find_one({"_id": oid})
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found after update")
    return {"settings": user.get("settings", {})}
