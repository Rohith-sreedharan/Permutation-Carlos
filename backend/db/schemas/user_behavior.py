"""
User Behavior Schema
Tracks all user actions for modeling and learning
"""
from datetime import datetime
from typing import Optional


def user_behavior_schema():
    """Schema for user_behavior collection"""
    return {
        "user_id": str,
        "event_id": Optional[str],
        "activity_type": str,  # pick_made, page_view, feature_used, etc.
        "bet_type": Optional[str],  # moneyline, spread, total, parlay
        "team": Optional[str],
        "odds": Optional[float],
        "amount": Optional[float],
        "sport": Optional[str],
        "league": Optional[str],
        "timestamp": datetime
    }


def create_user_behavior_indexes(db):
    """Create indexes for user_behavior"""
    db.user_behavior.create_index([("user_id", 1), ("timestamp", -1)])
    db.user_behavior.create_index("activity_type")
    db.user_behavior.create_index("sport")
