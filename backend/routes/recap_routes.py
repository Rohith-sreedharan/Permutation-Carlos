"""
Post-Game Recap API Routes
Generate and retrieve post-game analysis

Per spec Section 10: Auto recap per game with HIT/MISS tracking
"""

from fastapi import APIRouter, HTTPException, Query
from typing import Dict, Any, Optional
from services.post_game_recap import PostGameRecap
from services.logger import log_stage
import logging

router = APIRouter(prefix="/api/recap", tags=["Post-Game Recap"])
logger = logging.getLogger(__name__)


@router.post("/generate")
def generate_recap_endpoint(
    event_id: str,
    game_data: Dict[str, Any],
    predictions: Dict[str, Any],
    actual_results: Dict[str, Any]
):
    """
    Generate comprehensive post-game recap
    
    Args:
        event_id: Game identifier
        game_data: Original game data (teams, context)
        predictions: All predictions made
        actual_results: Actual game results
    """
    try:
        logger.info(f"Post-Game Recap Generation: {event_id}")
        
        recap = PostGameRecap.generate_recap(
            event_id=event_id,
            game_data=game_data,
            predictions=predictions,
            actual_results=actual_results
        )
        
        if "error" in recap:
            raise HTTPException(status_code=500, detail=recap["error"])
        
        return {
            "success": True,
            "recap": recap,
            "message": "Post-game recap generated successfully"
        }
        
    except Exception as e:
        logger.error(f"Recap generation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/recent")
def get_recent_recaps_endpoint(
    days: int = Query(7, ge=1, le=90),
    limit: int = Query(50, ge=1, le=500)
):
    """
    Get recent post-game recaps
    
    Args:
        days: Number of days to look back
        limit: Maximum number of recaps to return
    """
    try:
        logger.info(f"Recent Recaps Query: days={days}, limit={limit}")
        
        recaps = PostGameRecap.get_recent_recaps(days=days, limit=limit)
        
        return {
            "success": True,
            "count": len(recaps),
            "recaps": recaps,
            "message": f"Retrieved {len(recaps)} recaps from last {days} days"
        }
        
    except Exception as e:
        logger.error(f"Recent recaps query failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/performance_trends")
def get_performance_trends_endpoint(
    days: int = Query(30, ge=7, le=365)
):
    """
    Analyze performance trends across multiple games
    
    Identifies which prediction types are performing well/poorly
    
    Args:
        days: Number of days to analyze (default 30)
    """
    try:
        logger.info(f"Performance Trends Analysis: days={days}")
        
        trends = PostGameRecap.get_performance_trends(days=days)
        
        if "error" in trends:
            raise HTTPException(status_code=500, detail=trends["error"])
        
        return {
            "success": True,
            "data": trends,
            "message": f"Performance trends for last {days} days"
        }
        
    except Exception as e:
        logger.error(f"Performance trends query failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{event_id}")
def get_recap_by_event_endpoint(event_id: str):
    """
    Get recap for a specific event
    """
    try:
        from db.mongo import db
        
        recap = db.post_game_recaps.find_one({"event_id": event_id})
        
        if not recap:
            raise HTTPException(status_code=404, detail="Recap not found for this event")
        
        # Convert ObjectId to string
        if "_id" in recap:
            recap["_id"] = str(recap["_id"])
        
        return {
            "success": True,
            "recap": recap
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Recap retrieval failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
