"""
Risk Profile Routes - Decision Capital Profile Management
Handles user risk tolerance, bankroll management, and bet sizing strategies
"""
from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel, Field
from typing import Optional, Literal
from datetime import datetime, timezone
from db.mongo import db
from bson import ObjectId

router = APIRouter(prefix="/api/user", tags=["Risk Profile"])


class RiskProfile(BaseModel):
    """User's Decision Capital Profile"""
    user_id: Optional[str] = None
    starting_capital: float = Field(default=1000, ge=0, description="Starting bankroll in dollars")
    unit_strategy: Literal["percentage", "fixed"] = Field(default="percentage")
    unit_size: float = Field(default=2.0, ge=0, description="Unit size (% or $ depending on strategy)")
    risk_classification: Optional[Literal["conservative", "balanced", "aggressive"]] = None
    suggested_exposure_per_decision: Optional[float] = None
    volatility_tolerance: float = Field(default=0.15, ge=0, le=1, description="Max volatility tolerance (0-1)")
    max_daily_exposure: Optional[float] = Field(default=100, ge=0, description="Max $ exposure per day")
    
    # Performance metrics (calculated)
    total_decisions: int = Field(default=0, ge=0)
    winning_decisions: int = Field(default=0, ge=0)
    roi: Optional[float] = None
    sharpe_ratio: Optional[float] = None
    
    updated_at: Optional[str] = None


def _get_user_id_from_auth(authorization: Optional[str]) -> str:
    """Extract user_id from Bearer token"""
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing Authorization header")
    
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != 'bearer':
        raise HTTPException(status_code=401, detail="Invalid Authorization header format")
    
    token = parts[1]
    if not token.startswith('user:'):
        raise HTTPException(status_code=401, detail="Invalid token format")
    
    user_id = token.split(':', 1)[1]
    return user_id


def _calculate_risk_classification(profile: RiskProfile) -> Literal["conservative", "balanced", "aggressive"]:
    """
    Calculate risk classification based on unit sizing strategy
    
    Percentage strategy thresholds:
    - <= 1%: Conservative
    - 1-3%: Balanced  
    - >= 3%: Aggressive
    
    Fixed strategy: Convert to percentage of starting capital
    """
    if profile.unit_strategy == "percentage":
        if profile.unit_size <= 1:
            return "conservative"
        elif profile.unit_size >= 3:
            return "aggressive"
        else:
            return "balanced"
    else:  # Fixed strategy
        pct_of_capital = (profile.unit_size / profile.starting_capital) * 100
        if pct_of_capital <= 1:
            return "conservative"
        elif pct_of_capital >= 3:
            return "aggressive"
        else:
            return "balanced"


@router.get("/risk-profile")
async def get_risk_profile(authorization: Optional[str] = Header(None)):
    """
    Get user's Decision Capital Profile
    Returns risk tolerance, bankroll settings, and performance metrics
    """
    user_id = _get_user_id_from_auth(authorization)
    
    try:
        oid = ObjectId(user_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid user ID format")
    
    # Check if profile exists in risk_profiles collection
    profile = db["risk_profiles"].find_one({"user_id": user_id})
    
    if not profile:
        # Return default profile
        default_profile = RiskProfile(
            user_id=user_id,
            starting_capital=1000,
            unit_strategy="percentage",
            unit_size=2.0,
            risk_classification="balanced",
            suggested_exposure_per_decision=20,
            volatility_tolerance=0.15,
            max_daily_exposure=100,
            total_decisions=0,
            winning_decisions=0,
            roi=0.0,
            sharpe_ratio=0.0,
            updated_at=datetime.now(timezone.utc).isoformat()
        )
        return default_profile.dict()
    
    # Remove MongoDB _id field
    profile.pop("_id", None)
    
    return profile


@router.post("/risk-profile")
@router.put("/risk-profile")
async def update_risk_profile(
    profile_update: RiskProfile,
    authorization: Optional[str] = Header(None)
):
    """
    Update user's Decision Capital Profile
    Automatically calculates risk classification and suggested exposure
    """
    user_id = _get_user_id_from_auth(authorization)
    
    try:
        oid = ObjectId(user_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid user ID format")
    
    # Verify user exists
    user = db["users"].find_one({"_id": oid})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Calculate risk classification
    profile_update.user_id = user_id
    profile_update.risk_classification = _calculate_risk_classification(profile_update)
    
    # Calculate suggested exposure per decision
    if profile_update.unit_strategy == "percentage":
        profile_update.suggested_exposure_per_decision = (
            profile_update.starting_capital * profile_update.unit_size / 100
        )
    else:
        profile_update.suggested_exposure_per_decision = profile_update.unit_size
    
    profile_update.updated_at = datetime.now(timezone.utc).isoformat()
    
    # Upsert to risk_profiles collection
    profile_dict = profile_update.dict(exclude_none=True)
    
    db["risk_profiles"].update_one(
        {"user_id": user_id},
        {"$set": profile_dict},
        upsert=True
    )
    
    # Fetch updated profile
    updated_profile = db["risk_profiles"].find_one({"user_id": user_id})
    if updated_profile:
        updated_profile.pop("_id", None)
        return updated_profile
    
    return profile_dict


@router.get("/risk-profile/suggestions")
async def get_risk_profile_suggestions(authorization: Optional[str] = Header(None)):
    """
    Get personalized risk profile suggestions based on user's betting history
    """
    user_id = _get_user_id_from_auth(authorization)
    
    # Get user's historical performance
    # In production, analyze bet history from user_bets collection
    # For now, return general suggestions
    
    suggestions = {
        "recommended_strategy": "percentage",
        "recommended_unit_size": 2.0,
        "reasoning": "2% per decision is optimal for balanced growth with controlled downside risk",
        "risk_classification": "balanced",
        "expected_roi_range": [5.0, 15.0],
        "max_drawdown_estimate": 12.0,
        "bankroll_requirements": {
            "conservative": 2000,
            "balanced": 1000,
            "aggressive": 500
        }
    }
    
    return suggestions
