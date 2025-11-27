"""
Prediction Outcomes Schema - THE MOAT
Logs every prediction vs actual outcome for continuous learning
"""
from datetime import datetime
from typing import Optional, Dict, Any


def prediction_outcome_schema():
    """Schema for prediction_outcomes collection (Feedback Loop)"""
    return {
        "user_id": str,
        "event_id": str,
        "pick_data": Dict[str, Any],  # Full pick details
        "model_probability": float,  # Model's true probability (0-1)
        "market_probability": float,  # Market implied probability (0-1)
        "market_odds": float,  # American odds
        "outcome": Optional[str],  # win, loss, push
        "error_delta": Optional[float],  # |model_prob - actual_result|
        "settled": bool,
        "timestamp": datetime,  # When pick was made
        "settled_at": Optional[datetime]  # When outcome was recorded
    }


def create_prediction_outcome_indexes(db):
    """Create indexes for prediction_outcomes"""
    db.prediction_outcomes.create_index([("user_id", 1), ("timestamp", -1)])
    db.prediction_outcomes.create_index([("event_id", 1)])
    db.prediction_outcomes.create_index([("settled", 1), ("settled_at", -1)])
    db.prediction_outcomes.create_index([("pick_data.sport", 1), ("pick_data.bet_type", 1)])
