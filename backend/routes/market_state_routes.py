"""
Market State Registry API Routes

This module exposes the Market State Registry as the single source of truth
for all market state queries. Downstream features (Telegram, Parlay, War Room,
Daily Picks) MUST read from this registry.

🚨 CRITICAL VISIBILITY CONTRACTS:
   - EDGE: telegram_allowed=True, parlay_allowed=True, war_room_visible=True
   - LEAN: telegram_allowed=False, parlay_allowed=True, war_room_visible=True
   - NO_PLAY: telegram_allowed=False, parlay_allowed=False, war_room_visible=False
"""

from fastapi import APIRouter, HTTPException, Query, Depends
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, timedelta
import logging

from db.mongo import db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/market-states", tags=["Market State Registry"])


def get_market_state_service():
    """Dependency to get market state registry service"""
    from services.market_state_registry_service import MarketStateRegistryService
    return MarketStateRegistryService(db)


# =============================================================================
# RESPONSE MODELS
# =============================================================================

class MarketStateResponse(BaseModel):
    """Response model for a single market state"""
    game_id: str
    market_type: str
    state: str  # EDGE | LEAN | NO_PLAY
    selection: Optional[str] = None
    line_value: Optional[float] = None
    probability: Optional[float] = None
    edge_points: Optional[float] = None
    confidence_score: Optional[int] = None
    risk_score: Optional[float] = None
    visibility_flags: dict
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class WarRoomVisibleResponse(BaseModel):
    """Response model for War Room visible markets"""
    markets: List[MarketStateResponse]
    total_edge: int
    total_lean: int


class TelegramEligibleResponse(BaseModel):
    """Response model for Telegram eligible markets"""
    markets: List[MarketStateResponse]
    total: int


class ParlayEligibleResponse(BaseModel):
    """Response model for parlay eligible markets"""
    markets: List[MarketStateResponse]
    total: int
    parlay_thresholds: dict


class ParlayEligibilityResult(BaseModel):
    """Structured result for parlay eligibility check"""
    status: str  # ELIGIBLE | PARLAY_BLOCKED | INSUFFICIENT_LEGS
    message: str
    passed_legs: List[MarketStateResponse]
    failed_legs: List[dict]
    passed_count: int
    failed_count: int
    requested_legs: int
    best_single_pick: Optional[MarketStateResponse] = None
    next_best_actions: List[str] = []


# =============================================================================
# ENDPOINTS
# =============================================================================

@router.get("/war-room-visible", response_model=WarRoomVisibleResponse)
async def get_war_room_visible_markets(
    sport: Optional[str] = Query(None, description="Filter by sport key"),
    game_id: Optional[str] = Query(None, description="Filter by specific game"),
    service = Depends(get_market_state_service)
):
    """
    Get all markets visible in the War Room.
    
    🚨 WAR ROOM VISIBILITY CONTRACT:
       - Shows: state IN (EDGE, LEAN)
       - Excludes: state == NO_PLAY
       - NEVER depends on Telegram posting
       - Renders even when zero EDGEs exist (LEAN is the default content)
    """
    try:
        markets = await service.get_war_room_visible(sport_filter=sport, game_id=game_id)
        
        # Count by state
        edge_count = len([m for m in markets if m.get('state') == 'EDGE'])
        lean_count = len([m for m in markets if m.get('state') == 'LEAN'])
        
        return WarRoomVisibleResponse(
            markets=[MarketStateResponse(**m) for m in markets],
            total_edge=edge_count,
            total_lean=lean_count
        )
    except Exception as e:
        logger.error(f"Error fetching war room visible markets: {e}")
        # Return empty but valid response - War Room must never hard-fail
        return WarRoomVisibleResponse(markets=[], total_edge=0, total_lean=0)


@router.get("/telegram-eligible", response_model=TelegramEligibleResponse)
async def get_telegram_eligible_markets(
    sport: Optional[str] = Query(None, description="Filter by sport key"),
    limit: int = Query(10, description="Maximum results"),
    service = Depends(get_market_state_service)
):
    """
    Get markets eligible for Telegram posting.
    
    Thresholds (STRICT - Single Pick):
       - probability >= 58%
       - edge >= 4.0 points
       - confidence >= 65
       - state must be EDGE
    """
    try:
        markets = await service.get_telegram_eligible(sport_filter=sport, limit=limit)
        
        return TelegramEligibleResponse(
            markets=[MarketStateResponse(**m) for m in markets],
            total=len(markets)
        )
    except Exception as e:
        logger.error(f"Error fetching telegram eligible markets: {e}")
        return TelegramEligibleResponse(markets=[], total=0)


@router.get("/parlay-eligible", response_model=ParlayEligibleResponse)
async def get_parlay_eligible_markets(
    sport: Optional[str] = Query(None, description="Filter by sport key"),
    min_legs: int = Query(2, description="Minimum legs needed"),
    max_legs: int = Query(6, description="Maximum legs to return"),
    service = Depends(get_market_state_service)
):
    """
    Get markets eligible for parlay construction.
    
    🚨 PARLAY ELIGIBILITY DECOUPLING:
       Thresholds (LOOSER - Parlay Legs):
       - probability >= 53%
       - edge >= 1.5 points
       - confidence >= 50
       - risk_score <= 0.55
       - state must be EDGE or LEAN
       
       HARD RULE: NO_PLAY → NEVER eligible
    """
    try:
        markets = await service.get_parlay_eligible(sport_filter=sport, limit=max_legs)
        
        return ParlayEligibleResponse(
            markets=[MarketStateResponse(**m) for m in markets],
            total=len(markets),
            parlay_thresholds={
                "min_probability": 53,
                "min_edge": 1.5,
                "min_confidence": 50,
                "max_risk_score": 0.55
            }
        )
    except Exception as e:
        logger.error(f"Error fetching parlay eligible markets: {e}")
        return ParlayEligibleResponse(
            markets=[], 
            total=0,
            parlay_thresholds={
                "min_probability": 53,
                "min_edge": 1.5,
                "min_confidence": 50,
                "max_risk_score": 0.55
            }
        )


@router.post("/check-parlay-eligibility", response_model=ParlayEligibilityResult)
async def check_parlay_eligibility(
    requested_legs: int = Query(3, description="Number of legs requested"),
    sport: Optional[str] = Query(None, description="Filter by sport"),
    style: Optional[str] = Query(None, description="Parlay style: conservative, balanced, aggressive"),
    service = Depends(get_market_state_service)
):
    """
    Check if enough legs exist for parlay construction.
    
    🚨 PARLAY FAILURE UX:
       If eligible legs < requested legs:
       - Return structured response: status = PARLAY_BLOCKED
       - Include best_single_pick fallback
       - Include next_best_actions for user
       - NEVER hard-fail or show "Load failed"
    """
    try:
        result = await service.check_parlay_eligibility(
            requested_legs=requested_legs,
            sport_filter=sport,
            style=style
        )
        
        return ParlayEligibilityResult(**result)
        
    except Exception as e:
        logger.error(f"Error checking parlay eligibility: {e}")
        # Return PARLAY_BLOCKED, never error
        return ParlayEligibilityResult(
            status="PARLAY_BLOCKED",
            message="Unable to assess market conditions. Try again shortly.",
            passed_legs=[],
            failed_legs=[],
            passed_count=0,
            failed_count=0,
            requested_legs=requested_legs,
            best_single_pick=None,
            next_best_actions=[
                "Refresh to check for new edges",
                "Try a different sport",
                "Wait for more games to be analyzed"
            ]
        )


@router.get("/by-game/{game_id}", response_model=List[MarketStateResponse])
async def get_markets_by_game(
    game_id: str,
    service = Depends(get_market_state_service)
):
    """Get all market states for a specific game"""
    try:
        markets = await service.get_by_game(game_id)
        
        return [MarketStateResponse(**m) for m in markets]
    except Exception as e:
        logger.error(f"Error fetching markets for game {game_id}: {e}")
        return []


@router.post("/register")
async def register_market_state(
    game_id: str,
    sport: str,
    market_type: str,
    probability: float,
    edge_points: float,
    confidence_score: int,
    selection: str,
    line_value: Optional[float] = None,
    risk_score: float = 0.5,
    service = Depends(get_market_state_service)
):
    """
    Register or update a market state in the registry.
    
    This endpoint is called after simulation runs to update the canonical
    market state. All visibility flags are computed automatically based
    on thresholds.
    """
    try:
        # Import the schema types
        from db.schemas.market_state_registry import MarketType, MarketState, ReasonCode
        
        # Determine state and reasons from metrics
        if probability >= 0.58 and edge_points >= 4.0 and confidence_score >= 65:
            state = MarketState.EDGE
            reason_codes = [ReasonCode.EDGE_CONFIRMED, ReasonCode.STRONG_MODEL_SIGNAL]
        elif probability >= 0.53 and edge_points >= 1.5 and confidence_score >= 50:
            state = MarketState.LEAN
            reason_codes = [ReasonCode.PROBABILITY_BELOW_THRESHOLD]
        else:
            state = MarketState.NO_PLAY
            reason_codes = [ReasonCode.NO_MODEL_SIGNAL]
        
        result = await service.register_market_state(
            game_id=game_id,
            sport=sport,
            market_type=MarketType(market_type) if market_type in [e.value for e in MarketType] else MarketType.SPREAD,
            state=state,
            reason_codes=reason_codes,
            probability=probability,
            edge_points=edge_points,
            confidence_score=confidence_score,
            selection=selection,
            line_value=line_value,
            risk_score=risk_score
        )
        
        return {"status": "registered", "state": state.value, "registry_id": result.registry_id}
    except Exception as e:
        logger.error(f"Error registering market state: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats")
async def get_registry_stats(service = Depends(get_market_state_service)):
    """Get current registry statistics"""
    try:
        stats = await service.get_stats()
        
        return stats
    except Exception as e:
        logger.error(f"Error fetching registry stats: {e}")
        return {
            "total_markets": 0,
            "edge_count": 0,
            "lean_count": 0,
            "no_play_count": 0,
            "telegram_eligible": 0,
            "parlay_eligible": 0,
            "war_room_visible": 0
        }
