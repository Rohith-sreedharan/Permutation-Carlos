"""
Trust Loop API Routes

Provides endpoints for displaying model accuracy metrics.
"""

from fastapi import APIRouter, HTTPException
from typing import Dict
from core.feedback_loop import get_trust_loop_metrics, grade_predictions

router = APIRouter(prefix="/api/trust-loop", tags=["trust-loop"])


@router.get("/metrics")
async def get_metrics() -> Dict:
    """
    Get Trust Loop metrics for UI display
    
    Returns:
        7-day accuracy, 30-day ROI, Brier score, total predictions, trend
    """
    try:
        metrics = get_trust_loop_metrics()
        return {
            "success": True,
            "data": metrics
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch Trust Loop metrics: {str(e)}")


@router.post("/grade-predictions")
async def trigger_grading(lookback_hours: int = 24) -> Dict:
    """
    Manually trigger prediction grading
    
    Normally runs automatically at 4:15 AM EST daily.
    This endpoint allows manual triggering for testing.
    """
    try:
        grade_predictions(lookback_hours=lookback_hours)
        return {
            "success": True,
            "message": f"Grading completed for last {lookback_hours} hours"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Grading failed: {str(e)}")
