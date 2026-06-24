from fastapi import APIRouter, HTTPException, Query, Depends
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone, timedelta

from db.mongo import db
from services.entitlement_gate import require_web_platform_feature
from services.trust_metrics import trust_metrics_service

router = APIRouter(
    prefix="/api/performance",
    tags=["performance"],
    dependencies=[Depends(require_web_platform_feature)],
)


@router.get("/clv")
async def get_clv_data(
    user_id: str = Query(...),
    range: str = Query("30d", pattern="^(7d|30d|90d|all)$")
):
    """Get CLV and performance surface from canonical trust metrics cache."""
    try:
        metrics = await trust_metrics_service.get_cached_metrics()
        overall = metrics.get("overall", {})
        recent = metrics.get("recent_performance", [])
        return {
            "user_id": user_id,
            "range": range,
            "picks": recent,
            "stats": {
                "average_clv": 0.0,
                "total_picks": overall.get("total_predictions", 0),
                "positive_clv_picks": 0,
                "clv_trend": "stable",
                "last_30_days_avg": 0.0,
                "roi_30d": overall.get("30day_roi", 0.0),
                "accuracy_7d": overall.get("7day_accuracy", 0.0),
            },
            "source": "system_performance.metrics",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch canonical metrics: {str(e)}")


@router.get("/report")
async def get_performance_report(
    user_id: str = Query(...),
    range: str = Query("30d", pattern="^(7d|30d|90d|season)$")
):
    """Get performance report from canonical trust metrics cache."""
    try:
        metrics = await trust_metrics_service.get_cached_metrics()
        overall = metrics.get("overall", {})
        return {
            "user_id": user_id,
            "range": range,
            "brier_score": overall.get("brier_score", 0.0),
            "log_loss": 0.0,
            "roi": overall.get("30day_roi", 0.0),
            "clv": 0.0,
            "total_picks": overall.get("total_predictions", 0),
            "winning_picks": 0,
            "win_rate": overall.get("7day_accuracy", 0.0),
            "avg_odds": 0.0,
            "profit_loss": 0.0,
            "market_breakdown": metrics.get("by_sport", {}),
            "source": "system_performance.metrics",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch canonical metrics: {str(e)}")
