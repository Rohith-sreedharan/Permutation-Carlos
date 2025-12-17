"""
Pick State Machine - PICK / LEAN / NO PLAY Classification
NON-NEGOTIABLE state transitions for all picks

Truth Mode ONLY allows PICK state into parlays.
LEAN and NO_PLAY are blocked from parlays.

State Rules:
- PICK: Publishable, parlay-eligible, meets ALL thresholds
- LEAN: Publishable as standalone, BLOCKED from parlays
- NO_PLAY: NOT publishable, blocked everywhere

This prevents fake edges and weak picks from entering parlays.
"""

from enum import Enum
from typing import Dict, Any, Optional, Tuple
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


class PickState(str, Enum):
    """Pick classification states"""
    PICK = "PICK"          # ✅ Publishable + Parlay-eligible
    LEAN = "LEAN"          # ⚠️ Publishable, NO parlay
    NO_PLAY = "NO_PLAY"    # ❌ Not publishable


@dataclass
class PickClassification:
    """Result of pick classification"""
    state: PickState
    can_publish: bool
    can_parlay: bool
    confidence_tier: str  # "STRONG", "MODERATE", "WEAK"
    reasons: list[str]
    thresholds_met: Dict[str, bool]


# Sport-specific thresholds for PICK vs LEAN vs NO_PLAY
PICK_THRESHOLDS = {
    "americanfootball_nfl": {
        "PICK": {
            "min_probability": 0.58,
            "min_edge": 3.0,
            "min_confidence": 65,
            "max_variance_z": 1.25,
            "max_market_deviation": 6.0
        },
        "LEAN": {
            "min_probability": 0.55,
            "min_edge": 2.0,
            "min_confidence": 55,
            "max_variance_z": 1.40,
            "max_market_deviation": 8.0
        }
    },
    "americanfootball_ncaaf": {
        "PICK": {
            "min_probability": 0.56,
            "min_edge": 3.5,
            "min_confidence": 60,
            "max_variance_z": 1.30,
            "max_market_deviation": 7.0
        },
        "LEAN": {
            "min_probability": 0.53,
            "min_edge": 2.5,
            "min_confidence": 50,
            "max_variance_z": 1.45,
            "max_market_deviation": 9.0
        }
    },
    "basketball_nba": {
        "PICK": {
            "min_probability": 0.58,
            "min_edge": 4.0,
            "min_confidence": 65,
            "max_variance_z": 1.20,
            "max_market_deviation": 8.0
        },
        "LEAN": {
            "min_probability": 0.55,
            "min_edge": 3.0,
            "min_confidence": 55,
            "max_variance_z": 1.35,
            "max_market_deviation": 10.0
        }
    },
    "basketball_ncaab": {
        "PICK": {
            "min_probability": 0.56,
            "min_edge": 4.5,
            "min_confidence": 60,
            "max_variance_z": 1.25,
            "max_market_deviation": 9.0
        },
        "LEAN": {
            "min_probability": 0.53,
            "min_edge": 3.5,
            "min_confidence": 50,
            "max_variance_z": 1.40,
            "max_market_deviation": 11.0
        }
    },
    "baseball_mlb": {
        "PICK": {
            "min_probability": 0.60,
            "min_edge": 0.5,  # Runs
            "min_confidence": 70,
            "max_variance_z": 1.15,
            "max_market_deviation": 2.0
        },
        "LEAN": {
            "min_probability": 0.57,
            "min_edge": 0.3,
            "min_confidence": 60,
            "max_variance_z": 1.30,
            "max_market_deviation": 2.5
        }
    },
    "icehockey_nhl": {
        "PICK": {
            "min_probability": 0.60,
            "min_edge": 0.4,  # Goals
            "min_confidence": 70,
            "max_variance_z": 1.10,
            "max_market_deviation": 1.5
        },
        "LEAN": {
            "min_probability": 0.57,
            "min_edge": 0.25,
            "min_confidence": 60,
            "max_variance_z": 1.25,
            "max_market_deviation": 2.0
        }
    }
}


class PickStateMachine:
    """
    Classifies picks into PICK / LEAN / NO_PLAY states
    Enforces parlay eligibility rules
    """
    
    @staticmethod
    def classify_pick(
        sport_key: str,
        probability: float,
        edge: float,
        confidence_score: float,
        variance_z: float,
        market_deviation: float,
        calibration_publish: bool,
        data_quality_score: float = 1.0,
        calibration_block_reasons: list[str] = None,
        bootstrap_mode: bool = False
    ) -> PickClassification:
        """
        Classify pick into PICK / LEAN / NO_PLAY
        
        Args:
            sport_key: Sport identifier
            probability: Win probability (0.0 to 1.0)
            edge: Edge in points/runs/goals
            confidence_score: Confidence score (0-100)
            variance_z: Variance z-score
            market_deviation: Absolute deviation from market line
            calibration_publish: Whether calibration engine approved
            data_quality_score: Data quality (0.0 to 1.0)
            calibration_block_reasons: Specific reasons from calibration engine
        
        Returns:
            PickClassification with state and eligibility
        """
        thresholds = PICK_THRESHOLDS.get(sport_key, PICK_THRESHOLDS["americanfootball_nfl"])
        
        reasons = []
        thresholds_met = {}
        
        # Check if blocked by calibration (UNLESS bootstrap mode)
        if not calibration_publish and not bootstrap_mode:
            # Propagate calibration block reasons or use generic message
            block_reasons = calibration_block_reasons if calibration_block_reasons else ["BLOCKED_BY_CALIBRATION"]
            return PickClassification(
                state=PickState.NO_PLAY,
                can_publish=False,
                can_parlay=False,
                confidence_tier="NONE",
                reasons=block_reasons,
                thresholds_met={}
            )
        
        # Check PICK thresholds (highest bar)
        pick_thresholds = thresholds["PICK"]
        meets_pick = True
        
        if probability < pick_thresholds["min_probability"]:
            meets_pick = False
            reasons.append(f"Probability {probability:.1%} < {pick_thresholds['min_probability']:.1%}")
        thresholds_met["probability_pick"] = probability >= pick_thresholds["min_probability"]
        
        if edge < pick_thresholds["min_edge"]:
            meets_pick = False
            reasons.append(f"Edge {edge:.1f} < {pick_thresholds['min_edge']:.1f}")
        thresholds_met["edge_pick"] = edge >= pick_thresholds["min_edge"]
        
        if confidence_score < pick_thresholds["min_confidence"]:
            meets_pick = False
            reasons.append(f"Confidence {confidence_score} < {pick_thresholds['min_confidence']}")
        thresholds_met["confidence_pick"] = confidence_score >= pick_thresholds["min_confidence"]
        
        if variance_z > pick_thresholds["max_variance_z"]:
            meets_pick = False
            reasons.append(f"Variance z={variance_z:.2f} > {pick_thresholds['max_variance_z']:.2f}")
        thresholds_met["variance_pick"] = variance_z <= pick_thresholds["max_variance_z"]
        
        if market_deviation > pick_thresholds["max_market_deviation"]:
            meets_pick = False
            reasons.append(f"Market deviation {market_deviation:.1f} > {pick_thresholds['max_market_deviation']:.1f}")
        thresholds_met["market_deviation_pick"] = market_deviation <= pick_thresholds["max_market_deviation"]
        
        # Check data quality (70% minimum for PICK)
        if data_quality_score < 0.70:
            meets_pick = False
            reasons.append(f"Data quality {data_quality_score:.1%} < 70%")
        thresholds_met["data_quality_pick"] = data_quality_score >= 0.70
        
        # BOOTSTRAP MODE: Force LEAN tier (never PICK until calibration initializes)
        if bootstrap_mode and meets_pick:
            return PickClassification(
                state=PickState.LEAN,
                can_publish=True,
                can_parlay=False,
                confidence_tier="WEAK",
                reasons=[
                    "Meets PICK thresholds",
                    "BOOTSTRAP_MODE: Calibration uninitialized - forcing LEAN tier",
                    "NOT parlay-eligible until calibration data exists"
                ],
                thresholds_met=thresholds_met
            )
        
        # If meets all PICK thresholds → PICK
        if meets_pick:
            confidence_tier = PickStateMachine._get_confidence_tier(
                probability, edge, confidence_score, variance_z
            )
            return PickClassification(
                state=PickState.PICK,
                can_publish=True,
                can_parlay=True,
                confidence_tier=confidence_tier,
                reasons=["Meets all PICK thresholds"],
                thresholds_met=thresholds_met
            )
        
        # Check LEAN thresholds (lower bar)
        lean_thresholds = thresholds["LEAN"]
        meets_lean = True
        
        if probability < lean_thresholds["min_probability"]:
            meets_lean = False
        thresholds_met["probability_lean"] = probability >= lean_thresholds["min_probability"]
        
        if edge < lean_thresholds["min_edge"]:
            meets_lean = False
        thresholds_met["edge_lean"] = edge >= lean_thresholds["min_edge"]
        
        if confidence_score < lean_thresholds["min_confidence"]:
            meets_lean = False
        thresholds_met["confidence_lean"] = confidence_score >= lean_thresholds["min_confidence"]
        
        if variance_z > lean_thresholds["max_variance_z"]:
            meets_lean = False
        thresholds_met["variance_lean"] = variance_z <= lean_thresholds["max_variance_z"]
        
        if market_deviation > lean_thresholds["max_market_deviation"]:
            meets_lean = False
        thresholds_met["market_deviation_lean"] = market_deviation <= lean_thresholds["max_market_deviation"]
        
        # If meets LEAN thresholds → LEAN
        if meets_lean:
            return PickClassification(
                state=PickState.LEAN,
                can_publish=True,
                can_parlay=False,  # BLOCKED from parlays
                confidence_tier="WEAK",
                reasons=reasons + ["Meets LEAN thresholds, NOT parlay-eligible"],
                thresholds_met=thresholds_met
            )
        
        # Otherwise → NO_PLAY
        return PickClassification(
            state=PickState.NO_PLAY,
            can_publish=False,
            can_parlay=False,
            confidence_tier="NONE",
            reasons=reasons + ["Does not meet minimum LEAN thresholds"],
            thresholds_met=thresholds_met
        )
    
    @staticmethod
    def _get_confidence_tier(
        probability: float,
        edge: float,
        confidence_score: float,
        variance_z: float
    ) -> str:
        """Determine confidence tier for PICK state"""
        # STRONG: High probability, good edge, low variance
        if probability >= 0.63 and edge >= 4.0 and confidence_score >= 75 and variance_z <= 1.0:
            return "STRONG"
        
        # MODERATE: Good thresholds
        elif probability >= 0.60 and edge >= 3.0 and confidence_score >= 65 and variance_z <= 1.15:
            return "MODERATE"
        
        # WEAK: Meets minimums
        else:
            return "WEAK"
    
    @staticmethod
    def enforce_parlay_eligibility(picks: list[PickClassification]) -> Tuple[bool, list[str]]:
        """
        Enforce Truth Mode parlay rules
        
        Args:
            picks: List of pick classifications
        
        Returns:
            (is_eligible, rejection_reasons)
        """
        rejection_reasons = []
        
        # Check each pick state
        for i, pick in enumerate(picks):
            if pick.state != PickState.PICK:
                rejection_reasons.append(
                    f"Pick #{i+1} is {pick.state.value}, not PICK (parlay requires all PICK)"
                )
            
            if not pick.can_parlay:
                rejection_reasons.append(
                    f"Pick #{i+1} is not parlay-eligible"
                )
        
        # All picks must be PICK state
        if rejection_reasons:
            logger.warning(f"⚠️ Parlay blocked: {len(rejection_reasons)} reasons")
            return False, rejection_reasons
        
        logger.info(f"✅ Parlay eligible: All {len(picks)} picks are PICK state")
        return True, []
