"""Phase 1 Engine Lock canonical enums and mapping rules.

This module is intentionally runtime-safe and additive. It codifies locked
contracts from the governance spec so existing code can migrate to these
definitions incrementally without changing behavior elsewhere.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional, Tuple


class League(str, Enum):
    NBA = "NBA"
    NFL = "NFL"
    NHL = "NHL"
    NCAAB = "NCAAB"
    NCAAF = "NCAAF"
    MLB = "MLB"


class MarketType(str, Enum):
    SPREAD = "SPREAD"
    TOTAL = "TOTAL"
    MONEYLINE_2WAY = "MONEYLINE_2WAY"
    MONEYLINE_3WAY = "MONEYLINE_3WAY"


class Classification(str, Enum):
    NO_ACTION = "NO_ACTION"
    LEAN = "LEAN"
    EDGE = "EDGE"


class ReleaseStatus(str, Enum):
    OFFICIAL = "OFFICIAL"
    INFO_ONLY = "INFO_ONLY"
    BLOCKED_BY_RISK = "BLOCKED_BY_RISK"
    BLOCKED_BY_INTEGRITY = "BLOCKED_BY_INTEGRITY"
    BLOCKED_MISSING_CONTEXT = "BLOCKED_MISSING_CONTEXT"


class RecommendedAction(str, Enum):
    TAKE_THIS = "TAKE_THIS"
    TAKE_OPPOSITE = "TAKE_OPPOSITE"
    NO_PLAY = "NO_PLAY"


class RecommendedReasonCode(str, Enum):
    EDGE_THRESHOLD_MET = "EDGE_THRESHOLD_MET"
    LEAN_THRESHOLD_MET = "LEAN_THRESHOLD_MET"
    NO_ACTION_NO_SIGNAL = "NO_ACTION_NO_SIGNAL"
    NO_ACTION_SIGNAL_BLOCKED = "NO_ACTION_SIGNAL_BLOCKED"
    BLOCKED_BY_RISK = "BLOCKED_BY_RISK"
    BLOCKED_BY_INTEGRITY = "BLOCKED_BY_INTEGRITY"
    BLOCKED_MISSING_CONTEXT = "BLOCKED_MISSING_CONTEXT"


@dataclass(frozen=True)
class DecisionContext:
    league: str
    event_id: str
    market_type: str
    odds_snapshot_id: str
    sim_result_id: str
    caller_surface: str


def classify_context_validity(ctx: DecisionContext) -> Tuple[bool, Optional[ReleaseStatus]]:
    """Fail fast on missing or out-of-contract context.

    Returns:
        (is_valid, blocked_release_status)
    """
    if not ctx.event_id or not ctx.odds_snapshot_id or not ctx.sim_result_id:
        return False, ReleaseStatus.BLOCKED_MISSING_CONTEXT

    try:
        League(ctx.league)
        MarketType(ctx.market_type)
    except ValueError:
        return False, ReleaseStatus.BLOCKED_MISSING_CONTEXT

    return True, None


def classification_for_release(release_status: ReleaseStatus, classification: Optional[Classification]) -> Optional[Classification]:
    """Enforce classification nullability law.

    BLOCKED_* -> classification must be null.
    OFFICIAL/INFO_ONLY -> classification must be non-null.
    """
    if release_status in {
        ReleaseStatus.BLOCKED_BY_RISK,
        ReleaseStatus.BLOCKED_BY_INTEGRITY,
        ReleaseStatus.BLOCKED_MISSING_CONTEXT,
    }:
        return None

    return classification


def derive_recommended_action(
    release_status: ReleaseStatus,
    classification: Optional[Classification],
    validator_directional_action: Optional[RecommendedAction],
) -> RecommendedAction:
    """Apply closed recommended_action mapping.

    - BLOCKED_* -> NO_PLAY
    - INFO_ONLY -> NO_PLAY
    - OFFICIAL + NO_ACTION -> NO_PLAY
    - OFFICIAL + (EDGE|LEAN) -> TAKE_THIS or TAKE_OPPOSITE (if provided)
    """
    if release_status != ReleaseStatus.OFFICIAL:
        return RecommendedAction.NO_PLAY

    if classification == Classification.NO_ACTION or classification is None:
        return RecommendedAction.NO_PLAY

    if validator_directional_action in {RecommendedAction.TAKE_THIS, RecommendedAction.TAKE_OPPOSITE}:
        return validator_directional_action

    # Fail-closed for malformed directional result.
    return RecommendedAction.NO_PLAY


def derive_reason_code(
    release_status: ReleaseStatus,
    classification: Optional[Classification],
    signal_detected: bool,
) -> RecommendedReasonCode:
    """Apply the closed reason-code matrix."""
    if release_status == ReleaseStatus.BLOCKED_BY_RISK:
        return RecommendedReasonCode.BLOCKED_BY_RISK
    if release_status == ReleaseStatus.BLOCKED_BY_INTEGRITY:
        return RecommendedReasonCode.BLOCKED_BY_INTEGRITY
    if release_status == ReleaseStatus.BLOCKED_MISSING_CONTEXT:
        return RecommendedReasonCode.BLOCKED_MISSING_CONTEXT

    if classification == Classification.EDGE:
        return RecommendedReasonCode.EDGE_THRESHOLD_MET
    if classification == Classification.LEAN:
        return RecommendedReasonCode.LEAN_THRESHOLD_MET

    if classification == Classification.NO_ACTION:
        return (
            RecommendedReasonCode.NO_ACTION_SIGNAL_BLOCKED
            if signal_detected
            else RecommendedReasonCode.NO_ACTION_NO_SIGNAL
        )

    # Fail-closed fallback for malformed upstream states.
    return RecommendedReasonCode.BLOCKED_MISSING_CONTEXT
