"""
PARLAY ELIGIBILITY SYSTEM — DECOUPLED FROM SINGLE-PICK THRESHOLDS
==================================================================

🚨 CRITICAL FIX: Parlay eligibility MUST use separate thresholds from single-pick publishing.

The Problem:
------------
Previously, parlay eligibility reused single-pick LEAN thresholds (58% prob, 4.0 edge, 65 confidence).
This caused:
- Eligible simulations being blocked from parlays
- Empty parlay pools despite valid simulations
- False negatives ("Pick blocked by state machine")

The Solution:
-------------
Three SEPARATE threshold tiers:

1. SINGLE-PICK THRESHOLDS (for Telegram / Daily Pick):
   - Probability ≥ 58%
   - Edge ≥ 4.0 pts
   - Confidence ≥ 65
   
2. PARLAY POOL THRESHOLDS (INTERNAL for leg eligibility):
   - Probability ≥ 53%
   - Edge ≥ 1.5 pts
   - Confidence ≥ 50
   - Risk Score ≤ 0.55
   
3. PARLAY ASSEMBLY (selection from pool):
   - Uses correlation + diversification logic
   - NOT single-pick publish rules

🔒 LOCKED: Do NOT merge these thresholds back together.
"""

from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class EligibilityContext(str, Enum):
    """Where the pick will be used"""
    SINGLE_PICK_TELEGRAM = "SINGLE_PICK_TELEGRAM"  # Telegram / public posting
    SINGLE_PICK_DAILY = "SINGLE_PICK_DAILY"         # Daily best pick
    PARLAY_POOL = "PARLAY_POOL"                     # Internal parlay pool
    PARLAY_ASSEMBLY = "PARLAY_ASSEMBLY"             # Final parlay output


# =============================================================================
# LOCKED THRESHOLDS — DO NOT MODIFY WITHOUT APPROVAL
# =============================================================================

@dataclass(frozen=True)
class SinglePickThresholds:
    """
    Strict thresholds for Telegram / Daily Pick posting
    These are the HARDEST to pass
    """
    probability_min: float = 0.58   # 58%
    edge_min: float = 4.0           # 4+ points
    confidence_min: int = 65        # 65+
    variance_z_max: float = 1.25    # Max variance z-score
    risk_score_max: float = 0.40    # Max 40% risk


@dataclass(frozen=True)
class ParlayPoolThresholds:
    """
    LOOSER thresholds for parlay leg eligibility
    
    🚨 These MUST be lower than single-pick thresholds
    🚨 A pick can be in parlay pool WITHOUT being publishable as single
    """
    probability_min: float = 0.53   # 53% (lower than 58%)
    edge_min: float = 1.5           # 1.5 pts (lower than 4.0)
    confidence_min: int = 50        # 50 (lower than 65)
    variance_z_max: float = 1.50    # More variance allowed
    risk_score_max: float = 0.55    # 55% risk allowed


@dataclass(frozen=True)
class ParlayAssemblyThresholds:
    """
    Thresholds for final parlay assembly
    These control diversification, not individual leg quality
    """
    max_same_sport_legs: int = 2        # Max legs from same sport
    max_same_game_legs: int = 1         # Usually 1 (no SGP)
    min_leg_count: int = 3              # Minimum legs
    max_leg_count: int = 8              # Maximum legs
    max_correlation: float = 0.35       # Max correlation between legs
    min_diversification_score: float = 0.60  # Min diversification


# Global instances (frozen, immutable)
SINGLE_PICK_THRESHOLDS = SinglePickThresholds()
PARLAY_POOL_THRESHOLDS = ParlayPoolThresholds()
PARLAY_ASSEMBLY_THRESHOLDS = ParlayAssemblyThresholds()


# =============================================================================
# ELIGIBILITY CHECK RESULTS
# =============================================================================

@dataclass
class EligibilityResult:
    """Result of eligibility check"""
    is_eligible: bool
    context: EligibilityContext
    passed_checks: List[str]
    failed_checks: List[str]
    thresholds_used: Dict[str, float]
    actual_values: Dict[str, float]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "is_eligible": self.is_eligible,
            "context": self.context.value,
            "passed_checks": self.passed_checks,
            "failed_checks": self.failed_checks,
            "thresholds_used": self.thresholds_used,
            "actual_values": self.actual_values
        }


# =============================================================================
# ELIGIBILITY CHECKERS
# =============================================================================

def check_single_pick_eligibility(
    probability: float,
    edge: float,
    confidence: int,
    variance_z: float = 0.0,
    risk_score: float = 0.0
) -> EligibilityResult:
    """
    Check if pick is eligible for single-pick publishing (Telegram/Daily)
    Uses STRICT thresholds
    """
    thresholds = SINGLE_PICK_THRESHOLDS
    passed = []
    failed = []
    
    # Probability check
    if probability >= thresholds.probability_min:
        passed.append(f"probability >= {thresholds.probability_min:.0%}")
    else:
        failed.append(f"probability {probability:.1%} < {thresholds.probability_min:.0%}")
    
    # Edge check
    if edge >= thresholds.edge_min:
        passed.append(f"edge >= {thresholds.edge_min}")
    else:
        failed.append(f"edge {edge:.1f} < {thresholds.edge_min}")
    
    # Confidence check
    if confidence >= thresholds.confidence_min:
        passed.append(f"confidence >= {thresholds.confidence_min}")
    else:
        failed.append(f"confidence {confidence} < {thresholds.confidence_min}")
    
    # Variance check (if provided)
    if variance_z <= thresholds.variance_z_max:
        passed.append(f"variance_z <= {thresholds.variance_z_max}")
    else:
        failed.append(f"variance_z {variance_z:.2f} > {thresholds.variance_z_max}")
    
    # Risk check (if provided)
    if risk_score <= thresholds.risk_score_max:
        passed.append(f"risk_score <= {thresholds.risk_score_max}")
    else:
        failed.append(f"risk_score {risk_score:.2f} > {thresholds.risk_score_max}")
    
    return EligibilityResult(
        is_eligible=len(failed) == 0,
        context=EligibilityContext.SINGLE_PICK_TELEGRAM,
        passed_checks=passed,
        failed_checks=failed,
        thresholds_used={
            "probability_min": thresholds.probability_min,
            "edge_min": thresholds.edge_min,
            "confidence_min": thresholds.confidence_min,
            "variance_z_max": thresholds.variance_z_max,
            "risk_score_max": thresholds.risk_score_max
        },
        actual_values={
            "probability": probability,
            "edge": edge,
            "confidence": confidence,
            "variance_z": variance_z,
            "risk_score": risk_score
        }
    )


def check_parlay_pool_eligibility(
    probability: float,
    edge: float,
    confidence: int,
    variance_z: float = 0.0,
    risk_score: float = 0.0
) -> EligibilityResult:
    """
    Check if pick is eligible for PARLAY POOL (internal)
    Uses LOOSER thresholds than single-pick
    
    🚨 CRITICAL: A pick can be parlay-eligible WITHOUT being single-pick eligible
    """
    thresholds = PARLAY_POOL_THRESHOLDS
    passed = []
    failed = []
    
    # Probability check (LOOSER: 53% vs 58%)
    if probability >= thresholds.probability_min:
        passed.append(f"probability >= {thresholds.probability_min:.0%}")
    else:
        failed.append(f"probability {probability:.1%} < {thresholds.probability_min:.0%}")
    
    # Edge check (LOOSER: 1.5 vs 4.0)
    if edge >= thresholds.edge_min:
        passed.append(f"edge >= {thresholds.edge_min}")
    else:
        failed.append(f"edge {edge:.1f} < {thresholds.edge_min}")
    
    # Confidence check (LOOSER: 50 vs 65)
    if confidence >= thresholds.confidence_min:
        passed.append(f"confidence >= {thresholds.confidence_min}")
    else:
        failed.append(f"confidence {confidence} < {thresholds.confidence_min}")
    
    # Variance check (more lenient)
    if variance_z <= thresholds.variance_z_max:
        passed.append(f"variance_z <= {thresholds.variance_z_max}")
    else:
        failed.append(f"variance_z {variance_z:.2f} > {thresholds.variance_z_max}")
    
    # Risk check (more lenient)
    if risk_score <= thresholds.risk_score_max:
        passed.append(f"risk_score <= {thresholds.risk_score_max}")
    else:
        failed.append(f"risk_score {risk_score:.2f} > {thresholds.risk_score_max}")
    
    return EligibilityResult(
        is_eligible=len(failed) == 0,
        context=EligibilityContext.PARLAY_POOL,
        passed_checks=passed,
        failed_checks=failed,
        thresholds_used={
            "probability_min": thresholds.probability_min,
            "edge_min": thresholds.edge_min,
            "confidence_min": thresholds.confidence_min,
            "variance_z_max": thresholds.variance_z_max,
            "risk_score_max": thresholds.risk_score_max
        },
        actual_values={
            "probability": probability,
            "edge": edge,
            "confidence": confidence,
            "variance_z": variance_z,
            "risk_score": risk_score
        }
    )


def check_pick_eligibility(
    probability: float,
    edge: float,
    confidence: int,
    variance_z: float = 0.0,
    risk_score: float = 0.0
) -> Dict[str, EligibilityResult]:
    """
    Check eligibility for ALL contexts
    Returns dict with results for each context
    """
    return {
        "single_pick": check_single_pick_eligibility(
            probability, edge, confidence, variance_z, risk_score
        ),
        "parlay_pool": check_parlay_pool_eligibility(
            probability, edge, confidence, variance_z, risk_score
        )
    }


# =============================================================================
# PARLAY POOL BUILDER
# =============================================================================

@dataclass
class ParlayPoolCandidate:
    """A candidate in the parlay pool"""
    game_id: str
    sport: str
    selection: str
    line: float
    probability: float
    edge: float
    confidence: int
    variance_z: float
    risk_score: float
    market_type: str
    single_pick_eligible: bool
    parlay_pool_eligible: bool
    eligibility_details: Dict[str, Any] = field(default_factory=dict)


def build_parlay_pool(
    candidates: List[Dict[str, Any]]
) -> Tuple[List[ParlayPoolCandidate], List[Dict[str, Any]]]:
    """
    Build parlay pool from candidates
    
    🚨 CRITICAL: Uses PARLAY_POOL_THRESHOLDS, not single-pick thresholds
    
    Returns:
        (accepted_candidates, rejected_candidates_with_reasons)
    """
    accepted = []
    rejected = []
    
    for candidate in candidates:
        # Extract metrics
        probability = candidate.get("probability", 0) or candidate.get("win_probability", 0) or 0
        edge = candidate.get("edge", 0) or candidate.get("edge_points", 0) or 0
        confidence = candidate.get("confidence", 0) or candidate.get("confidence_score", 0) or 0
        variance_z = candidate.get("variance_z", 0) or 0
        risk_score = candidate.get("risk_score", 0) or 0
        
        # Check eligibility for BOTH contexts
        eligibility = check_pick_eligibility(
            probability=probability,
            edge=edge,
            confidence=int(confidence),
            variance_z=variance_z,
            risk_score=risk_score
        )
        
        parlay_eligible = eligibility["parlay_pool"].is_eligible
        single_eligible = eligibility["single_pick"].is_eligible
        
        pool_candidate = ParlayPoolCandidate(
            game_id=candidate.get("game_id", ""),
            sport=candidate.get("sport", ""),
            selection=candidate.get("selection", ""),
            line=candidate.get("line", 0),
            probability=probability,
            edge=edge,
            confidence=int(confidence),
            variance_z=variance_z,
            risk_score=risk_score,
            market_type=candidate.get("market_type", "GAME_TOTAL"),
            single_pick_eligible=single_eligible,
            parlay_pool_eligible=parlay_eligible,
            eligibility_details={
                "single_pick": eligibility["single_pick"].to_dict(),
                "parlay_pool": eligibility["parlay_pool"].to_dict()
            }
        )
        
        if parlay_eligible:
            accepted.append(pool_candidate)
            logger.debug(
                f"✅ Parlay pool ACCEPTED: {pool_candidate.selection} "
                f"(prob={probability:.1%}, edge={edge:.1f}, conf={confidence})"
            )
        else:
            rejected.append({
                "candidate": candidate,
                "rejection_reasons": eligibility["parlay_pool"].failed_checks,
                "single_pick_eligible": single_eligible
            })
            logger.debug(
                f"❌ Parlay pool REJECTED: {candidate.get('selection', 'unknown')} "
                f"- {eligibility['parlay_pool'].failed_checks}"
            )
    
    logger.info(
        f"🎯 Parlay pool built: {len(accepted)} accepted, {len(rejected)} rejected "
        f"(using PARLAY thresholds: prob≥{PARLAY_POOL_THRESHOLDS.probability_min:.0%}, "
        f"edge≥{PARLAY_POOL_THRESHOLDS.edge_min}, conf≥{PARLAY_POOL_THRESHOLDS.confidence_min})"
    )
    
    return accepted, rejected


# =============================================================================
# LOGGING HELPERS
# =============================================================================

def log_threshold_comparison():
    """Log threshold comparison for debugging"""
    logger.info("=" * 60)
    logger.info("PARLAY ELIGIBILITY THRESHOLDS (DECOUPLED)")
    logger.info("=" * 60)
    logger.info(f"SINGLE-PICK (Telegram/Daily):")
    logger.info(f"  - Probability: ≥ {SINGLE_PICK_THRESHOLDS.probability_min:.0%}")
    logger.info(f"  - Edge: ≥ {SINGLE_PICK_THRESHOLDS.edge_min} pts")
    logger.info(f"  - Confidence: ≥ {SINGLE_PICK_THRESHOLDS.confidence_min}")
    logger.info(f"  - Variance Z: ≤ {SINGLE_PICK_THRESHOLDS.variance_z_max}")
    logger.info(f"  - Risk Score: ≤ {SINGLE_PICK_THRESHOLDS.risk_score_max}")
    logger.info("")
    logger.info(f"PARLAY POOL (Internal leg eligibility):")
    logger.info(f"  - Probability: ≥ {PARLAY_POOL_THRESHOLDS.probability_min:.0%}")
    logger.info(f"  - Edge: ≥ {PARLAY_POOL_THRESHOLDS.edge_min} pts")
    logger.info(f"  - Confidence: ≥ {PARLAY_POOL_THRESHOLDS.confidence_min}")
    logger.info(f"  - Variance Z: ≤ {PARLAY_POOL_THRESHOLDS.variance_z_max}")
    logger.info(f"  - Risk Score: ≤ {PARLAY_POOL_THRESHOLDS.risk_score_max}")
    logger.info("=" * 60)


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    'EligibilityContext',
    'SinglePickThresholds',
    'ParlayPoolThresholds',
    'ParlayAssemblyThresholds',
    'SINGLE_PICK_THRESHOLDS',
    'PARLAY_POOL_THRESHOLDS',
    'PARLAY_ASSEMBLY_THRESHOLDS',
    'EligibilityResult',
    'ParlayPoolCandidate',
    'check_single_pick_eligibility',
    'check_parlay_pool_eligibility',
    'check_pick_eligibility',
    'build_parlay_pool',
    'log_threshold_comparison',
]
