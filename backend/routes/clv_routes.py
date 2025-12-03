"""
CLV API Routes
Track and report CLV performance

Per spec Section 4: CLV logging for model validation
Target: ≥ 63% favorable CLV rate
"""

from fastapi import APIRouter, HTTPException, Query
from typing import Optional
from services.clv_tracker import CLVTracker
from services.logger import log_stage
import logging

router = APIRouter(prefix="/api/clv", tags=["CLV Tracking"])
logger = logging.getLogger(__name__)


@router.post("/log_prediction")
def log_prediction_endpoint(
    event_id: str,
    model_projection: float,
    book_line_open: float,
    prediction_type: str,
    lean: str,
    sim_count: int,
    confidence: int,
    user_id: Optional[str] = None
):
    """
    Log a prediction for CLV tracking
    
    Args:
        event_id: Game identifier
        model_projection: Model's projected value
        book_line_open: Opening bookmaker line
        prediction_type: "total", "spread", "ml"
        lean: "over", "under", "home", "away"
        sim_count: Simulation tier used
        confidence: Confidence score 0-100
    """
    try:
        logger.info(f"CLV Prediction Log: {event_id}, {prediction_type}, {lean}, {sim_count} sims")
        
        prediction_id = CLVTracker.log_prediction(
            event_id=event_id,
            model_projection=model_projection,
            book_line_open=book_line_open,
            prediction_type=prediction_type,
            lean=lean,
            sim_count=sim_count,
            confidence=confidence,
            metadata={"user_id": user_id} if user_id else None
        )
        
        return {
            "success": True,
            "prediction_id": prediction_id,
            "message": "Prediction logged for CLV tracking"
        }
        
    except Exception as e:
        logger.error(f"CLV prediction logging failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/update_closing_line")
def update_closing_line_endpoint(
    event_id: str,
    prediction_type: str,
    closing_line: float
):
    """
    Update predictions with closing line and calculate CLV
    
    Call this 5-10 minutes before game start when lines close
    """
    try:
        logger.info(f"CLV Closing Line Update: {event_id}, {prediction_type}, line={closing_line}")
        
        result = CLVTracker.update_closing_line(
            event_id=event_id,
            prediction_type=prediction_type,
            closing_line=closing_line
        )
        
        return {
            "success": True,
            "predictions_updated": result.get("predictions_updated", 0),
            "favorable_clv_count": result.get("favorable_clv_count", 0),
            "clv_percentage": result.get("clv_percentage", 0),
            "message": f"CLV calculated for {result.get('predictions_updated', 0)} predictions"
        }
        
    except Exception as e:
        logger.error(f"CLV closing line update failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/record_result")
def record_actual_result_endpoint(
    event_id: str,
    actual_total: Optional[float] = None,
    actual_margin: Optional[float] = None,
    winner: Optional[str] = None
):
    """
    Record actual game results for accuracy tracking
    
    Args:
        event_id: Game identifier
        actual_total: Final score total
        actual_margin: Final margin
        winner: "home" or "away"
    """
    try:
        logger.info(f"CLV Result Recording: {event_id}, total={actual_total}, winner={winner}")
        
        result = CLVTracker.record_actual_result(
            event_id=event_id,
            actual_total=actual_total,
            actual_margin=actual_margin,
            winner=winner
        )
        
        return {
            "success": True,
            "predictions_updated": result.get("predictions_updated", 0),
            "message": "Actual results recorded"
        }
        
    except Exception as e:
        logger.error(f"Result recording failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/performance")
def get_clv_performance_endpoint(
    days: int = Query(7, ge=1, le=90),
    min_sim_count: int = Query(25000, ge=10000)
):
    """
    Get CLV performance statistics
    
    Target: ≥ 63% favorable CLV rate
    
    Args:
        days: Number of days to look back (default 7)
        min_sim_count: Minimum simulation tier (default 25K)
    """
    try:
        logger.info(f"CLV Performance Query: days={days}, min_sim_count={min_sim_count}")
        
        performance = CLVTracker.get_clv_performance(
            days=days,
            min_sim_count=min_sim_count
        )
        
        return {
            "success": True,
            "data": performance,
            "target_met": performance.get("meets_target", False),
            "message": f"CLV data for last {days} days"
        }
        
    except Exception as e:
        logger.error(f"CLV performance query failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
