"""
Admin Routes - Super-Admin Only Access
House Model generation, Trust Loop management, Platform analytics
"""
from fastapi import APIRouter, HTTPException, Header
from typing import Optional, Dict, Any
from pydantic import BaseModel
from bson import ObjectId

from services.house_model import (
    house_model_service,
    generate_house_model,
    compare_models,
    batch_generate
)
from services.verification_service import (
    verify_recent_outcomes,
    get_trust_metrics,
    get_accuracy_ledger
)
from db.mongo import db
from legacy_config import SUPER_ADMIN_IDS, FOUNDER_CAP, FOUNDER_TIER_NAME

router = APIRouter(prefix="/api/admin", tags=["admin"])


def _verify_super_admin(authorization: Optional[str]) -> str:
    """
    Verify user is super-admin
    Raises HTTPException if not authorized
    Returns user_id if authorized
    """
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing Authorization header")
    
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != 'bearer':
        raise HTTPException(status_code=401, detail="Invalid Authorization header")
    
    token = parts[1]
    if not token.startswith('user:'):
        raise HTTPException(status_code=401, detail="Invalid token format")
    
    user_id = token.split(':', 1)[1]
    
    # Check if user is super-admin
    try:
        oid = ObjectId(user_id)
        user = db["users"].find_one({"_id": oid})
        
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Check if user_id in SUPER_ADMIN_IDS or has is_super_admin flag
        if user_id in SUPER_ADMIN_IDS or user.get("is_super_admin", False):
            return user_id
        
        raise HTTPException(status_code=403, detail="Super-Admin access required")
        
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=403, detail="Authorization failed")


class HouseModelRequest(BaseModel):
    """Request body for house model generation"""
    event_id: str
    team_a: Optional[Dict[str, Any]] = None
    team_b: Optional[Dict[str, Any]] = None
    market_context: Optional[Dict[str, Any]] = None


# ============================================================================
# HOUSE MODEL ENDPOINTS (500k Iteration Private Engine)
# ============================================================================

@router.post("/house-model/run")
async def run_house_model(
    request: HouseModelRequest,
    authorization: Optional[str] = Header(None)
):
    """
    🏠 Run HOUSE MODEL simulation (500,000 iterations)
    
    Super-Admin only. Creates "Perfect Line" for model calibration.
    Stored separately from public predictions - Platform moat.
    """
    # Verify super-admin
    _verify_super_admin(authorization)
    
    # Fetch event
    event = db["events"].find_one({"event_id": request.event_id})
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    
    # Use provided parameters or defaults
    team_a = request.team_a or {
        "name": event.get("home_team", "Team A"),
        "recent_form": 0.55,
        "home_advantage": 0.52,
        "injury_impact": 1.0,
        "fatigue_factor": 1.0,
        "pace_factor": 1.0
    }
    
    team_b = request.team_b or {
        "name": event.get("away_team", "Team B"),
        "recent_form": 0.50,
        "home_advantage": 0.48,
        "injury_impact": 1.0,
        "fatigue_factor": 1.0,
        "pace_factor": 1.0
    }
    
    market_context = request.market_context or {
        "current_spread": 0,
        "total_line": 220,
        "public_betting_pct": 0.50
    }
    
    try:
        result = generate_house_model(
            event_id=request.event_id,
            team_a=team_a,
            team_b=team_b,
            market_context=market_context
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"House model generation failed: {str(e)}")


@router.get("/house-model/{event_id}")
async def get_house_model(
    event_id: str,
    authorization: Optional[str] = Header(None)
):
    """
    Retrieve house model for specific event
    Super-Admin only
    """
    _verify_super_admin(authorization)
    
    model = house_model_service.get_house_model(event_id)
    if not model:
        raise HTTPException(status_code=404, detail="House model not found")
    
    return model


@router.post("/house-model/batch-generate")
async def batch_generate_house_models(
    limit: int = 10,
    authorization: Optional[str] = Header(None)
):
    """
    Batch generate house models for upcoming events
    Super-Admin only - useful for overnight processing
    """
    _verify_super_admin(authorization)
    
    stats = batch_generate(limit)
    return {
        "status": "complete",
        "stats": stats
    }


@router.get("/house-model/{event_id}/compare")
async def compare_public_vs_house(
    event_id: str,
    authorization: Optional[str] = Header(None)
):
    """
    Compare public model vs house model for accuracy grading
    Super-Admin only - Powers Trust Loop validation
    """
    _verify_super_admin(authorization)
    
    comparison = compare_models(event_id)
    return comparison


# ============================================================================
# VERIFICATION & TRUST LOOP MANAGEMENT
# ============================================================================

@router.post("/verification/run")
async def run_verification(
    hours: int = 24,
    authorization: Optional[str] = Header(None)
):
    """
    Manually trigger outcome verification
    Super-Admin only - normally runs via cron
    """
    _verify_super_admin(authorization)
    
    stats = verify_recent_outcomes(hours)
    return {
        "status": "complete",
        "stats": stats
    }


@router.get("/verification/metrics")
async def get_verification_metrics(
    days: int = 7,
    authorization: Optional[str] = Header(None)
):
    """
    Get model accuracy metrics for admin dashboard
    Super-Admin only
    """
    _verify_super_admin(authorization)
    
    metrics = get_trust_metrics(days)
    return metrics


@router.get("/verification/ledger")
async def get_verification_ledger(
    limit: int = 50,
    authorization: Optional[str] = Header(None)
):
    """
    Get full accuracy ledger (not just top 10)
    Super-Admin only
    """
    _verify_super_admin(authorization)
    
    ledger = get_accuracy_ledger(limit)
    return {"count": len(ledger), "ledger": ledger}


# ============================================================================
# FOUNDER TIER MANAGEMENT
# ============================================================================

@router.get("/founder/status")
async def get_founder_status(authorization: Optional[str] = Header(None)):
    """
    Check Founder tier availability
    Super-Admin only
    """
    _verify_super_admin(authorization)
    
    # Count current founder subscriptions
    founder_count = db["subscriptions"].count_documents({"tier": FOUNDER_TIER_NAME})
    
    is_available = founder_count < FOUNDER_CAP
    remaining = max(0, FOUNDER_CAP - founder_count)
    
    return {
        "tier": FOUNDER_TIER_NAME,
        "cap": FOUNDER_CAP,
        "current_count": founder_count,
        "remaining": remaining,
        "is_available": is_available,
        "status": "OPEN" if is_available else "CLOSED"
    }


@router.post("/founder/force-enable")
async def force_enable_founder(authorization: Optional[str] = Header(None)):
    """
    Force enable Founder tier (bypass cap temporarily)
    Super-Admin only - emergency use
    """
    _verify_super_admin(authorization)
    
    # This would be implemented with a feature flag in production
    return {
        "status": "enabled",
        "message": "Founder tier force-enabled (cap bypassed)"
    }


# ============================================================================
# PLATFORM ANALYTICS
# ============================================================================

@router.get("/analytics/overview")
async def get_platform_analytics(authorization: Optional[str] = Header(None)):
    """
    Platform-wide analytics dashboard
    Super-Admin only
    """
    _verify_super_admin(authorization)
    
    # Aggregate key metrics
    total_users = db["users"].count_documents({})
    total_subscriptions = db["subscriptions"].count_documents({})
    total_predictions = db["predictions"].count_documents({})
    total_house_models = db["house_models"].count_documents({})
    
    # Tier distribution
    tier_distribution = list(db["subscriptions"].aggregate([
        {"$group": {"_id": "$tier", "count": {"$sum": 1}}}
    ]))
    
    # Recent activity (last 7 days)
    from datetime import datetime, timedelta, timezone
    week_ago = datetime.now(timezone.utc) - timedelta(days=7)
    
    recent_signups = db["users"].count_documents({
        "created_at": {"$gte": week_ago.isoformat()}
    })
    
    return {
        "overview": {
            "total_users": total_users,
            "total_subscriptions": total_subscriptions,
            "total_predictions": total_predictions,
            "total_house_models": total_house_models
        },
        "tier_distribution": tier_distribution,
        "recent_activity": {
            "signups_last_7d": recent_signups
        },
        "founder_tier": {
            "enabled": True,
            "capacity": f"{db['subscriptions'].count_documents({'tier': FOUNDER_TIER_NAME})}/{FOUNDER_CAP}"
        }
    }


@router.get("/analytics/revenue")
async def get_revenue_analytics(authorization: Optional[str] = Header(None)):
    """
    Revenue and creator payout analytics
    Super-Admin only
    """
    _verify_super_admin(authorization)
    
    from legacy_config import CREATOR_PAYOUT_PCT, PLATFORM_REVENUE_PCT
    
    # This would query actual payment records in production
    return {
        "revenue_split": {
            "creator_payout_pct": CREATOR_PAYOUT_PCT,
            "platform_revenue_pct": PLATFORM_REVENUE_PCT
        },
        "message": "Connect to Stripe webhook events for real revenue data"
    }
