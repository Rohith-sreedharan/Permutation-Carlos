"""
Signal API Routes
Immutable signal architecture with locking, deltas, and history
"""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from pymongo.database import Database
from pymongo import MongoClient
from dotenv import load_dotenv
import os

load_dotenv()

from services.signal_manager import SignalManager
from db.schemas.signal_schemas import (
    Signal,
    MarketSnapshot,
    SignalDelta,
    LockedSignal,
    SignalState,
    SignalIntent,
    VolatilityBucket,
    ConfidenceBand,
    GateEvaluation,
    GateResult,
    ReasonCode
)
from middleware.auth import get_current_user  # Assumes existing auth


router = APIRouter(prefix="/api/signals", tags=["signals"])


# Database connection helper
async def get_db() -> Database:
    """Get MongoDB database connection"""
    mongodb_uri = os.getenv("MONGO_URI", "mongodb://localhost:27017")
    database_name = os.getenv("DATABASE_NAME", "beatvegas")
    client = MongoClient(mongodb_uri)
    return client[database_name]


# ============================================================================
# REQUEST/RESPONSE MODELS
# ============================================================================

class CreateSignalRequest(BaseModel):
    """Request to create a new immutable signal"""
    game_id: str
    sport: str
    market_key: str
    selection: str
    line_value: float
    
    # Market snapshot data
    spread_line: Optional[float] = None
    spread_home_price: Optional[int] = None
    spread_away_price: Optional[int] = None
    total_line: Optional[float] = None
    total_over_price: Optional[int] = None
    total_under_price: Optional[int] = None
    ml_home_price: Optional[int] = None
    ml_away_price: Optional[int] = None
    
    # Simulation data
    model_version: str
    inputs_version: str
    seed: int
    num_sims: int
    distribution: Dict[str, float]
    
    # Signal parameters
    intent: SignalIntent
    edge_points: float
    win_prob: float
    volatility_score: float
    volatility_bucket: VolatilityBucket
    confidence_band: ConfidenceBand
    
    # Gate results
    gates: GateEvaluation
    explain_summary: str
    
    odds_price: Optional[int] = None
    ev: Optional[float] = None
    book_key: str = "CONSENSUS"


class SignalResponse(BaseModel):
    """Full signal response"""
    signal: Signal
    market_snapshot: Optional[MarketSnapshot] = None
    locked: bool = False
    lock_info: Optional[LockedSignal] = None
    has_updates: bool = False
    latest_delta: Optional[SignalDelta] = None


# ============================================================================
# SIGNAL ENDPOINTS
# ============================================================================

@router.post("/create", response_model=SignalResponse)
async def create_signal_endpoint(
    request: CreateSignalRequest,
    user: Dict = Depends(get_current_user)
):
    """
    Create a new immutable signal
    Re-simulations create NEW signals, never overwrite
    """
    db = await get_db()
    manager = SignalManager(db)
    
    # Create market snapshot
    snapshot = await manager.create_market_snapshot(
        game_id=request.game_id,
        spread_line=request.spread_line,
        spread_home_price=request.spread_home_price,
        spread_away_price=request.spread_away_price,
        total_line=request.total_line,
        total_over_price=request.total_over_price,
        total_under_price=request.total_under_price,
        ml_home_price=request.ml_home_price,
        ml_away_price=request.ml_away_price
    )
    
    # Record simulation run
    sim_run = await manager.record_simulation_run(
        game_id=request.game_id,
        model_version=request.model_version,
        inputs_version=request.inputs_version,
        seed=request.seed,
        num_sims=request.num_sims,
        distribution=request.distribution
    )
    
    # Create signal
    signal = await manager.create_signal(
        game_id=request.game_id,
        sport=request.sport,
        market_key=request.market_key,
        selection=request.selection,
        line_value=request.line_value,
        market_snapshot_id=snapshot.market_snapshot_id,
        sim_run_id=sim_run.sim_run_id,
        model_version=request.model_version,
        intent=request.intent,
        edge_points=request.edge_points,
        win_prob=request.win_prob,
        volatility_score=request.volatility_score,
        volatility_bucket=request.volatility_bucket,
        confidence_band=request.confidence_band,
        gates=request.gates,
        explain_summary=request.explain_summary,
        odds_price=request.odds_price,
        ev=request.ev,
        book_key=request.book_key
    )
    
    # Check lock status
    is_locked, lock_info = await manager.check_lock_status(
        request.game_id,
        request.market_key
    )
    
    return SignalResponse(
        signal=signal,
        market_snapshot=snapshot,
        locked=is_locked,
        lock_info=lock_info,
        has_updates=False,
        latest_delta=None
    )


@router.get("/game/{game_id}/market/{market_key}", response_model=SignalResponse)
async def get_latest_signal(
    game_id: str,
    market_key: str,
    user: Dict = Depends(get_current_user)
):
    """
    Get the latest signal for a specific game/market
    Includes lock status and update availability
    """
    db = await get_db()
    manager = SignalManager(db)
    
    # Get latest signal
    signal = await manager.get_latest_signal(game_id, market_key)
    
    if not signal:
        raise HTTPException(status_code=404, detail="No signal found")
    
    # Get market snapshot
    snapshot_doc = db["market_snapshots"].find_one({
        "market_snapshot_id": signal.market_snapshot_id
    })
    snapshot = MarketSnapshot(**snapshot_doc) if snapshot_doc else None
    
    # Check lock status
    is_locked, lock_info = await manager.check_lock_status(game_id, market_key)
    
    # Check for updates (if locked signal exists, check if newer signals available)
    has_updates = False
    latest_delta = None
    
    if is_locked and lock_info:
        locked_signal = await manager.get_signal(lock_info.signal_id)
        if locked_signal and signal.signal_id != locked_signal.signal_id:
            has_updates = True
            # Compute delta
            latest_delta = await manager.compute_delta(
                locked_signal.signal_id,
                signal.signal_id
            )
    
    return SignalResponse(
        signal=signal,
        market_snapshot=snapshot,
        locked=is_locked,
        lock_info=lock_info,
        has_updates=has_updates,
        latest_delta=latest_delta
    )


@router.get("/game/{game_id}/market/{market_key}/history", response_model=List[Signal])
async def get_signal_history(
    game_id: str,
    market_key: str,
    limit: int = 10,
    user: Dict = Depends(get_current_user)
):
    """Get signal history for a market"""
    db = await get_db()
    manager = SignalManager(db)
    
    signals = await manager.get_signal_history(game_id, market_key, limit)
    
    return signals


@router.get("/{signal_id}", response_model=Signal)
async def get_signal_by_id(
    signal_id: str,
    user: Dict = Depends(get_current_user)
):
    """Get a specific signal by ID"""
    db = await get_db()
    manager = SignalManager(db)
    
    signal = await manager.get_signal(signal_id)
    
    if not signal:
        raise HTTPException(status_code=404, detail="Signal not found")
    
    return signal


# ============================================================================
# DELTA ENDPOINTS
# ============================================================================

@router.get("/delta/{from_signal_id}/{to_signal_id}", response_model=SignalDelta)
async def get_delta(
    from_signal_id: str,
    to_signal_id: str,
    user: Dict = Depends(get_current_user)
):
    """
    Get delta between two signals
    Shows what changed
    """
    db = await get_db()
    manager = SignalManager(db)
    
    delta = await manager.compute_delta(from_signal_id, to_signal_id)
    
    return delta


# ============================================================================
# LOCKING ENDPOINTS
# ============================================================================

@router.post("/lock/{signal_id}", response_model=LockedSignal)
async def lock_signal(
    signal_id: str,
    freeze_duration_minutes: int = 60,
    user: Dict = Depends(get_current_user)
):
    """
    Manually lock a signal
    Prevents re-sim churn
    """
    db = await get_db()
    manager = SignalManager(db)
    
    locked = await manager.lock_signal(
        signal_id,
        lock_type="MANUAL",
        freeze_duration_minutes=freeze_duration_minutes,
        lock_reason="MANUAL_LOCK"
    )
    
    return locked


@router.get("/lock/status/{game_id}/{market_key}")
async def get_lock_status(
    game_id: str,
    market_key: str,
    user: Dict = Depends(get_current_user)
):
    """Check if market is locked"""
    db = await get_db()
    manager = SignalManager(db)
    
    is_locked, lock_info = await manager.check_lock_status(game_id, market_key)
    
    return {
        "is_locked": is_locked,
        "lock_info": lock_info.model_dump() if lock_info else None
    }


# ============================================================================
# SETTLEMENT ENDPOINTS
# ============================================================================

class SettleSignalRequest(BaseModel):
    """Request to settle a signal"""
    outcome: str = Field(..., description="WIN, LOSS, PUSH, or VOID")
    actual_result: Optional[float] = None


@router.post("/{signal_id}/settle")
async def settle_signal(
    signal_id: str,
    request: SettleSignalRequest,
    user: Dict = Depends(get_current_user)
):
    """
    Settle a signal with final outcome
    Marks signal as SETTLED
    """
    db = await get_db()
    manager = SignalManager(db)
    
    await manager.settle_signal(
        signal_id,
        request.outcome,
        request.actual_result
    )
    
    return {"status": "ok", "message": "Signal settled"}


# ============================================================================
# ADMIN/ANALYTICS ENDPOINTS
# ============================================================================

@router.get("/analytics/robustness/{game_id}/{market_key}")
async def get_robustness_analysis(
    game_id: str,
    market_key: str,
    user: Dict = Depends(get_current_user)
):
    """
    Get robustness analysis for a market
    Shows stability over time
    """
    db = await get_db()
    manager = SignalManager(db)
    
    signals = await manager.get_signal_history(game_id, market_key, limit=10)
    
    if not signals:
        raise HTTPException(status_code=404, detail="No signals found")
    
    # Compute metrics
    states = [s.state.value for s in signals]
    state_counts = {state: states.count(state) for state in set(states)}
    
    edges = [s.edge_points for s in signals]
    avg_edge = sum(edges) / len(edges)
    edge_std = (sum((e - avg_edge)**2 for e in edges) / len(edges)) ** 0.5
    
    return {
        "game_id": game_id,
        "market_key": market_key,
        "total_signals": len(signals),
        "state_distribution": state_counts,
        "avg_edge_points": round(avg_edge, 2),
        "edge_std_dev": round(edge_std, 2),
        "latest_robustness_label": signals[0].robustness_label.value if signals[0].robustness_label else None,
        "latest_robustness_score": signals[0].robustness_score
    }


@router.get("/events/{signal_id}")
async def get_signal_events(
    signal_id: str,
    user: Dict = Depends(get_current_user)
):
    """Get all lifecycle events for a signal"""
    db = await get_db()
    
    cursor = db["signal_events"].find({
        "signal_id": signal_id
    }).sort("created_at", 1)
    
    events = []
    for event in list(cursor):
        event.pop("_id", None)
        events.append(event)
    
    return {"events": events}
