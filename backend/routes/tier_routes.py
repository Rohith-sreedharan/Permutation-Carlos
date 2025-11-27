from fastapi import APIRouter, HTTPException
from datetime import datetime, timezone
from pydantic import BaseModel

from db.mongo import db
from services.tier_config import get_tier_features, upgrade_user_tier, SUBSCRIPTION_TIERS

router = APIRouter(prefix="/api/account", tags=["tier"])


@router.get("/tier")
async def get_user_tier(user_id: str):
    """Get current user's subscription tier and features"""
    # Fetch user from subscribers collection
    subscriber = db.subscribers.find_one({"user_id": user_id})
    
    if not subscriber:
        tier = "starter"
    else:
        tier = subscriber.get("tier", "starter")
    
    # Get tier features
    features = get_tier_features(tier)
    tier_info = SUBSCRIPTION_TIERS.get(tier, SUBSCRIPTION_TIERS["starter"])
    
    return {
        "tier": tier,
        "features": features,
        "tier_name": tier_info["name"],
        "price": tier_info["price"],
        "simulations": tier_info["simulations"]
    }


class UpgradeRequest(BaseModel):
    user_id: str
    tier: str


@router.post("/upgrade")
async def upgrade_tier(request: UpgradeRequest):
    """Upgrade user's subscription tier"""
    target_tier = request.tier
    
    # Validate tier
    valid_tiers = ["starter", "pro", "sharps_room", "founder"]
    if target_tier not in valid_tiers:
        raise HTTPException(status_code=400, detail="Invalid tier")
    
    try:
        upgrade_user_tier(request.user_id, target_tier)
        
        return {
            "success": True,
            "message": f"Successfully upgraded to {target_tier}",
            "new_tier": target_tier,
            "features": get_tier_features(target_tier)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upgrade failed: {str(e)}")
