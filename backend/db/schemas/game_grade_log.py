"""
MongoDB schema for game_grade_log collection
Stores automated post-game grading results
"""
from typing import Optional
from datetime import datetime
from pydantic import BaseModel, Field


class GameGradeLog(BaseModel):
    """
    Post-game grading record
    Automatically generated for every completed game
    """
    game_id: str = Field(..., description="Unique game identifier")
    event_id: str = Field(..., description="Event ID")
    
    # Pregame metrics
    vegas_total_close: float = Field(..., description="Vegas closing total")
    model_total: float = Field(..., description="Model's raw total (pre-RCL)")
    rcl_passed: bool = Field(..., description="Did RCL pass pregame")
    rcl_reason: str = Field(default="", description="RCL failure reason if any")
    
    # Final result
    final_total: float = Field(..., description="Actual final total points")
    final_spread: float = Field(..., description="Actual final spread")
    home_score: float = Field(..., description="Home team final score")
    away_score: float = Field(..., description="Away team final score")
    
    # Deltas (accuracy metrics)
    delta_model: float = Field(..., description="abs(final_total - model_total)")
    delta_vegas: float = Field(..., description="abs(final_total - vegas_total)")
    
    # Classification
    variance_type: str = Field(..., description="Variance classification")
    model_fault: bool = Field(..., description="True if model error, False if natural variance")
    confidence_retro: str = Field(..., description="Retrospective confidence: very_low, low, moderate, high")
    calibration_weight: float = Field(..., description="Weight for calibration (0.25-1.5)")
    
    # Metadata
    league: str = Field(..., description="League code")
    sport_key: str = Field(..., description="Sport key")
    game_date: Optional[datetime] = Field(None, description="Game commence time")
    graded_at: datetime = Field(default_factory=datetime.utcnow, description="When grading ran")
    
    class Config:
        json_schema_extra = {
            "example": {
                "game_id": "event123",
                "event_id": "event123",
                "vegas_total_close": 224.5,
                "model_total": 228.0,
                "rcl_passed": True,
                "rcl_reason": "",
                "final_total": 226.0,
                "final_spread": 8.0,
                "home_score": 117.0,
                "away_score": 109.0,
                "delta_model": 2.0,
                "delta_vegas": 1.5,
                "variance_type": "normal",
                "model_fault": False,
                "confidence_retro": "high",
                "calibration_weight": 1.0,
                "league": "NBA",
                "sport_key": "basketball_nba",
                "game_date": "2024-12-10T19:00:00Z",
                "graded_at": "2024-12-11T02:30:00Z"
            }
        }


class CalibrationLog(BaseModel):
    """
    Weekly calibration run results
    """
    run_at: datetime = Field(default_factory=datetime.utcnow)
    results: dict = Field(..., description="Calibration results by sport")
    total_samples: int = Field(..., description="Total games analyzed")


def create_indexes():
    """Create indexes for game_grade_log collection"""
    from db.mongo import db
    
    # game_grade_log indexes
    db["game_grade_log"].create_index("game_id", unique=True)
    db["game_grade_log"].create_index([("graded_at", -1)])
    db["game_grade_log"].create_index([("model_fault", 1)])
    db["game_grade_log"].create_index([("variance_type", 1)])
    db["game_grade_log"].create_index([("sport_key", 1), ("graded_at", -1)])
    db["game_grade_log"].create_index([("delta_model", 1)])
    
    # calibration_log indexes
    db["calibration_log"].create_index([("run_at", -1)])
