"""
Parlay Logs Schema
Stores parlay construction and results
"""
from datetime import datetime
from typing import Optional, List, Dict, Any


def parlay_log_schema():
    """Schema for parlay_logs collection"""
    return {
        "user_id": str,  # User who created parlay
        "legs": List[Dict[str, Any]],  # List of parlay legs
        "combined_probability": float,  # True combined probability (0-1)
        "correlation_score": float,  # Correlation between legs (0-1)
        "risk_score": str,  # LOW, MEDIUM, HIGH, EXTREME
        "expected_value": float,  # EV as decimal
        "parlay_odds": float,  # Decimal odds
        "recommendation": str,  # Agent recommendation
        "bet_amount": Optional[float],  # If user actually bet
        "outcome": Optional[str],  # win/loss/push if settled
        "created_at": datetime,
        "settled_at": Optional[datetime]
    }


def create_parlay_indexes(db):
    """Create indexes for parlay_logs collection"""
    db.parlay_logs.create_index([("user_id", 1), ("created_at", -1)])
    db.parlay_logs.create_index("outcome")
