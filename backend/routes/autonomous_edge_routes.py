"""
Autonomous Edge Execution API Routes
Endpoints for three-wave simulation control and monitoring
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from pymongo.database import Database
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
from pydantic import BaseModel, Field

from backend.services.autonomous_edge_engine import (
    AutonomousEdgeEngine,
    EdgeGrade,
    WaveState,
    EntrySnapshot
)


router = APIRouter(prefix="/api/autonomous-edge", tags=["autonomous-edge"])


# ============================================================================
# DATABASE DEPENDENCY
# ============================================================================
from pymongo.database import Database

async def get_db() -> Database:
    """Get database connection"""
    from backend.db.mongo import db
    return db


# ============================================================================
# REQUEST/RESPONSE SCHEMAS
# ============================================================================

class Wave1Request(BaseModel):
    """Wave 1: Primary Scan request"""
    game_id: str = Field(..., description="Unique game identifier")
    sport: str = Field(..., description="Sport type (NBA, NFL, etc)")
    simulation_output: Dict[str, Any] = Field(..., description="100K simulation results")
    market_data: Dict[str, Any] = Field(..., description="Current market snapshot")


class Wave2Request(BaseModel):
    """Wave 2: Stability Scan request"""
    candidate_id: str = Field(..., description="Candidate ID from Wave 1")
    simulation_output: Dict[str, Any] = Field(..., description="Re-run 100K simulation results")
    market_data: Dict[str, Any] = Field(..., description="Updated market snapshot")


class Wave3Request(BaseModel):
    """Wave 3: Final Lock Scan request"""
    candidate_id: str = Field(..., description="Candidate ID validated in Wave 2")
    simulation_output: Dict[str, Any] = Field(..., description="Final 100K simulation results")
    live_market_data: Dict[str, Any] = Field(..., description="Live sportsbook data")
    publish_enabled: bool = Field(default=True, description="Allow Telegram publishing")


class PriceValidationRequest(BaseModel):
    """Price validation before user entry"""
    snapshot_id: str = Field(..., description="Entry snapshot ID")
    current_market_line: float = Field(..., description="Current sportsbook line")


class EntrySnapshotResponse(BaseModel):
    """Entry snapshot response"""
    snapshot_id: str
    game_id: str
    market_type: str
    side: str
    entry_line: float
    entry_odds: int
    model_fair_value: float
    edge_gap: float
    win_probability: float
    clv_estimate: float
    timestamp: str
    max_acceptable_line: float
    signal_id: str
    edge_grade: str
    published: bool


class CandidateStatusResponse(BaseModel):
    """Candidate edge status"""
    candidate_id: str
    game_id: str
    sport: str
    wave: int
    state: str
    edge_gap: float
    win_probability: float
    created_at: str
    block_reason: Optional[str] = None


# ============================================================================
# WAVE 1: PRIMARY SCAN (DISCOVERY)
# ============================================================================

@router.post("/wave1/scan", response_model=Dict[str, Any])
async def wave_1_primary_scan(
    request: Wave1Request,
    db: Database = Depends(get_db)
):
    """
    Wave 1: Primary Scan (Discovery)
    
    Rules:
    - Run T-6h to T-4h before game start
    - 100,000 simulations
    - Store as CANDIDATE_EDGE
    - NO Telegram output
    - NO UI betting prompts
    
    Returns candidate_id if edge detected, null if outside window or no edge
    """
    engine = AutonomousEdgeEngine(db)
    
    candidate_id = await engine.wave_1_primary_scan(
        game_id=request.game_id,
        sport=request.sport,
        simulation_output=request.simulation_output,
        market_data=request.market_data
    )
    
    if not candidate_id:
        return {
            "status": "no_candidate",
            "message": "No edge detected or outside Wave 1 window"
        }
    
    return {
        "status": "candidate_created",
        "candidate_id": candidate_id,
        "wave": 1,
        "state": "CANDIDATE_EDGE",
        "publish_allowed": False
    }


# ============================================================================
# WAVE 2: STABILITY SCAN (VALIDATION)
# ============================================================================

@router.post("/wave2/validate", response_model=Dict[str, Any])
async def wave_2_stability_scan(
    request: Wave2Request,
    db: Database = Depends(get_db)
):
    """
    Wave 2: Stability Scan (Validation)
    
    Rules:
    - Run T-120 minutes before game start
    - Re-run 100,000 simulations
    - Compare vs Wave 1
    - Edge gap change ≤ ±1.5 pts
    - Volatility not increasing
    
    Returns: EDGE_CONFIRMED, LEAN_CONFIRMED, or EDGE_REJECTED
    """
    engine = AutonomousEdgeEngine(db)
    
    state = await engine.wave_2_stability_scan(
        candidate_id=request.candidate_id,
        new_simulation_output=request.simulation_output,
        market_data=request.market_data
    )
    
    # Get updated candidate
    candidate = db["edge_candidates"].find_one({
        "candidate_id": request.candidate_id
    })
    
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
    
    return {
        "status": "validation_complete",
        "candidate_id": request.candidate_id,
        "wave": 2,
        "state": state,
        "stability_passed": candidate.get("stability_passed", False),
        "edge_delta": candidate.get("edge_delta", 0),
        "advance_to_wave3": state in ["EDGE_CONFIRMED", "LEAN_CONFIRMED"]
    }


# ============================================================================
# WAVE 3: FINAL LOCK SCAN (PUBLISH GATE)
# ============================================================================

@router.post("/wave3/publish", response_model=Dict[str, Any])
async def wave_3_final_lock_scan(
    request: Wave3Request,
    db: Database = Depends(get_db)
):
    """
    Wave 3: Final Lock Scan (Publish Gate)
    
    THIS IS THE ONLY RUN THAT CAN PUBLISH
    
    Rules:
    - Run T-75 to T-60 minutes before game start
    - Final 100,000 simulations
    - Pull live sportsbook market line
    - Apply all publish gates
    - Decide POST or SILENCE
    
    Returns entry snapshot if published, null if silenced
    """
    engine = AutonomousEdgeEngine(db)
    
    # Mock telegram service if publish enabled
    telegram_service = None
    if request.publish_enabled:
        # TODO: Inject real TelegramBotService
        from backend.services.telegram_bot_service import TelegramBotService
        telegram_service = TelegramBotService(db)
    
    entry_snapshot = await engine.wave_3_final_lock_scan(
        candidate_id=request.candidate_id,
        final_simulation_output=request.simulation_output,
        live_market_data=request.live_market_data,
        telegram_service=telegram_service
    )
    
    if not entry_snapshot:
        # Get block reason
        candidate = db["edge_candidates"].find_one({
            "candidate_id": request.candidate_id
        })
        
        return {
            "status": "silenced",
            "message": "No publish (silence is correct outcome)",
            "block_reason": candidate.get("block_reason") if candidate else None
        }
    
    snapshot_doc = db["entry_snapshots"].find_one({
        "snapshot_id": entry_snapshot.snapshot_id
    })
    
    return {
        "status": "published",
        "entry_snapshot": entry_snapshot.to_dict(),
        "edge_grade": snapshot_doc["edge_grade"] if snapshot_doc else None,
        "message": "Published to Telegram"
    }


# ============================================================================
# PRICE VALIDATION (AUTO-BLOCK)
# ============================================================================

@router.post("/validate-price", response_model=Dict[str, Any])
async def validate_entry_price(
    request: PriceValidationRequest,
    db: Database = Depends(get_db)
):
    """
    Validate price before user entry
    
    Auto-blocks if current line exceeds max acceptable line
    
    Example:
    - Entry snapshot: Timberwolves -11.0
    - Max acceptable: -12.5
    - If current book shows -13 → BLOCKED
    """
    engine = AutonomousEdgeEngine(db)
    
    valid = await engine.validate_entry_price(
        snapshot_id=request.snapshot_id,
        current_market_line=request.current_market_line
    )
    
    if not valid:
        return {
            "status": "blocked",
            "message": "Price degraded beyond max acceptable line",
            "allow_entry": False
        }
    
    return {
        "status": "valid",
        "message": "Price within acceptable range",
        "allow_entry": True
    }


# ============================================================================
# MONITORING & ANALYTICS
# ============================================================================

@router.get("/candidates/active", response_model=List[CandidateStatusResponse])
async def get_active_candidates(
    sport: Optional[str] = Query(None, description="Filter by sport"),
    wave: Optional[int] = Query(None, description="Filter by wave (1, 2, or 3)"),
    db: Database = Depends(get_db)
):
    """
    Get all active edge candidates
    
    Used for monitoring dashboard
    """
    query: Dict[str, Any] = {
        "state": {"$nin": ["BLOCKED", "PUBLISHED"]}
    }
    
    if sport:
        query["sport"] = sport
    if wave:
        query["wave"] = wave
    
    candidates = list(db["edge_candidates"].find(query).sort("created_at", -1).limit(50))
    
    return [
        CandidateStatusResponse(
            candidate_id=c["candidate_id"],
            game_id=c["game_id"],
            sport=c["sport"],
            wave=c["wave"],
            state=c["state"],
            edge_gap=c.get("edge_gap", 0),
            win_probability=c.get("win_probability", 0),
            created_at=c["created_at"].isoformat(),
            block_reason=c.get("block_reason")
        )
        for c in candidates
    ]


@router.get("/snapshots/published", response_model=List[EntrySnapshotResponse])
async def get_published_snapshots(
    game_id: Optional[str] = Query(None, description="Filter by game ID"),
    edge_grade: Optional[str] = Query(None, description="Filter by edge grade"),
    db: Database = Depends(get_db)
):
    """
    Get all published entry snapshots
    
    These are the IMMUTABLE TRUTH for all published bets
    """
    query: Dict[str, Any] = {"published": True}
    
    if game_id:
        query["game_id"] = game_id
    if edge_grade:
        query["edge_grade"] = edge_grade
    
    snapshots = list(db["entry_snapshots"].find(query).sort("timestamp", -1).limit(100))
    
    return [
        EntrySnapshotResponse(
            snapshot_id=s["snapshot_id"],
            game_id=s["game_id"],
            market_type=s["market_type"],
            side=s["side"],
            entry_line=s["entry_line"],
            entry_odds=s["entry_odds"],
            model_fair_value=s["model_fair_value"],
            edge_gap=s["edge_gap"],
            win_probability=s["win_probability"],
            clv_estimate=s["clv_estimate"],
            timestamp=s["timestamp"],
            max_acceptable_line=s["max_acceptable_line"],
            signal_id=s["signal_id"],
            edge_grade=s["edge_grade"],
            published=s["published"]
        )
        for s in snapshots
    ]


@router.get("/candidate/{candidate_id}", response_model=Dict[str, Any])
async def get_candidate_detail(
    candidate_id: str,
    db: Database = Depends(get_db)
):
    """
    Get detailed candidate information across all waves
    """
    candidate = db["edge_candidates"].find_one({
        "candidate_id": candidate_id
    })
    
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
    
    # Remove MongoDB _id
    candidate.pop("_id", None)
    
    # Convert datetime objects
    for key in ["created_at", "updated_at", "published_at", "blocked_at"]:
        if key in candidate and candidate[key]:
            candidate[key] = candidate[key].isoformat()
    
    return candidate


@router.get("/snapshot/{snapshot_id}", response_model=Dict[str, Any])
async def get_entry_snapshot(
    snapshot_id: str,
    db: Database = Depends(get_db)
):
    """
    Get entry snapshot (immutable truth)
    """
    snapshot = db["entry_snapshots"].find_one({
        "snapshot_id": snapshot_id
    })
    
    if not snapshot:
        raise HTTPException(status_code=404, detail="Entry snapshot not found")
    
    # Remove MongoDB _id
    snapshot.pop("_id", None)
    
    return snapshot


@router.get("/stats/daily", response_model=Dict[str, Any])
async def get_daily_stats(
    date: Optional[str] = Query(None, description="Date in YYYY-MM-DD format"),
    db: Database = Depends(get_db)
):
    """
    Get daily autonomous edge statistics
    
    Returns:
    - Total candidates discovered
    - Wave 2 validation rate
    - Wave 3 publish rate
    - A-grade vs Strong Lean breakdown
    - Silence rate
    """
    if date:
        target_date = datetime.fromisoformat(date)
    else:
        target_date = datetime.now(timezone.utc)
    
    start_of_day = target_date.replace(hour=0, minute=0, second=0, microsecond=0)
    end_of_day = target_date.replace(hour=23, minute=59, second=59, microsecond=999999)
    
    # Aggregate stats
    pipeline = [
        {
            "$match": {
                "created_at": {"$gte": start_of_day, "$lte": end_of_day}
            }
        },
        {
            "$group": {
                "_id": "$state",
                "count": {"$sum": 1}
            }
        }
    ]
    
    state_counts = list(db["edge_candidates"].aggregate(pipeline))
    
    # Published snapshots
    published_pipeline = [
        {
            "$match": {
                "timestamp": {"$gte": start_of_day.isoformat(), "$lte": end_of_day.isoformat()},
                "published": True
            }
        },
        {
            "$group": {
                "_id": "$edge_grade",
                "count": {"$sum": 1}
            }
        }
    ]
    
    published_counts = list(db["entry_snapshots"].aggregate(published_pipeline))
    
    return {
        "date": target_date.strftime("%Y-%m-%d"),
        "candidate_states": {item["_id"]: item["count"] for item in state_counts},
        "published_grades": {item["_id"]: item["count"] for item in published_counts},
        "total_candidates": sum(item["count"] for item in state_counts),
        "total_published": sum(item["count"] for item in published_counts),
        "silence_rate": 1 - (sum(item["count"] for item in published_counts) / max(sum(item["count"] for item in state_counts), 1))
    }
