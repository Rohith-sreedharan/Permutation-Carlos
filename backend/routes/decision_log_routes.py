"""
Decision Log Routes - User Decision Tracking
Tracks forecasts users follow and calculates alignment scores
"""
from fastapi import APIRouter, HTTPException, Header
from typing import Optional, List, Dict, Any
from pydantic import BaseModel
from datetime import datetime, timezone, timedelta
from bson import ObjectId
from middleware.auth import get_current_user
from fastapi import Depends, Query

from db.mongo import db

router = APIRouter(prefix="/api/user", tags=["decision-log"])


def _normalize_outcome(result_code: Optional[str]) -> Optional[str]:
    if not result_code:
        return None
    rc = str(result_code).upper()
    if rc in {"WIN", "LOSS", "PUSH"}:
        return rc
    return None


@router.get("/opened-picks")
async def get_opened_picks(
    limit: int = Query(20, ge=1, le=100),
    user: Dict[str, Any] = Depends(get_current_user),
):
    """Read-only projection of a user's opened picks with canonical settlement outcomes."""
    raw_user_id = user.get("_id") or user.get("id")
    if raw_user_id is None:
        raise HTTPException(status_code=401, detail="User not resolved")
    user_id = str(raw_user_id)

    opened_docs = list(
        db["opened_event_log"].find(
            {"user_id": user_id},
            {
                "_id": 0,
                "opened_event_id": 1,
                "event_id": 1,
                "league": 1,
                "opened_at": 1,
                "decision_record_id": 1,
                "market_snapshot": 1,
            },
        ).sort("opened_at", -1).limit(limit)
    )

    if not opened_docs:
        return {
            "count": 0,
            "weekly_record": {"wins": 0, "losses": 0, "pushes": 0},
            "opened_picks": [],
        }

    event_ids = sorted({str(doc.get("event_id")) for doc in opened_docs if doc.get("event_id")})
    settlement_docs = list(
        db["decision_settlement_metrics"].find(
            {"event_id": {"$in": event_ids}},
            {"_id": 0, "event_id": 1, "result_code": 1, "timestamp": 1},
        ).sort("timestamp", -1)
    )

    latest_outcome_by_event: Dict[str, Optional[str]] = {}
    for settlement in settlement_docs:
        event_id = str(settlement.get("event_id") or "")
        if not event_id or event_id in latest_outcome_by_event:
            continue
        latest_outcome_by_event[event_id] = _normalize_outcome(settlement.get("result_code"))

    now = datetime.now(timezone.utc)
    week_start = now.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=now.weekday())

    wins = 0
    losses = 0
    pushes = 0
    projected_rows = []

    for opened in opened_docs:
        event_id = str(opened.get("event_id") or "")
        outcome = latest_outcome_by_event.get(event_id)
        opened_at_raw = opened.get("opened_at")
        opened_at_dt = None
        if isinstance(opened_at_raw, str):
            try:
                opened_at_dt = datetime.fromisoformat(opened_at_raw.replace("Z", "+00:00"))
            except Exception:
                opened_at_dt = None

        if opened_at_dt and opened_at_dt.tzinfo is None:
            opened_at_dt = opened_at_dt.replace(tzinfo=timezone.utc)

        if opened_at_dt and opened_at_dt >= week_start:
            if outcome == "WIN":
                wins += 1
            elif outcome == "LOSS":
                losses += 1
            elif outcome == "PUSH":
                pushes += 1

        projected_rows.append(
            {
                **opened,
                "settlement_outcome": outcome,
            }
        )

    return {
        "count": len(projected_rows),
        "weekly_record": {"wins": wins, "losses": losses, "pushes": pushes},
        "opened_picks": projected_rows,
    }


def _get_user_id_from_auth(authorization: Optional[str]) -> str:
    """Extract user_id from Bearer token"""
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing Authorization header")
    
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != 'bearer':
        raise HTTPException(status_code=401, detail="Invalid Authorization header")
    
    token = parts[1]
    if not token.startswith('user:'):
        raise HTTPException(status_code=401, detail="Invalid token format")
    
    user_id = token.split(':', 1)[1]
    return user_id


class FollowForecastRequest(BaseModel):
    """Request to follow/track a forecast"""
    event_id: str
    forecast: str
    confidence: float


@router.get("/decision-log")
async def get_decision_log(authorization: Optional[str] = Header(None)):
    """
    Get user's decision log with metrics
    
    Returns:
        {
            "decisions": [...],
            "alignment_score": 82,  # % alignment with high-confidence AI
            "analytical_roi": 15.3  # Expected value %
        }
    """
    user_id = _get_user_id_from_auth(authorization)
    
    try:
        # Fetch user's followed forecasts
        decisions = list(db["decision_log"].find(
            {"user_id": user_id}
        ).sort("followed_at", -1).limit(50))
        
        # Convert ObjectId to string
        for decision in decisions:
            if "_id" in decision:
                decision["_id"] = str(decision["_id"])
            decision["id"] = decision.get("_id", str(decision.get("id", "")))
        
        # Calculate alignment score
        # What % of followed forecasts were high-confidence (>60%) AI predictions?
        total_followed = len(decisions)
        high_confidence_followed = len([d for d in decisions if d.get("confidence", 0) >= 0.60])
        alignment_score = int((high_confidence_followed / total_followed * 100)) if total_followed > 0 else 0
        
        # Calculate analytical ROI
        # Sum of expected values from followed forecasts
        # EV = confidence * potential_return (simplified as confidence - 0.5 for demonstration)
        total_ev = sum([
            (d.get("confidence", 0.5) - 0.5) * 100
            for d in decisions
        ])
        analytical_roi = total_ev / total_followed if total_followed > 0 else 0.0
        
        return {
            "decisions": decisions,
            "alignment_score": alignment_score,
            "analytical_roi": round(analytical_roi, 1)
        }
        
    except Exception as e:
        print(f"Error loading decision log: {str(e)}")
        # Return empty state instead of error
        return {
            "decisions": [],
            "alignment_score": 0,
            "analytical_roi": 0.0
        }


@router.post("/follow-forecast")
async def follow_forecast(
    body: FollowForecastRequest,
    authorization: Optional[str] = Header(None)
):
    """
    Log that user followed a forecast
    
    Request:
        {
            "event_id": "abc123",
            "forecast": "Warriors -5.5",
            "confidence": 0.68
        }
    """
    user_id = _get_user_id_from_auth(authorization)
    
    try:
        # Fetch event details for context
        event = db["events"].find_one({"event_id": body.event_id})
        event_name = "Unknown Event"
        if event:
            event_name = f"{event.get('away_team', 'Team A')} @ {event.get('home_team', 'Team B')}"
        
        # Determine alignment level
        if body.confidence >= 0.70:
            alignment = "high"
        elif body.confidence >= 0.55:
            alignment = "medium"
        else:
            alignment = "low"
        
        # Create decision log entry
        decision_entry = {
            "user_id": user_id,
            "event_id": body.event_id,
            "event_name": event_name,
            "forecast": body.forecast,
            "confidence": body.confidence,
            "alignment": alignment,
            "followed_at": datetime.now(timezone.utc).isoformat()
        }
        
        # Insert into decision_log collection
        result = db["decision_log"].insert_one(decision_entry)
        
        return {
            "status": "success",
            "message": "Forecast followed successfully",
            "decision_id": str(result.inserted_id)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to log decision: {str(e)}")


@router.delete("/decision-log/{decision_id}")
async def remove_decision(
    decision_id: str,
    authorization: Optional[str] = Header(None)
):
    """Remove a decision from the log"""
    user_id = _get_user_id_from_auth(authorization)
    
    try:
        oid = ObjectId(decision_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid decision ID")
    
    # Delete only if it belongs to this user
    result = db["decision_log"].delete_one({
        "_id": oid,
        "user_id": user_id
    })
    
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Decision not found")
    
    return {"status": "success", "message": "Decision removed"}
