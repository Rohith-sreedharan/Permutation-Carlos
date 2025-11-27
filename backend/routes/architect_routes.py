"""
Parlay Architect Routes
API endpoints for AI-generated optimized parlays
"""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime, timezone
from db.mongo import db
from services.parlay_architect import parlay_architect_service


router = APIRouter()


class GenerateParlayRequest(BaseModel):
    """Request model for parlay generation"""
    sport_key: str = Field(..., description="Sport to focus on (basketball_nba, americanfootball_nfl, etc)")
    leg_count: int = Field(..., ge=3, le=6, description="Number of legs (3-6)")
    risk_profile: str = Field(..., description="high_confidence | balanced | high_volatility")
    user_id: Optional[str] = Field(None, description="User ID for tier checking")


class UnlockParlayRequest(BaseModel):
    """Request model for unlocking a parlay"""
    parlay_id: str
    user_id: str
    payment_intent_id: Optional[str] = None


@router.post("/api/architect/generate")
async def generate_parlay(request: GenerateParlayRequest):
    """
    Generate AI-optimized parlay
    
    This endpoint is PREVIEW-ONLY for Free/Explorer tiers.
    Elite tier can generate with full visibility.
    """
    try:
        # Get user tier
        user = None
        user_tier = "free"
        
        if request.user_id:
            user = db.users.find_one({"user_id": request.user_id})
            if user:
                subscription = db.subscriptions.find_one(
                    {"user_id": request.user_id},
                    sort=[("created_at", -1)]
                )
                if subscription and subscription.get("status") == "active":
                    user_tier = subscription.get("tier", "free").lower()
        
        # Validate sport key
        valid_sports = [
            "basketball_nba",
            "americanfootball_nfl",
            "baseball_mlb",
            "icehockey_nhl"
        ]
        if request.sport_key not in valid_sports:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid sport_key. Must be one of: {', '.join(valid_sports)}"
            )
        
        # Validate risk profile
        valid_profiles = ["high_confidence", "balanced", "high_volatility"]
        if request.risk_profile not in valid_profiles:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid risk_profile. Must be one of: {', '.join(valid_profiles)}"
            )
        
        # Generate parlay
        parlay = parlay_architect_service.generate_optimal_parlay(
            sport_key=request.sport_key,
            leg_count=request.leg_count,
            risk_profile=request.risk_profile,
            user_tier=user_tier
        )
        
        # Determine access level
        is_unlocked = False
        
        if user_tier == "elite":
            # Elite tier: Check if they have a free token
            token_count = db.parlay_architect_tokens.count_documents({
                "user_id": request.user_id,
                "used": False,
                "expires_at": {"$gt": datetime.now(timezone.utc).isoformat()}
            })
            
            if token_count > 0:
                is_unlocked = True
            else:
                # No free token - must pay discounted price
                is_unlocked = False
        elif user_tier in ["pro", "explorer"]:
            # Mid tier - pay-per-use at standard price
            is_unlocked = False
        else:
            # Free tier - teaser only
            is_unlocked = False
        
        # Blur sensitive data for non-unlocked users
        if not is_unlocked:
            response = {
                "parlay_id": parlay["parlay_id"],
                "sport": parlay["sport"],
                "leg_count": parlay["leg_count"],
                "risk_profile": parlay["risk_profile"],
                "parlay_odds": parlay["parlay_odds"],
                "expected_value": parlay["expected_value"],
                "confidence_rating": parlay["confidence_rating"],
                "is_unlocked": False,
                "legs_preview": [
                    {
                        "event": "███████ vs ███████",
                        "line": "████████",
                        "confidence": "███"
                    }
                    for _ in range(parlay["leg_count"])
                ],
                "unlock_price": 999 if user_tier == "elite" else 1499,  # Cents
                "unlock_message": "Upgrade to Elite for 1 free token/month" if user_tier != "elite" else "Use your Elite discount"
            }
        else:
            # Full access for unlocked users
            response = {
                **parlay,
                "is_unlocked": True
            }
        
        return response
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate parlay: {str(e)}")


@router.post("/api/architect/unlock")
async def unlock_parlay(request: UnlockParlayRequest):
    """
    Unlock a blurred parlay after payment
    
    This endpoint is called after successful micro-transaction payment.
    """
    try:
        # Get parlay
        parlay = db.parlay_architect_generations.find_one({"parlay_id": request.parlay_id})
        if not parlay:
            raise HTTPException(status_code=404, detail="Parlay not found")
        
        # Verify user tier and payment
        user = db.users.find_one({"user_id": request.user_id})
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        subscription = db.subscriptions.find_one(
            {"user_id": request.user_id},
            sort=[("created_at", -1)]
        )
        user_tier = subscription.get("tier", "free").lower() if subscription else "free"
        
        # Check if Elite tier has unused token
        if user_tier == "elite":
            token = db.parlay_architect_tokens.find_one({
                "user_id": request.user_id,
                "used": False,
                "expires_at": {"$gt": datetime.now(timezone.utc).isoformat()}
            })
            
            if token:
                # Use the free token
                db.parlay_architect_tokens.update_one(
                    {"_id": token["_id"]},
                    {"$set": {"used": True, "used_at": datetime.now(timezone.utc).isoformat()}}
                )
                payment_method = "elite_token"
            elif request.payment_intent_id:
                payment_method = "elite_discount"
            else:
                raise HTTPException(status_code=402, detail="Payment required")
        elif request.payment_intent_id:
            # Mid/Free tier - verify payment
            payment_method = "micro_transaction"
        else:
            raise HTTPException(status_code=402, detail="Payment required")
        
        # Record unlock
        db.parlay_architect_unlocks.insert_one({
            "parlay_id": request.parlay_id,
            "user_id": request.user_id,
            "user_tier": user_tier,
            "payment_method": payment_method,
            "payment_intent_id": request.payment_intent_id,
            "unlocked_at": datetime.now(timezone.utc).isoformat()
        })
        
        # Return full parlay data
        return {
            **parlay,
            "is_unlocked": True,
            "unlock_method": payment_method
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to unlock parlay: {str(e)}")


@router.get("/api/architect/history")
async def get_parlay_history(user_id: str, limit: int = 10):
    """
    Get user's parlay generation history
    
    Returns both locked and unlocked parlays.
    """
    try:
        # Get user's unlocked parlays
        unlocked_parlay_ids = set()
        unlocks = db.parlay_architect_unlocks.find(
            {"user_id": user_id},
            {"parlay_id": 1}
        )
        unlocked_parlay_ids = {u["parlay_id"] for u in unlocks}
        
        # Get parlay generations
        parlays = list(db.parlay_architect_generations.find(
            {},
            sort=[("created_at", -1)]
        ).limit(limit))
        
        # Add unlock status
        for parlay in parlays:
            parlay["is_unlocked"] = parlay["parlay_id"] in unlocked_parlay_ids
            
            # Blur if not unlocked
            if not parlay["is_unlocked"]:
                parlay["legs"] = [
                    {
                        "event": "███████ vs ███████",
                        "line": "████████",
                        "confidence": "███"
                    }
                    for _ in range(parlay["leg_count"])
                ]
        
        return parlays
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch history: {str(e)}")


@router.get("/api/architect/tokens")
async def get_elite_tokens(user_id: str):
    """
    Get Elite user's remaining free tokens
    
    Elite tier gets 1 free token per month.
    """
    try:
        # Check user tier
        subscription = db.subscriptions.find_one(
            {"user_id": user_id},
            sort=[("created_at", -1)]
        )
        
        if not subscription or subscription.get("tier", "").lower() != "elite":
            return {
                "is_elite": False,
                "tokens_remaining": 0,
                "message": "Upgrade to Elite to receive 1 free token per month"
            }
        
        # Count unused tokens
        tokens_remaining = db.parlay_architect_tokens.count_documents({
            "user_id": user_id,
            "used": False,
            "expires_at": {"$gt": datetime.now(timezone.utc).isoformat()}
        })
        
        return {
            "is_elite": True,
            "tokens_remaining": tokens_remaining,
            "message": f"You have {tokens_remaining} free parlay{'s' if tokens_remaining != 1 else ''} remaining this month"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch tokens: {str(e)}")
