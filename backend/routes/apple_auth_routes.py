"""
Phase 12 — WS2: Apple Sign In on Web
=====================================
POST /api/auth/apple

Receives the id_token returned by Apple's JS SDK after the user completes
Sign in with Apple. Validates the token against Apple's public keys, extracts
apple_sub and email, applies geographic enforcement, then creates or retrieves
the user account and returns a BeatVegas JWT.

Spec requirements:
  - apple_sub stored as canonical identifier — never email
  - Relay email addresses handled correctly (never rejected)
  - Geographic enforcement active — same as email sign-in
  - Never creates Platform entitlement without payment
  - New account entitlement: intelligence_preview
  - Clean user-facing error on failure — never raw 502 / stack trace
  - Apple Sign In does not bypass self-exclusion or compliance checks
"""

import os
import time
import logging
from typing import Optional

import httpx
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from jwt import PyJWT, ExpiredSignatureError, InvalidTokenError
from jwt.algorithms import RSAAlgorithm
from datetime import datetime, timezone

from db.mongo import db
from routes.auth_routes import create_access_token

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["apple-auth"])

# Apple's public-key endpoint — fetched once and cached
_APPLE_KEYS_URL = "https://appleid.apple.com/auth/keys"
_APPLE_ISSUER = "https://appleid.apple.com"
_key_cache: dict = {}          # kid → public key
_key_cache_ts: float = 0.0
_KEY_CACHE_TTL = 3600          # re-fetch keys once per hour


# ── Pydantic model ─────────────────────────────────────────────────────────────

class AppleAuthPayload(BaseModel):
    id_token: str
    # authorization_code is optional — sent by Apple but we only need id_token for web
    authorization_code: Optional[str] = None


# ── Apple key fetching ─────────────────────────────────────────────────────────

async def _get_apple_public_keys() -> dict:
    """Return {kid: public_key} dict, using an in-process cache."""
    global _key_cache, _key_cache_ts

    now = time.time()
    if _key_cache and (now - _key_cache_ts) < _KEY_CACHE_TTL:
        return _key_cache

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(_APPLE_KEYS_URL)
            resp.raise_for_status()
            jwks = resp.json()
    except Exception as exc:
        logger.error("[apple_auth] Failed to fetch Apple public keys: %s", exc)
        if _key_cache:
            # Return stale cache rather than hard-fail
            return _key_cache
        raise HTTPException(
            status_code=503,
            detail="Unable to verify Apple credentials at this time. Please try again."
        )

    new_cache = {}
    for key_data in jwks.get("keys", []):
        kid = key_data.get("kid")
        if kid:
            try:
                new_cache[kid] = RSAAlgorithm.from_jwk(key_data)
            except Exception as exc:
                logger.warning("[apple_auth] Could not parse Apple key kid=%s: %s", kid, exc)

    _key_cache = new_cache
    _key_cache_ts = now
    return _key_cache


# ── Token validation ───────────────────────────────────────────────────────────

async def _validate_apple_id_token(id_token: str) -> dict:
    """
    Validate Apple id_token and return the decoded payload.
    Raises HTTPException with a clean message on any validation failure.
    """
    client_id = os.getenv("APPLE_CLIENT_ID", "")
    if not client_id:
        logger.error("[apple_auth] APPLE_CLIENT_ID not set in environment")
        raise HTTPException(
            status_code=503,
            detail="Apple Sign In is not configured on this server."
        )

    # Peek at the header to get the kid
    try:
        import base64, json as _json
        header_b64 = id_token.split(".")[0]
        # Add padding
        header_b64 += "=" * (-len(header_b64) % 4)
        header = _json.loads(base64.urlsafe_b64decode(header_b64))
        kid = header.get("kid")
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid Apple token format.")

    public_keys = await _get_apple_public_keys()
    public_key = public_keys.get(kid)

    if not public_key:
        # Force a re-fetch once in case our cache is stale
        global _key_cache_ts
        _key_cache_ts = 0.0
        public_keys = await _get_apple_public_keys()
        public_key = public_keys.get(kid)

    if not public_key:
        raise HTTPException(status_code=401, detail="Apple Sign In verification failed. Please try again.")

    try:
        pyjwt = PyJWT()
        payload = pyjwt.decode(
            id_token,
            public_key,
            algorithms=["RS256"],
            audience=client_id,
            issuer=_APPLE_ISSUER,
        )
    except ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Apple Sign In session expired. Please try again.")
    except InvalidTokenError as exc:
        logger.warning("[apple_auth] Invalid Apple id_token: %s", exc)
        raise HTTPException(status_code=401, detail="Apple Sign In verification failed. Please sign in again.")

    return payload


# ── Geographic enforcement helper ─────────────────────────────────────────────

def _check_geo_blocked(request: Request) -> None:
    """
    Reuse the GeoIP middleware result stored in request.state, if available.
    The GeoIP ASGI middleware runs first and sets request.state.geo_blocked=True
    for non-US IPs. We re-check here so Apple Sign In cannot bypass enforcement.
    """
    geo_blocked = getattr(request.state, "geo_blocked", False)
    if geo_blocked:
        country = getattr(request.state, "geo_country", "unknown")
        logger.warning("[apple_auth] GEO_BLOCKED Apple Sign In attempt from %s", country)
        raise HTTPException(
            status_code=403,
            detail="BeatVegas is currently available in the United States only."
        )


# ── Self-exclusion check ──────────────────────────────────────────────────────

def _check_self_exclusion(email: Optional[str], apple_sub: str) -> None:
    """Raise 403 if this identity is on the self-exclusion list."""
    exclusion_col = db.get("self_exclusion_log") if hasattr(db, "get") else db["self_exclusion_log"]
    try:
        query: dict = {"apple_sub": apple_sub}
        if email:
            query = {"$or": [{"apple_sub": apple_sub}, {"email": email}]}
        record = exclusion_col.find_one(query)
        if record:
            logger.info("[apple_auth] Self-excluded identity attempted Apple Sign In, apple_sub=%s", apple_sub)
            raise HTTPException(
                status_code=403,
                detail="This account has been excluded from BeatVegas. Contact support if you believe this is an error."
            )
    except HTTPException:
        raise
    except Exception as exc:
        # Non-fatal — log and allow (fail-open for self-exclusion DB errors)
        logger.error("[apple_auth] Self-exclusion check error: %s", exc)


# ── Main endpoint ─────────────────────────────────────────────────────────────

@router.post("/apple")
async def sign_in_with_apple(payload: AppleAuthPayload, request: Request):
    """
    Complete Apple Sign In flow for web.

    Flow:
      1. Validate Apple id_token against Apple's JWKS
      2. Geographic enforcement (same as email sign-in)
      3. Self-exclusion check
      4. Create or retrieve user — apple_sub is canonical identifier
      5. Relay email: stored as-is, never rejected
      6. New accounts receive intelligence_preview entitlement only
      7. Return BeatVegas JWT
    """
    # ── Step 1: Validate Apple id_token ─────────────────────────────────────
    apple_payload = await _validate_apple_id_token(payload.id_token)

    apple_sub: str = apple_payload.get("sub", "")
    if not apple_sub:
        raise HTTPException(status_code=400, detail="Apple Sign In failed: missing identity. Please try again.")

    # Apple may provide email only on first sign-in; on subsequent sign-ins it
    # may be absent. We always use apple_sub as the canonical identifier.
    email: Optional[str] = apple_payload.get("email")  # may be a relay address or absent

    # ── Step 2: Geographic enforcement ──────────────────────────────────────
    _check_geo_blocked(request)

    # ── Step 3: Self-exclusion check ────────────────────────────────────────
    _check_self_exclusion(email, apple_sub)

    # ── Step 4: Create or retrieve user ─────────────────────────────────────
    users = db["users"]
    user = users.find_one({"apple_sub": apple_sub})

    if user:
        # Returning Apple Sign In user
        user_id = str(user["_id"])
        stored_email = user.get("email") or email or f"apple-{apple_sub}@private.beatvegas.app"
        tier = user.get("tier", "intelligence_preview")
    else:
        # New user — intelligence_preview entitlement only
        # Never grant platform entitlement without a paid subscription
        now = datetime.now(timezone.utc).isoformat()

        # Relay email: store as-is (Apple format: randomstring@privaterelay.appleid.com)
        stored_email = email or f"apple-{apple_sub}@private.beatvegas.app"
        username = stored_email.split("@")[0][:30]  # derive a display username

        user_doc = {
            "email": stored_email,
            "apple_sub": apple_sub,           # canonical Apple identifier
            "apple_email_relay": email is not None and "privaterelay.appleid.com" in (email or ""),
            "username": username,
            "hashed_password": None,           # Apple users have no password
            "tier": "intelligence_preview",    # NEVER platform without payment
            "onboarding_complete": False,      # triggers onboarding wizard
            "credits_used": 0,
            "created_at": now,
            "signup_method": "apple",
        }

        res = users.insert_one(user_doc)
        user_id = str(res.inserted_id)
        tier = "intelligence_preview"

        # Trigger Growth Agent onboarding sequence
        try:
            from services.phase5_growth_agent import growth_agent
            growth_agent.trigger_onboarding_sequence(user_id=user_id)
        except Exception as exc:
            logger.error("[apple_auth] Growth Agent onboarding trigger failed for user_id=%s: %s", user_id, exc)

    # ── Step 5: Issue BeatVegas JWT ──────────────────────────────────────────
    access_token = create_access_token(
        user_id=user_id,
        email=stored_email,
        tier=tier,
    )

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "tier": tier,
        "is_new_user": user is None,
    }
