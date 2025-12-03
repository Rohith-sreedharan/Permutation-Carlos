"""
Authentication Middleware
Centralized auth dependency for FastAPI routes
"""
from fastapi import Header, HTTPException, status
from typing import Optional, Dict, Any
from bson import ObjectId
from db.mongo import db


def get_current_user(authorization: Optional[str] = Header(None)) -> Dict[str, Any]:
    """
    Extract and validate user from Authorization header.
    
    Token format: "Bearer user:<mongodb_object_id>"
    
    Returns:
        User document from MongoDB
        
    Raises:
        HTTPException: 401 if token is missing or invalid
    """
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header"
        )
    
    # Remove 'Bearer ' prefix
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != 'bearer':
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Authorization header format"
        )
    
    token = parts[1]
    
    # Parse simple token format 'user:<id>'
    if not token.startswith('user:'):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token format"
        )
    
    user_id = token.split(':', 1)[1]
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User ID not found in token"
        )
    
    # Look up user in database
    try:
        user = db.users.find_one({"_id": ObjectId(user_id)})
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid user ID format"
        )
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found"
        )
    
    return user


def get_user_tier(user: Dict[str, Any]) -> str:
    """
    Get user's subscription tier.
    
    Args:
        user: User document from MongoDB
        
    Returns:
        Tier string (founder, sharps_room, elite, pro, explorer, free)
    """
    # Check for active subscription
    subscription = db.subscriptions.find_one(
        {"user_id": user.get("email")},
        sort=[("created_at", -1)]
    )
    
    if subscription and subscription.get("status") == "active":
        return subscription.get("tier", "free").lower()
    
    # Fallback to user.tier field (legacy)
    return user.get("tier", "free").lower()


def get_current_user_optional(authorization: Optional[str] = Header(None)) -> Optional[Dict[str, Any]]:
    """
    Extract and validate user from Authorization header (optional).
    
    Token format: "Bearer user:<mongodb_object_id>"
    
    Returns:
        User document from MongoDB, or None if not authenticated
    """
    if not authorization:
        return None
    
    try:
        # Remove 'Bearer ' prefix
        parts = authorization.split()
        if len(parts) != 2 or parts[0].lower() != 'bearer':
            return None
        
        token = parts[1]
        
        # Parse simple token format 'user:<id>'
        if not token.startswith('user:'):
            return None
        
        user_id = token.split(':', 1)[1]
        if not user_id:
            return None
        
        # Look up user in database
        user = db.users.find_one({"_id": ObjectId(user_id)})
        return user
    except Exception:
        return None
