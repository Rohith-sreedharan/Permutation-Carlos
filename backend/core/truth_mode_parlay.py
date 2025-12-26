"""
Truth Mode Parlay — Dual Mode System

CRITICAL DISTINCTION:
- TRUTH_MODE_STRICT: Singles shown on dashboard (existing gates, no changes)
- TRUTH_MODE_PARLAY: Parlay bundles (optimized scoring with penalties, not hard blocks)

The parlay mode does not "lie." It changes the claim:
- Strict: "Each leg is a high-confidence standalone bet"
- Parlay: "This parlay is the best risk bundle available given slate constraints"
"""

from enum import Enum
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass


class TruthMode(Enum):
    """Truth Mode types"""
    STRICT = "strict"  # Singles, dashboard picks, performance tracking
    PARLAY = "parlay"  # Parlay bundles, risk-adjusted optimization


class RiskProfile(Enum):
    """Parlay risk profiles"""
    HIGH_CONFIDENCE = "high_confidence"  # 3-6 legs, PICK-only default, no high-vol
    BALANCED = "balanced"              # PICK+LEAN, 1 high-vol allowed
    HIGH_VOLATILITY = "high_volatility"  # Moonshot, max risk tolerance


class MarketType(Enum):
    """Market types for parlay construction"""
    GAME_SPREAD = "game_spread"
    GAME_TOTAL = "game_total"
    GAME_ML = "game_ml"
    PLAYER_PROP = "player_prop"


class PropRiskBand(Enum):
    """Prop-specific risk classification"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


@dataclass
class ParlayWeight:
    """Parlay leg weight calculation breakdown"""
    base_score: float
    edge_score: float
    vol_penalty: float
    stability_penalty: float
    lean_penalty: float
    data_penalty: float
    market_type_penalty: float
    minutes_penalty: float  # Props only
    final_weight: float
    reason_codes: List[str]


@dataclass
class PropIntegrityCheck:
    """Prop-specific integrity validation"""
    player_status_pass: bool
    minutes_certainty: str  # HIGH/MED/LOW
    role_stability: str     # HIGH/MED/LOW
    injury_risk: str        # HIGH/MED/LOW
    blowout_risk: str       # HIGH/MED/LOW
    line_fresh: bool
    prop_risk_band: PropRiskBand
    fail_codes: List[str]


@dataclass
class ParlayLegCandidate:
    """Enhanced leg candidate with parlay-specific metadata"""
    claim_id: str
    event_id: str
    market_type: MarketType
    
    # Strict mode fields (existing)
    strict_state: str  # PICK/LEAN/NO_PLAY
    can_parlay: bool
    win_probability: float
    edge_points: float
    confidence_score: float
    volatility_band: str  # LOW/MED/HIGH
    distribution_stable: bool
    data_confidence: str  # HIGH/MED/LOW
    
    # Parlay mode fields (new)
    parlay_eligible: bool
    parlay_weight: float
    parlay_risk_band: str  # LOW/MED/HIGH
    parlay_reason_codes: List[str]
    
    # Prop-specific (if applicable)
    prop_integrity: Optional[PropIntegrityCheck] = None


def calculate_parlay_weight(
    candidate: Dict[str, Any],
    mode: TruthMode = TruthMode.PARLAY,
    include_props_penalty: bool = True
) -> ParlayWeight:
    """
    Calculate parlay weight using penalty-based optimization
    
    CRITICAL: This replaces hard blocking with scored penalties.
    Higher weight = better parlay candidate.
    
    Args:
        candidate: Leg data with strict_state, win_prob, volatility, etc.
        mode: STRICT (hard gates) or PARLAY (penalty optimization)
        include_props_penalty: Apply market_type_penalty for props
    
    Returns:
        ParlayWeight with breakdown and reason codes
    """
    reason_codes = []
    
    # 1. BASE SCORE (win probability edge over 50%)
    win_prob = candidate.get('win_probability', 0.5)
    base_score = (win_prob - 0.50) * 100
    
    # 2. EDGE SCORE (optional, from edge_points or EV)
    edge_raw = candidate.get('edge_points', 0.0)
    EDGE_NORM = 10.0  # Normalize edge to reasonable scale
    edge_score = max(-2.0, min(2.0, edge_raw / EDGE_NORM))
    
    # 3. VOLATILITY PENALTY
    volatility_band = candidate.get('volatility_band', 'MED').upper()
    if volatility_band == 'LOW':
        vol_penalty = 0.0
    elif volatility_band == 'MED':
        vol_penalty = 0.35
        reason_codes.append('MEDIUM_VOLATILITY')
    else:  # HIGH
        vol_penalty = 0.75
        reason_codes.append('HIGH_VOLATILITY')
    
    # 4. STABILITY PENALTY
    distribution_stable = candidate.get('distribution_stable', True)
    if distribution_stable:
        stability_penalty = 0.0
    else:
        stability_penalty = 0.60
        reason_codes.append('UNSTABLE_DISTRIBUTION')
    
    # 5. LEAN PENALTY (PICK vs LEAN)
    strict_state = candidate.get('strict_state', 'NO_PLAY')
    if strict_state == 'PICK':
        lean_penalty = 0.0
    elif strict_state == 'LEAN':
        lean_penalty = 0.40
        reason_codes.append('LEAN_STATE')
    else:  # NO_PLAY
        lean_penalty = 999.0  # Effectively blocks
        reason_codes.append('NO_PLAY_BLOCKED')
    
    # 6. DATA CONFIDENCE PENALTY
    data_confidence = candidate.get('data_confidence', 'MED').upper()
    if data_confidence == 'HIGH':
        data_penalty = 0.0
    elif data_confidence == 'MED':
        data_penalty = 0.30
        reason_codes.append('MEDIUM_DATA_CONF')
    else:  # LOW
        data_penalty = 0.70
        reason_codes.append('LOW_DATA_CONF')
    
    # 7. MARKET TYPE PENALTY (props penalized vs game lines)
    market_type = candidate.get('market_type', 'GAME_TOTAL')
    if include_props_penalty:
        if market_type in ['GAME_TOTAL', 'GAME_ML']:
            market_type_penalty = 0.0
        elif market_type == 'GAME_SPREAD':
            market_type_penalty = 0.15
            reason_codes.append('SPREAD_MARKET')
        elif market_type == 'PLAYER_PROP':
            market_type_penalty = 0.45
            reason_codes.append('PROP_MARKET')
        else:
            market_type_penalty = 0.0
    else:
        market_type_penalty = 0.0
    
    # 8. MINUTES PENALTY (props only)
    minutes_certainty = candidate.get('minutes_certainty', 'HIGH').upper()
    if market_type == 'PLAYER_PROP':
        if minutes_certainty == 'HIGH':
            minutes_penalty = 0.0
        elif minutes_certainty == 'MED':
            minutes_penalty = 0.35
            reason_codes.append('MEDIUM_MINUTES_CERTAINTY')
        else:  # LOW
            minutes_penalty = 0.75
            reason_codes.append('LOW_MINUTES_CERTAINTY')
    else:
        minutes_penalty = 0.0
    
    # FINAL WEIGHT
    final_weight = (
        base_score +
        edge_score -
        vol_penalty -
        stability_penalty -
        lean_penalty -
        data_penalty -
        market_type_penalty -
        minutes_penalty
    )
    
    return ParlayWeight(
        base_score=base_score,
        edge_score=edge_score,
        vol_penalty=vol_penalty,
        stability_penalty=stability_penalty,
        lean_penalty=lean_penalty,
        data_penalty=data_penalty,
        market_type_penalty=market_type_penalty,
        minutes_penalty=minutes_penalty,
        final_weight=final_weight,
        reason_codes=reason_codes
    )


def validate_prop_integrity(prop_data: Dict[str, Any]) -> PropIntegrityCheck:
    """
    Prop Integrity Gate — props-specific validation
    
    Checks:
    - Player status not questionable/out
    - Expected minutes >= min threshold
    - Market line exists and not stale
    - Role stability
    
    Returns:
        PropIntegrityCheck with pass/fail and risk band
    """
    fail_codes = []
    
    # 1. Player status check
    player_status = prop_data.get('player_status', 'ACTIVE').upper()
    player_status_pass = player_status in ['ACTIVE', 'PROBABLE']
    if not player_status_pass:
        fail_codes.append('PROP_PLAYER_STATUS_RISK')
    
    # 2. Minutes certainty
    expected_minutes = prop_data.get('expected_minutes', 0)
    min_minutes_threshold = prop_data.get('min_minutes_threshold', 20)
    
    if expected_minutes >= min_minutes_threshold + 10:
        minutes_certainty = 'HIGH'
    elif expected_minutes >= min_minutes_threshold:
        minutes_certainty = 'MED'
    else:
        minutes_certainty = 'LOW'
        fail_codes.append('PROP_MINUTES_TOO_LOW')
    
    # 3. Role stability
    role_changes_recent = prop_data.get('role_changes_recent', 0)
    if role_changes_recent == 0:
        role_stability = 'HIGH'
    elif role_changes_recent <= 1:
        role_stability = 'MED'
    else:
        role_stability = 'LOW'
        fail_codes.append('PROP_ROLE_UNCERTAIN')
    
    # 4. Injury risk
    injury_report_mentions = prop_data.get('injury_mentions', 0)
    if injury_report_mentions == 0:
        injury_risk = 'LOW'
    elif injury_report_mentions == 1:
        injury_risk = 'MED'
    else:
        injury_risk = 'HIGH'
    
    # 5. Blowout risk (game spread impact on prop)
    game_spread = abs(prop_data.get('game_spread', 0))
    if game_spread <= 7:
        blowout_risk = 'LOW'
    elif game_spread <= 12:
        blowout_risk = 'MED'
    else:
        blowout_risk = 'HIGH'
    
    # 6. Line freshness
    line_age_hours = prop_data.get('line_age_hours', 0)
    line_fresh = line_age_hours <= 4
    if not line_fresh:
        fail_codes.append('PROP_LINE_STALE')
    
    # Determine overall prop risk band
    high_risk_factors = sum([
        minutes_certainty == 'LOW',
        role_stability == 'LOW',
        injury_risk == 'HIGH',
        blowout_risk == 'HIGH',
        not line_fresh
    ])
    
    if high_risk_factors == 0:
        prop_risk_band = PropRiskBand.LOW
    elif high_risk_factors <= 2:
        prop_risk_band = PropRiskBand.MEDIUM
    else:
        prop_risk_band = PropRiskBand.HIGH
    
    return PropIntegrityCheck(
        player_status_pass=player_status_pass,
        minutes_certainty=minutes_certainty,
        role_stability=role_stability,
        injury_risk=injury_risk,
        blowout_risk=blowout_risk,
        line_fresh=line_fresh,
        prop_risk_band=prop_risk_band,
        fail_codes=fail_codes
    )


class RiskProfileConstraints:
    """Risk profile constraint definitions"""
    
    HIGH_CONFIDENCE = {
        'leg_count_range': (3, 6),
        'allow_lean': False,  # Can be toggled by user
        'max_high_vol_legs': 0,
        'max_unstable_legs': 0,
        'min_win_prob': 0.56,
        'min_parlay_weight': 3.0,
        'max_prop_legs': 2  # Limit props in high-confidence
    }
    
    BALANCED = {
        'leg_count_range': (3, 6),
        'allow_lean': True,
        'max_high_vol_legs': 1,
        'max_unstable_legs': 1,
        'min_win_prob': 0.53,
        'min_parlay_weight': 1.5,
        'max_prop_legs': 3
    }
    
    HIGH_VOLATILITY = {
        'leg_count_range': (3, 8),
        'allow_lean': True,
        'max_high_vol_legs': 99,  # Essentially unlimited
        'max_unstable_legs': 99,
        'min_win_prob': 0.50,
        'min_parlay_weight': 0.5,
        'max_prop_legs': 99  # Allow heavy prop usage
    }
    
    @classmethod
    def get_constraints(cls, profile: RiskProfile) -> Dict[str, Any]:
        """Get constraints for a risk profile"""
        if profile == RiskProfile.HIGH_CONFIDENCE:
            return cls.HIGH_CONFIDENCE.copy()
        elif profile == RiskProfile.BALANCED:
            return cls.BALANCED.copy()
        elif profile == RiskProfile.HIGH_VOLATILITY:
            return cls.HIGH_VOLATILITY.copy()
        else:
            return cls.BALANCED.copy()


MIN_PARLAY_WEIGHT = 0.5  # Global minimum threshold
