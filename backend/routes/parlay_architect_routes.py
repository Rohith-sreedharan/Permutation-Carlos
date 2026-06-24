"""
Parlay Architect Integration Routes
=====================================
FastAPI endpoints for parlay generation using the Parlay Architect system.

CRITICAL SCOPE:
- Parlay outputs are APP-ONLY (never Telegram)
- Uses parlay_runs + parlay_legs collections (NOT telegram_posts)
- Always returns PARLAY or FAIL with structured reasons
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime, timezone

from core.parlay_architect import (
    build_parlay, ParlayRequest, ParlayResult, Leg, Tier, MarketType, 
    PROFILE_RULES, derive_tier
)
from core.parlay_logging import persist_parlay_attempt, get_parlay_stats
from db.mongo import db  # MongoDB connection
from services.canonical_parlay_service import canonical_parlay_service


router = APIRouter(prefix="/api/parlay-architect", tags=["parlay-architect"])


# -----------------------------
# Request/Response Models
# -----------------------------

class GenerateParlayRequest(BaseModel):
    """Request to generate a parlay"""
    profile: str = Field(..., description="Risk profile: premium|balanced|speculative")
    legs: int = Field(..., ge=3, le=6, description="Number of legs (3-6)")
    allow_same_event: bool = Field(default=False, description="Allow multiple legs from same event")
    allow_same_team: bool = Field(default=True, description="Allow correlated legs with same team")
    include_props: bool = Field(default=False, description="Include prop bets")
    seed: Optional[int] = Field(default=None, description="Seed for deterministic generation")
    sports: Optional[List[str]] = Field(default=None, description="Filter by sports (e.g., ['NBA', 'NFL'])")


class ParlayLegResponse(BaseModel):
    """Single leg in parlay response"""
    decision_id: str
    snapshot_hash: str
    canonical_state: str
    event_id: str
    sport: str
    league: str
    market_type: str
    selection: str
    tier: str
    confidence: float
    leg_weight: float


class GenerateParlayResponse(BaseModel):
    """Response from parlay generation"""
    status: str  # PARLAY or FAIL
    attempt_id: str
    profile: str
    legs_requested: int
    legs_selected: Optional[List[ParlayLegResponse]] = None
    parlay_weight: Optional[float] = None
    reason_code: Optional[str] = None
    reason_detail: Optional[dict] = None


class ParlayStatsResponse(BaseModel):
    """Parlay generation statistics"""
    period_days: int
    status_counts: dict
    fail_reasons: dict
    success_rate: float


# -----------------------------
# Helper Functions
# -----------------------------

async def get_candidate_legs(
    sports: Optional[List[str]] = None,
) -> List[Leg]:
    """
    Fetch candidate legs from decision_records only.

    Required filters:
    - release_status = OFFICIAL
    - classification IN (EDGE, LEAN)
    - di_pass = TRUE
    - mv_pass = TRUE
    - snapshot_hash present
    """
    candidates = canonical_parlay_service.get_candidate_legs(sports=sports, limit=200)

    legs = []
    for cand in candidates:
        # Derive tier from canonical state and canonical probability.
        tier = derive_tier(
            canonical_state=cand.get("canonical_state", "LEAN"),
            confidence=float(cand.get("true_probability", 0.5)) * 100.0,
            ev=0.0,
            sport=cand.get("sport"),
        )

        market_key = cand.get("pick_type", "spread")
        market_type_map = {
            "spread": MarketType.SPREAD,
            "total": MarketType.TOTAL,
            "moneyline": MarketType.MONEYLINE,
            "prop": MarketType.PROP,
        }
        market_type = market_type_map.get(market_key.lower(), MarketType.SPREAD)

        event_id = cand.get("event_id", "unknown")
        selection = cand.get("selection", "")
        team_key = f"{event_id}_{selection.split()[0]}" if selection else None

        legs.append(Leg(
            event_id=event_id,
            sport=cand.get("sport", "UNKNOWN"),
            league=cand.get("league", cand.get("sport", "UNKNOWN")),
            start_time_utc=datetime.now(timezone.utc),
            market_type=market_type,
            selection=selection,
            tier=tier,
            confidence=float(cand.get("true_probability", 0.5)) * 100.0,
            clv=0.0,
            total_deviation=0.0,
            volatility="MEDIUM",
            ev=0.0,
            di_pass=True,
            mv_pass=True,
            is_locked=False,
            injury_stable=True,
            team_key=team_key,
            canonical_state=cand.get("canonical_state", "LEAN"),
            decision_id=cand.get("decision_id"),
            snapshot_hash=cand.get("snapshot_hash"),
            true_probability=float(cand.get("true_probability", 0.5)),
            american_odds=int(cand.get("american_odds", -110)),
        ))
    
    return legs


# -----------------------------
# Endpoints
# -----------------------------

@router.post("/generate", response_model=GenerateParlayResponse)
async def generate_parlay(
    request: GenerateParlayRequest,
):
    """
    Generate a parlay based on current eligible signals.
    
    ALWAYS returns either:
    - status=PARLAY with selected legs, or
    - status=FAIL with reason_code explaining why
    
    Never returns None or silently fails.
    """
    # Validate profile
    if request.profile not in PROFILE_RULES:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "INVALID_PROFILE",
                "allowed": list(PROFILE_RULES.keys())
            }
        )
    
    # Fetch candidate legs
    candidate_legs = await get_candidate_legs(sports=request.sports)
    
    # Build parlay request
    parlay_req = ParlayRequest(
        profile=request.profile,
        legs=request.legs,
        allow_same_event=request.allow_same_event,
        allow_same_team=request.allow_same_team,
        include_props=request.include_props,
        seed=request.seed,
    )
    
    # Generate parlay
    result = build_parlay(candidate_legs, parlay_req)
    
    # Persist attempt (audit + claim/fail)
    rules_base = PROFILE_RULES[request.profile].__dict__
    attempt_id = persist_parlay_attempt(db, candidate_legs, parlay_req, rules_base, result)
    
    # Build response
    if result.status == "PARLAY":
        from ..core.parlay_architect import compute_leg_weight
        
        return GenerateParlayResponse(
            status="PARLAY",
            attempt_id=attempt_id,
            profile=result.profile,
            legs_requested=result.legs_requested,
            parlay_weight=result.parlay_weight,
            legs_selected=[
                ParlayLegResponse(
                    decision_id=str(leg.decision_id),
                    snapshot_hash=str(leg.snapshot_hash),
                    canonical_state=str(leg.canonical_state or ""),
                    event_id=leg.event_id,
                    sport=leg.sport,
                    league=leg.league,
                    market_type=leg.market_type.value,
                    selection=leg.selection,
                    tier=leg.tier.value,
                    confidence=leg.confidence,
                    leg_weight=compute_leg_weight(leg),
                )
                for leg in result.legs_selected
            ],
        )
    else:
        return GenerateParlayResponse(
            status="FAIL",
            attempt_id=attempt_id,
            profile=result.profile,
            legs_requested=result.legs_requested,
            reason_code=result.reason_code,
            reason_detail=result.reason_detail,
        )


@router.get("/stats", response_model=ParlayStatsResponse)
async def parlay_stats(
    days: int = 7,
):
    """
    Get parlay generation statistics for the last N days.
    
    Useful for monitoring parlay generation health.
    """
    stats = get_parlay_stats(db, days=days)
    return ParlayStatsResponse(**stats)


@router.get("/profiles")
async def get_profiles():
    """
    Get available parlay profiles and their constraints.
    """
    return {
        profile_name: {
            "min_parlay_weight": rules.min_parlay_weight,
            "min_edges": rules.min_edges,
            "min_picks": rules.min_picks,
            "allow_lean": rules.allow_lean,
            "max_high_vol_legs": rules.max_high_vol_legs,
            "max_same_event": rules.max_same_event,
        }
        for profile_name, rules in PROFILE_RULES.items()
    }


# -----------------------------
# CRITICAL: Scope Enforcement
# -----------------------------

# These endpoints must NEVER:
# 1. Create telegram_posts records
# 2. Call Telegram bot/posting functions
# 3. Trigger notification pipelines
# 4. Appear in any Telegram channel
#
# Parlay outputs are APP-ONLY.
# Single-leg signals remain in signals + telegram_posts.
