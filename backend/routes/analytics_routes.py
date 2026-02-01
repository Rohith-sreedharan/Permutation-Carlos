"""
PHASE 18: Analytics Routes
Exposes numerical accuracy analytics service to frontend

Endpoints:
- POST /api/analytics/calculate-ev: Calculate expected value
- POST /api/analytics/classify-edge: EDGE/LEAN/NEUTRAL classification
- POST /api/analytics/parlay-ev: Calculate parlay expected value
- GET /api/analytics/confidence-tooltip: Generate confidence UI elements
- GET /api/analytics/clv-performance: Get CLV success rate
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import Dict, List, Any, Optional
import logging

from services.analytics_service import AnalyticsService
from services.feedback_loop import FeedbackLoop
from db.mongo import db
from core.event_bus import EventBus

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/analytics", tags=["Analytics"])

# Event bus for feedback loop
event_bus = EventBus()


# ============================================================================
# REQUEST MODELS
# ============================================================================

class EVCalculationRequest(BaseModel):
    """Request to calculate expected value"""
    model_probability: float = Field(..., ge=0, le=1, description="Model's probability (0-1)")
    american_odds: int = Field(..., description="American odds (e.g., -110, +150)")
    sim_count: int = Field(50000, description="Number of simulations run")


class EdgeClassificationRequest(BaseModel):
    """Request to classify bet strength"""
    model_prob: float = Field(..., ge=0, le=1, description="Model probability")
    implied_prob: float = Field(..., ge=0, le=1, description="Implied probability from odds")
    confidence: float = Field(..., ge=0, le=100, description="Confidence score")
    volatility: str = Field(..., description="Volatility level: LOW, MEDIUM, HIGH")
    sim_count: int = Field(..., description="Number of simulations")
    injury_impact: float = Field(0.0, description="Injury impact score")
    american_odds: int = Field(-110, description="American odds for this selection (e.g., -110, +150)")
    opp_american_odds: Optional[int] = Field(None, description="American odds for opposite side (optional, for vig removal)")


class ParlayLeg(BaseModel):
    """Single leg in a parlay"""
    model_prob: float = Field(..., ge=0, le=1)
    american_odds: int
    description: str = ""


class ParlayEVRequest(BaseModel):
    """Request to calculate parlay EV"""
    legs: List[ParlayLeg] = Field(..., description="2-10 legs in parlay")
    sim_count: int = Field(50000, description="Simulation power used")


class ConfidenceTooltipRequest(BaseModel):
    """Request confidence UI elements"""
    confidence_score: float = Field(..., ge=0, le=100)
    volatility: str = Field(..., description="LOW, MEDIUM, HIGH")
    sim_count: int


# ============================================================================
# EV CALCULATION
# ============================================================================

@router.post("/calculate-ev")
async def calculate_ev(payload: EVCalculationRequest) -> Dict[str, Any]:
    """
    Calculate Expected Value using strict mathematical formula
    
    EV = p_model * (decimal_odds - 1) - (1 - p_model)
    Edge = p_model - implied_p
    
    Returns:
    - ev_per_dollar: Expected value per $1 wagered
    - edge_percentage: Percentage edge over bookmaker
    - is_ev_plus: True if meets EV+ criteria (edge >= 3%, tier >= 25K)
    - display_edge: Formatted edge for UI (e.g., "+5.6%")
    """
    try:
        result = AnalyticsService.calculate_expected_value(
            model_probability=payload.model_probability,
            american_odds=payload.american_odds,
            sim_count=payload.sim_count
        )
        
        logger.info(f"EV Calculated: {result['display_edge']} (EV+: {result['is_ev_plus']})")
        return result
        
    except Exception as e:
        logger.error(f"Error calculating EV: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# EDGE CLASSIFICATION
# ============================================================================

@router.post("/classify-edge")
async def classify_edge(payload: EdgeClassificationRequest) -> Dict[str, Any]:
    """
    Classify bet strength: EDGE | LEAN | MARKET_ALIGNED | BLOCKED
    
    Uses Universal Tier Classifier (sport-agnostic, deterministic).
    Classification depends ONLY on:
    1. Probability edge (model vs market)
    2. Expected value (EV)
    3. Data integrity (sims, staleness, validity)
    
    Thresholds:
    - EDGE: prob_edge >= 5.0% AND ev >= 0.0%
    - LEAN: prob_edge >= 2.5% AND ev >= -0.5%
    - MARKET_ALIGNED: does not meet LEAN/EDGE thresholds
    - BLOCKED: insufficient sims (<20K) or invalid data
    
    CRITICAL: CLV, volatility, line movement, market efficiency do NOT affect tier.
    They are tracked separately for execution/sizing decisions.
    
    Returns:
    - classification: 'EDGE' | 'LEAN' | 'MARKET_ALIGNED' | 'BLOCKED'
    - prob_edge: Probability edge (model - market)
    - ev: Expected value
    - p_model: Model probability
    - p_market_fair: Vig-removed market probability
    - recommendation: User-facing text
    - badge_color: 'green' | 'yellow' | 'gray' | 'red'
    - metadata: Volatility/confidence (tracked, but not affecting tier)
    """
    try:
        result = AnalyticsService.classify_bet_strength(
            model_prob=payload.model_prob,
            implied_prob=payload.implied_prob,
            confidence=int(payload.confidence),
            volatility=payload.volatility,
            sim_count=payload.sim_count,
            injury_impact=payload.injury_impact,
            american_odds=payload.american_odds,
            opp_american_odds=payload.opp_american_odds
        )
        
        logger.info(f"Edge Classified: {result['classification']} (Edge: {result.get('prob_edge', 0)*100:.1f}%, EV: {result.get('ev', 0)*100:.1f}%)")
        return result
        
    except Exception as e:
        logger.error(f"Error classifying edge: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# PARLAY EV
# ============================================================================

@router.post("/parlay-ev")
async def calculate_parlay_ev(payload: ParlayEVRequest) -> Dict[str, Any]:
    """
    Calculate parlay expected value
    
    Combined probability = product of all leg probabilities
    Parlay EV from combined decimal odds
    
    Returns:
    - parlay_probability: Combined win probability
    - combined_odds: Parlay odds (American format)
    - expected_value: EV per $1 wagered on parlay
    - edge_percentage: Edge over bookmaker
    - per_leg_breakdown: Individual leg contributions
    """
    try:
        # Convert to list of dicts
        legs_data = [
            {
                'model_prob': leg.model_prob,
                'american_odds': leg.american_odds,
                'description': leg.description
            }
            for leg in payload.legs
        ]
        
        result = AnalyticsService.calculate_parlay_ev(
            legs=legs_data,
            sim_count=payload.sim_count
        )
        
        logger.info(f"Parlay EV: {result['expected_value']:.4f} ({len(payload.legs)} legs)")
        return result
        
    except Exception as e:
        logger.error(f"Error calculating parlay EV: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# CONFIDENCE UI
# ============================================================================

@router.get("/confidence-tooltip")
async def get_confidence_tooltip(
    confidence_score: float,
    volatility: str,
    sim_count: int
) -> Dict[str, Any]:
    """
    Generate confidence UI elements (tooltips, banners)
    
    Returns:
    - score: Confidence score (0-100)
    - label: 'High' | 'Medium' | 'Low'
    - banner_type: 'success' | 'warning' | 'info'
    - banner_message: User-facing banner text
    - tooltip: Detailed explanation with mathematical basis
    - tier_message: Tier-specific context
    """
    try:
        result = AnalyticsService.format_confidence_message(
            confidence_score=int(confidence_score),
            volatility=volatility,
            sim_count=sim_count
        )
        
        return result
        
    except Exception as e:
        logger.error(f"Error formatting confidence: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# CLV PERFORMANCE
# ============================================================================

@router.get("/clv-performance")
async def get_clv_performance(days_back: int = 30) -> Dict[str, Any]:
    """
    Get Closing Line Value (CLV) performance
    
    Target: >= 63% favorable CLV rate
    
    Returns:
    - total_clv_records: Number of settled predictions
    - clv_favorable_rate: % of favorable line movement
    - target_rate: Target rate (0.63)
    - meets_target: Boolean
    - by_prediction_type: Breakdown by total/spread/ml
    - recent_7day_rate: Recent trend
    """
    try:
        feedback_loop = FeedbackLoop(db_client=db, event_bus=event_bus)
        result = await feedback_loop.get_clv_performance(days_back=days_back)
        
        logger.info(f"CLV Performance: {result.get('clv_favorable_rate', 0):.1%} (Target: 63%)")
        return result
        
    except Exception as e:
        logger.error(f"Error getting CLV performance: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# TIER MESSAGING
# ============================================================================

@router.get("/tier-message")
async def get_tier_message(sim_count: int) -> Dict[str, str]:
    """
    Get tier-specific messaging
    
    Returns:
    - message: User-facing message about simulation power
    """
    try:
        message = AnalyticsService.get_tier_message(sim_count=sim_count)
        return {"message": message}
        
    except Exception as e:
        logger.error(f"Error getting tier message: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# HEALTH CHECK
# ============================================================================

@router.get("/health")
async def analytics_health() -> Dict[str, Any]:
    """Health check for analytics service"""
    return {
        "status": "healthy",
        "service": "Analytics Service",
        "phase": "18 - Numerical Accuracy & Simulation Integrity",
        "features": [
            "EV Calculation (strict formula)",
            "EDGE/LEAN/NEUTRAL Classification",
            "Parlay EV",
            "Confidence Tooltips",
            "CLV Performance Tracking"
        ]
    }
