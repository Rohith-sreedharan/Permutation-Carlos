"""
NCAAB Edge Evaluation API Routes
Endpoints for college basketball edge analysis
"""
from fastapi import APIRouter, Depends, HTTPException, Query, Path
from pymongo.database import Database
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
from pydantic import BaseModel, Field

from services.ncaab_edge_evaluator import (
    NCAABEdgeEvaluator,
    NCAABEvaluationResult,
    NCAABState,
    PrimaryMarket
)


router = APIRouter(prefix="/api/ncaab", tags=["ncaab"])


# ============================================================================
# DATABASE DEPENDENCY
# ============================================================================
from pymongo.database import Database

async def get_db() -> Database:
    """Get database connection"""
    from db.mongo import db
    return db


# ============================================================================
# REQUEST/RESPONSE SCHEMAS
# ============================================================================

class SimulationOutput(BaseModel):
    """NCAAB simulation output"""
    spread_win_probability: float = Field(..., description="Raw spread win probability")
    total_win_probability: Optional[float] = Field(None, description="Raw totals win probability")
    spread_edge_pts: float = Field(..., description="Spread edge in points")
    total_edge_pts: Optional[float] = Field(None, description="Totals edge in points")
    volatility_bucket: str = Field(default="MEDIUM", description="Volatility: LOW, MEDIUM, HIGH, EXTREME")
    distribution_width: float = Field(default=7.0, description="Distribution width in points")
    pace_driven_total: bool = Field(default=False, description="Is totals edge primarily pace-driven?")


class MarketData(BaseModel):
    """NCAAB market data"""
    spread_line: float = Field(..., description="Sportsbook spread line")
    total_line: Optional[float] = Field(None, description="Sportsbook total line")
    clv_forecast: Optional[float] = Field(None, description="CLV forecast")
    line_move_toward_model: bool = Field(default=False, description="Did line move toward model?")


class NCAABEvaluationRequest(BaseModel):
    """Single game evaluation request"""
    game_id: str = Field(..., description="Unique game identifier")
    simulation_output: SimulationOutput
    market_data: MarketData


class SlateEvaluationRequest(BaseModel):
    """Multiple games evaluation request"""
    games: List[Dict[str, Any]] = Field(..., description="List of games with simulation_output and market_data")


class EvaluationResponse(BaseModel):
    """Evaluation response"""
    game_id: str
    state: str
    primary_market: str
    reason_codes: List[str]
    spread_edge: Optional[float]
    total_edge: Optional[float]
    compressed_prob_spread: Optional[float]
    compressed_prob_total: Optional[float]
    volatility_bucket: Optional[str]
    distribution_flag: Optional[str]
    market_confirmation: bool
    evaluated_at: str


# ============================================================================
# EVALUATION ENDPOINTS
# ============================================================================

@router.post("/evaluate/game", response_model=EvaluationResponse)
async def evaluate_single_game(
    request: NCAABEvaluationRequest,
    db: Database = Depends(get_db)
):
    """
    Evaluate a single NCAAB game
    
    Two-layer system:
    - Layer A: Eligibility (edge + distribution)
    - Layer B: Grading (EDGE / LEAN / NO_PLAY)
    
    Returns normalized probabilities and classification
    """
    evaluator = NCAABEdgeEvaluator(db)
    
    result = await evaluator.evaluate_game(
        game_id=request.game_id,
        simulation_output=request.simulation_output.dict(),
        market_data=request.market_data.dict()
    )
    
    return EvaluationResponse(
        game_id=result.game_id,
        state=result.state.value,
        primary_market=result.primary_market.value,
        reason_codes=result.reason_codes,
        spread_edge=result.spread_edge,
        total_edge=result.total_edge,
        compressed_prob_spread=result.compressed_prob_spread,
        compressed_prob_total=result.compressed_prob_total,
        volatility_bucket=result.volatility_bucket,
        distribution_flag=result.distribution_flag.value if result.distribution_flag else None,
        market_confirmation=result.market_confirmation,
        evaluated_at=result.evaluated_at.isoformat()
    )


@router.post("/evaluate/slate", response_model=List[EvaluationResponse])
async def evaluate_slate(
    request: SlateEvaluationRequest,
    db: Database = Depends(get_db)
):
    """
    Evaluate multiple games (daily slate)
    
    Returns evaluations for all games
    Useful for checking system behavior across multiple matchups
    """
    evaluator = NCAABEdgeEvaluator(db)
    
    results = await evaluator.evaluate_slate(request.games)
    
    return [
        EvaluationResponse(
            game_id=r.game_id,
            state=r.state.value,
            primary_market=r.primary_market.value,
            reason_codes=r.reason_codes,
            spread_edge=r.spread_edge,
            total_edge=r.total_edge,
            compressed_prob_spread=r.compressed_prob_spread,
            compressed_prob_total=r.compressed_prob_total,
            volatility_bucket=r.volatility_bucket,
            distribution_flag=r.distribution_flag.value if r.distribution_flag else None,
            market_confirmation=r.market_confirmation,
            evaluated_at=r.evaluated_at.isoformat()
        )
        for r in results
    ]


# ============================================================================
# ANALYSIS & MONITORING
# ============================================================================

@router.get("/evaluations/recent", response_model=List[EvaluationResponse])
async def get_recent_evaluations(
    limit: int = Query(20, ge=1, le=100, description="Number of evaluations to return"),
    state: Optional[str] = Query(None, description="Filter by state: EDGE, LEAN, NO_PLAY"),
    db: Database = Depends(get_db)
):
    """
    Get recent NCAAB evaluations
    """
    query: Dict[str, Any] = {"archived": False}
    
    if state:
        query["evaluation.state"] = state
    
    evaluations = list(db["ncaab_evaluations"].find(query)
        .sort("created_at", -1)
        .limit(limit))
    
    if not evaluations:
        return []
    
    return [
        EvaluationResponse(
            game_id=e["game_id"],
            state=e["evaluation"]["state"],
            primary_market=e["evaluation"]["primary_market"],
            reason_codes=e["evaluation"]["reason_codes"],
            spread_edge=e["evaluation"]["spread_edge"],
            total_edge=e["evaluation"]["total_edge"],
            compressed_prob_spread=e["evaluation"]["compressed_prob_spread"],
            compressed_prob_total=e["evaluation"]["compressed_prob_total"],
            volatility_bucket=e["evaluation"]["volatility_bucket"],
            distribution_flag=e["evaluation"]["distribution_flag"],
            market_confirmation=e["evaluation"]["market_confirmation"],
            evaluated_at=e["evaluation"]["evaluated_at"]
        )
        for e in evaluations
    ]


@router.get("/stats/slate/{date}", response_model=Dict[str, Any])
async def get_slate_stats(
    date: str = Path(..., description="Date in YYYY-MM-DD format"),
    db: Database = Depends(get_db)
):
    """
    Get statistics for a daily slate
    
    Validates system behavior:
    - Edge count should be 0-3
    - Multiple leans expected
    - Majority should be NO_PLAY
    """
    try:
        target_date = datetime.fromisoformat(date)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
    
    start_of_day = target_date.replace(hour=0, minute=0, second=0, microsecond=0)
    end_of_day = target_date.replace(hour=23, minute=59, second=59, microsecond=999999)
    
    evaluations = list(db["ncaab_evaluations"].find({
        "created_at": {"$gte": start_of_day, "$lte": end_of_day},
        "archived": False
    }))
    
    # Parse evaluations
    results = [
        {
            "game_id": e["game_id"],
            "state": e["evaluation"]["state"],
            "spread_edge": e["evaluation"]["spread_edge"],
            "compressed_prob": e["evaluation"]["compressed_prob_spread"] or e["evaluation"]["compressed_prob_total"]
        }
        for e in evaluations
    ]
    
    # Calculate stats
    edge_count = sum(1 for r in results if r["state"] == "EDGE")
    lean_count = sum(1 for r in results if r["state"] == "LEAN")
    no_play_count = sum(1 for r in results if r["state"] == "NO_PLAY")
    total_count = len(results)
    
    probs = [r["compressed_prob"] for r in results if r["compressed_prob"]]
    avg_prob = sum(probs) / len(probs) if probs else 0.5
    probs_54_60 = sum(1 for p in probs if 0.54 <= p <= 0.60)
    
    return {
        "date": date,
        "total_games": total_count,
        "edge_count": edge_count,
        "lean_count": lean_count,
        "no_play_count": no_play_count,
        "statistics": {
            "edge_percentage": (edge_count / total_count * 100) if total_count else 0,
            "lean_percentage": (lean_count / total_count * 100) if total_count else 0,
            "no_play_percentage": (no_play_count / total_count * 100) if total_count else 0,
            "average_probability": avg_prob,
            "probs_54_60_count": probs_54_60,
            "probs_54_60_percentage": (probs_54_60 / len(probs) * 100) if probs else 0
        },
        "health_check": {
            "edges_reasonable": 0 <= edge_count <= 3,
            "leans_present": lean_count > 0,
            "mostly_no_play": no_play_count > (total_count * 0.7) if total_count else False,
            "probs_in_range": (probs_54_60 / len(probs) * 100) > 60 if probs else False
        },
        "games": results
    }


@router.get("/evaluation/{game_id}", response_model=EvaluationResponse)
async def get_evaluation(
    game_id: str,
    db: Database = Depends(get_db)
):
    """
    Get evaluation for specific game
    """
    evaluation = db["ncaab_evaluations"].find_one({
        "game_id": game_id,
        "archived": False
    })
    
    if not evaluation:
        raise HTTPException(status_code=404, detail="Evaluation not found")
    
    e = evaluation["evaluation"]
    return EvaluationResponse(
        game_id=evaluation["game_id"],
        state=e["state"],
        primary_market=e["primary_market"],
        reason_codes=e["reason_codes"],
        spread_edge=e["spread_edge"],
        total_edge=e["total_edge"],
        compressed_prob_spread=e["compressed_prob_spread"],
        compressed_prob_total=e["compressed_prob_total"],
        volatility_bucket=e["volatility_bucket"],
        distribution_flag=e["distribution_flag"],
        market_confirmation=e["market_confirmation"],
        evaluated_at=e["evaluated_at"]
    )


# ============================================================================
# PROBABILITY NORMALIZATION REFERENCE
# ============================================================================

@router.get("/normalize-prob", response_model=Dict[str, float])
async def normalize_probability(
    raw_prob: float = Query(..., ge=0, le=1, description="Raw probability (0-1)"),
    db: Database = Depends(get_db)
):
    """
    Reference endpoint: normalize a probability
    
    Formula: compressed = 0.5 + (raw - 0.5) * 0.80
    
    This removes false certainty from college basketball simulations
    """
    evaluator = NCAABEdgeEvaluator(db)
    compressed = evaluator.normalize_probability(raw_prob)
    
    return {
        "raw_probability": raw_prob,
        "compressed_probability": compressed,
        "compression_factor": 0.80,
        "note": "All user-facing NCAAB probabilities must use compressed values"
    }
