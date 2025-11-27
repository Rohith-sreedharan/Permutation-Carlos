"""
UGC Routes - Content Creator Bounties
Compliance Note: Content moderation happens during admin review phase.
URL-based submissions don't have captions/descriptions at submission time.
"""

from fastapi import APIRouter, HTTPException, Depends, Header, status
from typing import List, Optional
from pydantic import BaseModel, HttpUrl
from db.mongo import db
from services.ugc_service import UGCService, UGCSubmission, Platform, UGCStatus

router = APIRouter(prefix="/api/earn/ugc", tags=["ugc"])

ugc_service = UGCService(db)


def _get_user_from_auth(authorization: Optional[str] = Header(None)) -> dict:
    """Extract user from Authorization header"""
    if not authorization:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing Authorization header")
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != 'bearer':
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid Authorization header")
    token = parts[1]
    if not token.startswith('user:'):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token format")
    user_id = token.split(':', 1)[1]
    
    # Fetch user from DB
    from bson import ObjectId
    try:
        user = db['users'].find_one({"_id": ObjectId(user_id)})
        if not user:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
        return {
            "user_id": user_id,
            "email": user.get("email"),
            "role": user.get("role", "user")
        }
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid user ID")


class ContentSubmissionRequest(BaseModel):
    platform: Platform
    post_url: HttpUrl
    post_type: str
    views: Optional[int] = None
    engagement: Optional[float] = None


@router.post("/submit")
async def submit_ugc_content(
    submission: ContentSubmissionRequest,
    authorization: Optional[str] = Header(None)
):
    """
    User submits content for bounty review
    
    Example:
    ```json
    {
      "platform": "tiktok",
      "post_url": "https://tiktok.com/@user/video/123",
      "post_type": "reel",
      "views": 15000,
      "engagement": 0.08
    }
    ```
    """
    current_user = _get_user_from_auth(authorization)
    
    try:
        ugc_submission = UGCSubmission(
            user_id=current_user["user_id"],
            platform=submission.platform,
            post_url=submission.post_url,
            post_type=submission.post_type,
            views=submission.views,
            engagement=submission.engagement
        )
        
        result = ugc_service.submit_content(ugc_submission)
        return result
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Submission failed: {str(e)}")


@router.get("/history")
async def get_ugc_history(
    authorization: Optional[str] = Header(None),
    limit: int = 20
):
    """
    Get user's content submission history
    """
    current_user = _get_user_from_auth(authorization)
    
    try:
        submissions = ugc_service.get_user_submissions(
            user_id=current_user["user_id"],
            limit=limit
        )
        
        return {
            "count": len(submissions),
            "submissions": submissions
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/bounties")
async def get_active_bounties():
    """
    Get all active content bounty campaigns
    
    Returns:
    ```json
    {
      "count": 3,
      "bounties": [
        {
          "bounty_id": "bounty_tiktok_10k",
          "title": "$50 for 10k+ views on TikTok",
          "platform": "tiktok",
          "min_views": 10000,
          "payout_amount": 50.0,
          "slots_remaining": 15
        }
      ]
    }
    ```
    """
    try:
        bounties = ugc_service.get_active_bounties()
        
        return {
            "count": len(bounties),
            "bounties": bounties
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/balance")
async def get_ugc_balance(
    authorization: Optional[str] = Header(None)
):
    """
    Get user's UGC earnings balance
    
    Returns:
    ```json
    {
      "total_earned": 250.0,
      "total_submissions": 5,
      "payment_rail": "Whop"
    }
    ```
    """
    current_user = _get_user_from_auth(authorization)
    
    try:
        balance = ugc_service.get_user_balance(user_id=current_user["user_id"])
        return balance
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ADMIN ROUTES
class ApprovalRequest(BaseModel):
    submission_id: str
    payout_amount: float
    admin_notes: Optional[str] = None


@router.post("/admin/approve")
async def approve_ugc_submission(
    request: ApprovalRequest,
    authorization: Optional[str] = Header(None)
):
    """
    Admin approves submission and triggers Whop payout
    """
    current_user = _get_user_from_auth(authorization)
    
    # TODO: Add admin role check
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    try:
        result = ugc_service.approve_submission(
            submission_id=request.submission_id,
            payout_amount=request.payout_amount,
            admin_notes=request.admin_notes
        )
        return result
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class RejectionRequest(BaseModel):
    submission_id: str
    reason: str


@router.post("/admin/reject")
async def reject_ugc_submission(
    request: RejectionRequest,
    authorization: Optional[str] = Header(None)
):
    """
    Admin rejects submission
    """
    current_user = _get_user_from_auth(authorization)
    
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    try:
        result = ugc_service.reject_submission(
            submission_id=request.submission_id,
            reason=request.reason
        )
        return result
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/admin/pending")
async def get_pending_submissions(
    authorization: Optional[str] = Header(None),
    limit: int = 50
):
    """
    Admin: Get all pending submissions for review
    """
    current_user = _get_user_from_auth(authorization)
    
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    try:
        submissions = list(
            db["ugc_submissions"]
            .find({"status": UGCStatus.PENDING})
            .sort("submitted_at", 1)
            .limit(limit)
        )
        
        for sub in submissions:
            if "_id" in sub:
                sub["id"] = str(sub["_id"])
                del sub["_id"]
        
        return {
            "count": len(submissions),
            "submissions": submissions
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
