"""
Authentication & Authorization Middleware — Phase 2A.2

Validates Bearer tokens. Supports:
  1. JWT (HS256, signed with JWT_SECRET_KEY) — primary format post-Phase 2
  2. Legacy 'user:<id>' format — accepted during transition, logs a deprecation warning

JWT claims validated: exp (expiry enforced, no grace period), sub (user_id).
Expired sessions are rejected immediately — no grace period.
No plaintext secrets are ever written to logs.
"""
import logging
import os
from typing import Optional, Dict, Any

from bson import ObjectId
from fastapi import Depends, Header, HTTPException, status

from db.mongo import db

logger = logging.getLogger(__name__)


def _validate_jwt(token: str) -> Dict[str, Any]:
    """
    Validate a JWT access token and return its payload.
    Raises HTTPException 401 on any failure (expired, invalid signature, bad format).
    Secret is read from env — never logged.
    """
    secret = os.getenv("JWT_SECRET_KEY", "")
    if not secret:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Server misconfiguration: JWT_SECRET_KEY not set",
        )
    try:
        import jwt  # PyJWT
        from config.agent_config import AGENT_CONFIG

        algorithm = AGENT_CONFIG.get("auth", {}).get("jwt_algorithm", "HS256")
        payload = jwt.decode(token, secret, algorithms=[algorithm])
        return payload
    except Exception as exc:
        # Classify the error for the client without leaking internals
        exc_name = type(exc).__name__
        if "Expired" in exc_name or "expired" in str(exc).lower():
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Session expired. Please log in again.",
            )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or malformed token.",
        )


def _resolve_user_from_id(user_id: str) -> Dict[str, Any]:
    try:
        user = db.users.find_one({"_id": ObjectId(user_id)})
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid user ID format",
        )
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )
    return user


def _parse_token(authorization: Optional[str]) -> Optional[str]:
    """Extract raw token string from 'Bearer <token>' header."""
    if not authorization:
        return None
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None
    return parts[1]


def get_current_user(authorization: Optional[str] = Header(None)) -> Dict[str, Any]:
    """
    Validate Bearer token and return the authenticated user document.

    Accepts JWT (primary) or legacy user:<id> (deprecated).
    Raises 401 on missing / invalid / expired token — no grace period.
    """
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header",
        )

    token = _parse_token(authorization)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Authorization header format",
        )

    # ── JWT path ─────────────────────────────────────────────────────────────
    if token.count(".") == 2:
        payload = _validate_jwt(token)
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token missing subject claim",
            )
        return _resolve_user_from_id(user_id)

    # ── Legacy user:<id> path (transition period only) ───────────────────────
    if token.startswith("user:"):
        logger.warning(
            "[Auth] Legacy user:<id> token in use — client should upgrade to JWT"
        )
        user_id = token.split(":", 1)[1]
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User ID not found in token",
            )
        return _resolve_user_from_id(user_id)

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid token format",
    )


def get_user_tier(user: Dict[str, Any]) -> str:
    """
    Get user's subscription tier.

    Returns:
        Tier string (founder, sharps_room, elite, pro, explorer, free)
    """
    subscription = db.subscriptions.find_one(
        {"user_id": user.get("email")},
        sort=[("created_at", -1)],
    )

    if subscription and subscription.get("status") == "active":
        return subscription.get("tier", "free").lower()

    return user.get("tier", "free").lower()


def get_current_user_optional(authorization: Optional[str] = Header(None)) -> Optional[Dict[str, Any]]:
    """Non-raising variant — returns None if auth is absent or invalid."""
    if not authorization:
        return None
    try:
        return get_current_user(authorization)
    except HTTPException:
        return None

            return None
        
        # Look up user in database
        user = db.users.find_one({"_id": ObjectId(user_id)})
        return user
    except Exception:
        return None


# Additional auth dependencies for route protection
async def require_user(user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    """Require authenticated user"""
    return user


async def require_sharp_pass(user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    """Require Sharp Pass status"""
    if not user.get("sharp_pass_active"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Sharp Pass required"
        )
    return user


async def require_wire_pro(user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    """Require Wire Pro subscription"""
    tier = get_user_tier(user)
    if tier not in ["founder", "sharps_room", "elite"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Wire Pro subscription required (ELITE, SHARPS_ROOM, or FOUNDER)"
        )
    return user


async def require_admin(user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    """Require admin role"""
    if not user.get("is_admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    return user


async def require_simsports(user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    """Require SimSports API access"""
    if not user.get("simsports_active"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="SimSports API access required"
        )
    return user

