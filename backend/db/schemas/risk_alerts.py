"""
Risk Alerts Schema
Stores risk management alerts and guidance
"""
from datetime import datetime
from typing import Optional, List


def risk_alert_schema():
    """Schema for risk_alerts collection"""
    return {
        "user_id": str,
        "alert_type": str,  # bet_size, tilt_warning, bankroll_health, etc.
        "severity": str,  # SAFE, WARNING, DANGER, CRITICAL
        "message": str,
        "details": dict,  # Additional context
        "timestamp": datetime,
        "acknowledged": bool
    }


def create_risk_alert_indexes(db):
    """Create indexes for risk_alerts"""
    db.risk_alerts.create_index([("user_id", 1), ("timestamp", -1)])
    db.risk_alerts.create_index("severity")
    db.risk_alerts.create_index("acknowledged")
