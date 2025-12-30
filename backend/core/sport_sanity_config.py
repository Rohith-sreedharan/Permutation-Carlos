"""
SPORT SANITY CHECK CONFIGURATION — PRODUCTION READY (LOCKED)
============================================================
Universal sport-specific calibration, gating, and classification logic.

This module defines ALL sport-specific thresholds for:
- MLB: Moneyline + totals dominant, pitcher/bullpen sensitive
- NCAAB: More opportunities than NBA, blowout-aware
- NCAAF: Blowout math, scheme variance handling
- NFL: Key numbers, QB sensitivity, scarcity
- NHL: Tight markets, compression required, rare edges
- NBA: Reference sport (highest volume)

ALL VALUES ARE CONFIGURABLE via environment or admin override.
"""

from typing import Dict, Any, Optional, List, Literal
from dataclasses import dataclass, field
from enum import Enum
import os


# ============================================================================
# ENUMS (UNIVERSAL)
# ============================================================================

class EdgeState(str, Enum):
    """Universal edge classification states"""
    EDGE = "EDGE"          # Telegram-worthy, actionable
    LEAN = "LEAN"          # Informational, optional
    NO_PLAY = "NO_PLAY"    # Default state


class PrimaryMarket(str, Enum):
    """Primary market type"""
    SPREAD = "SPREAD"
    TOTAL = "TOTAL"
    MONEYLINE = "MONEYLINE"
    PUCKLINE = "PUCKLINE"
    NONE = "NONE"


class DistributionFlag(str, Enum):
    """Distribution stability assessment"""
    STABLE = "STABLE"
    UNSTABLE_MEDIUM = "UNSTABLE_MEDIUM"
    UNSTABLE_EXTREME = "UNSTABLE_EXTREME"


class VolatilityBucket(str, Enum):
    """Volatility classification"""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    EXTREME = "EXTREME"


# ============================================================================
# SPORT-SPECIFIC CONFIGURATIONS (LOCKED)
# ============================================================================

@dataclass
class SportSanityConfig:
    """
    Sport-specific sanity check configuration
    All thresholds are configurable, not hardcoded in logic
    """
    sport_key: str
    sport_name: str
    
    # PROBABILITY COMPRESSION (MANDATORY)
    compression_factor: float  # 0.6-0.85 depending on sport
    
    # SPREAD MARKET THRESHOLDS
    spread_edge_eligibility: float   # Minimum edge to consider
    spread_edge_edge: float          # Minimum edge for EDGE state
    spread_edge_lean_min: float      # Minimum edge for LEAN
    spread_edge_lean_max: float      # Maximum edge for LEAN (below EDGE)
    
    # SPREAD SIZE GUARDRAILS
    max_auto_favorite_spread: float  # Auto-allowed favorite spreads
    max_auto_underdog_spread: float  # Auto-allowed dog spreads
    large_spread_edge_requirement: float  # Extra edge needed for large spreads
    
    # TOTALS MARKET THRESHOLDS
    total_edge_eligibility: float
    total_edge_edge: float
    total_edge_lean_min: float
    total_edge_lean_max: float
    
    # MONEYLINE THRESHOLDS (MLB/NHL primary)
    ml_win_prob_edge_eligibility: float  # Minimum win prob edge
    ml_win_prob_edge_edge: float         # EDGE threshold
    ml_favorite_guardrail: float         # Beyond this requires extra edge
    ml_underdog_guardrail: float         # Beyond this requires extra edge
    ml_guardrail_edge_requirement: float # Extra edge if beyond guardrails
    
    # MARKET CONFIRMATION (SUPPORTIVE, NOT REQUIRED)
    min_clv_confirmation: float  # CLV threshold for confirmation
    
    # VOLATILITY/DISTRIBUTION THRESHOLDS
    volatility_downgrade: str    # Bucket that triggers downgrade
    volatility_block: str        # Bucket that forces NO_PLAY
    distribution_max_ot: float   # Max OT/close game frequency (NHL)
    distribution_max_close: float  # Max close games for ML edges (NHL)
    
    # KEY NUMBER HANDLING (NFL specific)
    key_numbers: List[float] = field(default_factory=list)
    key_number_extra_edge: float = 0.5  # Extra edge needed near key numbers
    
    # EXPECTED OUTPUT DISTRIBUTION (SANITY CHECK)
    expected_edge_count_per_day: tuple = (0, 3)  # (min, max)
    expected_prob_range: tuple = (0.52, 0.62)    # Normal probability range
    expected_no_play_rate: float = 0.60          # Minimum NO_PLAY rate
    
    # WEATHER/PARK ADJUSTMENTS (MLB/NFL)
    weather_edge_adjustment: float = 1.0  # Extra edge needed in weather games
    
    # INJURY/ROSTER SENSITIVITY
    max_injury_uncertainty_for_edge: float = 0.15
    qb_uncertain_forces_no_play: bool = False
    pitcher_uncertain_forces_no_play: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "sport_key": self.sport_key,
            "sport_name": self.sport_name,
            "compression_factor": self.compression_factor,
            "spread_edge_eligibility": self.spread_edge_eligibility,
            "spread_edge_edge": self.spread_edge_edge,
            "total_edge_eligibility": self.total_edge_eligibility,
            "total_edge_edge": self.total_edge_edge,
            "ml_win_prob_edge_eligibility": self.ml_win_prob_edge_eligibility,
            "ml_win_prob_edge_edge": self.ml_win_prob_edge_edge,
            "expected_edge_count_per_day": self.expected_edge_count_per_day,
            "expected_prob_range": self.expected_prob_range,
        }


# ============================================================================
# NBA CONFIGURATION
# ============================================================================

NBA_SANITY_CONFIG = SportSanityConfig(
    sport_key="basketball_nba",
    sport_name="NBA",
    
    # Compression: Moderate (0.85 preserves strong favorites)
    compression_factor=0.85,
    
    # Spreads
    spread_edge_eligibility=3.0,
    spread_edge_edge=4.5,
    spread_edge_lean_min=3.0,
    spread_edge_lean_max=4.4,
    max_auto_favorite_spread=-10.5,
    max_auto_underdog_spread=10.5,
    large_spread_edge_requirement=6.0,
    
    # Totals
    total_edge_eligibility=4.0,
    total_edge_edge=6.0,
    total_edge_lean_min=4.0,
    total_edge_lean_max=5.9,
    
    # Moneyline (secondary)
    ml_win_prob_edge_eligibility=0.025,
    ml_win_prob_edge_edge=0.04,
    ml_favorite_guardrail=-200.0,
    ml_underdog_guardrail=180.0,
    ml_guardrail_edge_requirement=0.05,
    
    # Market confirmation
    min_clv_confirmation=0.0025,
    
    # Volatility
    volatility_downgrade="HIGH",
    volatility_block="EXTREME",
    distribution_max_ot=0.0,
    distribution_max_close=0.0,
    
    # Expected outputs
    expected_edge_count_per_day=(1, 3),
    expected_prob_range=(0.54, 0.62),
    expected_no_play_rate=0.65,
    
    # Weather N/A
    weather_edge_adjustment=0.0,
    
    # Injury sensitivity
    max_injury_uncertainty_for_edge=0.15,
    qb_uncertain_forces_no_play=False,
    pitcher_uncertain_forces_no_play=False,
)


# ============================================================================
# NFL CONFIGURATION (KEY NUMBERS CRITICAL)
# ============================================================================

NFL_SANITY_CONFIG = SportSanityConfig(
    sport_key="americanfootball_nfl",
    sport_name="NFL",
    
    # Compression: Less aggressive (0.85 preserves strong favorites)
    compression_factor=0.85,
    
    # Spreads
    spread_edge_eligibility=3.0,
    spread_edge_edge=4.5,
    spread_edge_lean_min=3.0,
    spread_edge_lean_max=4.4,
    max_auto_favorite_spread=-7.5,
    max_auto_underdog_spread=8.5,
    large_spread_edge_requirement=6.0,
    
    # Totals (very important in NFL)
    total_edge_eligibility=3.5,
    total_edge_edge=5.0,
    total_edge_lean_min=3.5,
    total_edge_lean_max=4.9,
    
    # Moneyline (secondary)
    ml_win_prob_edge_eligibility=0.025,
    ml_win_prob_edge_edge=0.04,
    ml_favorite_guardrail=-180.0,
    ml_underdog_guardrail=160.0,
    ml_guardrail_edge_requirement=0.05,
    
    # Market confirmation
    min_clv_confirmation=0.0025,
    
    # Volatility
    volatility_downgrade="HIGH",
    volatility_block="EXTREME",
    distribution_max_ot=0.0,
    distribution_max_close=0.0,
    
    # KEY NUMBERS (NFL SPECIFIC - CRITICAL)
    key_numbers=[3.0, 7.0, 10.0],
    key_number_extra_edge=0.5,
    
    # Expected outputs (fewer than NBA due to scarcity)
    expected_edge_count_per_day=(0, 2),
    expected_prob_range=(0.54, 0.59),
    expected_no_play_rate=0.70,
    
    # Weather (mandatory consideration)
    weather_edge_adjustment=1.0,
    
    # Injury sensitivity (QB critical)
    max_injury_uncertainty_for_edge=0.10,
    qb_uncertain_forces_no_play=True,
    pitcher_uncertain_forces_no_play=False,
)


# ============================================================================
# NCAAF CONFIGURATION (BLOWOUTS + SCHEME VARIANCE)
# ============================================================================

NCAAF_SANITY_CONFIG = SportSanityConfig(
    sport_key="americanfootball_ncaaf",
    sport_name="NCAAF",
    
    # Compression: More aggressive (0.80 kills fake certainty from blowouts)
    compression_factor=0.80,
    
    # Spreads (primary market, higher thresholds due to blowout noise)
    spread_edge_eligibility=4.0,
    spread_edge_edge=6.0,
    spread_edge_lean_min=4.0,
    spread_edge_lean_max=5.9,
    max_auto_favorite_spread=-21.0,  # College allows blowouts
    max_auto_underdog_spread=24.0,
    large_spread_edge_requirement=8.0,  # High threshold for large spreads
    
    # Totals (secondary, valuable)
    total_edge_eligibility=4.5,
    total_edge_edge=6.5,
    total_edge_lean_min=4.5,
    total_edge_lean_max=6.4,
    
    # Moneyline (less relevant)
    ml_win_prob_edge_eligibility=0.03,
    ml_win_prob_edge_edge=0.05,
    ml_favorite_guardrail=-300.0,
    ml_underdog_guardrail=250.0,
    ml_guardrail_edge_requirement=0.06,
    
    # Market confirmation
    min_clv_confirmation=0.003,
    
    # Volatility
    volatility_downgrade="HIGH",
    volatility_block="EXTREME",
    distribution_max_ot=0.0,
    distribution_max_close=0.0,
    
    # Expected outputs (more than NFL, less than NBA)
    expected_edge_count_per_day=(1, 3),
    expected_prob_range=(0.54, 0.60),
    expected_no_play_rate=0.65,
    
    # Weather
    weather_edge_adjustment=0.5,
    
    # Injury sensitivity (QB + scheme)
    max_injury_uncertainty_for_edge=0.20,
    qb_uncertain_forces_no_play=True,
    pitcher_uncertain_forces_no_play=False,
)


# ============================================================================
# NCAAB CONFIGURATION (MORE OPPORTUNITIES, BLOWOUT AWARE)
# ============================================================================

NCAAB_SANITY_CONFIG = SportSanityConfig(
    sport_key="basketball_ncaab",
    sport_name="NCAAB",
    
    # Compression: Aggressive (0.80)
    compression_factor=0.80,
    
    # Spreads (primary edge source)
    spread_edge_eligibility=4.5,
    spread_edge_edge=6.0,
    spread_edge_lean_min=4.5,
    spread_edge_lean_max=5.9,
    max_auto_favorite_spread=-12.5,
    max_auto_underdog_spread=12.5,
    large_spread_edge_requirement=7.5,
    
    # Totals (more volatile in NCAAB)
    total_edge_eligibility=5.5,
    total_edge_edge=7.0,
    total_edge_lean_min=5.5,
    total_edge_lean_max=6.9,
    
    # Moneyline (less relevant)
    ml_win_prob_edge_eligibility=0.03,
    ml_win_prob_edge_edge=0.045,
    ml_favorite_guardrail=-250.0,
    ml_underdog_guardrail=220.0,
    ml_guardrail_edge_requirement=0.055,
    
    # Market confirmation
    min_clv_confirmation=0.003,
    
    # Volatility
    volatility_downgrade="HIGH",
    volatility_block="EXTREME",
    distribution_max_ot=0.0,
    distribution_max_close=0.0,
    
    # Expected outputs (more than NBA)
    expected_edge_count_per_day=(2, 5),
    expected_prob_range=(0.53, 0.58),
    expected_no_play_rate=0.60,
    
    # Weather N/A
    weather_edge_adjustment=0.0,
    
    # Injury sensitivity
    max_injury_uncertainty_for_edge=0.20,
    qb_uncertain_forces_no_play=False,
    pitcher_uncertain_forces_no_play=False,
)


# ============================================================================
# MLB CONFIGURATION (MONEYLINE + TOTALS DOMINANT)
# ============================================================================

MLB_SANITY_CONFIG = SportSanityConfig(
    sport_key="baseball_mlb",
    sport_name="MLB",
    
    # Compression: Slightly less aggressive (0.82 preserves pitcher mismatches)
    compression_factor=0.82,
    
    # Spreads (run lines - secondary)
    spread_edge_eligibility=1.0,
    spread_edge_edge=1.5,
    spread_edge_lean_min=1.0,
    spread_edge_lean_max=1.4,
    max_auto_favorite_spread=-1.5,
    max_auto_underdog_spread=1.5,
    large_spread_edge_requirement=2.0,
    
    # Totals (very important, weather-sensitive)
    total_edge_eligibility=1.5,
    total_edge_edge=2.5,
    total_edge_lean_min=1.5,
    total_edge_lean_max=2.4,
    
    # Moneyline (PRIMARY MLB MARKET)
    ml_win_prob_edge_eligibility=0.02,
    ml_win_prob_edge_edge=0.035,
    ml_favorite_guardrail=-165.0,  # Beyond -165 requires extra edge
    ml_underdog_guardrail=160.0,   # Beyond +160 requires extra edge
    ml_guardrail_edge_requirement=0.045,
    
    # Market confirmation
    min_clv_confirmation=0.002,
    
    # Volatility
    volatility_downgrade="HIGH",
    volatility_block="EXTREME",
    distribution_max_ot=0.0,
    distribution_max_close=0.0,
    
    # Expected outputs (fewer plays, small true edges)
    expected_edge_count_per_day=(0, 2),
    expected_prob_range=(0.53, 0.57),
    expected_no_play_rate=0.75,
    
    # Weather (MANDATORY for totals)
    weather_edge_adjustment=0.5,
    
    # Pitcher sensitivity (CRITICAL)
    max_injury_uncertainty_for_edge=0.10,
    qb_uncertain_forces_no_play=False,
    pitcher_uncertain_forces_no_play=True,
)


# ============================================================================
# NHL CONFIGURATION (TIGHTEST MARKETS, MOST COMPRESSION)
# ============================================================================

NHL_SANITY_CONFIG = SportSanityConfig(
    sport_key="icehockey_nhl",
    sport_name="NHL",
    
    # Compression: MOST AGGRESSIVE (0.60 - removes false certainty)
    compression_factor=0.60,
    
    # Spreads/Pucklines (puckline -1.5/+1.5)
    spread_edge_eligibility=0.5,
    spread_edge_edge=0.8,
    spread_edge_lean_min=0.5,
    spread_edge_lean_max=0.79,
    max_auto_favorite_spread=-1.5,
    max_auto_underdog_spread=1.5,
    large_spread_edge_requirement=1.0,
    
    # Totals (primary edge source in NHL)
    total_edge_eligibility=0.5,
    total_edge_edge=0.8,
    total_edge_lean_min=0.5,
    total_edge_lean_max=0.79,
    
    # Moneyline (important but tightly priced)
    ml_win_prob_edge_eligibility=0.025,  # Hard cap at 3% edge
    ml_win_prob_edge_edge=0.03,
    ml_favorite_guardrail=-180.0,
    ml_underdog_guardrail=160.0,
    ml_guardrail_edge_requirement=0.04,
    
    # Market confirmation (REQUIRED for NHL per spec)
    min_clv_confirmation=0.003,  # CLV >= 0.3%
    
    # Volatility (NHL specific - high OT/1-goal games)
    volatility_downgrade="MEDIUM",  # More aggressive downgrade
    volatility_block="HIGH",        # High volatility = block
    distribution_max_ot=0.65,       # >65% OT/1-goal → invalidate spread
    distribution_max_close=0.75,    # >75% → invalidate moneyline
    
    # Expected outputs (EDGE very rare, LEAN occasional)
    expected_edge_count_per_day=(0, 2),
    expected_prob_range=(0.52, 0.56),  # Tight range
    expected_no_play_rate=0.80,  # Most games NO_PLAY
    
    # Weather N/A
    weather_edge_adjustment=0.0,
    
    # Goalie sensitivity
    max_injury_uncertainty_for_edge=0.10,
    qb_uncertain_forces_no_play=False,
    pitcher_uncertain_forces_no_play=False,  # Goalie handled separately
)


# ============================================================================
# CONFIG REGISTRY
# ============================================================================

SPORT_SANITY_CONFIGS: Dict[str, SportSanityConfig] = {
    "basketball_nba": NBA_SANITY_CONFIG,
    "americanfootball_nfl": NFL_SANITY_CONFIG,
    "americanfootball_ncaaf": NCAAF_SANITY_CONFIG,
    "basketball_ncaab": NCAAB_SANITY_CONFIG,
    "baseball_mlb": MLB_SANITY_CONFIG,
    "icehockey_nhl": NHL_SANITY_CONFIG,
}


def get_sport_sanity_config(sport_key: str) -> Optional[SportSanityConfig]:
    """Get sanity config for a sport"""
    return SPORT_SANITY_CONFIGS.get(sport_key)


def get_compression_factor(sport_key: str) -> float:
    """Get probability compression factor for a sport"""
    config = get_sport_sanity_config(sport_key)
    return config.compression_factor if config else 0.85


def compress_probability(raw_prob: float, sport_key: str) -> float:
    """
    Compress raw probability using sport-specific factor
    
    Formula: compressed = 0.5 + (raw - 0.5) * compression_factor
    """
    factor = get_compression_factor(sport_key)
    compressed = 0.5 + (raw_prob - 0.5) * factor
    return max(0.01, min(0.99, compressed))
