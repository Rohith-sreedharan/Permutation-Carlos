"""
API Routes for Simulation Engine

Endpoints for running simulations, managing signals, and B2B access
"""
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from typing import Optional, List, Dict
from datetime import datetime
from pydantic import BaseModel

from ..core.sport_configs import Sport, MarketType, EdgeState
from ..core.signal_lifecycle import (
    Signal, SignalWave, SignalStatus, SignalIntent,
    create_signal, add_simulation_run, add_market_snapshot
)
from ..core.sharp_side_selection import SharpSideSelection
from ..services.simulation_engine import SimulationEngine
from ..services.signal_manager import SignalManager
from ..middleware.auth import require_user, require_sharp_pass, require_simsports
from ..db.database import get_database, Database

router = APIRouter(prefix="/api/simulation", tags=["simulation"])


# =============================================================================
# REQUEST/RESPONSE MODELS
# =============================================================================

class RunSimulationRequest(BaseModel):
    game_id: str
    sport: Sport
    team_a: str
    team_b: str
    game_time: datetime
    
    # Market data
    team_a_spread: float
    team_a_spread_odds: int
    team_b_spread: float
    team_b_spread_odds: int
    over_line: float
    over_odds: int
    under_line: float
    under_odds: int
    team_a_ml_odds: Optional[int] = None
    team_b_ml_odds: Optional[int] = None
    
    # Simulation parameters
    num_simulations: int = 50000
    wave: SignalWave = SignalWave.WAVE_3_PUBLISH
    intent: SignalIntent = SignalIntent.TRUTH_MODE
    
    # Sport-specific confirmations
    pitcher_confirmed: Optional[bool] = None
    qb_confirmed: Optional[bool] = None
    goalie_confirmed: Optional[bool] = None
    weather_clear: bool = True


class SimulationResult(BaseModel):
    sim_run_id: str
    game_id: str
    sport: str
    wave: str
    
    # Edge results
    edge_state: str
    compressed_edge: float
    raw_edge: float
    
    # Sharp side
    sharp_side: Optional[str] = None
    recommended_bet: Optional[str] = None
    favored_team: Optional[str] = None
    points_side: Optional[str] = None
    
    # Distribution
    volatility: str
    distribution_flag: str
    
    # Metadata
    executed_at: datetime
    execution_duration_ms: int


class SignalResponse(BaseModel):
    signal_id: str
    game_id: str
    status: str
    intent: str
    
    # Latest simulation
    latest_edge_state: Optional[str] = None
    latest_compressed_edge: Optional[float] = None
    latest_sharp_side: Optional[str] = None
    
    # Entry snapshot (if published)
    entry_sharp_side: Optional[str] = None
    entry_market_type: Optional[str] = None
    entry_spread: Optional[float] = None
    entry_total: Optional[float] = None
    entry_odds: Optional[int] = None
    
    # Timing
    created_at: datetime
    published_at: Optional[datetime] = None
    
    # Result
    final_result: Optional[str] = None


# =============================================================================
# ENDPOINTS
# =============================================================================

@router.post("/run", response_model=SimulationResult)
async def run_simulation_endpoint(
    request: RunSimulationRequest,
    background_tasks: BackgroundTasks,
    user = Depends(require_simsports),
    db: Database = Depends(get_database)
):
    """
    Run simulation for a game
    
    Access: All authenticated users
    
    For Wave 3 (publish), requires appropriate subscription tier
    """
    # TODO: Check subscription tier for Wave 3 publish
    
    try:
        # Run simulation
        engine = SimulationEngine(db)
        result = await engine.run_simulation(
            game_id=request.game_id,
            sport=request.sport,
            market_type=MarketType.SPREAD,  # Default to spread
            num_simulations=request.num_simulations,
            team_a_spread=request.team_a_spread,
            team_a_spread_odds=request.team_a_spread_odds,
            team_b_spread=request.team_b_spread,
            team_b_spread_odds=request.team_b_spread_odds,
            over_line=request.over_line,
            over_odds=request.over_odds,
            under_line=request.under_line,
            under_odds=request.under_odds,
            team_a_ml_odds=request.team_a_ml_odds,
            team_b_ml_odds=request.team_b_ml_odds
        )
        
        # Queue background tasks (logging, Telegram, etc.)
        background_tasks.add_task(
            log_simulation_audit,
            sim_run_id=result.get('sim_run_id'),  # type: ignore
            event_type="SIMULATION_COMPLETE"
        )
        
        return SimulationResult(**result)
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/signal/{signal_id}", response_model=SignalResponse)
async def get_signal(
    signal_id: str,
    user = Depends(require_user),
    db: Database = Depends(get_database)
):
    """
    Get signal details
    
    Access: All authenticated users
    """
    signal_manager = SignalManager(db.db)
    signal = await signal_manager.get_signal(signal_id)
    
    if not signal:
        raise HTTPException(status_code=404, detail="Signal not found")
    
    # Check access permissions
    # TODO: Verify user has access to this signal intent
    
    return SignalResponse(
        signal_id=signal.signal_id,
        game_id=signal.game_id,
        status=signal.status.value,  # type: ignore
        intent=signal.intent.value,
        latest_edge_state=signal.simulation_runs[-1].edge_state if signal.simulation_runs else None,  # type: ignore
        latest_compressed_edge=signal.simulation_runs[-1].compressed_edge if signal.simulation_runs else None,  # type: ignore
        latest_sharp_side=signal.simulation_runs[-1].sharp_side if signal.simulation_runs else None,  # type: ignore
        entry_sharp_side=signal.entry_snapshot.sharp_side if signal.entry_snapshot else None,  # type: ignore
        entry_market_type=signal.entry_snapshot.market_type if signal.entry_snapshot else None,  # type: ignore
        entry_spread=signal.entry_snapshot.entry_spread if signal.entry_snapshot else None,  # type: ignore
        entry_total=signal.entry_snapshot.entry_total if signal.entry_snapshot else None,  # type: ignore
        entry_odds=signal.entry_snapshot.entry_odds if signal.entry_snapshot else None,  # type: ignore
        created_at=signal.created_at,
        published_at=signal.published_at,  # type: ignore
        final_result=signal.result  # type: ignore
    )


@router.get("/signals/active", response_model=List[SignalResponse])
async def get_active_signals(
    sport: Optional[Sport] = None,
    intent: Optional[SignalIntent] = None,
    user = Depends(require_user),
    db: Database = Depends(get_database)
):
    """
    Get all active signals
    
    Filters by subscription tier access
    """
    signal_manager = SignalManager(db.db)
    signals = await signal_manager.get_active_signals(  # type: ignore
        sport=sport.value if sport else None,
        intent=intent.value if intent else None
    )
    
    # TODO: Filter by user subscription tier
    
    return [
        SignalResponse(
            signal_id=s.signal_id,
            game_id=s.game_id,
            status=s.status.value,
            intent=s.intent.value,
            latest_edge_state=s.simulation_runs[-1].edge_state if s.simulation_runs else None,
            latest_compressed_edge=s.simulation_runs[-1].compressed_edge if s.simulation_runs else None,
            latest_sharp_side=s.simulation_runs[-1].sharp_side if s.simulation_runs else None,
            entry_sharp_side=s.entry_snapshot.sharp_side if s.entry_snapshot else None,
            entry_market_type=s.entry_snapshot.market_type if s.entry_snapshot else None,
            created_at=s.created_at,
            published_at=s.published_at
        )
        for s in signals
    ]


@router.post("/simsports/run", response_model=SimulationResult)
async def simsports_run_simulation(
    request: RunSimulationRequest,
    user = Depends(require_simsports)
):
    """
    B2B SimSports API endpoint
    
    Access: SimSports subscribers only
    Rate limited based on tier
    """
    # TODO: Check rate limits based on user.simsports_tier
    # TODO: Track API usage
    
    return await run_simulation_endpoint(
        request=request,
        background_tasks=BackgroundTasks(),
        user=user
    )


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

async def log_simulation_audit(sim_run_id: str, event_type: str):
    """Log simulation to audit table"""
    # TODO: Implement audit logging
    pass
