"""
Verification Routes - Public Trust Loop Data
No auth required - radical transparency
"""
from fastapi import APIRouter, Query
from typing import List, Dict

from services.verification_service import (
    get_trust_metrics,
    get_accuracy_ledger
)
from legacy_config import PUBLIC_LEDGER_SIZE, TRUST_WINDOWS

router = APIRouter(prefix="/api/verification", tags=["verification"])


@router.get("/metrics")
async def get_model_accuracy_metrics(days: int = Query(7, description="Window size: 7, 30, or 90 days")):
    """
    Get model accuracy metrics for Trust Loop display
    
    Public endpoint - no auth required
    Radical transparency into model performance
    
    Args:
        days: Rolling window size (7, 30, or 90)
    
    Returns:
        {
            "accuracy": 0.64,
            "win_rate": 0.64,
            "total_verified": 120,
            "correct": 77,
            "incorrect": 43,
            "window_days": 7
        }
    """
    # Validate window size
    if days not in TRUST_WINDOWS:
        days = 7  # Default to 7 days
    
    metrics = get_trust_metrics(days)
    return metrics


@router.get("/ledger")
async def get_public_accuracy_ledger(limit: int = Query(PUBLIC_LEDGER_SIZE, description="Number of entries")):
    """
    Get public ledger of top verified forecasts
    
    Public endpoint - no auth required
    Shows top N most accurate high-confidence forecasts from last 7 days
    
    Returns:
        [
            {
                "creator_name": "SharpAnalyst",
                "forecast": "Warriors -5.5",
                "confidence": 0.78,
                "result": "CORRECT",
                "event": "Warriors vs Lakers",
                "verified_at": "2025-11-24T...",
                "sport": "NBA"
            },
            ...
        ]
    """
    ledger = get_accuracy_ledger(limit)
    return ledger


@router.get("/windows")
async def get_all_windows():
    """
    Get model accuracy for all trust windows (7, 30, 90 days)
    
    Public endpoint - convenience for loading Trust Loop component
    
    Returns:
        {
            "7": {...metrics...},
            "30": {...metrics...},
            "90": {...metrics...}
        }
    """
    all_metrics = {}
    
    for days in TRUST_WINDOWS:
        metrics = get_trust_metrics(days)
        all_metrics[str(days)] = metrics
    
    return all_metrics
