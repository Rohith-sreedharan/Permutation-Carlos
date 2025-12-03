"""
Parlay Architect Routes
API endpoints for AI-generated optimized parlays
"""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
from db.mongo import db
from services.parlay_architect import parlay_architect_service
from services.stake_intelligence import stake_intelligence_service
from services.parlay_calculator import parlay_calculator_service
from middleware.auth import get_current_user, get_user_tier
from utils.mongo_helpers import sanitize_mongo_doc
from config.pricing import (
    get_parlay_price,
    get_simulation_iterations,
    should_blur_parlay,
    PARLAY_ACCESS
)


router = APIRouter()


class GenerateParlayRequest(BaseModel):
    """Request model for parlay generation"""
    sport_key: str = Field(..., description="Sport to focus on (basketball_nba, americanfootball_nfl, etc)")
    leg_count: int = Field(..., ge=3, le=6, description="Number of legs (3-6)")
    risk_profile: str = Field(..., description="high_confidence | balanced | high_volatility")


class UnlockParlayRequest(BaseModel):
    """Request model for unlocking a parlay"""
    parlay_id: str
    payment_intent_id: Optional[str] = None


class AnalyzeStakeRequest(BaseModel):
    """Request model for stake context analysis"""
    stake_amount: float = Field(..., gt=0, description="User-entered stake amount")
    parlay_confidence: str = Field(..., description="SPECULATIVE | MODERATE | HIGH")
    parlay_risk: str = Field(..., description="Low | Medium | High | Extreme")
    leg_count: int = Field(..., ge=2, le=10, description="Number of legs in parlay")
    combined_probability: float = Field(..., gt=0, lt=1, description="Model's true win probability (0-1)")
    total_odds: float = Field(..., gt=1, description="Decimal odds (e.g., 5.2)")
    potential_payout: float = Field(..., gt=0, description="Stake × odds")
    ev_percent: float = Field(..., description="Expected value percentage")


@router.post("/api/architect/generate")
async def generate_parlay(
    request: GenerateParlayRequest,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Generate AI-optimized parlay
    
    🔒 REQUIRES AUTHENTICATION
    
    Access Levels by Tier:
    - Starter (Free): Blurred preview only → Upgrade prompt
    - Bronze/Silver/Platinum: Full generation, pay per parlay
    - Founder: Full generation, optional lifetime discount
    - Internal: Full access, 1M simulations
    """
    try:
        # Get user tier from authenticated user
        user_tier = get_user_tier(current_user)
        user_email = current_user.get("email")
        
        print(f"[Parlay Architect] Authenticated user {user_email} has tier: {user_tier}")
        
        # Check parlay access level
        access_level = PARLAY_ACCESS.get(user_tier.lower(), "blur_only")
        
        # Starter tier: Return blurred preview with upgrade prompt
        if should_blur_parlay(user_tier):
            return {
                "parlay_id": f"preview_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
                "sport": request.sport_key,
                "leg_count": request.leg_count,
                "risk_profile": request.risk_profile,
                "is_blurred": True,
                "access_level": "blur_only",
                "preview_message": "Upgrade to Bronze or higher to generate parlays",
                "legs_preview": [
                    {
                        "event": "███████ vs ███████",
                        "line": "████████",
                        "confidence": "███"
                    }
                    for _ in range(request.leg_count)
                ],
                "blurred_info": {
                    "parlay_odds": "████",
                    "expected_value": "████",
                    "confidence_rating": "████"
                },
                "upgrade_cta": {
                    "title": "Upgrade to Generate Parlays",
                    "message": "Bronze tier unlocks full parlay generation with 25K simulations",
                    "options": [
                        {"tier": "bronze", "price": "Starting at $XX/month"},
                        {"tier": "silver", "price": "50K simulations"},
                        {"tier": "platinum", "price": "100K simulations"}
                    ]
                }
            }
        
        # Validate sport key
        valid_sports = [
            "basketball_nba",
            "basketball_ncaab",
            "americanfootball_nfl",
            "americanfootball_ncaaf",
            "baseball_mlb",
            "icehockey_nhl"
        ]
        if request.sport_key not in valid_sports:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Invalid sport_key '{request.sport_key}'. "
                    f"Must be one of: {', '.join(valid_sports)}. "
                    f"💡 Tip: Use 'basketball_nba' for NBA, 'basketball_ncaab' for NCAA Basketball, "
                    f"'americanfootball_nfl' for NFL, 'americanfootball_ncaaf' for NCAA Football."
                )
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
        
        # Get universal pricing
        leg_price = get_parlay_price(request.leg_count, user_tier)
        
        # Determine if parlay should be locked
        # FOUNDER and INTERNAL tiers get free unlimited access
        is_unlocked = user_tier.lower() in ["founder", "internal"]
        
        if not is_unlocked:
            # Return locked parlay with pricing info
            response = {
                "parlay_id": parlay["parlay_id"],
                "sport": parlay["sport"],
                "leg_count": parlay["leg_count"],
                "risk_profile": parlay["risk_profile"],
                "parlay_odds": parlay["parlay_odds"],
                "expected_value": parlay["expected_value"],
                "confidence_rating": parlay["confidence_rating"],
                "transparency_message": parlay.get("transparency_message"),
                "is_unlocked": False,
                "legs_preview": [
                    {
                        "event": "███████ vs ███████",
                        "line": "████████",
                        "confidence": "███"
                    }
                    for _ in range(parlay["leg_count"])
                ],
                "unlock_price": leg_price,  # Universal pricing (in cents)
                "unlock_message": f"Unlock this {request.leg_count}-leg parlay for ${leg_price/100:.2f}"
            }
            print(f"🔒 Locked parlay for {user_tier}: {request.leg_count} legs = ${leg_price/100:.2f}")
        else:
            # FOUNDER and INTERNAL tiers get full access immediately
            response = {
                **parlay,
                "is_unlocked": True,
                "unlock_reason": "founder_tier" if user_tier.lower() == "founder" else "internal_tier"
            }
        
        return response
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate parlay: {str(e)}")


@router.post("/api/architect/unlock")
async def unlock_parlay(
    request: UnlockParlayRequest,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Unlock a blurred parlay after payment
    
    🔒 REQUIRES AUTHENTICATION
    
    This endpoint is called after successful micro-transaction payment.
    """
    try:
        user_email = current_user.get("email")
        user_tier = get_user_tier(current_user)
        
        # Get parlay
        parlay = db.parlay_architect_generations.find_one({"parlay_id": request.parlay_id})
        if not parlay:
            raise HTTPException(status_code=404, detail="Parlay not found")
        
        # FOUNDER and INTERNAL tiers don't need to unlock (already unlocked)
        if user_tier.lower() in ["founder", "internal"]:
            raise HTTPException(status_code=400, detail=f"{user_tier.title()} tier parlays are already unlocked")
        
        # All other tiers must pay
        if not request.payment_intent_id:
            raise HTTPException(status_code=402, detail="Payment required")
        
        # Record payment
        payment_method = "micro_transaction"
        
        # Record unlock
        db.parlay_architect_unlocks.insert_one({
            "parlay_id": request.parlay_id,
            "user_id": user_email,
            "user_tier": user_tier,
            "payment_method": payment_method,
            "payment_intent_id": request.payment_intent_id,
            "unlocked_at": datetime.now(timezone.utc).isoformat()
        })
        
        # Return full parlay data
        parlay_clean = sanitize_mongo_doc(parlay)
        return {
            **parlay_clean,
            "is_unlocked": True,
            "unlock_method": payment_method
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to unlock parlay: {str(e)}")


@router.get("/api/architect/history")
async def get_parlay_history(
    limit: int = 10,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Get user's parlay generation history
    
    🔒 REQUIRES AUTHENTICATION
    
    Returns both locked and unlocked parlays.
    """
    user_email = current_user.get("email")
    try:
        # Get user's unlocked parlays
        unlocked_parlay_ids = set()
        unlocks = db.parlay_architect_unlocks.find(
            {"user_id": user_email},
            {"parlay_id": 1}
        )
        unlocked_parlay_ids = {u["parlay_id"] for u in unlocks}
        
        # Get parlay generations
        parlays = list(db.parlay_architect_generations.find(
            {},
            sort=[("created_at", -1)]
        ).limit(limit))
        
        # Sanitize parlays to remove MongoDB ObjectIds
        parlays = [sanitize_mongo_doc(p) for p in parlays]
        
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


@router.get("/api/architect/pricing")
async def get_parlay_pricing(
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Get parlay pricing for current user
    
    🔒 REQUIRES AUTHENTICATION
    
    Returns universal pricing (same for all tiers) and simulation power for user's tier.
    """
    try:
        user_tier = get_user_tier(current_user)
        
        # Get pricing info
        from config.pricing import PARLAY_PRICING, SIMULATION_POWER, TIER_CONFIG
        
        return {
            "user_tier": user_tier,
            "simulation_power": SIMULATION_POWER.get(user_tier.lower(), 10_000),
            "parlay_pricing": {
                "3_leg": PARLAY_PRICING["3_leg"] / 100,  # Convert to dollars
                "4_leg": PARLAY_PRICING["4_leg"] / 100,
                "5_leg": PARLAY_PRICING["5_leg"] / 100,
                "6_leg": PARLAY_PRICING["6_leg"] / 100
            },
            "tier_info": TIER_CONFIG.get(user_tier.lower(), TIER_CONFIG["starter"]),
            "message": "Universal pricing - same for all tiers" if user_tier.lower() != "internal" else "Internal tier - free access"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch pricing: {str(e)}")


@router.post("/api/architect/analyze-stake")
async def analyze_stake(request: AnalyzeStakeRequest):
    """
    🧠 Stake Intelligence Endpoint (CONTEXT ONLY)
    
    Provides INTERPRETATION of parlay risk and payout context.
    
    This is NOT:
    - Betting advice
    - Bankroll management
    - Stake recommendations
    - Financial guidance
    
    This IS:
    - Risk interpretation
    - Probability context
    - Expected value math
    - Volatility alignment
    
    BeatVegas is a sports intelligence platform - we interpret data, not manage money.
    
    Example Request:
    ```json
    {
        "stake_amount": 10.00,
        "parlay_confidence": "SPECULATIVE",
        "parlay_risk": "High",
        "leg_count": 4,
        "combined_probability": 0.041,
        "total_odds": 10.78,
        "potential_payout": 107.80,
        "ev_percent": -2.3
    }
    ```
    
    Example Response:
    ```json
    {
        "hit_probability": 4.1,
        "hit_probability_label": "Very Low",
        "risk_level": "High 🔥",
        "ev_interpretation": "Neutral",
        "context_message": "This parlay has a longshot payout. High risk, high reward.",
        "payout_context": "Your potential payout of $107.80 represents a high-risk, high-reward scenario.",
        "volatility_alignment": "This payout aligns with the model's volatility rating — this is a pure longshot play."
    }
    ```
    """
    try:
        context = stake_intelligence_service.interpret_stake_context(
            stake_amount=request.stake_amount,
            parlay_confidence=request.parlay_confidence,
            parlay_risk=request.parlay_risk,
            leg_count=request.leg_count,
            combined_probability=request.combined_probability,
            total_odds=request.total_odds,
            potential_payout=request.potential_payout,
            ev_percent=request.ev_percent
        )
        
        return context
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Stake context interpretation failed: {str(e)}")


class ParlayLeg(BaseModel):
    """Single leg in a parlay"""
    event_id: str
    pick_type: str  # "spread", "total", "moneyline"
    selection: str  # e.g., "Miami -5", "Over 215.5"
    true_probability: float = Field(..., gt=0, lt=1, description="Model probability (0-1)")
    american_odds: int
    sport: str


class CalculateParlayRequest(BaseModel):
    """Request model for parlay probability and EV calculation"""
    legs: List[ParlayLeg]
    stake_amount: Optional[float] = Field(None, gt=0, description="Optional stake for payout calculation")


@router.post("/api/architect/calculate-parlay")
async def calculate_parlay_probability_and_ev(request: CalculateParlayRequest):
    """
    📊 Calculate Parlay Probability & Expected Value
    
    Calculates:
    - Combined parlay win probability
    - Correlation detection (positive/negative/neutral)
    - Expected Value (EV%)
    - Volatility classification
    
    This is PURE MATH - not betting advice, just probability calculations.
    
    Example Request:
    ```json
    {
        "legs": [
            {
                "event_id": "123",
                "pick_type": "spread",
                "selection": "Miami -5",
                "true_probability": 0.52,
                "american_odds": -110,
                "sport": "NBA"
            },
            {
                "event_id": "124",
                "pick_type": "total",
                "selection": "Over 215.5",
                "true_probability": 0.48,
                "american_odds": -110,
                "sport": "NBA"
            }
        ],
        "stake_amount": 10.00
    }
    ```
    
    Example Response:
    ```json
    {
        "combined_probability": 0.2496,
        "combined_probability_pct": 24.96,
        "correlation_type": "neutral",
        "correlation_label": "Legs uncorrelated",
        "decimal_odds": 3.64,
        "ev_percent": -9.1,
        "ev_interpretation": "Negative",
        "ev_label": "Slight Disadvantage",
        "volatility": "Medium",
        "potential_payout": 36.40,
        "potential_profit": 26.40,
        "notes": "Pure math - not betting advice"
    }
    ```
    """
    try:
        if len(request.legs) < 2:
            raise HTTPException(status_code=400, detail="Parlay must have at least 2 legs")
        
        # Convert Pydantic models to dicts for service layer
        legs_data = [leg.dict() for leg in request.legs]
        
        # 1. Calculate parlay probability
        prob_result = parlay_calculator_service.calculate_parlay_probability(legs_data)
        
        combined_prob = prob_result["combined_probability"]
        combined_prob_pct = combined_prob * 100
        
        # 2. Calculate decimal odds from American odds
        decimal_odds = 1.0
        for leg in request.legs:
            american = leg.american_odds
            if american < 0:
                leg_decimal = 1 + (100 / abs(american))
            else:
                leg_decimal = 1 + (american / 100)
            decimal_odds *= leg_decimal
        
        decimal_odds = round(decimal_odds, 2)
        
        # 3. Calculate EV%
        ev_result = parlay_calculator_service.calculate_parlay_ev(
            parlay_probability=combined_prob,
            decimal_odds=decimal_odds
        )
        
        # 4. Calculate volatility
        volatility = parlay_calculator_service.calculate_volatility_level(
            parlay_probability=combined_prob,
            leg_count=len(request.legs),
            odds=decimal_odds
        )
        
        # 5. Calculate payout if stake provided
        payout_data = {}
        if request.stake_amount:
            potential_payout = request.stake_amount * decimal_odds
            potential_profit = potential_payout - request.stake_amount
            payout_data = {
                "stake_amount": request.stake_amount,
                "potential_payout": round(potential_payout, 2),
                "potential_profit": round(potential_profit, 2)
            }
        
        return {
            # Probability
            "combined_probability": combined_prob,
            "combined_probability_pct": round(combined_prob_pct, 2),
            "correlation_type": prob_result["correlation_type"],
            "correlation_label": prob_result["correlation_label"],
            "correlation_adjustment": prob_result["correlation_adjustment"],
            "independent_probability": prob_result["independent_probability"],
            
            # Odds
            "decimal_odds": decimal_odds,
            
            # Expected Value
            "ev_percent": ev_result["ev_percent"],
            "ev_interpretation": ev_result["ev_interpretation"],
            "ev_label": ev_result["ev_label"],
            "expected_return_per_dollar": ev_result["expected_return_per_dollar"],
            
            # Volatility
            "volatility": volatility,
            
            # Payout (if stake provided)
            **payout_data,
            
            # Metadata
            "leg_count": len(request.legs),
            "notes": "Pure math - not betting advice"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Parlay calculation failed: {str(e)}")
