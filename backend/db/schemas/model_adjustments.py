"""
Model Adjustments Schema
Stores recommended parameter adjustments from feedback loop
"""
from datetime import datetime
from typing import Dict, Any


def model_adjustment_schema():
    """Schema for model_adjustments collection"""
    return {
        "sport": str,
        "bet_type": str,
        "avg_error": float,
        "sample_size": int,
        "timestamp": datetime,
        "status": str,  # pending, applied, rejected
        "recommendation": Dict[str, Any],
        "applied_at": datetime
    }


def create_model_adjustment_indexes(db):
    """Create indexes for model_adjustments"""
    db.model_adjustments.create_index([("sport", 1), ("bet_type", 1)])
    db.model_adjustments.create_index([("status", 1), ("timestamp", -1)])
