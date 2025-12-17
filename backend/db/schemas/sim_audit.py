"""
MongoDB Schema for Simulation Audit with Reality Check Layer (RCL)
Tracks every total projection with sanity check results
"""
from typing import Optional, Dict, Any, List
from datetime import datetime
from pydantic import BaseModel, Field


class SimAuditRecord(BaseModel):
    """
    Simulation Audit Record with Reality Check Layer (RCL) tracking
    """
    # Core identification
    sim_audit_id: str = Field(..., description="Unique simulation audit ID")
    simulation_id: str = Field(..., description="Reference to monte_carlo_simulations")
    event_id: str = Field(..., description="Event ID")
    
    # Projection data
    raw_total: float = Field(..., description="Raw total from simulation (median)")
    rcl_total: float = Field(..., description="Final total after RCL (may be clamped)")
    vegas_total: float = Field(..., description="Bookmaker total line")
    
    # Reality Check Layer (RCL) status
    rcl_passed: bool = Field(default=False, description="Did projection pass all RCL checks")
    rcl_reason: str = Field(default="PENDING", description="RCL status reason")
    
    # Historical sanity check
    historical_mean: Optional[float] = Field(None, description="League historical mean total")
    historical_std: Optional[float] = Field(None, description="League historical std deviation")
    historical_z_score: Optional[float] = Field(None, description="Z-score vs historical")
    
    # Live pace guardrail (if in-game)
    current_total_points: Optional[float] = Field(None, description="Current game score (live)")
    elapsed_minutes: Optional[float] = Field(None, description="Game time elapsed")
    live_pace_projection: Optional[float] = Field(None, description="Pace-based projection")
    live_pace_ppm: Optional[float] = Field(None, description="Points per minute")
    
    # Per-team pace guardrail
    per_team_pace_needed: Optional[float] = Field(None, description="Required pts/min per team")
    pace_guardrail_status: str = Field(default="not_applicable", description="Per-team pace status")
    
    # Edge eligibility
    edge_eligible: bool = Field(default=True, description="Can declare strong edge if RCL passed")
    confidence_adjustment: Optional[str] = Field(None, description="Confidence tier adjustment if RCL failed")
    
    # Metadata
    league_code: str = Field(..., description="League code (NCAAB, NBA, etc.)")
    regulation_minutes: float = Field(..., description="Total regulation time (40 for college, 48 for NBA)")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        json_schema_extra = {
            "example": {
                "sim_audit_id": "audit_12345",
                "simulation_id": "sim_event123_20241210120000",
                "event_id": "event123",
                "raw_total": 153.0,
                "rcl_total": 145.5,
                "vegas_total": 145.5,
                "rcl_passed": False,
                "rcl_reason": "HISTORICAL_OUTLIER_Z=2.50",
                "historical_mean": 145.0,
                "historical_std": 3.0,
                "historical_z_score": 2.67,
                "edge_eligible": False,
                "confidence_adjustment": "DOWNGRADE_2_TIERS",
                "league_code": "NCAAB",
                "regulation_minutes": 40.0,
                "created_at": "2024-12-10T12:00:00Z"
            }
        }


class LeagueTotalStats(BaseModel):
    """
    Historical total statistics per league for RCL sanity checks
    """
    league_code: str = Field(..., description="League identifier")
    sample_size: int = Field(..., description="Number of games in sample")
    mean_total: float = Field(..., description="Historical mean total")
    std_total: float = Field(..., description="Historical standard deviation")
    min_total: float = Field(..., description="Minimum historical total")
    max_total: float = Field(..., description="Maximum historical total")
    p25_total: float = Field(..., description="25th percentile")
    p50_total: float = Field(..., description="50th percentile (median)")
    p75_total: float = Field(..., description="75th percentile")
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        json_schema_extra = {
            "example": {
                "league_code": "NCAAB",
                "sample_size": 5000,
                "mean_total": 145.0,
                "std_total": 12.0,
                "min_total": 100.0,
                "max_total": 190.0,
                "p25_total": 137.0,
                "p50_total": 145.0,
                "p75_total": 153.0,
                "updated_at": "2024-12-10T00:00:00Z"
            }
        }


def get_sim_audit_collection():
    """Get MongoDB collection for sim_audit"""
    from db.mongo import db
    return db["sim_audit"]


def get_league_total_stats_collection():
    """Get MongoDB collection for league_total_stats"""
    from db.mongo import db
    return db["league_total_stats"]


def create_indexes():
    """Create indexes for sim_audit and league_total_stats collections"""
    from db.mongo import db
    
    # sim_audit indexes
    db["sim_audit"].create_index("sim_audit_id", unique=True)
    db["sim_audit"].create_index([("event_id", 1), ("created_at", -1)])
    db["sim_audit"].create_index("simulation_id")
    db["sim_audit"].create_index([("rcl_passed", 1)])
    db["sim_audit"].create_index([("edge_eligible", 1)])
    db["sim_audit"].create_index([("league_code", 1), ("created_at", -1)])
    
    # league_total_stats indexes
    db["league_total_stats"].create_index("league_code", unique=True)
    db["league_total_stats"].create_index([("updated_at", -1)])
