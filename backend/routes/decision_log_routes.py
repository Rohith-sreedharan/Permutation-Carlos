"""
Decision Log Routes - User Decision Tracking
Tracks forecasts users follow and calculates alignment scores
"""
from fastapi import APIRouter, HTTPException, Header
from typing import Optional, List, Dict, Any
from pydantic import BaseModel
from datetime import datetime, timezone
from bson import ObjectId

from db.mongo import db

router = APIRouter(prefix="/api/user", tags=["decision-log"])


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
