"""
User Identity and Authentication Routes
Provides whoami endpoint for user identity verification
"""
from fastapi import APIRouter, Depends
from typing import Dict, Any
from middleware.auth import get_current_user, get_user_tier

router = APIRouter(prefix="/api", tags=["auth"])


@router.get("/whoami")
async def whoami(current_user: Dict[str, Any] = Depends(get_current_user)):
    """
    Get current authenticated user's information
    
    🔒 REQUIRES AUTHENTICATION
    
    Returns user profile with subscription tier and access levels.
    Used by frontend to initialize user context.
    """
    user_email = current_user.get("email")
    user_tier = get_user_tier(current_user)
    
    return {
        "user_id": str(current_user.get("_id")),
        "email": user_email,
        "username": current_user.get("username"),
        "tier": user_tier,
        "created_at": current_user.get("created_at"),
        "avatar_url": current_user.get("avatarUrl") or f"https://i.pravatar.cc/150?u={user_email}",
        "access": {
            "parlay_architect": user_tier in ["founder", "sharps_room", "elite", "pro"],
            "unlimited_parlays": user_tier in ["founder", "sharps_room"],
            "daily_best_cards": True,  # Available to all authenticated users
            "trust_loop": True,
            "command_center": True
        }
    }
