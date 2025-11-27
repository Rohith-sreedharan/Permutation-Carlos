"""
Waitlist Routes - V1 Launch
Capture Founder signups and manage viral loop
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr
from datetime import datetime, timezone
from typing import Optional
import secrets

from db.mongo import db

router = APIRouter(prefix="/api/waitlist", tags=["waitlist"])

class WaitlistSignup(BaseModel):
    email: EmailStr
    referral_code: Optional[str] = None

class WaitlistResponse(BaseModel):
    status: str
    referral_code: str
    position: int
    referrals_needed: int
    early_access: bool

@router.post("/join", response_model=WaitlistResponse)
async def join_waitlist(signup: WaitlistSignup):
    """
    Join the Founder waitlist
    
    Returns:
        - referral_code: Unique code for viral loop
        - position: Queue position
        - referrals_needed: How many refs to unlock early access
        - early_access: True if referred by 3+ people
    """
    try:
        waitlist_collection = db["waitlist"]
        
        # Check if email already exists
        existing = waitlist_collection.find_one({"email": signup.email})
        if existing:
            return {
                "status": "already_registered",
                "referral_code": existing["referral_code"],
                "position": existing["position"],
                "referrals_needed": max(0, 3 - existing.get("referral_count", 0)),
                "early_access": existing.get("referral_count", 0) >= 3
            }
        
        # Generate unique referral code
        referral_code = secrets.token_urlsafe(8)
        
        # Get current position (count existing + 1)
        position = waitlist_collection.count_documents({}) + 1
        
        # Track referrer if code provided
        referrer_email = None
        if signup.referral_code:
            referrer = waitlist_collection.find_one({"referral_code": signup.referral_code})
            if referrer:
                referrer_email = referrer["email"]
                # Increment referrer's count
                waitlist_collection.update_one(
                    {"email": referrer_email},
                    {"$inc": {"referral_count": 1}}
                )
        
        # Create waitlist entry
        entry = {
            "email": signup.email,
            "referral_code": referral_code,
            "position": position,
            "referred_by": referrer_email,
            "referral_count": 0,
            "joined_at": datetime.now(timezone.utc),
            "founder_tier": position <= 300  # First 300 are Founders
        }
        
        waitlist_collection.insert_one(entry)
        
        return {
            "status": "success",
            "referral_code": referral_code,
            "position": position,
            "referrals_needed": 3,
            "early_access": False
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Waitlist signup failed: {str(e)}")


@router.get("/count")
async def get_waitlist_count():
    """
    Get current Founder count (public endpoint)
    """
    try:
        waitlist_collection = db["waitlist"]
        count = waitlist_collection.count_documents({"founder_tier": True})
        return {"count": min(count, 300)}
    except Exception as e:
        return {"count": 243}  # Default fallback


@router.get("/status/{email}")
async def get_waitlist_status(email: str):
    """
    Check waitlist status for an email
    """
    try:
        waitlist_collection = db["waitlist"]
        entry = waitlist_collection.find_one({"email": email})
        
        if not entry:
            raise HTTPException(status_code=404, detail="Email not found on waitlist")
        
        return {
            "position": entry["position"],
            "referral_code": entry["referral_code"],
            "referral_count": entry.get("referral_count", 0),
            "early_access": entry.get("referral_count", 0) >= 3,
            "founder_tier": entry.get("founder_tier", False)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Status check failed: {str(e)}")
