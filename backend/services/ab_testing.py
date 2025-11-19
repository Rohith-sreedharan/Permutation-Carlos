"""
A/B Testing Middleware
Server-side A/B test bucketing with 90-day cookie persistence
"""
import secrets
import hashlib
from typing import Literal, Optional
from fastapi import Request, Response
from datetime import datetime, timezone, timedelta


# Variant weights (equal distribution)
VARIANTS: list[Literal["A", "B", "C", "D", "E"]] = ["A", "B", "C", "D", "E"]
VARIANT_WEIGHTS = [0.2, 0.2, 0.2, 0.2, 0.2]  # 20% each

COOKIE_NAME = "bv_var"
COOKIE_MAX_AGE = 90 * 24 * 60 * 60  # 90 days in seconds


def assign_variant(session_id: str) -> Literal["A", "B", "C", "D", "E"]:
    """
    Deterministic variant assignment based on session_id hash
    Ensures consistent experience across 90-day window
    """
    # Hash session_id to get deterministic 0-1 value
    hash_obj = hashlib.sha256(session_id.encode())
    hash_int = int(hash_obj.hexdigest(), 16)
    hash_normalized = (hash_int % 100) / 100.0  # 0.00 to 0.99
    
    # Assign variant based on hash
    cumulative = 0.0
    for variant, weight in zip(VARIANTS, VARIANT_WEIGHTS):
        cumulative += weight
        if hash_normalized < cumulative:
            return variant
    
    return "A"  # Fallback (should never reach)


def get_or_create_session(request: Request, response: Response) -> tuple[str, str]:
    """
    Get existing session from cookie or create new one
    Returns: (session_id, variant)
    """
    # Try to get existing session from cookie
    session_id = request.cookies.get(COOKIE_NAME)
    
    if session_id:
        # Parse session_id format: "sess_{random}_{variant}"
        parts = session_id.split("_")
        if len(parts) == 3 and parts[0] == "sess" and parts[2] in VARIANTS:
            variant = parts[2]
            return session_id, variant
    
    # Create new session
    random_id = secrets.token_urlsafe(16)
    variant = assign_variant(random_id)
    session_id = f"sess_{random_id}_{variant}"
    
    # Set cookie with 90-day expiry
    response.set_cookie(
        key=COOKIE_NAME,
        value=session_id,
        max_age=COOKIE_MAX_AGE,
        httponly=True,
        samesite="lax",
        secure=True  # HTTPS only in production
    )
    
    return session_id, variant


def extract_ref_param(request: Request) -> Optional[str]:
    """
    Extract affiliate ref parameter from URL
    Example: /?ref=AFF_12345
    """
    return request.query_params.get("ref")


async def ab_test_middleware(request: Request, call_next):
    """
    Middleware to handle A/B test bucketing and tracking
    """
    response = await call_next(request)
    
    # Only process for non-API routes (frontend pages)
    if not request.url.path.startswith("/api/"):
        session_id, variant = get_or_create_session(request, response)
        
        # Store in request state for use in route handlers
        request.state.session_id = session_id
        request.state.variant = variant
        request.state.ref = extract_ref_param(request)
    
    return response
