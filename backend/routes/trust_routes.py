"""
Trust Loop API Routes
=====================

Exposes model performance metrics for transparency.

Endpoints:
- GET /api/trust/metrics - Overall performance metrics
- GET /api/trust/history - Historical graded predictions
- GET /api/trust/trend - 7-day accuracy trend for sparkline
- GET /api/trust/yesterday - Yesterday's performance
"""
from fastapi import APIRouter, Depends, HTTPException
from typing import Dict, List, Optional, Any
from datetime import datetime
from services.trust_metrics import trust_metrics_service
from services.result_service import result_service

router = APIRouter(prefix="/api/trust", tags=["trust_loop"])


@router.get("/metrics")
async def get_trust_metrics() -> Dict[str, Any]:
    """
    GET /api/trust/metrics
    
    Returns comprehensive model performance metrics.
    """
    try:
        metrics = await trust_metrics_service.get_cached_metrics()
        return metrics
    except Exception as e:
        import traceback
        traceback.print_exc()
        
        # Return empty state instead of failing
        return {
            "overall": {
                "7day_accuracy": 0.0,
                "7day_record": "0-0",
                "7day_units": 0.0,
                "30day_roi": 0.0,
                "30day_units": 0.0,
                "30day_record": "0-0",
                "brier_score": 0.0,
                "total_predictions": 0
            },
            "by_sport": {},
            "confidence_calibration": {},
            "recent_performance": [],
            "yesterday": {
                "record": "0-0",
                "units": 0.0,
                "accuracy": 0.0,
                "message": "📊 No graded predictions yet"
            },
            "message": "Trust metrics will appear after games are graded"
        }


@router.get("/history")
async def get_prediction_history(
    days: int = 7,
    limit: int = 50,
    sport: Optional[str] = None,
    result: Optional[str] = None  # WIN, LOSS, PUSH
) -> Dict[str, Any]:
    """
    GET /api/trust/history
    
    Returns historical graded predictions for transparency ledger.
    
    Query Parameters:
    - days: Look back period (default 7)
    - limit: Max results (default 50)
    - sport: Filter by sport (NBA, NFL, etc.)
    - result: Filter by outcome (WIN, LOSS, PUSH)
    
    Response:
    {
        "count": 23,
        "predictions": [
            {
                "event_id": "...",
                "game": "Lakers vs Celtics",
                "sport": "NBA",
                "prediction": "Lakers -5",
                "result": "WIN",
                "actual_score": "112-108",
                "units_won": 0.91,
                "confidence": 0.75,
                "graded_at": "2024-11-28T..."
            }
        ]
    }
    """
    try:
        predictions = result_service.get_recent_graded_predictions(days=days, limit=limit)
        
        # Apply filters
        if sport:
            predictions = [p for p in predictions if p.get('sport') == sport]
        
        if result:
            predictions = [p for p in predictions if p.get('result') == result]
        
        return {
            'count': len(predictions),
            'predictions': predictions
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch prediction history: {str(e)}")


@router.get("/trend")
async def get_accuracy_trend(days: int = 7) -> Dict[str, Any]:
    """
    GET /api/trust/trend?days=7
    
    Returns daily accuracy trend for sparkline visualization.
    
    Response:
    {
        "trend": [
            {"date": "2024-11-22", "accuracy": 68.5, "units": 2.3, "wins": 5, "losses": 2},
            {"date": "2024-11-23", "accuracy": 71.2, "units": 1.8, "wins": 6, "losses": 2},
            ...
        ]
    }
    """
    try:
        trend = await trust_metrics_service.get_accuracy_trend(days=days)
        return {
            'trend': trend
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch trend: {str(e)}")


@router.get("/yesterday")
async def get_yesterday_performance() -> Dict[str, Any]:
    """
    GET /api/trust/yesterday
    
    Returns yesterday's performance for hero display.
    
    Response:
    {
        "record": "4-1",
        "units": 3.2,
        "accuracy": 80.0,
        "message": "🎯 4-1 (+3.2 Units)"
    }
    """
    try:
        metrics = await trust_metrics_service.get_cached_metrics()
        return metrics.get('yesterday', {
            'record': '0-0',
            'units': 0.0,
            'accuracy': 0.0,
            'message': 'No games graded yesterday'
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch yesterday's performance: {str(e)}")


@router.post("/grade-now")
async def trigger_manual_grading(hours_back: int = 24) -> Dict[str, Any]:
    """
    POST /api/trust/grade-now
    
    Manually trigger prediction grading (for admin use).
    
    Body:
    {
        "hours_back": 24
    }
    
    Response:
    {
        "graded_count": 15,
        "wins": 10,
        "losses": 5,
        "units_won": 3.2,
        "win_rate": 66.7
    }
    """
    try:
        result = await result_service.grade_completed_games(hours_back=hours_back)
        
        # Trigger metrics recalculation
        await trust_metrics_service.calculate_all_metrics()
        
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to grade predictions: {str(e)}")


@router.get("/calibration")
async def get_confidence_calibration() -> Dict[str, Any]:
    """
    GET /api/trust/calibration
    
    Returns confidence calibration metrics (how well confidence scores match reality).
    
    Response:
    {
        "high_confidence": {
            "predicted": 0.80,
            "actual": 0.78,
            "count": 45,
            "calibration_error": 0.02
        },
        "medium_confidence": {
            "predicted": 0.65,
            "actual": 0.62,
            "count": 52,
            "calibration_error": 0.03
        },
        "low_confidence": {
            "predicted": 0.52,
            "actual": 0.51,
            "count": 30,
            "calibration_error": 0.01
        }
    }
    """
    try:
        metrics = await trust_metrics_service.get_cached_metrics()
        calibration = metrics.get('confidence_calibration', {})
        
        # Add calibration error
        for key in calibration:
            predicted = calibration[key].get('predicted', 0)
            actual = calibration[key].get('actual', 0)
            calibration[key]['calibration_error'] = round(abs(predicted - actual), 3)
        
        return calibration
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch calibration: {str(e)}")


@router.get("/by-sport/{sport}")
async def get_sport_performance(sport: str) -> Dict[str, Any]:
    """
    GET /api/trust/by-sport/NBA
    
    Returns performance metrics for a specific sport.
    
    Response:
    {
        "sport": "NBA",
        "accuracy": 68.5,
        "roi": 12.3,
        "units": 5.7,
        "record": "22-10",
        "total_predictions": 32,
        "brier_score": 0.16
    }
    """
    try:
        metrics = await trust_metrics_service.get_cached_metrics()
        sport_metrics = metrics.get('by_sport', {}).get(sport.upper())
        
        if not sport_metrics:
            raise HTTPException(status_code=404, detail=f"No metrics found for sport: {sport}")
        
        return {
            'sport': sport.upper(),
            **sport_metrics
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch sport metrics: {str(e)}")
