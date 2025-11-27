"""
Backend API endpoints for player-specific prop mispricings and decision intelligence.

This module provides endpoints for:
1. Player-specific prop mispricing data (replacing generic position labels)
2. Risk profile management (Decision Capital Profile)
3. Decision logging and tracking

COMPLIANCE NOTE: All terminology uses "decision", "forecast", "analysis" language.
NO gambling-implied terms like "bet", "wager", "gamble".
"""

from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime


# ============================================================================
# PLAYER-SPECIFIC PROP MODELS
# ============================================================================

class PropMispricing(BaseModel):
    """
    Player-specific prop mispricing with drill-down analytics.
    
    Replaces generic "Indiana Pacers Guard" with "Tyrese Haliburton (PG)".
    """
    player_name: str  # "Tyrese Haliburton"
    position: str  # Exact position: "PG", "SG", "SF", "PF", "C", "QB", etc.
    team: str  # "Indiana Pacers"
    market: str  # "Assists", "Points", "Rebounds", "Passing Yards"
    line: float  # 7.5
    win_probability: float  # 0.58 (58%)
    expected_value: float  # 4.2 (4.2% edge)
    confidence: float  # 0.75 (model confidence)
    
    # Performance context
    recent_avg: Optional[float] = None  # Last 5 games average
    season_avg: Optional[float] = None
    minutes_projection: Optional[int] = None
    opponent_rank: Optional[int] = None  # Defensive rank vs position
    
    # Simulation data for drill-down
    distribution: Optional[List[dict]] = None  # [{"value": 8.0, "probability": 0.23}, ...]
    confidence_range: Optional[tuple[float, float]] = None  # (6.2, 9.1) for 95% CI
    scenario_factors: Optional[List[str]] = None  # ["Pace-up matchup", "High usage rate"]


class EventPropMispricings(BaseModel):
    """Event with top player-specific prop mispricings."""
    event_id: str
    sport_key: str
    home_team: str
    away_team: str
    commence_time: str
    top_prop_mispricings: List[PropMispricing]  # Top 5 props


# ============================================================================
# RISK PROFILE MODELS (Decision Capital Profile)
# ============================================================================

class RiskProfile(BaseModel):
    """
    User risk profile for Decision Capital Profile feature.
    
    Replaces gambling-focused "bankroll" with intelligence-focused risk management.
    """
    user_id: str
    starting_capital: float
    unit_strategy: str  # "fixed" or "percentage"
    unit_size: float  # Dollar amount or percentage (1-5%)
    risk_classification: str  # "conservative", "balanced", "aggressive"
    
    # Calculated fields
    suggested_exposure_per_decision: Optional[float] = None
    volatility_tolerance: Optional[float] = None
    max_daily_exposure: Optional[float] = None
    
    # Performance tracking
    total_decisions: Optional[int] = 0
    winning_decisions: Optional[int] = 0
    roi: Optional[float] = None  # Return on Intelligence
    sharpe_ratio: Optional[float] = None


class DecisionLog(BaseModel):
    """
    Decision tracking log for transparency and alignment scoring.
    
    Tracks user decisions vs model recommendations for performance analysis.
    """
    decision_id: str
    user_id: str
    event_id: str
    player_name: Optional[str] = None  # For prop decisions
    market: str  # "Moneyline", "Assists", etc.
    line: float
    confidence_weight: float  # 1-5 units based on win probability
    exposure: float  # Dollar amount of decision
    expected_value: float
    win_probability: float
    decision_time: datetime
    
    # Resolution
    outcome: Optional[str] = None  # "win", "loss", "push", "pending"
    actual_result: Optional[float] = None
    profit_loss: Optional[float] = None
    
    # Alignment tracking
    aligned_with_model: bool  # Did user follow high-confidence forecast?


# ============================================================================
# EXAMPLE API ENDPOINT IMPLEMENTATIONS
# ============================================================================

# ENDPOINT: GET /api/events/{event_id}/prop-mispricings
def get_event_prop_mispricings(event_id: str) -> EventPropMispricings:
    """
    Get top 5 player-specific prop mispricings for an event.
    
    Example response:
    {
        "event_id": "abc123",
        "sport_key": "basketball_nba",
        "home_team": "Indiana Pacers",
        "away_team": "Cleveland Cavaliers",
        "commence_time": "2025-11-23T19:00:00Z",
        "top_prop_mispricings": [
            {
                "player_name": "Tyrese Haliburton",
                "position": "PG",
                "team": "Indiana Pacers",
                "market": "Assists",
                "line": 7.5,
                "win_probability": 0.58,
                "expected_value": 4.2,
                "confidence": 0.75,
                "recent_avg": 8.4,
                "season_avg": 8.1,
                "minutes_projection": 34,
                "opponent_rank": 28,
                "distribution": [
                    {"value": 6.0, "probability": 0.15},
                    {"value": 7.0, "probability": 0.20},
                    {"value": 8.0, "probability": 0.25},
                    {"value": 9.0, "probability": 0.23},
                    {"value": 10.0, "probability": 0.17}
                ],
                "confidence_range": [6.2, 9.8],
                "scenario_factors": [
                    "Pace-up matchup (102.5 projected pace)",
                    "High usage rate without Mathurin",
                    "Opponent allows 9.2 APG to PGs"
                ]
            },
            ...
        ]
    }
    """
    # TODO: Implement with actual Monte Carlo simulation data
    raise NotImplementedError("Player-specific prop mispricings endpoint not yet implemented")


# ENDPOINT: GET /api/user/risk-profile
def get_risk_profile(user_id: str) -> RiskProfile:
    """
    Get user's Decision Capital Profile.
    
    Example response:
    {
        "user_id": "user123",
        "starting_capital": 1000,
        "unit_strategy": "percentage",
        "unit_size": 2.0,
        "risk_classification": "balanced",
        "suggested_exposure_per_decision": 20,
        "volatility_tolerance": 0.15,
        "max_daily_exposure": 100,
        "total_decisions": 47,
        "winning_decisions": 28,
        "roi": 8.4,
        "sharpe_ratio": 1.23
    }
    """
    # TODO: Implement with MongoDB user_risk_profiles collection
    raise NotImplementedError("Risk profile endpoint not yet implemented")


# ENDPOINT: POST /api/user/risk-profile
def update_risk_profile(profile: RiskProfile) -> RiskProfile:
    """
    Update user's Decision Capital Profile.
    
    Calculates risk_classification based on unit_strategy and unit_size:
    - Percentage strategy:
        - <= 1%: Conservative
        - 1-3%: Balanced
        - >= 3%: Aggressive
    - Fixed strategy:
        - Calculate % of starting_capital
        - Apply same thresholds
    """
    # Calculate risk classification
    if profile.unit_strategy == "percentage":
        if profile.unit_size <= 1:
            profile.risk_classification = "conservative"
        elif profile.unit_size >= 3:
            profile.risk_classification = "aggressive"
        else:
            profile.risk_classification = "balanced"
    else:  # Fixed strategy
        pct_of_capital = (profile.unit_size / profile.starting_capital) * 100
        if pct_of_capital <= 1:
            profile.risk_classification = "conservative"
        elif pct_of_capital >= 3:
            profile.risk_classification = "aggressive"
        else:
            profile.risk_classification = "balanced"
    
    # Calculate suggested exposure
    if profile.unit_strategy == "percentage":
        profile.suggested_exposure_per_decision = (profile.starting_capital * profile.unit_size) / 100
    else:
        profile.suggested_exposure_per_decision = profile.unit_size
    
    # Calculate max daily exposure (5x unit size)
    profile.max_daily_exposure = profile.suggested_exposure_per_decision * 5
    
    # TODO: Save to MongoDB and return
    return profile


# ENDPOINT: GET /api/user/decisions
def get_decision_logs(user_id: str, limit: int = 50, offset: int = 0) -> List[DecisionLog]:
    """
    Get user's decision logs for Command Center display.
    
    Used for:
    - Decision Command Center table
    - Alignment Score calculation
    - Performance tracking
    """
    # TODO: Implement with MongoDB decision_logs collection
    raise NotImplementedError("Decision logs endpoint not yet implemented")


# ENDPOINT: POST /api/user/decisions
def log_decision(decision: DecisionLog) -> DecisionLog:
    """
    Log a user decision for tracking and alignment scoring.
    
    This endpoint tracks:
    1. What decision the user made
    2. Whether it aligned with high-confidence model forecast
    3. Exposure amount relative to risk profile
    4. Outcome (resolved after event completes)
    """
    # TODO: Implement with MongoDB decision_logs collection
    raise NotImplementedError("Log decision endpoint not yet implemented")


# ============================================================================
# PROP RESOLUTION LOGIC (Convert Position Labels to Player Names)
# ============================================================================

def resolve_position_to_player(team: str, position: str, market: str, line: float) -> PropMispricing:
    """
    Resolve generic position label to specific player.
    
    Example:
        Input: team="Indiana Pacers", position="Guard", market="Assists", line=7.5
        Output: PropMispricing with player_name="Tyrese Haliburton", position="PG"
    
    Logic:
    1. Query odds API for team roster
    2. Filter by position group (Guard → PG/SG, Forward → SF/PF, Center → C)
    3. Match to specific prop line from odds feed
    4. Enrich with performance context (recent avg, opponent rank, etc.)
    5. Run Monte Carlo simulation for distribution and EV
    """
    # TODO: Implement with odds API integration
    # Steps:
    # 1. Get roster from odds API
    # 2. Match position group to specific player prop
    # 3. Fetch player stats (recent games, season avg)
    # 4. Fetch opponent defensive rank vs position
    # 5. Run simulation for distribution
    # 6. Calculate confidence range
    # 7. Generate scenario factors
    raise NotImplementedError("Position to player resolution not yet implemented")


# ============================================================================
# COMPLIANCE VALIDATION
# ============================================================================

def validate_prop_display(prop: PropMispricing) -> bool:
    """
    Ensure prop display uses compliant terminology.
    
    ALLOWED:
    - "forecast", "analysis", "projection", "insight"
    - "win probability", "expected value", "confidence"
    - "decision", "exposure", "alignment"
    
    PROHIBITED:
    - "bet", "wager", "gamble"
    - "guaranteed win", "lock", "sure thing"
    - "bankroll", "stake"
    """
    prohibited_terms = ["bet", "wager", "gamble", "guaranteed", "lock", "bankroll"]
    
    # Check all string fields
    fields_to_check = [
        prop.market,
        *[f for f in (prop.scenario_factors or [])],
    ]
    
    for field in fields_to_check:
        if isinstance(field, str):
            for term in prohibited_terms:
                if term.lower() in field.lower():
                    return False
    
    return True
