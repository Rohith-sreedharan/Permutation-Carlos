"""
Sport-Specific Configuration System
All thresholds must be configurable, not hardcoded.
"""
from enum import Enum
from dataclasses import dataclass
from typing import Dict, Optional


class Sport(Enum):
    MLB = "mlb"
    NBA = "nba"
    NFL = "nfl"
    NCAAB = "ncaab"
    NCAAF = "ncaaf"
    NHL = "nhl"


class MarketType(Enum):
    SPREAD = "spread"
    TOTAL = "total"
    MONEYLINE = "moneyline"
    PUCKLINE = "puckline"
    PLAYER_PROP = "player_prop"


class EdgeState(Enum):
    EDGE = "EDGE"
    LEAN = "LEAN"
    NO_PLAY = "NO_PLAY"


class VolatilityLevel(Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    EXTREME = "EXTREME"


class DistributionFlag(Enum):
    STABLE = "STABLE"
    UNSTABLE = "UNSTABLE"
    UNSTABLE_EXTREME = "UNSTABLE_EXTREME"


@dataclass
class SportConfig:
    """Configuration for a specific sport"""
    
    # Probability compression
    compression_factor: float
    
    # Spread market thresholds
    spread_eligibility_min: float
    spread_edge_threshold: float
    spread_lean_min: float
    spread_lean_max: float
    
    # Total market thresholds
    total_eligibility_min: float
    total_edge_threshold: float
    total_lean_min: float
    total_lean_max: float
    
    # Moneyline thresholds (if applicable)
    ml_win_prob_edge_min: Optional[float] = None
    ml_edge_threshold: Optional[float] = None
    ml_lean_min: Optional[float] = None
    
    # Spread size guardrails
    max_favorite_spread: Optional[float] = None
    max_dog_spread: Optional[float] = None
    large_spread_edge_requirement: Optional[float] = None
    
    # Volatility rules
    max_volatility_for_edge: VolatilityLevel = VolatilityLevel.MEDIUM
    
    # Expected probability ranges (for monitoring only, not gates)
    expected_prob_min: float = 0.51
    expected_prob_max: float = 0.62
    
    # Sport-specific flags
    requires_pitcher_confirmation: bool = False
    requires_qb_confirmation: bool = False
    requires_goalie_confirmation: bool = False
    weather_sensitive: bool = False
    key_numbers: Optional[list] = None


# MLB Configuration
MLB_CONFIG = SportConfig(
    compression_factor=0.82,
    
    # Moneyline primary market
    ml_win_prob_edge_min=2.0,  # 2.0% minimum
    ml_edge_threshold=3.5,  # 3.5% for EDGE
    ml_lean_min=2.0,
    
    # Totals (very sharp market)
    total_eligibility_min=1.5,
    total_edge_threshold=2.5,
    total_lean_min=1.5,
    total_lean_max=2.4,
    
    # Not spread-first sport, but include for completeness
    spread_eligibility_min=2.0,
    spread_edge_threshold=3.5,
    spread_lean_min=2.0,
    spread_lean_max=3.4,
    
    # MLB specific
    requires_pitcher_confirmation=True,
    weather_sensitive=True,
    expected_prob_min=0.53,
    expected_prob_max=0.57,
)


# NCAAB Configuration
NCAAB_CONFIG = SportConfig(
    compression_factor=0.80,
    
    # Spread primary market
    spread_eligibility_min=4.5,
    spread_edge_threshold=6.0,
    spread_lean_min=4.5,
    spread_lean_max=5.9,
    
    # Totals secondary
    total_eligibility_min=5.5,
    total_edge_threshold=7.0,
    total_lean_min=5.5,
    total_lean_max=6.9,
    
    # Spread guardrails (college allows blowouts)
    max_favorite_spread=12.5,
    max_dog_spread=12.5,
    large_spread_edge_requirement=7.5,
    
    expected_prob_min=0.53,
    expected_prob_max=0.58,
)


# NCAAF Configuration
NCAAF_CONFIG = SportConfig(
    compression_factor=0.80,
    
    # Spread primary
    spread_eligibility_min=4.0,
    spread_edge_threshold=6.0,
    spread_lean_min=4.0,
    spread_lean_max=5.9,
    
    # Totals secondary
    total_eligibility_min=4.5,
    total_edge_threshold=6.5,
    total_lean_min=4.5,
    total_lean_max=6.4,
    
    # Large spread guardrails
    max_favorite_spread=21.0,
    max_dog_spread=24.0,
    large_spread_edge_requirement=8.0,
    
    requires_qb_confirmation=True,
    expected_prob_min=0.54,
    expected_prob_max=0.60,
)


# NFL Configuration
NFL_CONFIG = SportConfig(
    compression_factor=0.85,
    
    # Spread primary
    spread_eligibility_min=3.0,
    spread_edge_threshold=4.5,
    spread_lean_min=3.0,
    spread_lean_max=4.4,
    
    # Totals (very important in NFL)
    total_eligibility_min=3.5,
    total_edge_threshold=5.0,
    total_lean_min=3.5,
    total_lean_max=4.9,
    
    # Spread guardrails (no college blowouts)
    max_favorite_spread=7.5,
    max_dog_spread=8.5,
    large_spread_edge_requirement=6.0,
    
    requires_qb_confirmation=True,
    weather_sensitive=True,
    key_numbers=[3, 7, 10],
    expected_prob_min=0.54,
    expected_prob_max=0.59,
)


# NHL Configuration
NHL_CONFIG = SportConfig(
    compression_factor=0.60,  # Most aggressive compression
    
    # Totals/puckline focused
    total_eligibility_min=1.5,
    total_edge_threshold=2.5,
    total_lean_min=1.5,
    total_lean_max=2.4,
    
    # Spread/puckline (limited)
    spread_eligibility_min=1.0,
    spread_edge_threshold=1.5,
    spread_lean_min=1.0,
    spread_lean_max=1.4,
    
    # Strict caps
    max_favorite_spread=2.5,
    max_dog_spread=2.5,
    
    requires_goalie_confirmation=True,
    expected_prob_min=0.52,
    expected_prob_max=0.56,
)


# NBA Configuration (not in client specs but included for completeness)
NBA_CONFIG = SportConfig(
    compression_factor=0.83,
    
    spread_eligibility_min=4.0,
    spread_edge_threshold=5.5,
    spread_lean_min=4.0,
    spread_lean_max=5.4,
    
    total_eligibility_min=4.5,
    total_edge_threshold=6.0,
    total_lean_min=4.5,
    total_lean_max=5.9,
    
    max_favorite_spread=12.5,
    max_dog_spread=12.5,
    large_spread_edge_requirement=7.0,
    
    expected_prob_min=0.54,
    expected_prob_max=0.62,
)


# Configuration registry
SPORT_CONFIGS: Dict[Sport, SportConfig] = {
    Sport.MLB: MLB_CONFIG,
    Sport.NCAAB: NCAAB_CONFIG,
    Sport.NCAAF: NCAAF_CONFIG,
    Sport.NFL: NFL_CONFIG,
    Sport.NHL: NHL_CONFIG,
    Sport.NBA: NBA_CONFIG,
}


def get_sport_config(sport: Sport) -> SportConfig:
    """Get configuration for a sport"""
    return SPORT_CONFIGS[sport]
