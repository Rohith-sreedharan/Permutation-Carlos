"""
NCAAF Edge Evaluation Routes
FastAPI endpoints for NCAA Football edge evaluation system
Locked specification implementation
"""

from fastapi import APIRouter, HTTPException, Query
from datetime import datetime, timedelta
from pydantic import BaseModel, Field
from typing import Optional, List

from services.ncaaf_edge_evaluator import (
    NCAAFEdgeEvaluator,
    SimulationOutput,
    MarketData,
    GameContext,
    EdgeState,
    MarketType,
    NCAAFGameEvaluation
)
from db.mongo import db


router = APIRouter(prefix="/api/ncaaf", tags=["NCAAF"])


# ====== REQUEST/RESPONSE SCHEMAS ======

class GameEvaluationRequest(BaseModel):
    """Request to evaluate a single game"""
    game_id: str = Field(..., description="Unique game identifier")
    game_context: dict = Field(..., description="Game context (teams, week, QB status, etc.)")
    simulation_output: dict = Field(..., description="Simulation results")
    market_data: dict = Field(..., description="Live market conditions")
    volatility_level: str = Field(default="LOW", description="LOW|MEDIUM|HIGH|EXTREME")


class SlateEvaluationRequest(BaseModel):
    """Request to evaluate entire slate"""
    slate_date: str = Field(..., description="YYYY-MM-DD format")
    games: List[dict] = Field(..., description="List of games with context/sim/market data")


class EvaluationResponse(BaseModel):
    """Response from evaluation"""
    game_id: str
    combined_state: str  # EDGE | LEAN | NO_PLAY
    primary_market: str  # SPREAD | TOTAL | NONE
    compressed_spread_prob: float
    compressed_total_prob: float
    reason_codes: List[str]
    market_confirmation: dict
    timestamp: datetime


class SlateResponse(BaseModel):
    """Response from slate evaluation"""
    slate_date: str
    total_games: int
    summary: dict
    evaluations: List[dict]


# ====== ENDPOINTS ======

@router.post(
    "/evaluate/game",
    response_model=EvaluationResponse,
    summary="Evaluate single game",
    description="Runs two-layer NCAAF edge evaluation on a single game"
)
async def evaluate_game(request: GameEvaluationRequest):
    """
    Evaluate a single NCAA Football game
    
    Returns:
    - state: EDGE (Telegram-worthy) | LEAN (informational) | NO_PLAY (default)
    - reason_codes: Debug codes for transparency
    - compressed_probs: Probability compression applied
    
    Example request:
    ```json
    {
        "game_id": "ncaaf_ohio_state_michigan",
        "game_context": {
            "home_team": "Ohio State",
            "away_team": "Michigan",
            "week": 12,
            "qb_status": "confirmed",
            "is_rivalry": true
        },
        "simulation_output": {
            "spread_win_prob": 0.68,
            "total_over_prob": 0.55,
            "spread_edge_pts": 7.5,
            "total_edge_pts": 5.2,
            "distribution_std": 3.1
        },
        "market_data": {
            "spread_line": -9.5,
            "total_line": 48.5,
            "clv_forecast": 0.35,
            "line_move_toward_model": true
        },
        "volatility_level": "LOW"
    }
    ```
    """
    try:
        evaluator = NCAAFEdgeEvaluator(db)
        
        # Construct objects
        game_ctx = GameContext(**request.game_context)
        sim_output = SimulationOutput(**request.simulation_output)
        market_data_obj = MarketData(**request.market_data)
        
        # Run evaluation
        result = await evaluator.evaluate_game(
            game_id=request.game_id,
            game_context=game_ctx,
            simulation_output=sim_output,
            market_data=market_data_obj,
            volatility_level=request.volatility_level
        )
        
        return EvaluationResponse(
            game_id=result.game_id,
            combined_state=result.combined_state,
            primary_market=result.primary_market,
            compressed_spread_prob=result.compressed_spread_prob,
            compressed_total_prob=result.compressed_total_prob,
            reason_codes=result.reason_codes,
            market_confirmation=result.market_confirmation,
            timestamp=result.timestamp
        )
    
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Evaluation failed: {str(e)}")


@router.post(
    "/evaluate/slate",
    response_model=SlateResponse,
    summary="Evaluate entire slate",
    description="Evaluates all games for a given Saturday slate"
)
async def evaluate_slate(request: SlateEvaluationRequest):
    """
    Evaluate entire NCAAF slate (all Saturday games)
    
    Returns:
    - Summary: edge/lean/no_play counts and percentages
    - Full evaluations: All game details
    
    Example:
    ```json
    {
        "slate_date": "2024-11-09",
        "games": [
            {
                "game_id": "ncaaf_ohio_state_michigan",
                "game_context": {...},
                "simulation_output": {...},
                "market_data": {...}
            },
            ...
        ]
    }
    ```
    """
    try:
        evaluator = NCAAFEdgeEvaluator(db)
        result = await evaluator.evaluate_slate(
            slate_date=request.slate_date,
            games=request.games
        )
        
        return SlateResponse(**result)
    
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Slate evaluation failed: {str(e)}")


@router.get(
    "/evaluations/recent",
    summary="Get recent evaluations",
    description="Fetch most recent NCAAF evaluations with optional filtering"
)
async def get_recent_evaluations(
    limit: int = Query(20, ge=1, le=100),
    state: Optional[str] = Query(None, description="Filter by state: EDGE|LEAN|NO_PLAY")
):
    """
    Retrieve recent NCAAF evaluations
    
    Query parameters:
    - limit: Number of evaluations to return (1-100, default 20)
    - state: Optional filter by EDGE|LEAN|NO_PLAY
    
    Returns: List of evaluations sorted by timestamp (newest first)
    """
    try:
        evaluator = NCAAFEdgeEvaluator(db)
        results = await evaluator.get_recent_evaluations(limit=limit, state_filter=state)
        
        return {
            "count": len(results),
            "evaluations": results
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Query failed: {str(e)}")


@router.get(
    "/stats/slate/{slate_date}",
    summary="Get slate statistics",
    description="Daily statistics and system health check for NCAAF slate"
)
async def get_slate_stats(slate_date: str):
    """
    Get daily slate statistics and system health
    
    Returns:
    - Distribution: EDGE/LEAN/NO_PLAY percentages
    - Probability analysis: Average compressed prob, % in optimal range
    - Health warnings: Alerts if thresholds are miscalibrated
    
    Example response:
    ```json
    {
        "slate_date": "2024-11-09",
        "status": "healthy",
        "distribution": {
            "edges": 2,
            "leans": 8,
            "no_plays": 35,
            "edge_percentage": "5.1%",
            "lean_percentage": "20.5%",
            "no_play_percentage": "74.4%"
        },
        "probability_analysis": {
            "average_compressed_prob": "0.556",
            "probs_54_60_percentage": "68.2%"
        },
        "warnings": []
    }
    ```
    """
    try:
        evaluator = NCAAFEdgeEvaluator(db)
        health = await evaluator.health_check()
        
        return {
            "slate_date": slate_date,
            **health
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Stats request failed: {str(e)}")


@router.get(
    "/evaluation/{game_id}",
    summary="Get specific evaluation",
    description="Retrieve evaluation for a specific game"
)
async def get_evaluation(game_id: str):
    """
    Get evaluation details for a single game
    
    Returns:
    - Full evaluation including internal state for debugging
    - Market data at time of evaluation
    - Reasoning for classification
    """
    try:
        evaluator = NCAAFEdgeEvaluator(db)
        result = await evaluator.get_evaluation(game_id)
        
        if not result:
            raise HTTPException(status_code=404, detail=f"Game {game_id} not found")
        
        return result
    
    except Exception as e:
        if isinstance(e, HTTPException):
            raise
        raise HTTPException(status_code=500, detail=f"Lookup failed: {str(e)}")


@router.get(
    "/normalize-prob",
    summary="Probability normalization reference",
    description="Shows how probability compression works for NCAAF"
)
async def normalize_prob_reference():
    """
    Reference endpoint showing probability normalization formula
    
    College football uses aggressive compression (0.80 factor) due to:
    - Massive talent disparities
    - Blowout feedback loops
    - Garbage time distortion
    
    Formula:
    compressed = 0.5 + (raw - 0.5) * 0.80
    
    Examples:
    - Raw 0.70 (very confident) → Compressed 0.66 (reduced certainty)
    - Raw 0.60 (moderately confident) → Compressed 0.58 (slight reduction)
    - Raw 0.55 (slight lean) → Compressed 0.54 (minimal change)
    - Raw 0.50 (toss-up) → Compressed 0.50 (unchanged)
    """
    evaluator = NCAAFEdgeEvaluator(db)
    
    # Generate examples
    raw_probs = [0.50, 0.55, 0.60, 0.65, 0.70, 0.75, 0.80, 0.85]
    examples = [
        {
            "raw_probability": prob,
            "compressed_probability": evaluator._compress_probability(prob),
            "compression_applied": evaluator.config["compression_factor"]
        }
        for prob in raw_probs
    ]
    
    return {
        "formula": "compressed = 0.5 + (raw - 0.5) * 0.80",
        "compression_factor": evaluator.config["compression_factor"],
        "purpose": "Remove false certainty from college blowouts",
        "examples": examples,
        "config": {
            "spread_eligibility_min": evaluator.config["spread_eligibility_min"],
            "spread_edge_min": evaluator.config["spread_edge_min"],
            "spread_lean_min": evaluator.config["spread_lean_min"],
            "total_eligibility_min": evaluator.config["total_eligibility_min"],
            "total_edge_min": evaluator.config["total_edge_min"],
            "total_lean_min": evaluator.config["total_lean_min"],
            "large_favorite_threshold": evaluator.config["large_favorite_threshold"],
            "large_favorite_edge_min": evaluator.config["large_favorite_edge_min"],
            "large_underdog_threshold": evaluator.config["large_underdog_threshold"],
        }
    }


# ====== HEALTH & MONITORING ======

@router.get(
    "/health",
    summary="System health check",
    description="Quick health check for NCAAF system"
)
async def health_check():
    """System health status"""
    try:
        evaluator = NCAAFEdgeEvaluator(db)
        health = await evaluator.health_check()
        return health
    except Exception as e:
        return {"status": "error", "message": str(e)}
