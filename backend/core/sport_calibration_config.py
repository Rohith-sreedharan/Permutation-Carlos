"""
Sport Configuration - System-Wide Calibration Thresholds
Locked institutional-grade constraints applied across all sports
"""
from typing import Dict, Any
from dataclasses import dataclass


@dataclass
class SportCalibrationConfig:
    """
    Sport-specific calibration thresholds
    These are HARD CONSTRAINTS, not suggestions
    """
    # Sport identifier
    sport_key: str
    sport_name: str
    
    # A) MARKET ANCHOR THRESHOLDS (Vegas prior penalty)
    soft_deviation: float  # Penalty starts (pts/runs/goals)
    hard_deviation: float  # Block unless elite confidence
    
    # B) MINIMUM EDGE TO PUBLISH (don't publish noise)
    min_probability: float      # Minimum O/U probability (0.56-0.58)
    min_ev_vs_vig: float       # Minimum EV % vs vig
    min_model_vegas_diff: float # Minimum deviation to publish
    
    # C) VARIANCE GATING (kill fake certainty)
    normal_variance_z: float    # No penalty threshold
    high_variance_z: float      # Dampen edge/probability
    extreme_variance_z: float   # Block unless elite
    
    # D) ELITE OVERRIDE THRESHOLDS (rare, allowed)
    elite_min_probability: float
    elite_max_z_variance: float
    elite_min_data_quality: float
    elite_max_injury_uncertainty: float
    
    # E) LEAGUE BASELINE CLAMP (daily calibration)
    max_bias_vs_actual: float       # Max drift from actual results
    max_bias_vs_market: float       # Max drift from Vegas
    max_over_rate: float            # Max % of overs allowed
    calibration_window_days: int    # Rolling window for calibration


# LOCKED SPORT CONFIGS (institutional grade)
SPORT_CONFIGS = {
    "americanfootball_nfl": SportCalibrationConfig(
        sport_key="americanfootball_nfl",
        sport_name="NFL",
        
        # Market anchor
        soft_deviation=4.5,
        hard_deviation=7.5,
        
        # Publish minimums
        min_probability=0.58,
        min_ev_vs_vig=2.0,
        min_model_vegas_diff=2.5,
        
        # Variance gating
        normal_variance_z=1.05,
        high_variance_z=1.25,
        extreme_variance_z=1.40,
        
        # Elite override
        elite_min_probability=0.62,
        elite_max_z_variance=1.15,
        elite_min_data_quality=0.95,
        elite_max_injury_uncertainty=0.15,
        
        # Baseline clamp
        max_bias_vs_actual=1.5,
        max_bias_vs_market=1.0,
        max_over_rate=0.62,
        calibration_window_days=28
    ),
    
    "americanfootball_ncaaf": SportCalibrationConfig(
        sport_key="americanfootball_ncaaf",
        sport_name="NCAAF",
        
        soft_deviation=6.5,
        hard_deviation=10.5,
        
        min_probability=0.57,
        min_ev_vs_vig=1.5,
        min_model_vegas_diff=3.0,
        
        normal_variance_z=1.05,
        high_variance_z=1.25,
        extreme_variance_z=1.40,
        
        elite_min_probability=0.61,
        elite_max_z_variance=1.15,
        elite_min_data_quality=0.95,
        elite_max_injury_uncertainty=0.20,
        
        max_bias_vs_actual=1.5,
        max_bias_vs_market=1.0,
        max_over_rate=0.62,
        calibration_window_days=28
    ),
    
    "basketball_nba": SportCalibrationConfig(
        sport_key="basketball_nba",
        sport_name="NBA",
        
        soft_deviation=6.0,
        hard_deviation=9.5,
        
        min_probability=0.57,
        min_ev_vs_vig=1.5,
        min_model_vegas_diff=3.0,
        
        normal_variance_z=1.05,
        high_variance_z=1.25,
        extreme_variance_z=1.40,
        
        elite_min_probability=0.61,
        elite_max_z_variance=1.15,
        elite_min_data_quality=0.95,
        elite_max_injury_uncertainty=0.15,
        
        max_bias_vs_actual=1.5,
        max_bias_vs_market=1.0,
        max_over_rate=0.62,
        calibration_window_days=28
    ),
    
    "basketball_ncaab": SportCalibrationConfig(
        sport_key="basketball_ncaab",
        sport_name="NCAAB",
        
        soft_deviation=5.5,
        hard_deviation=9.0,
        
        min_probability=0.565,
        min_ev_vs_vig=1.25,
        min_model_vegas_diff=2.5,
        
        normal_variance_z=1.05,
        high_variance_z=1.25,
        extreme_variance_z=1.40,
        
        elite_min_probability=0.605,
        elite_max_z_variance=1.15,
        elite_min_data_quality=0.95,
        elite_max_injury_uncertainty=0.20,
        
        max_bias_vs_actual=1.5,
        max_bias_vs_market=1.0,
        max_over_rate=0.62,
        calibration_window_days=28
    ),
    
    "baseball_mlb": SportCalibrationConfig(
        sport_key="baseball_mlb",
        sport_name="MLB",
        
        soft_deviation=0.9,
        hard_deviation=1.5,
        
        min_probability=0.56,
        min_ev_vs_vig=1.25,
        min_model_vegas_diff=0.6,
        
        normal_variance_z=1.05,
        high_variance_z=1.25,
        extreme_variance_z=1.35,
        
        elite_min_probability=0.60,
        elite_max_z_variance=1.10,
        elite_min_data_quality=0.95,
        elite_max_injury_uncertainty=0.10,
        
        max_bias_vs_actual=0.25,
        max_bias_vs_market=0.15,
        max_over_rate=0.62,
        calibration_window_days=28
    ),
    
    "icehockey_nhl": SportCalibrationConfig(
        sport_key="icehockey_nhl",
        sport_name="NHL",
        
        soft_deviation=0.8,
        hard_deviation=1.3,
        
        min_probability=0.56,
        min_ev_vs_vig=1.25,
        min_model_vegas_diff=0.6,
        
        normal_variance_z=1.05,
        high_variance_z=1.25,
        extreme_variance_z=1.35,
        
        elite_min_probability=0.60,
        elite_max_z_variance=1.10,
        elite_min_data_quality=0.95,
        elite_max_injury_uncertainty=0.10,
        
        max_bias_vs_actual=0.20,
        max_bias_vs_market=0.15,
        max_over_rate=0.62,
        calibration_window_days=28
    )
}


def get_sport_config(sport_key: str) -> SportCalibrationConfig:
    """
    Get calibration config for sport
    Returns NFL config as fallback for unknown sports
    """
    return SPORT_CONFIGS.get(sport_key, SPORT_CONFIGS["americanfootball_nfl"])
