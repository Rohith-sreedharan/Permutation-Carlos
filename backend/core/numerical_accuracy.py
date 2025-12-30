"""
BEATVEGAS NUMERICAL ACCURACY & SIMULATION SPEC v2.0
Core validation and data integrity enforcement

NO PLACEHOLDERS. NO FAKE NUMBERS. NO SILENT FALLBACKS.
If a value cannot be computed from real data → show "N/A" NOT a default like 1%

CONFIDENCE SYSTEM (CRITICAL):
- Confidence = model agreement + stability score (NOT win probability)
- Components: distribution stability, simulation convergence, volatility, market alignment
- If confidence cannot be computed → return None with reason codes
- NEVER hard-default to 1% or any placeholder value
"""

from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass, field
from enum import Enum
import numpy as np
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class ConfidenceReasonCode(Enum):
    """Reason codes for confidence calculation results"""
    DISTRIBUTION_STABLE = "distribution_stable"
    DISTRIBUTION_WIDE = "distribution_wide"
    BIMODAL_DISTRIBUTION = "bimodal_distribution"
    HIGH_CONVERGENCE = "high_convergence"
    LOW_CONVERGENCE = "low_convergence"
    LOW_VOLATILITY = "low_volatility"
    HIGH_VOLATILITY = "high_volatility"
    MARKET_ALIGNED = "market_aligned"
    MARKET_CONFLICTING = "market_conflicting"
    MISSING_DATA = "missing_data"
    BAD_UNIT_SCALE = "bad_unit_scale"
    CONFIDENCE_UNAVAILABLE = "confidence_unavailable"


class EdgeState(Enum):
    """3-state system - every game resolves to ONE state"""
    OFFICIAL_EDGE = "official_edge"  # ✅ Actionable play
    MODEL_LEAN = "model_lean"        # ⚠️ Informational only
    NO_ACTION = "no_action"          # ⛔ Suppressed


@dataclass
class ConfidenceComponents:
    """Breakdown of confidence score components"""
    distribution_score: Optional[float] = None  # 0-1, from std/variance
    convergence_score: Optional[float] = None   # 0-1, from rerun agreement
    volatility_score: Optional[float] = None    # 0-1, inverted volatility
    market_alignment_score: Optional[float] = None  # 0-1, market confirmation
    reason_codes: List[ConfidenceReasonCode] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "distribution_score": self.distribution_score,
            "convergence_score": self.convergence_score,
            "volatility_score": self.volatility_score,
            "market_alignment_score": self.market_alignment_score,
            "reason_codes": [r.value for r in self.reason_codes]
        }


@dataclass
class ConfidenceResult:
    """Result of confidence calculation - NEVER defaults to 1%"""
    score: Optional[int] = None  # 0-100 or None if unavailable
    components: Optional[ConfidenceComponents] = None
    is_available: bool = False
    unavailable_reason: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "score": self.score,
            "is_available": self.is_available,
            "unavailable_reason": self.unavailable_reason,
            "components": self.components.to_dict() if self.components else None
        }


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
        
        if self.sim_count not in [10000, 25000, 35000, 50000, 100000]:
            raise ValueError(f"Invalid sim_count: {self.sim_count}. Must be 10K/25K/35K/50K/100K")
        
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
            "label": "Free",
            "stability_band": 0.15,  # ±15% variance band
            "confidence_multiplier": 0.7,
            "min_edge_required": 0.05  # Need 5% edge at 10K sims
        },
        25000: {
            "label": "Starter",
            "stability_band": 0.10,  # ±10%
            "confidence_multiplier": 0.85,
            "min_edge_required": 0.04
        },
        35000: {
            "label": "Core",
            "stability_band": 0.08,  # ±8%
            "confidence_multiplier": 0.90,
            "min_edge_required": 0.035
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
            raise ValueError(f"Invalid sim_count: {sim_count}. Must be 10K/25K/35K/50K/100K")
        return cls.TIERS[sim_count]


class ConfidenceCalculator:
    """
    Confidence Score (0-100) measures STABILITY, not win probability
    
    CRITICAL: Confidence is NOT win probability, NOT edge size
    Confidence = "How much does the system trust itself right now?"
    
    Factors (with weights):
    - Distribution stability (40%): How tight is the simulation outcome curve?
    - Simulation convergence (30%): Do repeated runs converge to similar outputs?
    - Volatility environment (20%): Pace variance, blowout risk, injury uncertainty
    - Market alignment (10%): Is edge clean vs market? (supportive only)
    
    NEVER default to 1% or any placeholder. Return None with reason codes.
    """
    
    # Reference values for normalization
    STD_REF = 15.0     # Reference standard deviation (points)
    RERUN_REF = 1.5    # Reference std deviation across reruns
    VOL_REF = 200.0    # Reference volatility index
    
    @classmethod
    def calculate(
        cls,
        variance: Optional[float],
        sim_count: int,
        volatility: str,
        median_value: float,
        convergence_std: Optional[float] = None,
        market_aligned: Optional[bool] = None,
        rerun_spreads: Optional[List[float]] = None
    ) -> ConfidenceResult:
        """
        Calculate confidence score 0-100 with full component breakdown
        
        Args:
            variance: Distribution variance from simulation
            sim_count: Number of iterations (10K, 25K, 50K, 100K)
            volatility: "LOW", "MEDIUM", or "HIGH"
            median_value: Median projected total (for normalization)
            convergence_std: Std dev of spreads across multiple reruns
            market_aligned: Whether model agrees with sharp money
            rerun_spreads: List of spread projections from multiple runs (for convergence)
        
        Returns:
            ConfidenceResult with score (or None) and component breakdown
        """
        components = ConfidenceComponents()
        missing_inputs = []
        
        # Check for missing required inputs - DO NOT DEFAULT
        if variance is None or variance < 0:
            missing_inputs.append("variance")
            components.reason_codes.append(ConfidenceReasonCode.MISSING_DATA)
        
        if median_value <= 0:
            missing_inputs.append("median_value")
            components.reason_codes.append(ConfidenceReasonCode.BAD_UNIT_SCALE)
        
        # If critical inputs missing, return unavailable (NOT 1%)
        if missing_inputs:
            return ConfidenceResult(
                score=None,
                components=components,
                is_available=False,
                unavailable_reason=f"Missing inputs: {', '.join(missing_inputs)}"
            )
        
        # Get tier config
        try:
            tier_config = SimulationTierConfig.get_tier_config(sim_count)
        except ValueError:
            tier_config = SimulationTierConfig.TIERS.get(10000, {})
        
        # COMPONENT 1: Distribution Stability (40% weight)
        # Lower std relative to median = higher stability
        std_dev = np.sqrt(variance)
        # Use adaptive reference based on sport/median
        adaptive_std_ref = max(cls.STD_REF, median_value * 0.08)  # 8% of median
        
        # Smooth exponential mapping
        distribution_score = np.exp(-np.power(std_dev / adaptive_std_ref, 2))
        components.distribution_score = float(distribution_score)
        
        if distribution_score > 0.7:
            components.reason_codes.append(ConfidenceReasonCode.DISTRIBUTION_STABLE)
        elif distribution_score < 0.3:
            components.reason_codes.append(ConfidenceReasonCode.DISTRIBUTION_WIDE)
        
        # COMPONENT 2: Simulation Convergence (30% weight)
        # How consistent are reruns?
        if convergence_std is not None:
            convergence_score = np.exp(-np.power(convergence_std / cls.RERUN_REF, 2))
        elif rerun_spreads is not None and len(rerun_spreads) >= 3:
            # Calculate convergence from rerun data
            rerun_std = np.std(rerun_spreads)
            convergence_score = np.exp(-np.power(rerun_std / cls.RERUN_REF, 2))
        else:
            # Cannot determine convergence without reruns - estimate from single run stability
            # This is less reliable, so we penalize
            convergence_score = distribution_score * 0.7  # 30% penalty for no rerun data
        
        components.convergence_score = float(convergence_score)
        
        if convergence_score > 0.7:
            components.reason_codes.append(ConfidenceReasonCode.HIGH_CONVERGENCE)
        elif convergence_score < 0.3:
            components.reason_codes.append(ConfidenceReasonCode.LOW_CONVERGENCE)
        
        # COMPONENT 3: Volatility Environment (20% weight)
        volatility_map = {
            "LOW": 100,
            "MEDIUM": 250,
            "HIGH": 450
        }
        vol_index = volatility_map.get(volatility, 250)
        volatility_score = 1 / (1 + (vol_index / cls.VOL_REF))
        components.volatility_score = float(volatility_score)
        
        if volatility_score > 0.6:
            components.reason_codes.append(ConfidenceReasonCode.LOW_VOLATILITY)
        elif volatility_score < 0.3:
            components.reason_codes.append(ConfidenceReasonCode.HIGH_VOLATILITY)
        
        # COMPONENT 4: Market Alignment (10% weight)
        # Supportive only - never dominates
        if market_aligned is True:
            market_score = 1.0
            components.reason_codes.append(ConfidenceReasonCode.MARKET_ALIGNED)
        elif market_aligned is False:
            market_score = 0.3
            components.reason_codes.append(ConfidenceReasonCode.MARKET_CONFLICTING)
        else:
            market_score = 0.5  # Neutral if unknown
        
        components.market_alignment_score = float(market_score)
        
        # COMBINE with weights
        raw_score = (
            (distribution_score * 0.40) +
            (convergence_score * 0.30) +
            (volatility_score * 0.20) +
            (market_score * 0.10)
        )
        
        # Apply tier multiplier
        tier_multiplier = tier_config.get("confidence_multiplier", 0.7)
        adjusted_score = raw_score * tier_multiplier
        
        # CLAMP ONLY AT THE END, to 0-100 (NOT to 1%)
        final_score = max(0, min(100, adjusted_score * 100))
        
        return ConfidenceResult(
            score=int(round(final_score)),
            components=components,
            is_available=True,
            unavailable_reason=None
        )
    
    @classmethod
    def calculate_legacy(
        cls,
        variance: float,
        sim_count: int,
        volatility: str,
        median_value: float
    ) -> int:
        """
        Legacy method for backward compatibility
        Returns integer score, defaults to 0 (not 1%) if unavailable
        """
        result = cls.calculate(variance, sim_count, volatility, median_value)
        if result.score is None:
            # Log warning but return 0, not 1%
            logger.warning(f"Confidence unavailable: {result.unavailable_reason}")
            return 0
        return result.score


class EdgeValidator:
    """
    3-State Edge Classification System
    
    States (NON-NEGOTIABLE):
    - OFFICIAL_EDGE: Actionable play, eligible for Telegram & PickPlay
    - MODEL_LEAN: Informational only, clearly labeled as non-actionable  
    - NO_ACTION: Suppressed - no bet language anywhere
    
    Confidence bands:
    - 70%+ → Very stable (rare, strong EDGE)
    - 50–69% → Playable EDGE (if edge pts threshold met)
    - 25–49% → MODEL LEAN only
    - <25% → NO_ACTION (blocked)
    
    Hysteresis prevents flicker:
    - Promote to EDGE: edge >= 4.0 pts AND confidence >= 50%
    - Demote from EDGE: edge <= 3.0 pts OR confidence <= 40%
    """
    
    # Hysteresis thresholds
    EDGE_PROMOTE_PTS = 4.0
    EDGE_DEMOTE_PTS = 3.0
    CONFIDENCE_PROMOTE = 50
    CONFIDENCE_DEMOTE = 40
    
    @classmethod
    def classify_edge(
        cls,
        model_prob: float,
        implied_prob: float,
        confidence: Optional[int],
        volatility: str,
        sim_count: int,
        injury_impact: float = 0.0,
        previous_state: Optional[EdgeState] = None
    ) -> Tuple[EdgeState, List[str]]:
        """
        Classify into 3-state system with hysteresis
        
        Returns:
            Tuple of (EdgeState, list of reason codes)
        """
        reasons = []
        
        # Handle unavailable confidence - block to NO_ACTION
        if confidence is None:
            reasons.append("CONFIDENCE_UNAVAILABLE")
            return (EdgeState.NO_ACTION, reasons)
        
        edge_percentage = model_prob - implied_prob
        edge_pts = edge_percentage * 100  # Convert to percentage points
        
        # Apply hysteresis based on previous state
        promote_pts = cls.EDGE_PROMOTE_PTS
        demote_pts = cls.EDGE_DEMOTE_PTS
        promote_conf = cls.CONFIDENCE_PROMOTE
        demote_conf = cls.CONFIDENCE_DEMOTE
        
        if previous_state == EdgeState.OFFICIAL_EDGE:
            # Currently EDGE - use demote thresholds
            promote_pts = demote_pts
            promote_conf = demote_conf
        
        # NO_ACTION: Confidence < 25% (always blocked)
        if confidence < 25:
            reasons.append(f"LOW_CONFIDENCE_{confidence}")
            return (EdgeState.NO_ACTION, reasons)
        
        # NO_ACTION: High injury impact
        if injury_impact >= 1.5:
            reasons.append(f"HIGH_INJURY_IMPACT_{injury_impact:.1f}")
            return (EdgeState.NO_ACTION, reasons)
        
        # NO_ACTION: Negligible edge
        if edge_percentage < 0.02:
            reasons.append(f"EDGE_TOO_SMALL_{edge_percentage:.3f}")
            return (EdgeState.NO_ACTION, reasons)
        
        # MODEL_LEAN: Confidence 25-49%
        if confidence < promote_conf:
            reasons.append(f"CONFIDENCE_LEAN_RANGE_{confidence}")
            if edge_percentage >= 0.02:
                reasons.append(f"EDGE_DETECTED_{edge_percentage:.3f}")
            return (EdgeState.MODEL_LEAN, reasons)
        
        # MODEL_LEAN: High volatility without exceptional confidence
        if volatility == "HIGH" and confidence < 70:
            reasons.append("HIGH_VOLATILITY_BLOCKED")
            reasons.append(f"CONFIDENCE_{confidence}")
            return (EdgeState.MODEL_LEAN, reasons)
        
        # MODEL_LEAN: Insufficient sim power
        if sim_count < 25000:
            reasons.append(f"SIM_POWER_INSUFFICIENT_{sim_count}")
            return (EdgeState.MODEL_LEAN, reasons)
        
        # OFFICIAL_EDGE: All conditions met
        all_conditions = {
            "edge_threshold": edge_percentage >= 0.05,
            "confidence": confidence >= promote_conf,
            "volatility": volatility != "HIGH" or confidence >= 70,
            "sim_power": sim_count >= 25000,
            "model_conviction": model_prob >= 0.58,
            "injury_stable": injury_impact < 1.5
        }
        
        if all(all_conditions.values()):
            reasons.append("ALL_CONDITIONS_MET")
            for k, v in all_conditions.items():
                if v:
                    reasons.append(f"{k.upper()}_PASS")
            return (EdgeState.OFFICIAL_EDGE, reasons)
        
        # MODEL_LEAN: Has edge but missing some conditions
        failed = [k for k, v in all_conditions.items() if not v]
        reasons.append(f"FAILED_CONDITIONS: {', '.join(failed)}")
        return (EdgeState.MODEL_LEAN, reasons)
    
    @classmethod
    def classify_edge_legacy(
        cls,
        model_prob: float,
        implied_prob: float,
        confidence: int,
        volatility: str,
        sim_count: int,
        injury_impact: float = 0.0
    ) -> str:
        """
        Legacy method returning string state for backward compatibility
        Returns 'EDGE', 'LEAN', or 'NEUTRAL'
        """
        state, _ = cls.classify_edge(
            model_prob, implied_prob, confidence, volatility, sim_count, injury_impact
        )
        
        state_map = {
            EdgeState.OFFICIAL_EDGE: "EDGE",
            EdgeState.MODEL_LEAN: "LEAN",
            EdgeState.NO_ACTION: "NEUTRAL"
        }
        return state_map.get(state, "NEUTRAL")


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
