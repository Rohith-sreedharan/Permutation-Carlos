"""
Truth Mode Routes
==================
Endpoints for Truth Mode validation and NO PLAY responses
"""
from fastapi import APIRouter, HTTPException, Depends
from typing import List, Dict, Any, Optional
from pydantic import BaseModel
from datetime import datetime, timezone
from db.mongo import db
from middleware.auth import get_current_user
from middleware.truth_mode_enforcement import (
    enforce_truth_mode_on_pick,
    filter_picks_with_truth_mode,
    validate_parlay_with_truth_mode
)

router = APIRouter(prefix="/api/truth-mode", tags=["Truth Mode"])


class ValidatePickRequest(BaseModel):
    """Request to validate a single pick"""
    event_id: str
    bet_type: str = "moneyline"


class ValidatePicksRequest(BaseModel):
    """Request to validate multiple picks"""
    picks: List[Dict[str, Any]]
    include_blocked: bool = False


@router.post("/validate-pick")
async def validate_pick(
    request: ValidatePickRequest,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Validate a single pick through Truth Mode
    Returns VALID or NO_PLAY with block reasons
    """
    result = enforce_truth_mode_on_pick(
        event_id=request.event_id,
        bet_type=request.bet_type
    )
    
    return result


@router.post("/validate-picks")
async def validate_picks(
    request: ValidatePicksRequest,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Validate multiple picks through Truth Mode
    Returns filtered lists of valid and blocked picks
    """
    result = filter_picks_with_truth_mode(
        picks=request.picks,
        include_blocked=request.include_blocked
    )
    
    return result


@router.get("/status")
async def truth_mode_status():
    """
    Get Truth Mode system status
    """
    # Count recent validations
    recent_validations = db.truth_mode_validations.count_documents({
        "timestamp": {"$gt": datetime.now(timezone.utc).isoformat()}
    })
    
    return {
        "status": "active",
        "version": "1.0",
        "principle": "ZERO-LIES: No pick shown unless it passes Data Integrity + Model Validity + RCL Gate",
        "enforcement": "ALL sports, ALL endpoints, ALL pick displays",
        "recent_validations_today": recent_validations,
        "gates": [
            "Gate 1: Data Integrity Check",
            "Gate 2: Model Validity Check",
            "Gate 3: RCL Gate (Publish/Block)"
        ]
    }


@router.get("/dashboard-picks")
async def get_dashboard_picks_with_truth_mode(
    sport_key: Optional[str] = None,
    limit: int = 10,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Get dashboard picks with Truth Mode enforcement
    Only returns validated picks or NO PLAY responses
    """
    # Query for today's events
    from datetime import timedelta
    now = datetime.now(timezone.utc)
    today_end = now + timedelta(hours=24)
    
    query = {
        "commence_time": {
            "$gt": now.isoformat(),
            "$lt": today_end.isoformat()
        }
    }
    
    if sport_key:
        query["sport_key"] = sport_key
    
    events = list(db.events.find(query).limit(limit))
    
    # Get picks for each event
    picks = []
    for event in events:
        # Get latest simulation
        simulation = db.monte_carlo_simulations.find_one(
            {"event_id": event["event_id"]},
            sort=[("created_at", -1)]
        )
        
        if simulation:
            # Determine recommended bet type based on highest confidence
            bet_type = "moneyline"  # Default
            max_confidence = simulation.get("team_a_win_probability", 0.5)
            
            if simulation.get("spread_confidence", 0) > max_confidence:
                bet_type = "spread"
                max_confidence = simulation.get("spread_confidence", 0)
            
            if simulation.get("total_confidence", 0) > max_confidence:
                bet_type = "total"
            
            picks.append({
                "event_id": event["event_id"],
                "event": f"{event['away_team']} @ {event['home_team']}",
                "sport": event["sport_key"],
                "commence_time": event["commence_time"],
                "bet_type": bet_type
            })
    
    # Filter through Truth Mode
    result = filter_picks_with_truth_mode(
        picks=picks,
        include_blocked=False  # Don't show blocked picks on dashboard
    )
    
    return {
        "picks": result["valid_picks"],
        "count": result["valid_count"],
        "blocked_count": result["blocked_count"],
        "truth_mode_enabled": True,
        "message": f"Showing {result['valid_count']} Truth Mode validated picks ({result['blocked_count']} blocked)"
    }
