"""
BeatVegas Engine Configuration
Defines simulation tiers, garbage-time parameters, and calibration settings

Per Engine Upgrade Spec:
- Public engine: Always 100K simulations
- Internal engine: 1M-2M simulations for calibration
- Sport-specific garbage-time modules
"""

from typing import Dict, Any
from dataclasses import dataclass


# PUBLIC ENGINE CONFIGURATION (NON-NEGOTIABLE)
PUBLIC_SIMULATION_COUNT = 100000  # Never fallback below this
INTERNAL_SIMULATION_COUNT = 1000000  # For calibration only

# Minimum viable simulation count (error if can't achieve)
MINIMUM_SIMULATION_COUNT = 100000

# Old tier system deprecated for public-facing
# Now only used internally for subscription display
LEGACY_TIER_DISPLAY = {
    10000: "Starter",
    25000: "Core", 
    50000: "Pro",
    100000: "Elite"
}


@dataclass
class GarbageTimeConfig:
    """
    NBA Late-Game Volatility Module Configuration
    
    Purpose: Prevent Unders from being blown up by Q4 chaos pace spikes
    Applies to: basketball_nba only
    """
    enabled: bool = True
    sport_key: str = "basketball_nba"
    
    # Detection thresholds
    lead_threshold_points: int = 10  # Minimum lead for garbage time
    time_threshold_seconds: int = 180  # Last 3:00 of Q4
    quarter: int = 4  # Only Q4
    
    # Mode probabilities
    prob_slow_mode: float = 0.70  # 70% of blowouts slow down
    prob_chaos_mode: float = 0.30  # 30% turn chaotic
    
    # Slow Mode multipliers (most common - preserves Unders)
    slow_possession_leading: float = 1.10  # +10% slower possessions
    slow_possession_trailing: float = 1.05  # +5% slower
    slow_offensive_eff_leading: float = 0.95  # -5% efficiency
    slow_offensive_eff_trailing: float = 0.95  # -5% efficiency
    
    # Chaos Mode multipliers (rare - blows up totals)
    chaos_possession_leading: float = 0.90  # -10% faster possessions
    chaos_possession_trailing: float = 0.85  # -15% faster
    chaos_offensive_eff_leading: float = 1.05  # +5% efficiency
    chaos_offensive_eff_trailing: float = 1.08  # +8% efficiency
    chaos_three_point_rate_boost: float = 0.15  # +15% 3P rate
    chaos_turnover_rate_boost: float = 0.05  # +5% TO rate
    
    # Confidence/volatility penalties
    confidence_penalty_per_garbage_share: float = 20.0  # e.g., 40% share → -8 points
    volatility_boost_multiplier: float = 1.5  # Multiply volatility by garbage share


# Sport-specific garbage-time configurations
GARBAGE_TIME_CONFIGS: Dict[str, GarbageTimeConfig] = {
    "basketball_nba": GarbageTimeConfig(
        enabled=True,
        sport_key="basketball_nba"
    ),
    "basketball_ncaab": GarbageTimeConfig(
        enabled=True,
        sport_key="basketball_ncaab",
        lead_threshold_points=12,  # College needs bigger lead
        prob_slow_mode=0.75,  # College slows down more
        prob_chaos_mode=0.25
    ),
    # Other sports don't have garbage time module
    "americanfootball_nfl": GarbageTimeConfig(enabled=False),
    "baseball_mlb": GarbageTimeConfig(enabled=False),
    "icehockey_nhl": GarbageTimeConfig(enabled=False)
}


class EdgeCriteria:
    """
    Strict Edge Logic - ALL conditions must be met
    
    Per spec: A real edge must satisfy ALL requirements
    If ANY fail → classify as LEAN, not EDGE
    """
    
    # Edge thresholds (non-negotiable)
    MIN_EDGE_PERCENTAGE = 0.05  # Model win prob must be ≥5% above implied
    MIN_CONFIDENCE = 60  # Confidence score must be ≥60/100
    DISALLOWED_VOLATILITY = "HIGH"  # Cannot be HIGH volatility
    REQUIRED_SIM_COUNT = 100000  # Public engine only (100K)
    MIN_DISTRIBUTION_SKEW = 0.58  # Distribution must favor one side ≥58%
    MAX_INJURY_IMPACT = 1.5  # Injury impact must be <1.5
    
    @classmethod
    def validate_edge(
        cls,
        model_prob: float,
        implied_prob: float,
        confidence: int,
        volatility: str,
        sim_count: int,
        distribution_skew: float,
        injury_impact: float
    ) -> Dict[str, Any]:
        """
        Validate if prediction qualifies as EDGE
        
        Returns:
            {
                'is_edge': bool,
                'classification': 'EDGE' | 'LEAN' | 'NEUTRAL',
                'conditions_met': {...},
                'failures': [...]
            }
        """
        edge_percentage = model_prob - implied_prob
        
        conditions = {
            'edge_threshold': edge_percentage >= cls.MIN_EDGE_PERCENTAGE,
            'confidence': confidence >= cls.MIN_CONFIDENCE,
            'volatility': volatility != cls.DISALLOWED_VOLATILITY,
            'sim_power': sim_count >= cls.REQUIRED_SIM_COUNT,
            'ev_positive': edge_percentage > 0,
            'distribution_skew': distribution_skew >= cls.MIN_DISTRIBUTION_SKEW,
            'injury_stable': injury_impact < cls.MAX_INJURY_IMPACT
        }
        
        failures = [k for k, v in conditions.items() if not v]
        all_met = len(failures) == 0
        
        # Classification
        if all_met:
            classification = 'EDGE'
        elif edge_percentage >= 0.02:  # 2%+ but missing conditions
            classification = 'LEAN'
        else:
            classification = 'NEUTRAL'
        
        return {
            'is_edge': all_met,
            'classification': classification,
            'conditions_met': conditions,
            'failures': failures,
            'edge_percentage': edge_percentage
        }


class FeedbackLoopConfig:
    """
    Automatic Recalibration Configuration
    
    Every wrong projection triggers recalibration of:
    1. Tempo weighting
    2. Scoring volatility parameters
    3. Early-game inflation factors
    4. Bench/rotation patterns
    5. Variance envelopes
    6. Regression curves
    7. Distribution skew
    """
    
    # Recalibration parameters
    LEARNING_RATE = 0.05  # How much to adjust per wrong call
    MIN_SAMPLES_FOR_RECALIBRATION = 10  # Need at least 10 games
    
    # What triggers recalibration
    RECALIBRATION_TRIGGERS = [
        'total_wrong',
        'spread_wrong',
        'h1_wrong',
        'side_wrong'
    ]
    
    # What gets updated
    RECALIBRATION_MODULES = [
        'tempo_weighting',
        'scoring_volatility',
        'early_game_inflation',
        'rotation_patterns',
        'variance_envelopes',
        'regression_curves',
        'distribution_skew',
        'injury_impact_scaling'
    ]


class ValidationRules:
    """
    Zero-Placeholder Enforcement
    
    Per spec: Every displayed number MUST come from real simulation output
    NO hardcoded fallbacks, NO synthetic numbers, NO estimates
    """
    
    @staticmethod
    def validate_simulation_output(output: Dict[str, Any]) -> None:
        """
        Validate simulation output has all required fields
        
        Raises ValueError if any required field is missing or invalid
        """
        required_fields = [
            'median_total',
            'mean_total', 
            'variance_total',
            'home_win_probability',
            'away_win_probability',
            'sim_count',
            'timestamp'
        ]
        
        for field in required_fields:
            if field not in output:
                raise ValueError(
                    f"CRITICAL: Missing required field '{field}'. "
                    f"NO PLACEHOLDERS ALLOWED. Hide this metric from UI."
                )
            
            if output[field] is None:
                raise ValueError(
                    f"CRITICAL: Field '{field}' is None. "
                    f"Cannot display synthetic values. Show error state."
                )
        
        # Validate sim count
        if output['sim_count'] < MINIMUM_SIMULATION_COUNT:
            raise ValueError(
                f"CRITICAL: Simulation count {output['sim_count']} is below "
                f"minimum {MINIMUM_SIMULATION_COUNT}. DO NOT FALLBACK. "
                f"Show error and retry with full 100K simulations."
            )
        
        # Validate probabilities
        home_p = output['home_win_probability']
        away_p = output['away_win_probability']
        
        if not (0 <= home_p <= 1) or not (0 <= away_p <= 1):
            raise ValueError(
                f"Invalid win probabilities: home={home_p}, away={away_p}. "
                f"Must be between 0 and 1."
            )
        
        prob_sum = home_p + away_p
        if abs(prob_sum - 1.0) > 0.01:
            raise ValueError(
                f"Win probabilities don't sum to 1.0: {prob_sum:.4f}. "
                f"Simulation integrity violation."
            )
    
    @staticmethod
    def enforce_no_fallback(value: Any, field_name: str) -> Any:
        """
        Enforce that value is not a placeholder
        
        Raises ValueError if value appears to be a placeholder/fallback
        """
        if value is None:
            raise ValueError(
                f"Field '{field_name}' is None. Show 'data unavailable' - "
                f"do NOT use placeholder."
            )
        
        # Check for common placeholder patterns
        if isinstance(value, (int, float)):
            # Common placeholder totals
            if field_name in ['median_total', 'projected_total']:
                suspicious_values = [45.5, 50.0, 225.0, 230.0, 0.0]
                if value in suspicious_values:
                    raise ValueError(
                        f"Field '{field_name}' has suspicious placeholder value {value}. "
                        f"Verify this comes from real simulation."
                    )
            
            # Probabilities
            if field_name.endswith('_probability'):
                if value == 0.5:  # Coin flip is suspicious
                    raise ValueError(
                        f"Field '{field_name}' is exactly 0.5. "
                        f"Verify this is from simulation, not a placeholder."
                    )
        
        return value


# Export configuration
def get_garbage_time_config(sport_key: str) -> GarbageTimeConfig:
    """Get garbage-time config for sport, or disabled config if not applicable"""
    return GARBAGE_TIME_CONFIGS.get(
        sport_key,
        GarbageTimeConfig(enabled=False, sport_key=sport_key)
    )


# Engine mode flags
ENGINE_MODE_PUBLIC = "public"  # 100K simulations, shown to users
ENGINE_MODE_INTERNAL = "internal"  # 1M+ simulations, calibration only
ENGINE_MODE_DEVELOPMENT = "development"  # Variable simulations for testing
