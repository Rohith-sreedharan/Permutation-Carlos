"""
auth_service.py — Shared auth helpers for internal service use.

Provides get_user_from_token_safe(), a non-raising wrapper around JWT decode
that returns the user_id string on success or None on any failure.

Used by route handlers that need to resolve a user_id from a Bearer token
without going through the FastAPI dependency injection chain.
"""
import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)


def get_user_from_token_safe(token: str) -> Optional[str]:
    """
    Decode a JWT Bearer token and return the `sub` claim (user_id).

    Returns None on any failure — expired, invalid signature, missing claim, etc.
    Never raises an exception; callers handle the None case as 401.

    Mirrors the validation logic in middleware/auth.py _validate_jwt()
    but returns None instead of raising HTTPException.
    """
    if not token or token.count(".") != 2:
        return None

    secret = os.getenv("JWT_SECRET_KEY", "")
    if not secret:
        logger.error("[auth_service] JWT_SECRET_KEY not set — cannot validate token")
        return None

    try:
        import jwt  # PyJWT
        from config.agent_config import AGENT_CONFIG

        algorithm = AGENT_CONFIG.get("auth", {}).get("jwt_algorithm", "HS256")
        payload = jwt.decode(token, secret, algorithms=[algorithm])
        user_id = payload.get("sub")
        if not user_id:
            logger.warning("[auth_service] Token missing sub claim")
            return None
        return str(user_id)
    except Exception as exc:
        logger.debug("[auth_service] Token validation failed: %s", type(exc).__name__)
        return None
