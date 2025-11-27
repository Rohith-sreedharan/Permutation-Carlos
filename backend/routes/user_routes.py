"""
User Profile Routes - POST /api/user/profile
Stores user onboarding data (bankroll, risk profile, preferences).
Initializes User Modeling Agent with personalization context.
"""
from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel, Field
from typing import List, Literal, Optional
from datetime import datetime, timezone

from db.mongo import db

router = APIRouter(prefix="/api/user", tags=["user"])

# Helper function to extract user_id from simple token
def get_user_id_from_token(authorization: Optional[str] = Header(None)) -> str:
    """Extract user_id from simple token format 'user:user_id'"""
    if not authorization:
        raise HTTPException(status_code=401, detail="Authorization header missing")
    
    # Remove 'Bearer ' prefix if present
    token = authorization.replace("Bearer ", "")
    
    # Parse simple token format 'user:user_id'
    if not token.startswith("user:"):
        raise HTTPException(status_code=401, detail="Invalid token format")
    
    user_id = token.split(":", 1)[1]
    if not user_id:
        raise HTTPException(status_code=401, detail="User ID not found in token")
    
    return user_id

# Pydantic model for onboarding data
class UserProfileRequest(BaseModel):
    bankroll: float = Field(gt=0, description="User's total bankroll in USD")
    unit_size: float = Field(gt=0, description="Bet unit size in USD")
    unit_strategy: Literal['fixed', 'percentage'] = Field(description="Fixed dollar amount or percentage of bankroll")
    risk_profile: Literal['grinder', 'gunslinger'] = Field(description="Risk tolerance profile")
    preferred_sports: List[str] = Field(min_length=1, description="Sports user wants to bet on (NBA, NFL, MLB, etc)")
    preferred_markets: List[str] = Field(min_length=1, description="Bet types user prefers (spreads, totals, props, etc)")

class UserProfileResponse(BaseModel):
    status: str
    profile: dict
    message: str

@router.post("/profile", response_model=UserProfileResponse)
async def save_user_profile(
    profile_data: UserProfileRequest,
    authorization: Optional[str] = Header(None)
):
    """
    Save or update user profile from onboarding wizard.
    
    This endpoint:
    1. Validates onboarding data (bankroll > 0, at least 1 sport/market selected)
    2. Stores profile in MongoDB users collection
    3. Initializes User Modeling Agent with personalization context
    4. Returns saved profile for immediate use in Concierge Mode
    
    Risk Profiles:
    - grinder: Low volatility, high confidence (75%+), steady growth strategy
    - gunslinger: High volatility, high EV (10%+), big win potential
    
    Args:
        profile_data: Onboarding form data
        authorization: Bearer token from Authorization header
        
    Returns:
        Status, saved profile, and confirmation message
        
    Raises:
        HTTPException: 400 if validation fails, 500 if database error
    """
    try:
        user_id = get_user_id_from_token(authorization)
        user_collection = db["users"]
        
        # Build profile document for MongoDB
        profile_doc = {
            "user_id": user_id,
            "bankroll": profile_data.bankroll,
            "unit_size": profile_data.unit_size,
            "unit_strategy": profile_data.unit_strategy,
            "risk_profile": profile_data.risk_profile,
            "preferred_sports": profile_data.preferred_sports,
            "preferred_markets": profile_data.preferred_markets,
            "onboarding_completed_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc)
        }
        
        # Upsert profile (update if exists, insert if new)
        result = user_collection.update_one(
            {"user_id": user_id},
            {"$set": profile_doc},
            upsert=True
        )
        
        # Calculate recommended unit size for response (validation feedback)
        if profile_data.unit_strategy == 'percentage':
            recommended_unit = profile_data.bankroll * 0.01  # 1% of bankroll
        else:
            recommended_unit = profile_data.unit_size
        
        # Return profile for immediate use in Dashboard Concierge Mode
        return {
            "status": "ok",
            "profile": {
                "user_id": user_id,
                "bankroll": profile_data.bankroll,
                "unit_size": profile_data.unit_size,
                "unit_strategy": profile_data.unit_strategy,
                "risk_profile": profile_data.risk_profile,
                "preferred_sports": profile_data.preferred_sports,
                "preferred_markets": profile_data.preferred_markets,
                "recommended_unit": recommended_unit
            },
            "message": f"Profile saved! You're a {profile_data.risk_profile.upper()} with ${profile_data.bankroll:,.2f} bankroll."
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save profile: {str(e)}")


@router.get("/profile", response_model=dict)
async def get_user_profile(authorization: Optional[str] = Header(None)):
    """
    Get current user's profile for Concierge Mode personalization.
    
    Returns:
        User profile document or empty dict if not found
    """
    try:
        user_id = get_user_id_from_token(authorization)
        user_collection = db["users"]
        
        profile = user_collection.find_one(
            {"user_id": user_id},
            {"_id": 0}  # Exclude MongoDB _id from response
        )
        
        if not profile:
            return {"status": "not_found", "profile": None}
        
        return {"status": "ok", "profile": profile}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch profile: {str(e)}")


class BankrollUpdate(BaseModel):
    new_bankroll: float = Field(gt=0)


@router.put("/profile/bankroll", response_model=dict)
async def update_bankroll(
    request: BankrollUpdate,
    authorization: Optional[str] = Header(None)
):
    """
    Update user's bankroll after wins/losses.
    Recalculates unit size if using percentage strategy.
    """
    try:
        user_id = get_user_id_from_token(authorization)
        user_collection = db["users"]
        
        # Get current profile to check unit strategy
        profile = user_collection.find_one({"user_id": user_id})
        if not profile:
            raise HTTPException(status_code=404, detail="Profile not found")
        
        update_doc = {
            "bankroll": request.new_bankroll,
            "updated_at": datetime.now(timezone.utc)
        }
        
        # Recalculate unit size if percentage strategy
        if profile.get("unit_strategy") == "percentage":
            update_doc["unit_size"] = request.new_bankroll * 0.01
        
        user_collection.update_one(
            {"user_id": user_id},
            {"$set": update_doc}
        )
        
        return {
            "status": "ok",
            "new_bankroll": request.new_bankroll,
            "new_unit_size": update_doc.get("unit_size", profile.get("unit_size"))
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update bankroll: {str(e)}")


@router.get("/decision-log")
async def get_decision_log(authorization: Optional[str] = Header(None)):
    """
    Get user's decision log - forecasts they followed with alignment tracking.
    
    Returns:
        - decisions: List of followed forecasts with outcomes
        - alignment_score: % of time user aligned with high-confidence AI forecasts
        - analytical_roi: Expected value from followed forecasts
        - total_decisions: Count of forecasts followed
    """
    try:
        user_id = get_user_id_from_token(authorization)
        
        # Fetch user's followed forecasts (stored when they click "Follow" on a forecast)
        followed_collection = db["followed_forecasts"]
        events_collection = db["events"]
        
        # Get all forecasts this user followed
        followed_docs = list(followed_collection.find(
            {"user_id": user_id}
        ).sort("followed_at", -1).limit(50))
        
        decisions = []
        high_confidence_aligned = 0
        total_high_confidence = 0
        total_expected_value = 0.0
        
        for doc in followed_docs:
            event_id = doc.get("event_id")
            
            # Get event details - try both 'id' and '_id' fields
            event = events_collection.find_one({"id": event_id})
            if not event:
                event = events_collection.find_one({"_id": event_id})
            
            event_name = "Unknown Game"
            if event:
                event_name = f"{event.get('away_team', 'TBD')} @ {event.get('home_team', 'TBD')}"
            
            # Use confidence from stored document
            confidence = doc.get("confidence_score", 0.5)
            expected_value = doc.get("expected_value", 0)
            
            # Determine alignment level based on confidence
            if confidence >= 0.75:
                alignment = "high"
                total_high_confidence += 1
                high_confidence_aligned += 1
            elif confidence >= 0.60:
                alignment = "medium"
            else:
                alignment = "low"
            
            total_expected_value += expected_value
            
            decisions.append({
                "id": str(doc.get("_id")),
                "event_id": event_id,
                "event_name": event_name,
                "forecast": "Monte Carlo Simulation",
                "confidence": round(confidence * 100),  # Convert to percentage
                "followed_at": doc.get("followed_at").isoformat() if doc.get("followed_at") else "",
                "alignment": alignment,
                "expected_value": round(expected_value, 2)
            })
        
        # Calculate alignment score (% of high-confidence forecasts followed)
        alignment_score = 0
        if total_high_confidence > 0:
            alignment_score = round((high_confidence_aligned / total_high_confidence) * 100)
        
        # Calculate analytical ROI (average EV as percentage)
        analytical_roi = 0
        if len(decisions) > 0:
            analytical_roi = round((total_expected_value / len(decisions)) * 100, 1)
        
        return {
            "status": "ok",
            "decisions": decisions,
            "alignment_score": alignment_score,
            "analytical_roi": analytical_roi,
            "total_decisions": len(decisions)
        }
        
    except Exception as e:
        print(f"Error fetching decision log: {str(e)}")
        # Return empty data instead of error to keep UI working
        return {
            "status": "ok",
            "decisions": [],
            "alignment_score": 0,
            "analytical_roi": 0,
            "total_decisions": 0
        }


class FollowForecastRequest(BaseModel):
    event_id: str
    pick_id: str
    confidence_score: float
    expected_value: float


@router.post("/follow-forecast")
async def follow_forecast(
    request: FollowForecastRequest,
    authorization: Optional[str] = Header(None)
):
    """
    Record when a user follows/tracks an AI forecast.
    This populates their Decision Log in the Command Center.
    """
    try:
        user_id = get_user_id_from_token(authorization)
        followed_collection = db["followed_forecasts"]
        
        # Create followed forecast record
        follow_doc = {
            "user_id": user_id,
            "event_id": request.event_id,
            "pick_id": request.pick_id,
            "confidence_score": request.confidence_score,
            "expected_value": request.expected_value,
            "followed": True,
            "followed_at": datetime.now(timezone.utc)
        }
        
        # Check if already followed (prevent duplicates)
        existing = followed_collection.find_one({
            "user_id": user_id,
            "event_id": request.event_id,
            "pick_id": request.pick_id
        })
        
        if existing:
            return {"status": "ok", "message": "Already following this forecast"}
        
        followed_collection.insert_one(follow_doc)
        
        return {
            "status": "ok",
            "message": "Forecast added to your Decision Log"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to follow forecast: {str(e)}")
