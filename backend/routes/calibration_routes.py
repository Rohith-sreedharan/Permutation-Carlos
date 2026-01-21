"""
Logging & Calibration System API Routes
========================================
Endpoints for calibration, grading, and performance analytics.
"""
from fastapi import APIRouter, HTTPException, Query
from typing import Optional, List
from datetime import datetime, timedelta
from pydantic import BaseModel

from services.calibration_service import calibration_service
from services.grading_service import grading_service
from services.publishing_service import publishing_service
from services.sim_run_tracker import sim_run_tracker
from services.snapshot_capture import snapshot_service
from db.mongo import db

router = APIRouter(prefix="/api/calibration", tags=["Calibration & Grading"])


# ============================================================================
# REQUEST/RESPONSE MODELS
# ============================================================================

class CalibrationJobRequest(BaseModel):
    training_days: int = 30
    method: str = "isotonic"


class CalibrationJobResponse(BaseModel):
    calibration_version: str
    status: str
    metrics: dict


class GradeAllRequest(BaseModel):
    lookback_hours: int = 72


class PerformanceSummaryRequest(BaseModel):
    cohort_key: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None


# ============================================================================
# CALIBRATION ENDPOINTS
# ============================================================================

@router.post("/run-calibration-job", response_model=CalibrationJobResponse)
async def run_calibration_job(request: CalibrationJobRequest):
    """
    Run weekly calibration job
    
    Creates a new versioned calibration model and activates it if it passes gates.
    """
    try:
        calibration_version = calibration_service.run_calibration_job(
            training_days=request.training_days,
            method=request.method
        )
        
        if not calibration_version:
            raise HTTPException(
                status_code=400,
                detail="Calibration job failed (insufficient data or error)"
            )
        
        # Get created version
        version_doc = calibration_service.calibration_versions_collection.find_one({
            "calibration_version": calibration_version
        })
        
        if not version_doc:
            raise HTTPException(status_code=404, detail="Calibration version not found")
        
        return CalibrationJobResponse(
            calibration_version=calibration_version,
            status=version_doc["activation_status"],
            metrics={
                "overall_ece": version_doc["overall_ece"],
                "overall_brier": version_doc["overall_brier"],
                "overall_mce": version_doc["overall_mce"]
            }
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/active-calibration-version")
async def get_active_calibration_version():
    """
    Get the currently active calibration version
    """
    version = calibration_service.get_active_calibration_version()
    
    if not version:
        return {"calibration_version": None, "status": "NO_ACTIVE_VERSION"}
    
    version_doc = calibration_service.calibration_versions_collection.find_one({
        "calibration_version": version
    })
    
    if not version_doc:
        return {"calibration_version": None, "status": "VERSION_NOT_FOUND"}
    
    return {
        "calibration_version": version,
        "created_at": version_doc["created_at_utc"],
        "method": version_doc["method"],
        "overall_ece": version_doc["overall_ece"],
        "overall_brier": version_doc["overall_brier"],
        "trained_on_start": version_doc["trained_on_start"],
        "trained_on_end": version_doc["trained_on_end"]
    }


@router.get("/calibration-versions")
async def list_calibration_versions(limit: int = Query(10, ge=1, le=100)):
    """
    List all calibration versions (most recent first)
    """
    versions = list(
        calibration_service.calibration_versions_collection
        .find({}, {"_id": 0})
        .sort("created_at_utc", -1)
        .limit(limit)
    )
    
    return {"versions": versions, "count": len(versions)}


@router.post("/activate-calibration/{calibration_version}")
async def activate_calibration_version(calibration_version: str):
    """
    Manually activate a calibration version
    """
    success = calibration_service.activate_calibration_version(calibration_version)
    
    if not success:
        raise HTTPException(
            status_code=404,
            detail=f"Calibration version {calibration_version} not found"
        )
    
    return {"status": "ACTIVATED", "calibration_version": calibration_version}


@router.get("/calibration-segments/{calibration_version}")
async def get_calibration_segments(calibration_version: str):
    """
    Get all segments for a calibration version
    """
    segments = list(
        calibration_service.calibration_segments_collection
        .find({"calibration_version": calibration_version}, {"_id": 0})
    )
    
    return {"calibration_version": calibration_version, "segments": segments, "count": len(segments)}


# ============================================================================
# GRADING ENDPOINTS
# ============================================================================

@router.post("/grade-all-pending")
async def grade_all_pending(request: GradeAllRequest):
    """
    Grade all pending published predictions
    """
    stats = grading_service.grade_all_pending(lookback_hours=request.lookback_hours)
    
    return {
        "status": "COMPLETE",
        "graded": stats["graded"],
        "voided": stats["voided"],
        "pending": stats["pending"]
    }


@router.post("/grade-published/{publish_id}")
async def grade_published_prediction(publish_id: str, force_regrade: bool = False):
    """
    Grade a specific published prediction
    """
    graded_id = grading_service.grade_published_prediction(
        publish_id=publish_id,
        force_regrade=force_regrade
    )
    
    if not graded_id:
        raise HTTPException(
            status_code=400,
            detail="Cannot grade prediction (event not complete or already graded)"
        )
    
    grading = grading_service.grading_collection.find_one(
        {"graded_id": graded_id},
        {"_id": 0}
    )
    
    return grading


@router.get("/grading/{publish_id}")
async def get_grading(publish_id: str):
    """
    Get grading record for a published prediction
    """
    grading = grading_service.get_grading_for_publish(publish_id)
    
    if not grading:
        raise HTTPException(
            status_code=404,
            detail=f"No grading found for publish_id {publish_id}"
        )
    
    grading.pop("_id", None)
    return grading


# ============================================================================
# PERFORMANCE ANALYTICS ENDPOINTS
# ============================================================================

@router.post("/performance-summary")
async def get_performance_summary(request: PerformanceSummaryRequest):
    """
    Get performance summary from grading records
    """
    summary = grading_service.get_performance_summary(
        cohort_key=request.cohort_key,
        start_date=request.start_date,
        end_date=request.end_date
    )
    
    return summary


@router.get("/performance/by-cohort")
async def get_performance_by_cohort(
    days_back: int = Query(30, ge=1, le=365),
    limit: int = Query(10, ge=1, le=100)
):
    """
    Get performance breakdown by cohort (league, market, etc.)
    """
    start_date = datetime.now() - timedelta(days=days_back)
    
    # Aggregate by cohort
    pipeline = [
        {
            "$match": {
                "bet_status": "SETTLED",
                "graded_at": {"$gte": start_date}
            }
        },
        {
            "$group": {
                "_id": "$cohort_tags.league",
                "total": {"$sum": 1},
                "wins": {
                    "$sum": {
                        "$cond": [{"$eq": ["$result_code", "WIN"]}, 1, 0]
                    }
                },
                "losses": {
                    "$sum": {
                        "$cond": [{"$eq": ["$result_code", "LOSS"]}, 1, 0]
                    }
                },
                "total_units": {"$sum": "$unit_return"},
                "avg_clv": {"$avg": "$clv"}
            }
        },
        {
            "$project": {
                "league": "$_id",
                "total": 1,
                "wins": 1,
                "losses": 1,
                "win_rate": {
                    "$multiply": [
                        {"$divide": ["$wins", {"$add": ["$wins", "$losses"]}]},
                        100
                    ]
                },
                "roi": {
                    "$multiply": [
                        {"$divide": ["$total_units", {"$add": ["$wins", "$losses"]}]},
                        100
                    ]
                },
                "total_units": 1,
                "avg_clv": 1
            }
        },
        {"$sort": {"roi": -1}},
        {"$limit": limit}
    ]
    
    results = list(grading_service.grading_collection.aggregate(pipeline))
    
    return {"cohorts": results, "count": len(results)}


@router.get("/performance/clv-distribution")
async def get_clv_distribution(days_back: int = Query(30, ge=1, le=365)):
    """
    Get CLV distribution histogram
    """
    start_date = datetime.now() - timedelta(days=days_back)
    
    gradings = list(grading_service.grading_collection.find({
        "bet_status": "SETTLED",
        "graded_at": {"$gte": start_date},
        "clv": {"$exists": True, "$ne": None}
    }, {"clv": 1}))
    
    clvs = [g["clv"] for g in gradings]
    
    if not clvs:
        return {"error": "No CLV data available"}
    
    import numpy as np
    
    # Create histogram
    hist, bin_edges = np.histogram(clvs, bins=20)
    
    return {
        "histogram": {
            "counts": hist.tolist(),
            "bin_edges": bin_edges.tolist()
        },
        "stats": {
            "mean": float(np.mean(clvs)),
            "median": float(np.median(clvs)),
            "std": float(np.std(clvs)),
            "min": float(np.min(clvs)),
            "max": float(np.max(clvs)),
            "positive_clv_pct": float(np.mean([1 if c > 0 else 0 for c in clvs]) * 100)
        },
        "total_samples": len(clvs)
    }


# ============================================================================
# PUBLISHING ENDPOINTS
# ============================================================================

@router.get("/publishable-predictions")
async def get_publishable_predictions(
    event_id: Optional[str] = None,
    recommendation_state: Optional[str] = None,
    limit: int = Query(50, ge=1, le=500)
):
    """
    Get predictions eligible for publishing
    """
    publishable = publishing_service.get_publishable_predictions(
        event_id=event_id,
        recommendation_state=recommendation_state
    )
    
    return {
        "predictions": publishable[:limit],
        "count": len(publishable)
    }


@router.get("/published-predictions/recent")
async def get_recent_published_predictions(
    visibility: Optional[str] = None,
    channel: Optional[str] = None,
    limit: int = Query(50, ge=1, le=500)
):
    """
    Get recent published predictions
    """
    published = publishing_service.get_recent_published_predictions(
        visibility=visibility,
        channel=channel,
        limit=limit
    )
    
    return {
        "published_predictions": published,
        "count": len(published)
    }


# ============================================================================
# SIM RUN TRACKING ENDPOINTS
# ============================================================================

@router.get("/sim-runs/event/{event_id}")
async def get_sim_runs_for_event(
    event_id: str,
    limit: int = Query(10, ge=1, le=100)
):
    """
    Get simulation runs for an event
    """
    sim_runs = sim_run_tracker.get_sim_runs_for_event(event_id, limit=limit)
    
    return {
        "event_id": event_id,
        "sim_runs": sim_runs,
        "count": len(sim_runs)
    }


@router.get("/sim-runs/{sim_run_id}")
async def get_sim_run(sim_run_id: str):
    """
    Get simulation run details with inputs and predictions
    """
    sim_run = sim_run_tracker.get_sim_run(sim_run_id)
    
    if not sim_run:
        raise HTTPException(
            status_code=404,
            detail=f"Sim run {sim_run_id} not found"
        )
    
    inputs = sim_run_tracker.get_sim_run_inputs(sim_run_id)
    predictions = sim_run_tracker.get_predictions_for_sim_run(sim_run_id)
    
    sim_run.pop("_id", None)
    if inputs:
        inputs.pop("_id", None)
    
    for pred in predictions:
        pred.pop("_id", None)
    
    return {
        "sim_run": sim_run,
        "inputs": inputs,
        "predictions": predictions
    }


# ============================================================================
# SNAPSHOT ENDPOINTS
# ============================================================================

@router.get("/snapshots/odds/{event_id}")
async def get_odds_snapshots_for_event(
    event_id: str,
    market_key: Optional[str] = None,
    book: Optional[str] = None
):
    """
    Get odds snapshots for an event
    """
    query = {"event_id": event_id}
    
    if market_key:
        query["market_key"] = market_key
    
    if book:
        query["book"] = book
    
    snapshots = list(
        snapshot_service.odds_collection
        .find(query, {"_id": 0})
        .sort("timestamp_utc", 1)
    )
    
    return {
        "event_id": event_id,
        "snapshots": snapshots,
        "count": len(snapshots)
    }


@router.get("/snapshots/closing-line/{event_id}")
async def get_closing_line(
    event_id: str,
    market_key: str,
    book: str
):
    """
    Get closing line snapshot for an event
    """
    snapshot = snapshot_service.get_closing_line_snapshot(
        event_id=event_id,
        market_key=market_key,
        book=book
    )
    
    if not snapshot:
        raise HTTPException(
            status_code=404,
            detail="Closing line not found"
        )
    
    snapshot.pop("_id", None)
    return snapshot


# ============================================================================
# HEALTH CHECK
# ============================================================================

@router.get("/health")
async def health_check():
    """
    Health check for calibration system
    """
    active_version = calibration_service.get_active_calibration_version()
    
    # Count recent gradings
    start_date = datetime.now() - timedelta(days=7)
    recent_gradings = grading_service.grading_collection.count_documents({
        "graded_at": {"$gte": start_date}
    })
    
    # Count recent publishes
    recent_publishes = publishing_service.published_collection.count_documents({
        "published_at_utc": {"$gte": start_date},
        "is_official": True
    })
    
    return {
        "status": "HEALTHY",
        "active_calibration_version": active_version or "NONE",
        "recent_gradings_7d": recent_gradings,
        "recent_publishes_7d": recent_publishes,
        "timestamp": datetime.now()
    }
