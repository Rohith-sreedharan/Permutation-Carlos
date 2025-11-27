"""
UGC (User Generated Content) Service - Whop Payment Rail
Manages content creator bounties and payouts via Whop API
"""

from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, HttpUrl
from enum import Enum
import os
import requests


class Platform(str, Enum):
    TIKTOK = "tiktok"
    INSTAGRAM = "instagram"
    YOUTUBE = "youtube"
    TWITTER = "twitter"


class UGCStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    PAID = "paid"


class UGCSubmission(BaseModel):
    user_id: str
    platform: Platform
    post_url: HttpUrl
    post_type: str  # "reel", "video", "story", "post"
    views: Optional[int] = None
    engagement: Optional[float] = None  # likes + comments / views
    payout_amount: float = 0.0
    status: UGCStatus = UGCStatus.PENDING
    review_notes: Optional[str] = None
    submitted_at: datetime = datetime.now(timezone.utc)
    reviewed_at: Optional[datetime] = None
    paid_at: Optional[datetime] = None
    whop_transaction_id: Optional[str] = None


class UGCBounty(BaseModel):
    """Active content bounty campaigns"""
    bounty_id: str
    title: str
    description: str
    platform: Platform
    min_views: int
    payout_amount: float
    active_until: datetime
    total_slots: int
    claimed_slots: int = 0


class WhopPaymentService:
    """
    Whop Payment Integration
    https://docs.whop.com/api-reference
    """
    
    def __init__(self):
        self.api_key = os.getenv("WHOP_API_KEY")
        self.base_url = "https://api.whop.com/v1"
        
    def create_payout(self, user_id: str, amount: float, memo: str) -> Dict[str, Any]:
        """
        Create a payout to user via Whop
        
        Returns:
            {"transaction_id": "...", "status": "pending", "amount": 50.0}
        """
        if not self.api_key:
            raise ValueError("WHOP_API_KEY not configured")
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "user_id": user_id,
            "amount_cents": int(amount * 100),  # Convert to cents
            "currency": "USD",
            "memo": memo,
            "payout_method": "instant"  # or "ach", "check"
        }
        
        try:
            response = requests.post(
                f"{self.base_url}/payouts",
                headers=headers,
                json=payload,
                timeout=10
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            raise Exception(f"Whop API error: {str(e)}")


class UGCService:
    """
    UGC Management Service
    Handles content submissions, approvals, and payouts
    """
    
    def __init__(self, db):
        self.db = db
        self.whop = WhopPaymentService()
    
    def submit_content(self, submission: UGCSubmission) -> Dict[str, Any]:
        """
        User submits content for bounty
        """
        submission_dict = submission.dict()
        submission_dict["_id"] = f"ugc_{submission.user_id}_{int(datetime.now(timezone.utc).timestamp())}"
        submission_dict["post_url"] = str(submission.post_url)  # Convert HttpUrl to string
        submission_dict["submitted_at"] = submission.submitted_at.isoformat()
        
        self.db["ugc_submissions"].insert_one(submission_dict)
        
        return {
            "success": True,
            "submission_id": submission_dict["_id"],
            "status": submission.status,
            "message": "Content submitted successfully. Our team will review within 24-48 hours."
        }
    
    def get_user_submissions(self, user_id: str, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Get all submissions by user
        """
        submissions = list(
            self.db["ugc_submissions"]
            .find({"user_id": user_id})
            .sort("submitted_at", -1)
            .limit(limit)
        )
        
        # Remove MongoDB _id for JSON serialization
        for sub in submissions:
            if "_id" in sub:
                sub["id"] = str(sub["_id"])
                del sub["_id"]
        
        return submissions
    
    def approve_submission(
        self, 
        submission_id: str, 
        payout_amount: float,
        admin_notes: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Admin approves submission and triggers payout
        """
        submission = self.db["ugc_submissions"].find_one({"_id": submission_id})
        if not submission:
            raise ValueError(f"Submission {submission_id} not found")
        
        # Update status to approved
        self.db["ugc_submissions"].update_one(
            {"_id": submission_id},
            {
                "$set": {
                    "status": UGCStatus.APPROVED,
                    "payout_amount": payout_amount,
                    "review_notes": admin_notes,
                    "reviewed_at": datetime.now(timezone.utc).isoformat()
                }
            }
        )
        
        # Trigger Whop payout
        try:
            payout_result = self.whop.create_payout(
                user_id=submission["user_id"],
                amount=payout_amount,
                memo=f"UGC Bounty Payment - {submission['platform']} content"
            )
            
            # Mark as paid
            self.db["ugc_submissions"].update_one(
                {"_id": submission_id},
                {
                    "$set": {
                        "status": UGCStatus.PAID,
                        "paid_at": datetime.now(timezone.utc).isoformat(),
                        "whop_transaction_id": payout_result.get("transaction_id")
                    }
                }
            )
            
            return {
                "success": True,
                "submission_id": submission_id,
                "payout_amount": payout_amount,
                "transaction_id": payout_result.get("transaction_id"),
                "message": f"Paid ${payout_amount} to user via Whop"
            }
            
        except Exception as e:
            # Rollback approval if payout fails
            self.db["ugc_submissions"].update_one(
                {"_id": submission_id},
                {"$set": {"status": UGCStatus.PENDING, "review_notes": f"Payment failed: {str(e)}"}}
            )
            raise Exception(f"Payout failed: {str(e)}")
    
    def reject_submission(self, submission_id: str, reason: str) -> Dict[str, Any]:
        """
        Admin rejects submission
        """
        self.db["ugc_submissions"].update_one(
            {"_id": submission_id},
            {
                "$set": {
                    "status": UGCStatus.REJECTED,
                    "review_notes": reason,
                    "reviewed_at": datetime.now(timezone.utc).isoformat()
                }
            }
        )
        
        return {
            "success": True,
            "submission_id": submission_id,
            "message": "Submission rejected"
        }
    
    def get_active_bounties(self) -> List[Dict[str, Any]]:
        """
        Get all active bounty campaigns
        """
        bounties = list(
            self.db["ugc_bounties"]
            .find({
                "active_until": {"$gte": datetime.now(timezone.utc).isoformat()},
                "$expr": {"$lt": ["$claimed_slots", "$total_slots"]}
            })
        )
        
        for bounty in bounties:
            if "_id" in bounty:
                bounty["id"] = str(bounty["_id"])
                del bounty["_id"]
        
        return bounties
    
    def get_user_balance(self, user_id: str) -> Dict[str, Any]:
        """
        Get user's total UGC earnings
        """
        pipeline = [
            {
                "$match": {
                    "user_id": user_id,
                    "status": UGCStatus.PAID
                }
            },
            {
                "$group": {
                    "_id": None,
                    "total_earned": {"$sum": "$payout_amount"},
                    "total_submissions": {"$sum": 1}
                }
            }
        ]
        
        result = list(self.db["ugc_submissions"].aggregate(pipeline))
        
        if result:
            return {
                "total_earned": result[0]["total_earned"],
                "total_submissions": result[0]["total_submissions"],
                "payment_rail": "Whop"
            }
        
        return {
            "total_earned": 0.0,
            "total_submissions": 0,
            "payment_rail": "Whop"
        }
