"""
Parlay Architect Routes
API endpoints for AI-generated optimized parlays
"""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
from uuid import uuid4
from db.mongo import db
from core.parlay_architect import ParlayRequest, build_parlay, derive_tier, MarketType, Leg
from services.stake_intelligence import stake_intelligence_service
from services.parlay_calculator import parlay_calculator_service
from services.canonical_parlay_service import canonical_parlay_service
from services.parlay_execution_agent import parlay_execution_agent, BillingWriteFailure
from middleware.auth import get_current_user, get_user_tier
from utils.mongo_helpers import sanitize_mongo_doc
from config.pricing import (
    get_parlay_price,
    get_simulation_iterations,
    should_blur_parlay,
    PARLAY_ACCESS
)


router = APIRouter()


SPORT_KEY_TO_LEAGUES = {
    "basketball_nba": ["NBA"],
    "basketball_ncaab": ["NCAAB"],
    "americanfootball_nfl": ["NFL"],
    "americanfootball_ncaaf": ["NCAAF"],
    "baseball_mlb": ["MLB"],
    "icehockey_nhl": ["NHL"],
    "all": None,
}

RISK_PROFILE_TO_CORE_PROFILE = {
    "high_confidence": "premium",
    "balanced": "balanced",
    "high_volatility": "speculative",
}


class GenerateParlayRequest(BaseModel):
    """Request model for parlay generation"""
    sport_key: str = Field(..., description="Sport to focus on (basketball_nba, americanfootball_nfl, etc) or 'all' for multi-sport")
    leg_count: int = Field(..., ge=2, le=6, description="Number of legs (2-6)")
    risk_profile: str = Field(..., description="high_confidence | balanced | high_volatility")
    multi_sport: bool = Field(default=False, description="If True, include games from all sports (same day only)")


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


def _convert_candidates_to_core_legs(candidates: List[Dict[str, Any]]) -> List[Leg]:
    legs: List[Leg] = []
    market_type_map = {
        "spread": MarketType.SPREAD,
        "total": MarketType.TOTAL,
        "moneyline": MarketType.MONEYLINE,
    }

    for cand in candidates:
        confidence_pct = float(cand["true_probability"]) * 100.0
        tier = derive_tier(
            canonical_state=str(cand["canonical_state"]),
            confidence=confidence_pct,
            ev=0.0,
            sport=str(cand.get("sport") or ""),
        )
        legs.append(
            Leg(
                event_id=str(cand["event_id"]),
                sport=str(cand.get("sport") or "UNKNOWN"),
                league=str(cand.get("league") or cand.get("sport") or "UNKNOWN"),
                start_time_utc=datetime.now(timezone.utc),
                market_type=market_type_map.get(str(cand.get("pick_type", "spread")).lower(), MarketType.SPREAD),
                selection=str(cand.get("selection") or ""),
                tier=tier,
                confidence=confidence_pct,
                clv=0.0,
                total_deviation=0.0,
                volatility="MEDIUM",
                ev=0.0,
                di_pass=True,
                mv_pass=True,
                is_locked=False,
                injury_stable=True,
                team_key=None,
                canonical_state=str(cand["canonical_state"]),
                decision_id=str(cand["decision_id"]),
                snapshot_hash=str(cand["snapshot_hash"]),
                true_probability=float(cand["true_probability"]),
                american_odds=int(cand["american_odds"]),
            )
        )

    return legs


def _american_to_decimal(american: int) -> float:
    if american < 0:
        return 1 + (100.0 / abs(american))
    return 1 + (american / 100.0)


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
        print(f"🔍 [Parlay Debug] current_user: {current_user}")
        user_tier = get_user_tier(current_user)
        user_email = current_user.get("email")
        
        print(f"[Parlay Architect] Authenticated user {user_email} has tier: {user_tier}")
        print(f"🔑 [Parlay Debug] Extracted tier: {user_tier}")
        
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
            "icehockey_nhl",
            "all"  # Multi-sport parlays
        ]
        if request.sport_key not in valid_sports:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Invalid sport_key '{request.sport_key}'. "
                    f"Must be one of: {', '.join(valid_sports)}. "
                    f"💡 Tip: Use 'basketball_nba' for NBA, 'all' for multi-sport parlays, etc."
                )
            )
        
        # Validate risk profile
        valid_profiles = ["high_confidence", "balanced", "high_volatility"]
        if request.risk_profile not in valid_profiles:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid risk_profile. Must be one of: {', '.join(valid_profiles)}"
            )
        
        leagues = SPORT_KEY_TO_LEAGUES.get(request.sport_key)
        candidates = canonical_parlay_service.get_candidate_legs(sports=leagues, limit=400)
        if len(candidates) < request.leg_count:
            return {
                "status": "BLOCKED",
                "reason_code": "INSUFFICIENT_CANONICAL_CANDIDATES",
                "reason_detail": {
                    "available": len(candidates),
                    "requested": request.leg_count,
                    "requirements": {
                        "release_status": "OFFICIAL",
                        "classification": ["EDGE", "LEAN"],
                        "di_pass": True,
                        "mv_pass": True,
                        "snapshot_hash": "required",
                    },
                },
                "parlay_available": False,
                "truth_mode_enforced": True,
            }

        run_id = str(uuid4())
        trace_id = str(uuid4())
        amount = 0.0 if user_tier.lower() in ["founder", "elite", "internal"] else -1.0
        try:
            parlay_execution_agent.enforce_billing_write_before_execution(
                run_id=run_id,
                user_id=str(user_email),
                trace_id=trace_id,
                amount=amount,
            )
        except BillingWriteFailure as exc:
            raise HTTPException(status_code=503, detail="BILLING_WRITE_FAIL") from exc

        core_profile = RISK_PROFILE_TO_CORE_PROFILE[request.risk_profile]
        result = build_parlay(
            _convert_candidates_to_core_legs(candidates),
            ParlayRequest(
                profile=core_profile,
                legs=request.leg_count,
                allow_same_event=False,
                allow_same_team=True,
                seed=None,
                include_props=False,
            ),
        )

        if result.status != "PARLAY":
            return {
                "status": "BLOCKED",
                "reason_code": result.reason_code,
                "reason_detail": result.reason_detail,
                "parlay_available": False,
                "truth_mode_enforced": True,
            }

        parlay_decimal_odds = 1.0
        for leg in result.legs_selected:
            if leg.american_odds is None:
                raise HTTPException(status_code=500, detail="Missing canonical odds for selected leg")
            parlay_decimal_odds *= _american_to_decimal(int(leg.american_odds))
        parlay_decimal_odds = round(parlay_decimal_odds, 2)

        avg_probability = sum(float(leg.true_probability or 0.0) for leg in result.legs_selected) / max(1, len(result.legs_selected))
        combined_probability = 1.0
        for leg in result.legs_selected:
            combined_probability *= float(leg.true_probability or 0.0)
        expected_value = parlay_calculator_service.calculate_parlay_ev(
            parlay_probability=combined_probability,
            decimal_odds=parlay_decimal_odds,
        )["ev_percent"]

        parlay = {
            "parlay_id": f"parlay_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
            "sport": request.sport_key,
            "leg_count": len(result.legs_selected),
            "risk_profile": request.risk_profile,
            "legs": [
                {
                    "event": leg.event_id,
                    "line": leg.selection,
                    "bet_type": leg.market_type.value,
                    "probability": leg.true_probability,
                    "confidence": round(float(leg.confidence), 2),
                    "ev": leg.ev,
                    "decision_id": leg.decision_id,
                    "snapshot_hash": leg.snapshot_hash,
                    "canonical_state": leg.canonical_state,
                }
                for leg in result.legs_selected
            ],
            "parlay_odds": parlay_decimal_odds,
            "expected_value": expected_value,
            "confidence_rating": round(avg_probability * 100.0, 1),
            "transparency_message": "Canonical decision_id-only parlay. Lineage enforced.",
            "trace_id": trace_id,
        }

        db.parlay_architect_generations.insert_one(
            {
                **parlay,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "user_id": user_email,
                "run_id": run_id,
            }
        )
        
        # Get universal pricing
        leg_price = get_parlay_price(request.leg_count, user_tier)
        
        # Determine if parlay should be locked
        # FOUNDER, ELITE, and INTERNAL tiers get free unlimited access
        is_unlocked = user_tier.lower() in ["founder", "elite", "internal"]
        print(f"🔑 [Parlay Unlock Check] User tier: {user_tier.lower()}, is_unlocked: {is_unlocked}")
        
        if not is_unlocked:
            print(f"🔒 [Parlay] Returning LOCKED parlay for tier: {user_tier}")
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
            # FOUNDER, ELITE, and INTERNAL tiers get full access immediately
            print(f"🔓 [Parlay] Returning UNLOCKED parlay for tier: {user_tier}")
            unlock_reason = "elite_tier"
            if user_tier.lower() == "founder":
                unlock_reason = "founder_tier"
            elif user_tier.lower() == "internal":
                unlock_reason = "internal_tier"
            
            response = {
                **parlay,
                "is_unlocked": True,
                "unlock_reason": unlock_reason
            }
            print(f"✅ [Parlay] Response is_unlocked: {response.get('is_unlocked')}")
            print(f"✅ [Parlay] Full response keys: {list(response.keys())}")
        
        return response
        
    except ValueError as e:
        # Check if this is a blocked state response (dict) or regular error (str)
        error_detail = str(e)
        
        # Try to eval if it's a dict string representation
        try:
            # Extract dict from ValueError if present
            if "{'status': 'BLOCKED'" in error_detail or '{"status": "BLOCKED"' in error_detail:
                # ValueError contains our blocked state dict - extract and return it
                import ast
                blocked_data = ast.literal_eval(error_detail)
                
                # Add user tier and unlock status to blocked response
                is_unlocked = user_tier.lower() in ["founder", "elite", "internal"]
                
                # Return blocked state with tier info
                return {
                    **blocked_data,
                    "parlay_available": False,
                    "truth_mode_enforced": True,
                    "is_unlocked": is_unlocked,
                    "user_tier": user_tier,
                    "unlock_reason": f"{user_tier.lower()}_tier" if is_unlocked else None
                }
        except:
            pass
        
        # Regular error - raise HTTP exception
        raise HTTPException(status_code=400, detail=error_detail)
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


class CalculateParlayRequest(BaseModel):
    """Canonical parlay calculation request (decision IDs only)."""
    decision_ids: List[str] = Field(..., min_length=2, description="Canonical decision IDs")
    stake_amount: Optional[float] = Field(None, gt=0, description="Optional stake for payout calculation")


@router.post("/api/architect/calculate-parlay")
async def calculate_parlay_probability_and_ev(
    request: CalculateParlayRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
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
        if len(request.decision_ids) < 2:
            raise HTTPException(status_code=400, detail="Parlay must have at least 2 legs")

        run_id = str(uuid4())
        trace_id = str(uuid4())
        user_id = str(current_user.get("email") or current_user.get("sub") or current_user.get("id") or "unknown")
        try:
            parlay_execution_agent.enforce_billing_write_before_execution(
                run_id=run_id,
                user_id=user_id,
                trace_id=trace_id,
                amount=-1.0,
            )
        except BillingWriteFailure as exc:
            raise HTTPException(status_code=503, detail="BILLING_WRITE_FAIL") from exc

        try:
            resolved_legs = canonical_parlay_service.resolve_decision_ids(request.decision_ids)
        except KeyError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        legs_data = [
            {
                "event_id": leg["event_id"],
                "pick_type": leg["pick_type"],
                "selection": leg["selection"],
                "true_probability": leg["true_probability"],
                "american_odds": leg["american_odds"],
                "sport": leg["sport"],
            }
            for leg in resolved_legs
        ]
        
        # 1. Calculate parlay probability
        prob_result = parlay_calculator_service.calculate_parlay_probability(legs_data)
        
        combined_prob = prob_result["combined_probability"]
        combined_prob_pct = combined_prob * 100
        
        # 2. Calculate decimal odds from American odds
        decimal_odds = 1.0
        for leg in resolved_legs:
            american = int(leg["american_odds"])
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
            leg_count=len(resolved_legs),
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
            "leg_count": len(resolved_legs),
            "resolved_legs": [
                {
                    "decision_id": leg["decision_id"],
                    "snapshot_hash": leg["snapshot_hash"],
                    "canonical_state": leg["canonical_state"],
                    "event_id": leg["event_id"],
                }
                for leg in resolved_legs
            ],
            "notes": "Pure math - not betting advice"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Parlay calculation failed: {str(e)}")
