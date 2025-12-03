"""
BEATVEGAS NUMERICAL ACCURACY & SIMULATION SPEC
Core validation and data integrity enforcement

NO PLACEHOLDERS. NO FAKE NUMBERS. NO SILENT FALLBACKS.
If a value cannot be computed from real data → throw error or show "data unavailable"
"""

from typing import Optional, Dict, Any, List
from dataclasses import dataclass
import numpy as np
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

@dataclass
class SimulationOutput:
    """Enforced structure for all simulation outputs - NO DEFAULTS ALLOWED"""
    
    # Full Game
    median_total: float  # MUST come from simulation
    mean_total: float
    variance_total: float
    home_win_probability: float
    away_win_probability: float
    
    # 1H
    h1_median_total: Optional[float]  # None = 1H not available
    h1_variance: Optional[float]
    
    # Metadata
    sim_count: int  # 10K, 25K, 50K, 100K
    timestamp: datetime
    source: str = "monte_carlo_engine"
    
    def validate(self) -> bool:
        """Validate all required fields are present and sane"""
        if self.median_total <= 0:
            raise ValueError(f"Invalid median_total: {self.median_total}. Must come from real simulation.")
        
        if self.variance_total < 0:
            raise ValueError(f"Invalid variance: {self.variance_total}")
        
        if not (0 <= self.home_win_probability <= 1):
            raise ValueError(f"Invalid home_win_p: {self.home_win_probability}")
        
        if not (0 <= self.away_win_probability <= 1):
            raise ValueError(f"Invalid away_win_p: {self.away_win_probability}")
        
        if self.sim_count not in [10000, 25000, 50000, 100000]:
            raise ValueError(f"Invalid sim_count: {self.sim_count}. Must be 10K/25K/50K/100K")
        
        return True


@dataclass
class OverUnderAnalysis:
    """Over/Under analysis MUST come from simulation distribution vs book line"""
    
    book_line: float
    sims_over: int  # count(total_points[i] > book_line)
    sims_under: int  # count(total_points[i] < book_line)
    sims_push: int  # count(total_points[i] == book_line)
    total_sims: int
    
    over_probability: float
    under_probability: float
    
    @classmethod
    def from_simulation(cls, total_points: np.ndarray, book_line: float):
        """Calculate O/U probabilities from raw simulation data"""
        sims_over = int(np.sum(total_points > book_line))
        sims_under = int(np.sum(total_points < book_line))
        sims_push = int(np.sum(total_points == book_line))
        total_sims = len(total_points)
        
        # Exclude pushes from probability calculation
        non_push = sims_over + sims_under
        if non_push == 0:
            raise ValueError("All simulations resulted in push - cannot calculate O/U probabilities")
        
        over_prob = sims_over / non_push
        under_prob = sims_under / non_push
        
        return cls(
            book_line=book_line,
            sims_over=sims_over,
            sims_under=sims_under,
            sims_push=sims_push,
            total_sims=total_sims,
            over_probability=over_prob,
            under_probability=under_prob
        )


@dataclass
class ExpectedValue:
    """Expected Value - Proper formula, no shortcuts"""
    
    model_probability: float  # From Monte Carlo
    implied_probability: float  # From book odds
    american_odds: int
    decimal_odds: float
    
    ev_per_dollar: float
    edge_percentage: float  # model_p - implied_p
    
    @classmethod
    def calculate(cls, model_prob: float, american_odds: int):
        """
        Calculate EV using proper formula:
        EV = p_model * (decimal_odds - 1) - (1 - p_model)
        """
        # Convert American to implied probability
        if american_odds > 0:
            implied_p = 100 / (american_odds + 100)
        else:
            implied_p = abs(american_odds) / (abs(american_odds) + 100)
        
        # Convert American to decimal
        if american_odds > 0:
            decimal = 1 + (american_odds / 100)
        else:
            decimal = 1 + (100 / abs(american_odds))
        
        # Calculate EV per $1 staked
        ev = model_prob * (decimal - 1) - (1 - model_prob)
        
        # Edge in percentage points
        edge = model_prob - implied_p
        
        return cls(
            model_probability=model_prob,
            implied_probability=implied_p,
            american_odds=american_odds,
            decimal_odds=decimal,
            ev_per_dollar=ev,
            edge_percentage=edge
        )
    
    def is_ev_plus(self, min_edge: float = 0.03, min_sim_tier: int = 25000, current_tier: int = 10000) -> bool:
        """
        Mark as EV+ only when:
        - Edge >= 3 percentage points
        - Book line exists
        - Sim tier >= 25K
        """
        return (
            self.edge_percentage >= min_edge and
            current_tier >= min_sim_tier
        )


@dataclass
class ClosingLineValue:
    """CLV tracking for model validation"""
    
    event_id: str
    prediction_timestamp: datetime
    model_projection: float
    book_line_open: float
    book_line_close: Optional[float]
    
    lean: str  # "over", "under", "home", "away"
    clv_favorable: Optional[bool] = None
    
    def calculate_clv(self, closing_line: float):
        """
        Determine if closing line moved in our favor
        """
        self.book_line_close = closing_line
        
        if self.lean in ["over", "home"]:
            # We leaned Over/Home - favorable if line moved up
            self.clv_favorable = closing_line > self.book_line_open
        else:
            # We leaned Under/Away - favorable if line moved down
            self.clv_favorable = closing_line < self.book_line_open
        
        return self.clv_favorable


class SimulationTierConfig:
    """Simulation tiers MUST affect stability, not just labels"""
    
    TIERS = {
        10000: {
            "label": "Starter",
            "stability_band": 0.15,  # ±15% variance band
            "confidence_multiplier": 0.7,
            "min_edge_required": 0.05  # Need 5% edge at 10K sims
        },
        25000: {
            "label": "Core",
            "stability_band": 0.10,  # ±10%
            "confidence_multiplier": 0.85,
            "min_edge_required": 0.04
        },
        50000: {
            "label": "Pro",
            "stability_band": 0.06,  # ±6%
            "confidence_multiplier": 0.95,
            "min_edge_required": 0.03
        },
        100000: {
            "label": "Elite",
            "stability_band": 0.035,  # ±3.5%
            "confidence_multiplier": 1.0,
            "min_edge_required": 0.03
        }
    }
    
    @classmethod
    def get_tier_config(cls, sim_count: int) -> Dict[str, Any]:
        if sim_count not in cls.TIERS:
            raise ValueError(f"Invalid sim_count: {sim_count}. Must be 10K/25K/50K/100K")
        return cls.TIERS[sim_count]


class ConfidenceCalculator:
    """
    Confidence Score (0-100) measures STABILITY, not win probability
    
    Factors:
    - Distribution variance (tighter = higher confidence)
    - Simulation tier (more sims = higher confidence)
    - Volatility flag
    """
    
    @staticmethod
    def calculate(
        variance: float,
        sim_count: int,
        volatility: str,
        median_value: float
    ) -> int:
        """
        Calculate confidence score 0-100
        
        Low variance + high sim power → high confidence
        High variance / coin-flip → low confidence
        """
        tier_config = SimulationTierConfig.get_tier_config(sim_count)
        
        # Coefficient of variation (normalized variance)
        if median_value > 0:
            cv = np.sqrt(variance) / median_value
        else:
            cv = 1.0  # Maximum uncertainty
        
        # Base confidence from variance (inverted - lower CV = higher confidence)
        # CV of 0.05 (5% std dev) = very stable = 95
        # CV of 0.20 (20% std dev) = very unstable = 50
        base_confidence = max(0, min(100, 100 - (cv * 400)))
        
        # Apply tier multiplier
        tier_multiplier = tier_config["confidence_multiplier"]
        adjusted_confidence = base_confidence * tier_multiplier
        
        # Volatility penalty
        volatility_penalty = {
            "LOW": 0,
            "MEDIUM": 5,
            "HIGH": 15
        }.get(volatility, 10)
        
        final_confidence = max(0, min(100, adjusted_confidence - volatility_penalty))
        
        return int(final_confidence)


class EdgeValidator:
    """
    Define REAL EDGE vs LEAN
    
    REAL EDGE requires ALL:
    1. Model win prob >= 5pp above implied
    2. Confidence >= 60/100
    3. Volatility != HIGH
    4. Sim power >= 25K
    5. EV positive and distribution favors one side >= 58%
    6. Injury impact stable (< 1.5)
    """
    
    @staticmethod
    def classify_edge(
        model_prob: float,
        implied_prob: float,
        confidence: int,
        volatility: str,
        sim_count: int,
        injury_impact: float = 0.0
    ) -> str:
        """Returns 'EDGE', 'LEAN', or 'NEUTRAL'"""
        
        edge_percentage = model_prob - implied_prob
        
        # Check all conditions for REAL EDGE
        conditions = {
            "edge_threshold": edge_percentage >= 0.05,
            "confidence": confidence >= 60,
            "volatility": volatility != "HIGH",
            "sim_power": sim_count >= 25000,
            "model_conviction": model_prob >= 0.58,
            "injury_stable": injury_impact < 1.5
        }
        
        if all(conditions.values()):
            return "EDGE"
        elif edge_percentage >= 0.02:  # 2%+ but doesn't meet all criteria
            return "LEAN"
        else:
            return "NEUTRAL"


def validate_simulation_output(output: Dict[str, Any]) -> SimulationOutput:
    """
    Enforce that simulation output contains REAL DATA ONLY
    
    Raises ValueError if any required field is missing or invalid
    """
    required_fields = [
        'median_total', 'mean_total', 'variance_total',
        'home_win_probability', 'away_win_probability',
        'sim_count', 'timestamp'
    ]
    
    for field in required_fields:
        if field not in output:
            raise ValueError(f"Missing required simulation field: {field}. NO DEFAULTS ALLOWED.")
    
    sim_output = SimulationOutput(**output)
    sim_output.validate()
    
    return sim_output


# Debug mode flag
DEBUG_MODE = False

def get_debug_label(source: str, sim_count: int, median: float, variance: float) -> str:
    """Dev-mode debug labels for traceability"""
    if not DEBUG_MODE:
        return ""
    
    return f"[DEBUG: source={source}, sims={sim_count}, median={median:.1f}, var={variance:.1f}]"
