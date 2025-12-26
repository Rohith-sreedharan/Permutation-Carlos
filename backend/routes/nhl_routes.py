"""
NHL Edge Evaluation API Routes

6 Endpoints:
1. POST /api/nhl/evaluate/game - Single game evaluation
2. POST /api/nhl/evaluate/slate - Daily slate evaluation
3. GET /api/nhl/evaluations/recent - Recent evaluations with filtering
4. GET /api/nhl/stats/date/{date} - Daily statistics + health check
5. GET /api/nhl/evaluation/{game_id} - Specific game evaluation
6. GET /api/nhl/compression-guide - Probability compression reference + examples

All routes include protective calibration gates per locked specification.
"""

from fastapi import APIRouter, Query, Path, HTTPException
from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field
import logging

from services.nhl_edge_evaluator import (
    NHLEdgeEvaluator,
    EdgeState,
    GameContext,
    MarketData,
    SimulationOutput,
)
from db.mongo import db

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/nhl", tags=["NHL Edge Evaluation"])

# Initialize evaluator
evaluator = NHLEdgeEvaluator(db=db)


# ============================================================================
# REQUEST/RESPONSE MODELS
# ============================================================================

class GameEvaluationRequest(BaseModel):
    """Request for single game evaluation"""
    game_id: str = Field(..., description="Unique game identifier")
    date: str = Field(..., description="Game date (YYYY-MM-DD)")
    home_team: str = Field(..., description="Home team")
    away_team: str = Field(..., description="Away team")
    market_line: float = Field(..., description="Spread line")
    market_total: float = Field(..., description="Over/Under total")
    market_prob: float = Field(..., ge=0.0, le=1.0, description="Implied win probability")
    
    # Simulation outputs
    win_probability_raw: float = Field(..., ge=0.0, le=1.0, description="Raw simulation win prob")
    goal_differential: float = Field(..., description="Expected goal differential (model - opponent)")
    ot_frequency: float = Field(..., ge=0.0, le=1.0, description="% of sims ending in OT")
    one_goal_games: float = Field(..., ge=0.0, le=1.0, description="% of sims within 1 goal")
    volatility_index: float = Field(..., ge=0.0, description="Distribution spread measure")
    confidence_score: int = Field(..., ge=0, le=100, description="Convergence score")
    
    # Optional market signals
    clv_forecast: Optional[float] = Field(None, description="Closing line value forecast")
    line_moved: bool = Field(False, description="Has line moved toward model side?")


class SlateEvaluationRequest(BaseModel):
    """Request for daily slate evaluation"""
    date: str = Field(..., description="Slate date (YYYY-MM-DD)")
    games: List[Dict[str, Any]] = Field(..., description="List of games with simulation data")


class GameEvaluationResponse(BaseModel):
    """Response for game evaluation"""
    game_id: str
    combined_state: str
    primary_market: str
    compressed_win_prob: float
    goal_edge: float
    reason_codes: List[str]
    market_confirmation: Dict[str, bool]
    internal_state: Dict[str, Any]
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class SlateEvaluationResponse(BaseModel):
    """Response for slate evaluation"""
    date: str
    total_games: int
    edge_count: int
    lean_count: int
    no_play_count: int
    evaluations: List[GameEvaluationResponse]
    statistics: Dict[str, Any]


class CompressionGuideExample(BaseModel):
    """Example of probability compression"""
    raw_probability: float
    compressed_probability: float
    difference: float
    interpretation: str


# ============================================================================
# ROUTE 1: SINGLE GAME EVALUATION
# ============================================================================

@router.post(
    "/evaluate/game",
    response_model=GameEvaluationResponse,
    summary="Evaluate single NHL game for edge",
    tags=["Game Evaluation"]
)
async def evaluate_game(request: GameEvaluationRequest) -> GameEvaluationResponse:
    """
    Evaluate a single NHL game through protective calibration gates
    
    All six fixes applied:
    1. Hard-capped edge bounds (±3.0% win prob, ±1.25 goals)
    2. Probability compression (0.6 factor)
    3. Multi-gate validation (all must pass)
    4. Distribution sanity check (invalidate high OT/1-goal)
    5. Volatility override (forces NO_PLAY if exceeds ceiling)
    6. Market efficiency floor (anti-spam guard)
    
    Expected outputs:
    - Most games → NO_PLAY
    - Occasional LEAN (informational)
    - EDGE = very rare
    
    Parameters:
    - game_id: Unique identifier
    - date: Game date (YYYY-MM-DD)
    - market_line: Current spread
    - market_prob: Implied win probability from line
    - Simulation data: Raw outputs from Monte Carlo engine
    
    Returns:
    GameEvaluationResponse with:
    - combined_state: EDGE | LEAN | NO_PLAY
    - compressed_win_prob: After 0.6 compression
    - reason_codes: Debug information
    - internal_state: Full evaluation state
    """
    try:
        game_context = GameContext(
            game_id=request.game_id,
            date=request.date,
            home_team=request.home_team,
            away_team=request.away_team,
            market_line=request.market_line,
            market_total=request.market_total,
            clv_forecast=request.clv_forecast,
        )
        
        simulation = SimulationOutput(
            win_probability_raw=request.win_probability_raw,
            goal_differential=request.goal_differential,
            ot_frequency=request.ot_frequency,
            one_goal_games=request.one_goal_games,
            volatility_index=request.volatility_index,
            confidence_score=request.confidence_score,
        )
        
        evaluation = await evaluator.evaluate_game(
            game_id=request.game_id,
            game_context=game_context,
            simulation=simulation,
            market_prob=request.market_prob,
        )
        
        return GameEvaluationResponse(
            game_id=evaluation.game_id,
            combined_state=evaluation.combined_state.value,
            primary_market=evaluation.primary_market,
            compressed_win_prob=evaluation.compressed_win_prob,
            goal_edge=evaluation.goal_edge,
            reason_codes=evaluation.reason_codes,
            market_confirmation=evaluation.market_confirmation.dict(),
            internal_state=evaluation.internal_state,
        )
    
    except Exception as e:
        logger.error(f"Error evaluating game {request.game_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# ROUTE 2: DAILY SLATE EVALUATION
# ============================================================================

@router.post(
    "/evaluate/slate",
    response_model=SlateEvaluationResponse,
    summary="Evaluate daily NHL slate",
    tags=["Slate Evaluation"]
)
async def evaluate_slate(request: SlateEvaluationRequest) -> SlateEvaluationResponse:
    """
    Evaluate a complete daily NHL slate (7-14 games)
    
    Batch processes all games and returns:
    - Individual game evaluations
    - Slate-level statistics
    - Expected behavior confirmation
    
    Parameters:
    - date: Slate date (YYYY-MM-DD)
    - games: List of games with simulation data
    
    Returns:
    SlateEvaluationResponse with:
    - Counts of EDGE/LEAN/NO_PLAY
    - Statistics and percentage breakdowns
    - All individual game evaluations
    
    Expected results:
    - Most games = NO_PLAY (60-90%)
    - Few games = LEAN (10-30%)
    - Rare = EDGE (<5%)
    """
    try:
        result = await evaluator.evaluate_slate(
            date=request.date,
            games=request.games,
        )
        
        return SlateEvaluationResponse(
            date=result["date"],
            total_games=result["total_games"],
            edge_count=result["edge_count"],
            lean_count=result["lean_count"],
            no_play_count=result["no_play_count"],
            evaluations=[
                GameEvaluationResponse(
                    game_id=e.game_id,
                    combined_state=e.combined_state.value,
                    primary_market=e.primary_market,
                    compressed_win_prob=e.compressed_win_prob,
                    goal_edge=e.goal_edge,
                    reason_codes=e.reason_codes,
                    market_confirmation=e.market_confirmation.dict(),
                    internal_state=e.internal_state,
                )
                for e in result["evaluations"]
            ],
            statistics=result["statistics"],
        )
    
    except Exception as e:
        logger.error(f"Error evaluating slate {request.date}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# ROUTE 3: RECENT EVALUATIONS
# ============================================================================

@router.get(
    "/evaluations/recent",
    summary="Retrieve recent evaluations with filtering",
    tags=["Evaluation History"]
)
async def get_recent_evaluations(
    limit: int = Query(20, ge=1, le=100, description="Number of records"),
    state: Optional[str] = Query(None, description="Filter by state: EDGE|LEAN|NO_PLAY"),
) -> Dict[str, Any]:
    """
    Retrieve recent evaluations from database
    
    Parameters:
    - limit: Number of records (1-100, default 20)
    - state: Optional filter by classification state
    
    Returns:
    List of evaluations with most recent first
    
    Example:
    GET /api/nhl/evaluations/recent?limit=10&state=EDGE
    """
    try:
        evaluations = await evaluator.get_recent_evaluations(
            limit=limit,
            state_filter=state,
        )
        
        return {
            "count": len(evaluations),
            "limit": limit,
            "state_filter": state,
            "evaluations": evaluations,
        }
    
    except Exception as e:
        logger.error(f"Error retrieving recent evaluations: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# ROUTE 4: DAILY STATISTICS + HEALTH CHECK
# ============================================================================

@router.get(
    "/stats/date/{date}",
    summary="Daily statistics and system health check",
    tags=["Statistics"]
)
async def get_daily_stats(
    date: str = Path(..., description="Date (YYYY-MM-DD)")
) -> Dict[str, Any]:
    """
    Get daily evaluations statistics and validate system health
    
    Includes:
    - Game count by state (EDGE/LEAN/NO_PLAY)
    - Statistical breakdown
    - System health check with all 6 fixes verified
    - Expected behavior confirmation
    
    Parameters:
    - date: Query date (YYYY-MM-DD)
    
    Returns:
    Dictionary with:
    - date_stats: Games by state
    - percentage_breakdown: % EDGE, LEAN, NO_PLAY
    - health_check: All fixes verified as present
    - system_status: healthy|misconfigured
    
    Example:
    GET /api/nhl/stats/date/2024-12-25
    """
    try:
        # Get health check
        health = await evaluator.health_check()
        
        # Retrieve all evaluations for date
        evaluations = await evaluator.get_recent_evaluations(limit=100)
        
        # Filter by date if needed
        date_evals = [
            e for e in evaluations
            if e.get("evaluation", {}).get("timestamp", "").startswith(date)
        ] if evaluations else []
        
        edge_count = sum(1 for e in date_evals if e.get("evaluation", {}).get("combined_state") == "EDGE")
        lean_count = sum(1 for e in date_evals if e.get("evaluation", {}).get("combined_state") == "LEAN")
        no_play_count = sum(1 for e in date_evals if e.get("evaluation", {}).get("combined_state") == "NO_PLAY")
        
        total = edge_count + lean_count + no_play_count
        
        return {
            "date": date,
            "date_stats": {
                "total_games": total,
                "edge_count": edge_count,
                "lean_count": lean_count,
                "no_play_count": no_play_count,
            },
            "percentage_breakdown": {
                "edge_percent": (edge_count / total * 100) if total > 0 else 0,
                "lean_percent": (lean_count / total * 100) if total > 0 else 0,
                "no_play_percent": (no_play_count / total * 100) if total > 0 else 0,
            },
            "health_check": health,
            "system_status": health["status"],
            "expected_behavior": health["expected_behavior"],
        }
    
    except Exception as e:
        logger.error(f"Error getting daily stats for {date}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# ROUTE 5: SPECIFIC GAME EVALUATION
# ============================================================================

@router.get(
    "/evaluation/{game_id}",
    summary="Retrieve specific game evaluation with internal state",
    tags=["Evaluation History"]
)
async def get_evaluation(
    game_id: str = Path(..., description="Game ID")
) -> Dict[str, Any]:
    """
    Retrieve complete evaluation for specific game
    
    Includes internal state for debugging and validation
    
    Parameters:
    - game_id: Unique game identifier
    
    Returns:
    Complete evaluation with:
    - combined_state: EDGE|LEAN|NO_PLAY
    - reason_codes: All decision gates
    - internal_state: Debug information
    - timestamp: Evaluation datetime
    
    Example:
    GET /api/nhl/evaluation/nhl_2024_12_25_vegas_edmonton
    """
    try:
        evaluation = await evaluator.get_evaluation(game_id)
        
        if not evaluation:
            raise HTTPException(status_code=404, detail=f"Game {game_id} not found")
        
        return {
            "game_id": game_id,
            "found": True,
            "evaluation": evaluation.get("evaluation", {}),
            "updated_at": evaluation.get("updated_at", None),
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving evaluation for {game_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# ROUTE 6: COMPRESSION GUIDE + EXAMPLES
# ============================================================================

@router.get(
    "/compression-guide",
    summary="Probability compression reference with examples",
    tags=["Reference"]
)
async def get_compression_guide() -> Dict[str, Any]:
    """
    Reference guide for NHL probability compression (FIX #2)
    
    Explains the 0.6 compression factor and shows examples
    
    Returns:
    Compression guide with:
    - Formula: compressed = 0.5 + (raw - 0.5) * 0.6
    - Why: Removes false certainty, preserves direction
    - Examples: Common probability compressions
    - Effect: Typical 60% raw → 54% compressed
    
    NHL-specific:
    - Compression factor = 0.6 (moderate)
    - Respects market efficiency
    - Prevents overconfidence
    """
    
    # Generate compression examples
    raw_probs = [0.50, 0.55, 0.60, 0.65, 0.70, 0.75]
    compression_examples = []
    
    for raw in raw_probs:
        compressed = 0.5 + (raw - 0.5) * 0.6
        difference = raw - compressed
        
        if raw == 0.50:
            interp = "Even odds"
        elif raw <= 0.55:
            interp = "Slight edge, minimal after compression"
        elif raw <= 0.65:
            interp = "Moderate edge, dampened by compression"
        else:
            interp = "Strong edge, still capped by compression"
        
        compression_examples.append({
            "raw_probability": raw,
            "compressed_probability": round(compressed, 4),
            "difference": round(difference, 4),
            "interpretation": interp,
        })
    
    return {
        "sport": "NHL",
        "compression_factor": 0.6,
        "formula": "compressed = 0.5 + (raw - 0.5) * 0.6",
        "purpose": "Remove false certainty while preserving direction",
        "why_0_6": [
            "NHL markets are efficient and tight",
            "Prevents overconfidence from raw simulations",
            "Moderate dampening preserves real edges",
            "Aligns with 52-56% typical win prob range",
        ],
        "examples": compression_examples,
        "typical_effect": {
            "60_percent_raw": "54% compressed",
            "55_percent_raw": "53% compressed",
            "50_percent_raw": "50% compressed (unchanged)",
        },
        "interpretation": {
            "EDGE": "Extremely rare in NHL; passes all gates with confirmatory signals",
            "LEAN": "Occasional, informational only; lower confidence or no confirmation",
            "NO_PLAY": "Default state for most games (correct and expected)",
        },
        "note": "This compression is applied BEFORE edge classification logic",
    }


# ============================================================================
# HEALTH CHECK / DIAGNOSTIC ENDPOINT (INTERNAL)
# ============================================================================

@router.get(
    "/health",
    summary="System health check",
    tags=["Diagnostics"],
    include_in_schema=False
)
async def health_check() -> Dict[str, Any]:
    """Internal health check endpoint"""
    return await evaluator.health_check()
