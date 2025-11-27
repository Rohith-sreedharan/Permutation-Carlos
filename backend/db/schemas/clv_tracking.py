"""
CLV Tracking Schema
Tracks closing line value for each pick
"""
from datetime import datetime
from typing import Optional


def clv_tracking_schema():
    """Schema for clv_tracking collection"""
    return {
        "user_id": str,
        "event_id": str,
        "team": str,
        "market_type": str,  # h2h, spreads, totals
        "pick_price": float,  # Odds when user made pick
        "pick_timestamp": datetime,
        "closing_price": Optional[float],  # Odds when game started
        "clv": Optional[float],  # Closing line value
        "clv_calculated": bool,
        "calculated_at": Optional[datetime]
    }


def create_clv_tracking_indexes(db):
    """Create indexes for clv_tracking"""
    db.clv_tracking.create_index([("user_id", 1), ("pick_timestamp", -1)])
    db.clv_tracking.create_index([("event_id", 1), ("clv_calculated", 1)])
