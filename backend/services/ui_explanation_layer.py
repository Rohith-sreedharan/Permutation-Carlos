"""
BeatVegas UI Explanation Layer v1.0.2
Status: LOCKED FOR IMPLEMENTATION
Package: 2.5 – Decision Explanation & Transparency

CANONICAL IMPLEMENTATION - ZERO INTERPRETATION ALLOWED

Implements 6 explanation boxes:
1. Key Drivers (simulation inputs - descriptive only)
2. Edge Context Notes (threshold gaps & constraints - conditional display)
3. Edge Summary (classification verdict - always shown)
4. CLV Forecast / Market Drift Forecast (line movement - always shown)
5. Why This Edge Exists (global edge detection - always shown)
6. Final Unified Summary (master verdict - always shown)

CRITICAL RULES (ADDENDUM v1.0.2):
- Verdict source of truth: EDGE > LEAN > NO_ACTION across 3 markets
- Verdict derived ONLY from market classifications, NOT from best_pick
- Missing best_pick MUST NOT downgrade verdict
- Edge Context Notes shows when classification != EDGE OR execution_constraints exist
- GlobalState computed ONLY across 3 markets (SPREAD, TOTAL, MONEYLINE) within SAME GAME
"""

from enum import Enum
from typing import Dict, List, Optional, Literal
from dataclasses import dataclass


# ==================== CANONICAL ENUMS ====================

class Classification(str, Enum):
    """Internal classification enum - CANONICAL."""
    NO_ACTION = "NO_ACTION"
    LEAN = "LEAN"
    EDGE = "EDGE"


class NoActionSubtype(str, Enum):
    """NO_ACTION subtypes for explanation clarity."""
    NO_SIGNAL = "NO_ACTION_NO_SIGNAL"
    SIGNAL_BLOCKED = "NO_ACTION_SIGNAL_BLOCKED"


class GlobalState(str, Enum):
    """Global state across all markets within SAME GAME CARD."""
    EDGE_AVAILABLE = "EDGE_AVAILABLE"
    LEANS_ONLY = "LEANS_ONLY"
    NO_PLAY = "NO_PLAY"


class ExecutionConstraint(str, Enum):
    """Execution constraints that may block EDGE."""
    HIGH_VOLATILITY = "HIGH_VOLATILITY"
    BOOTSTRAP_CALIBRATION = "BOOTSTRAP_CALIBRATION"
    DISPUTED_LINE = "DISPUTED_LINE"
    STALE_ODDS = "STALE_ODDS"
    REVIEW_WINDOW = "REVIEW_WINDOW"


# Display Labels (UI Only)
DISPLAY_LABELS = {
    Classification.NO_ACTION: "NO ACTION",
    Classification.LEAN: "LEAN",
    Classification.EDGE: "EDGE"
}

# Thresholds (from vFinal spec)
EDGE_THRESHOLD = 3.0  # 3.0% EV
LEAN_THRESHOLD = 0.5  # 0.5% EV


# ==================== GLOBAL STATE COMPUTATION ====================

def compute_global_state(
    spread_classification: Classification,
    total_classification: Classification,
    ml_classification: Classification
) -> GlobalState:
    """
    Compute global state from market classifications.
    
    LOCKED RULES:
    - If any market is EDGE → EDGE_AVAILABLE
    - Else if any market is LEAN → LEANS_ONLY
    - Else → NO_PLAY
    
    GlobalState is computed ONLY across the three markets (SPREAD, TOTAL, MONEYLINE)
    within the SAME GAME CARD. NOT across slate, NOT influenced by other games.
    """
    classifications = [spread_classification, total_classification, ml_classification]
    
    if Classification.EDGE in classifications:
        return GlobalState.EDGE_AVAILABLE
    elif Classification.LEAN in classifications:
        return GlobalState.LEANS_ONLY
    else:
        return GlobalState.NO_PLAY


# ==================== BOX 1: KEY DRIVERS ====================

def render_key_drivers(simulation_data: dict) -> dict:
    """
    Render Key Drivers box.
    
    PURPOSE: Explain simulation inputs, NOT betting decisions
    TRUTH: "What the model sees" ≠ "What to bet"
    CONSTRAINT: Descriptive only, zero prescriptive language
    
    Always displays. Content explains simulation inputs only.
    """
    drivers = []
    
    # Pace differential
    pace_delta = simulation_data.get('pace_delta', 0)
    if abs(pace_delta) > 2.0:
        direction = "faster" if pace_delta > 0 else "slower"
        drivers.append(
            f"Pace differential: {direction} by {abs(pace_delta):.1f} possessions"
        )
    
    # Injury impact (if already priced in)
    if simulation_data.get('injury_adjusted'):
        drivers.append("Injury impact: Incorporated into baseline projections")
    
    # Matchup asymmetry
    matchup_factor = simulation_data.get('matchup_factor')
    if matchup_factor:
        drivers.append(f"Matchup variance: {matchup_factor}")
    
    # Simulation depth
    total_sims = simulation_data.get('total_sims', 0)
    if total_sims > 0:
        drivers.append(f"Simulation depth: {total_sims:,} Monte Carlo iterations")
    
    return {
        'title': 'Key Drivers',
        'items': drivers,
        'disclaimer': 'Model inputs shown for transparency. Does not imply actionability.'
    }


# ==================== BOX 2: EDGE CONTEXT NOTES ====================

def render_edge_context(
    classification: Classification,
    ev: float,
    volatility_state: str,
    calibration_state: str,
    max_ev: float,
    execution_constraints: List[ExecutionConstraint]
) -> Optional[dict]:
    """
    Render Edge Context Notes.
    
    DISPLAY RULES (ADDENDUM v1.0.2 - CRITICAL):
    - Shows when classification != EDGE
    - Shows when classification == EDGE AND execution_constraints is non-empty
    - Hidden when classification == EDGE AND no execution_constraints
    
    PURPOSE: Explain why thresholds blocked execution OR what constraints apply to EDGE
    """
    # Hide for clean EDGE
    if classification == Classification.EDGE and not execution_constraints:
        return None
    
    notes = []
    
    # EV threshold context (for NO_ACTION and LEAN)
    if classification == Classification.NO_ACTION:
        if max_ev <= 0.0:
            notes.append("No positive EV detected")
        elif max_ev < LEAN_THRESHOLD:
            notes.append(
                f"EV insufficient: {max_ev:.1f}% below minimum threshold ({LEAN_THRESHOLD}%)"
            )
    elif classification == Classification.LEAN:
        notes.append(
            f"EV marginal: {max_ev:.1f}% below institutional threshold ({EDGE_THRESHOLD}%)"
        )
    
    # Execution constraints (can apply to any classification)
    for constraint in execution_constraints:
        if constraint == ExecutionConstraint.HIGH_VOLATILITY:
            notes.append("Volatility elevated: Requires higher edge threshold for execution")
        elif constraint == ExecutionConstraint.BOOTSTRAP_CALIBRATION:
            notes.append("Calibration incomplete: Model in validation period")
        elif constraint == ExecutionConstraint.DISPUTED_LINE:
            notes.append("Line consensus disputed: Execution criteria not met")
        elif constraint == ExecutionConstraint.STALE_ODDS:
            notes.append("Odds stale: Line may have moved, refresh required")
        elif constraint == ExecutionConstraint.REVIEW_WINDOW:
            notes.append("Manual review required: Edge magnitude triggers verification protocol")
    
    # If EDGE with constraints, add clarification (LOCKED RULE)
    if classification == Classification.EDGE and execution_constraints:
        notes.insert(0, "Edge detected but execution constraints active")
    
    return {
        'title': 'Edge Context Notes',
        'notes': notes,
        'state': {
            'volatility': volatility_state,
            'calibration': calibration_state,
            'constraints': [c.value for c in execution_constraints]
        }
    }


# ==================== BOX 3: EDGE SUMMARY ====================

def render_edge_summary(
    classification: Classification,
    max_ev: float,
    sharp_side: Optional[str],
    market_type: str,
    execution_constraints: List[ExecutionConstraint]
) -> dict:
    """
    Render Edge Summary box.
    
    PURPOSE: State final classification
    TRUTH: Binary outcome (NO_ACTION | LEAN | EDGE)
    CONSTRAINT: Must explain threshold position
    
    Always displays. States classification and reasoning.
    """
    # Generate summary text based on classification
    if classification == Classification.NO_ACTION:
        text = _generate_no_action_summary(max_ev)
        color = 'gray'
    elif classification == Classification.LEAN:
        text = _generate_lean_summary(max_ev, sharp_side, market_type)
        color = 'yellow'
    else:  # EDGE
        text = _generate_edge_summary(max_ev, sharp_side, market_type, execution_constraints)
        color = 'green'
    
    return {
        'classification': classification.value,
        'badge_label': DISPLAY_LABELS[classification],
        'color': color,
        'text': text
    }


def _generate_no_action_summary(max_ev: float) -> str:
    """Generate NO_ACTION summary (CANONICAL COPY)"""
    if max_ev <= 0.0:
        return "No positive EV detected. Expected value does not favor any side."
    elif max_ev < LEAN_THRESHOLD:
        return f"Signal magnitude ({max_ev:.1f}%) insufficient to meet minimum execution criteria."
    else:
        return "Execution blocked by risk controls."


def _generate_lean_summary(max_ev: float, sharp_side: Optional[str], market_type: str) -> str:
    """Generate LEAN summary (CANONICAL COPY)"""
    side_display = format_side_display(sharp_side, market_type)
    return (
        f"Directional bias toward {side_display} detected ({max_ev:.1f}% EV). "
        f"Below institutional threshold ({EDGE_THRESHOLD}%). Not recommended for execution."
    )


def _generate_edge_summary(
    max_ev: float,
    sharp_side: Optional[str],
    market_type: str,
    execution_constraints: List[ExecutionConstraint]
) -> str:
    """
    Generate EDGE summary (CANONICAL COPY)
    
    ADDENDUM v1.0.2 RULE:
    - IF classification == EDGE AND execution_constraints == []:
      "All risk controls passed."
    - IF classification == EDGE AND execution_constraints != []:
      "Edge detected. Execution constraints active."
      FORBIDDEN: "All risk controls passed" or any implication of clean execution
    """
    side_display = format_side_display(sharp_side, market_type)
    
    if execution_constraints:
        # EDGE with constraints
        return (
            f"Statistically significant edge detected: {side_display} at {max_ev:.1f}% EV. "
            f"Edge detected. Execution constraints active."
        )
    else:
        # Clean EDGE
        return (
            f"Statistically significant edge detected: {side_display} at {max_ev:.1f}% EV. "
            f"All risk controls passed."
        )


# ==================== BOX 4: CLV FORECAST (MARKET DRIFT FORECAST) ====================

def render_clv_forecast(
    classification: Classification,
    current_line: float,
    opening_line: float,
    projected_close_line: Optional[float],
    sharp_side: Optional[str],
    market_type: str
) -> dict:
    """
    Render CLV Forecast (Market Drift Forecast) box.
    
    PURPOSE: Market movement expectation, not profit forecast
    TRUTH: "Where the line is going" ≠ "How much you'll win"
    CONSTRAINT: Qualitative only unless projected close line exists
    
    Always displays. Framing changes based on classification.
    
    NOTE: This box shows expected market movement direction, not CLV calculation.
    True CLV requires bet line vs closing line, which doesn't exist yet.
    """
    # Calculate line drift (opening to current)
    line_drift = current_line - opening_line
    
    # Determine movement direction relative to sharp side
    movement_direction = None
    if sharp_side:
        moving_toward = (
            (sharp_side == 'home' and line_drift < 0) or
            (sharp_side == 'away' and line_drift > 0) or
            (sharp_side == 'over' and line_drift > 0) or
            (sharp_side == 'under' and line_drift < 0)
        )
        movement_direction = 'toward' if moving_toward else 'away from'
    
    # Magnitude classification (qualitative)
    abs_drift = abs(line_drift)
    if abs_drift < 0.5:
        magnitude = 'minimal'
    elif abs_drift < 1.0:
        magnitude = 'minor'
    elif abs_drift < 2.0:
        magnitude = 'moderate'
    else:
        magnitude = 'significant'
    
    # Generate forecast text
    if projected_close_line is not None:
        expected_movement = projected_close_line - current_line
        forecast_text = _generate_clv_with_projection(
            classification, magnitude, movement_direction,
            sharp_side, market_type, expected_movement
        )
    else:
        forecast_text = _generate_clv_qualitative(
            classification, magnitude, movement_direction,
            sharp_side, market_type
        )
    
    return {
        'title': 'CLV Forecast',
        'forecast': forecast_text,
        'line_drift': line_drift,
        'magnitude': magnitude,
        'has_projection': projected_close_line is not None
    }


def _generate_clv_qualitative(
    classification: Classification,
    magnitude: str,
    direction: Optional[str],
    sharp_side: Optional[str],
    market_type: str
) -> str:
    """Generate qualitative CLV forecast without numeric projection (CANONICAL COPY)"""
    if classification == Classification.NO_ACTION:
        return f"{magnitude.title()} line movement expected. Informational only—no execution threshold met."
    
    elif classification == Classification.LEAN:
        if direction and sharp_side:
            side_display = format_side_display(sharp_side, market_type)
            return (
                f"{magnitude.title()} movement {direction} {side_display} anticipated. "
                f"Market incorporating directional signal. Movement insufficient to clear execution thresholds."
            )
        else:
            return f"{magnitude.title()} line movement expected. Directional signal present but insufficient for execution."
    
    else:  # EDGE
        if direction and sharp_side:
            side_display = format_side_display(sharp_side, market_type)
            return (
                f"{magnitude.title()} movement {direction} {side_display} expected. "
                f"Market likely to incorporate mispricing by game time."
            )
        else:
            return f"{magnitude.title()} line movement expected toward model consensus."


def _generate_clv_with_projection(
    classification: Classification,
    magnitude: str,
    direction: Optional[str],
    sharp_side: Optional[str],
    market_type: str,
    expected_movement: float
) -> str:
    """Generate CLV forecast with numeric projection (CANONICAL COPY)"""
    base_forecast = _generate_clv_qualitative(
        classification, magnitude, direction, sharp_side, market_type
    )
    
    if abs(expected_movement) >= 0.1:
        movement_str = f"{expected_movement:+.1f}"
        return f"{base_forecast} Expected movement: {movement_str}."
    else:
        return base_forecast


# ==================== BOX 5: WHY THIS EDGE EXISTS ====================

def render_why_edge_exists(
    classification: Classification,
    global_state: GlobalState,
    max_ev: float,
    sharp_side: Optional[str],
    market_type: str,
    volatility_state: str
) -> dict:
    """
    Render Why This Edge Exists box with global context.
    
    PURPOSE: Global market context
    TRUTH: "Is there mispricing across the entire simulation space?"
    CONSTRAINT: Must reference global efficiency
    
    This is the CRITICAL trust signal. Always displays.
    """
    # Global edge detection section
    global_context = _generate_global_edge_context(classification, global_state, max_ev)
    
    # Specific edge explanation (if applicable)
    if classification == Classification.EDGE:
        edge_explanation = _generate_edge_explanation(sharp_side, market_type, volatility_state)
    elif classification == Classification.LEAN:
        edge_explanation = _generate_lean_explanation(sharp_side, market_type)
    else:
        edge_explanation = None
    
    return {
        'title': 'Why This Edge Exists',
        'global_context': global_context,
        'edge_explanation': edge_explanation
    }


def _generate_global_edge_context(
    classification: Classification,
    global_state: GlobalState,
    max_ev: float
) -> dict:
    """
    Generate global edge detection context (CANONICAL COPY).
    
    This section MUST reinforce restraint and global efficiency.
    """
    if classification == Classification.NO_ACTION:
        if global_state == GlobalState.NO_PLAY:
            return {
                'statement': 'No statistically significant edge detected across global simulation space.',
                'implication': 'Market prices reflect available information efficiently. No mispricing identified.',
                'tone': 'neutral'
            }
        else:
            # Edge exists elsewhere but not in this market/side
            return {
                'statement': 'No actionable mispricing detected in this market configuration.',
                'implication': 'Model identified potential value in alternative markets. Current selection does not meet thresholds.',
                'tone': 'informational'
            }
    
    elif classification == Classification.LEAN:
        return {
            'statement': 'Directional bias identified, but global edge criteria not satisfied.',
            'implication': (
                f'Signal strength ({max_ev:.1f}%) below institutional threshold. '
                f'Insufficient to overcome market efficiency and execution costs.'
            ),
            'tone': 'cautious'
        }
    
    else:  # EDGE
        return {
            'statement': 'Localized mispricing detected relative to global distribution.',
            'implication': (
                f'Model projections diverge from market consensus by statistically significant margin. '
                f'Edge magnitude ({max_ev:.1f}%) sufficient to justify risk-adjusted execution.'
            ),
            'tone': 'confident'
        }


def _generate_edge_explanation(sharp_side: Optional[str], market_type: str, volatility_state: str) -> str:
    """Generate specific edge explanation for EDGE classification (CANONICAL COPY)"""
    side_display = format_side_display(sharp_side, market_type)
    base_explanation = (
        f"Market consensus underpricing {side_display}. "
        f"Model projections identify exploitable inefficiency."
    )
    
    if volatility_state == 'LOW':
        return base_explanation + " Low volatility environment supports execution."
    else:
        return base_explanation


def _generate_lean_explanation(sharp_side: Optional[str], market_type: str) -> str:
    """Generate specific explanation for LEAN classification (CANONICAL COPY)"""
    side_display = format_side_display(sharp_side, market_type)
    return (
        f"Model shows directional preference toward {side_display}, "
        f"but magnitude insufficient for institutional execution standards."
    )


# ==================== BOX 6: FINAL UNIFIED SUMMARY ====================

def render_final_unified_summary(
    spread_classification: Classification,
    total_classification: Classification,
    ml_classification: Classification,
    volatility_state: str,
    calibration_state: str,
    execution_constraints: List[ExecutionConstraint],
    best_market: Optional[str],
    best_pick: Optional[dict]
) -> dict:
    """
    Render Final Unified Summary.
    
    PURPOSE: Master verdict reconciling all sub-analyses
    TRUTH: "What the system decided and why"
    CONSTRAINT: Must never contradict sub-boxes
    
    This is the master verdict that reconciles all sub-analyses.
    Must never contradict sub-boxes. Always displays.
    
    ADDENDUM v1.0.2 - CRITICAL LOCKED RULE:
    Final Unified Summary verdict MUST be computed as:
    EDGE > LEAN > NO_ACTION
    across the THREE market classifications inside the SAME GAME CARD.
    
    Verdict is derived ONLY from market classifications.
    best_pick is DISPLAY-ONLY metadata.
    best_pick MUST NEVER determine verdict.
    Missing best_pick MUST NOT downgrade verdict.
    """
    # Compute global state
    global_state = compute_global_state(
        spread_classification,
        total_classification,
        ml_classification
    )
    
    # CRITICAL: Determine global verdict from market classifications ONLY
    # This prevents the bug: "best_pick missing ⇒ NO_ACTION"
    classifications = [spread_classification, total_classification, ml_classification]
    
    if Classification.EDGE in classifications:
        global_verdict = Classification.EDGE
    elif Classification.LEAN in classifications:
        global_verdict = Classification.LEAN
    else:
        global_verdict = Classification.NO_ACTION
    
    # Determine NO_ACTION subtype if applicable
    no_action_subtype = None
    if global_verdict == Classification.NO_ACTION:
        # Check if any signal exists (LEAN or EDGE) that was blocked
        any_signal = Classification.LEAN in classifications or Classification.EDGE in classifications
        no_action_subtype = (
            NoActionSubtype.SIGNAL_BLOCKED if any_signal or execution_constraints
            else NoActionSubtype.NO_SIGNAL
        )
    
    # Generate summary text
    summary_text = _generate_unified_summary_text(
        global_verdict=global_verdict,
        no_action_subtype=no_action_subtype,
        spread_classification=spread_classification,
        total_classification=total_classification,
        ml_classification=ml_classification,
        execution_constraints=execution_constraints,
        best_pick=best_pick
    )
    
    return {
        'title': 'Final Unified Summary',
        'verdict': global_verdict.value,
        'subtype': no_action_subtype.value if no_action_subtype else None,
        'summary': summary_text,
        'market_breakdown': {
            'spread': spread_classification.value,
            'total': total_classification.value,
            'moneyline': ml_classification.value
        }
    }


def _generate_unified_summary_text(
    global_verdict: Classification,
    no_action_subtype: Optional[NoActionSubtype],
    spread_classification: Classification,
    total_classification: Classification,
    ml_classification: Classification,
    execution_constraints: List[ExecutionConstraint],
    best_pick: Optional[dict]
) -> str:
    """
    Generate canonical unified summary text (CANONICAL COPY).
    
    Must follow hedge fund voice: precise, unemotional, complete.
    """
    if global_verdict == Classification.NO_ACTION:
        if no_action_subtype == NoActionSubtype.NO_SIGNAL:
            return (
                "No model signals detected across any market. "
                "Expected value does not favor any side. "
                "No action warranted."
            )
        else:  # SIGNAL_BLOCKED
            # Determine blocking factors
            blocking_factors = []
            for constraint in execution_constraints:
                if constraint == ExecutionConstraint.HIGH_VOLATILITY:
                    blocking_factors.append("elevated variance")
                elif constraint == ExecutionConstraint.BOOTSTRAP_CALIBRATION:
                    blocking_factors.append("incomplete calibration")
                elif constraint == ExecutionConstraint.DISPUTED_LINE:
                    blocking_factors.append("disputed line consensus")
                elif constraint == ExecutionConstraint.STALE_ODDS:
                    blocking_factors.append("stale odds")
                elif constraint == ExecutionConstraint.REVIEW_WINDOW:
                    blocking_factors.append("manual review requirement")
            
            if blocking_factors:
                blocking_text = " and ".join(blocking_factors)
                return (
                    f"Model signals detected; however, {blocking_text} prevent risk-adjusted execution. "
                    f"No action warranted."
                )
            else:
                # Signal exists but magnitude insufficient
                return (
                    "Directional signals identified but magnitude insufficient for institutional thresholds. "
                    "No action warranted."
                )
    
    elif global_verdict == Classification.LEAN:
        if best_pick:
            best_market_display = _format_market_display(best_pick.get('market', ''))
            best_side_display = format_side_display(best_pick.get('side'), best_pick.get('market', ''))
            ev = best_pick.get('ev', 0)
            return (
                f"Directional bias detected in {best_market_display} market toward {best_side_display} "
                f"({ev:.1f}% EV). "
                f"Below institutional execution threshold ({EDGE_THRESHOLD}%). "
                f"Informational signal only—execution not recommended."
            )
        else:
            # Fallback if best_pick missing (should not happen but safe)
            return (
                f"Directional bias detected. "
                f"Below institutional execution threshold ({EDGE_THRESHOLD}%). "
                f"Informational signal only—execution not recommended."
            )
    
    else:  # EDGE
        if best_pick:
            best_market_display = _format_market_display(best_pick.get('market', ''))
            best_side_display = format_side_display(best_pick.get('side'), best_pick.get('market', ''))
            ev = best_pick.get('ev', 0)
            
            # Check if multiple markets have edge
            edge_count = sum(
                1 for cls in [spread_classification, total_classification, ml_classification]
                if cls == Classification.EDGE
            )
            
            if edge_count > 1:
                secondary_note = f" Multiple edges identified; {best_market_display} presents optimal risk-reward."
            else:
                secondary_note = ""
            
            # CRITICAL: Check for execution constraints
            if execution_constraints:
                # EDGE with constraints → Cannot say "all risk controls passed"
                return (
                    f"Statistically significant edge identified: {best_market_display} market, {best_side_display} "
                    f"at {ev:.1f}% expected value. "
                    f"Edge detected. Execution constraints active.{secondary_note}"
                )
            else:
                # Clean EDGE → Can say "all risk controls passed"
                return (
                    f"Statistically significant edge identified: {best_market_display} market, {best_side_display} "
                    f"at {ev:.1f}% expected value. "
                    f"All risk controls passed.{secondary_note}"
                )
        else:
            # Fallback if best_pick missing
            if execution_constraints:
                return (
                    f"Statistically significant edge identified. "
                    f"Edge detected. Execution constraints active."
                )
            else:
                return (
                    f"Statistically significant edge identified. "
                    f"All risk controls passed."
                )


# ==================== HELPER FUNCTIONS ====================

def _format_market_display(market_type: str) -> str:
    """Format market type for display (CANONICAL)"""
    market_map = {
        'SPREAD': 'spread',
        'TOTAL': 'total',
        'MONEYLINE_2WAY': 'moneyline',
        'MONEYLINE_3WAY': '3-way moneyline',
        'MONEYLINE': 'moneyline'
    }
    return market_map.get(market_type, market_type.lower())


def format_side_display(sharp_side: Optional[str], market_type: str) -> str:
    """
    Format side for display based on market type.
    
    NOTE: This is a placeholder. Full implementation requires game metadata
    (team names, line values) which should be passed in context.
    
    For production, this should be called with full context:
    format_side_display(sharp_side, market_type, team_name, line, odds)
    """
    if not sharp_side:
        return "undetermined"
    
    # Placeholder - production needs team names and lines
    # Example outputs: "Lakers -7.5", "Over 215.5", "Lakers ML"
    side_map = {
        'home': 'home',
        'away': 'away',
        'over': 'over',
        'under': 'under',
        'favorite': 'favorite',
        'underdog': 'underdog'
    }
    return side_map.get(sharp_side, sharp_side)


# ==================== CANONICAL COPY LIBRARY (REFERENCE) ====================

CANONICAL_COPY_REFERENCE = {
    "key_drivers": {
        "allowed": [
            "Pace differential: [direction] by [X] possessions",
            "Defensive efficiency mismatch: [X] points per 100 possessions",
            "Offensive rating gap: [X] points",
            "Injury impact: Incorporated into baseline projections",
            "Simulation depth: [N] Monte Carlo iterations",
            "Matchup variance: [description]",
            "Rest differential: [X] days"
        ],
        "forbidden": [
            "This creates betting value",
            "Strong edge indicator",
            "High confidence opportunity",
            "Take advantage of this mismatch"
        ],
        "disclaimer": "Model inputs shown for transparency. Does not imply actionability."
    },
    
    "edge_context_notes": {
        "no_action": [
            "No positive EV detected",
            "EV insufficient: [X]% below minimum threshold ([LEAN_THRESHOLD]%)"
        ],
        "lean": [
            "EV marginal: [X]% below institutional threshold ([EDGE_THRESHOLD]%)"
        ],
        "edge_with_constraints": [
            "Edge detected but execution constraints active",
            "Volatility elevated: Requires higher edge threshold for execution",
            "Calibration incomplete: Model in validation period",
            "Line consensus disputed: Execution criteria not met",
            "Odds stale: Line may have moved, refresh required",
            "Manual review required: Edge magnitude triggers verification protocol"
        ]
    },
    
    "edge_summary": {
        "no_action": [
            "No positive EV detected. Expected value does not favor any side.",
            "Signal magnitude ([X]%) insufficient to meet minimum execution criteria.",
            "Execution blocked by risk controls."
        ],
        "lean": [
            "Directional bias toward [side] detected ([X]% EV). Below institutional threshold ([EDGE_THRESHOLD]%). Not recommended for execution."
        ],
        "edge_clean": [
            "Statistically significant edge detected: [side] at [X]% EV. All risk controls passed."
        ],
        "edge_constrained": [
            "Statistically significant edge detected: [side] at [X]% EV. Edge detected. Execution constraints active."
        ]
    }
}


if __name__ == "__main__":
    # Test basic functionality
    print("=== BeatVegas UI Explanation Layer v1.0.2 ===\n")
    
    # Test global state computation
    print("Test 1: Global State Computation")
    state = compute_global_state(
        Classification.EDGE,
        Classification.NO_ACTION,
        Classification.NO_ACTION
    )
    print(f"EDGE + NO_ACTION + NO_ACTION = {state}")
    assert state == GlobalState.EDGE_AVAILABLE
    
    state = compute_global_state(
        Classification.LEAN,
        Classification.NO_ACTION,
        Classification.LEAN
    )
    print(f"LEAN + NO_ACTION + LEAN = {state}")
    assert state == GlobalState.LEANS_ONLY
    
    state = compute_global_state(
        Classification.NO_ACTION,
        Classification.NO_ACTION,
        Classification.NO_ACTION
    )
    print(f"NO_ACTION + NO_ACTION + NO_ACTION = {state}")
    assert state == GlobalState.NO_PLAY
    
    print("✅ Global state computation tests passed\n")
    
    # Test Key Drivers rendering
    print("Test 2: Key Drivers Rendering")
    sim_data = {
        'pace_delta': 3.2,
        'injury_adjusted': True,
        'matchup_factor': 'Defensive efficiency mismatch',
        'total_sims': 100000
    }
    drivers = render_key_drivers(sim_data)
    print(f"Title: {drivers['title']}")
    print(f"Items: {drivers['items']}")
    print(f"Disclaimer: {drivers['disclaimer']}")
    print("✅ Key Drivers rendering test passed\n")
    
    # Test Edge Context Notes visibility
    print("Test 3: Edge Context Notes Display Logic")
    
    # Case 1: Clean EDGE (should be None)
    context = render_edge_context(
        Classification.EDGE, 4.2, 'LOW', 'CALIBRATED', 4.2, []
    )
    print(f"Clean EDGE: {context}")
    assert context is None, "Clean EDGE should have no context notes"
    
    # Case 2: EDGE with constraints (should show)
    context = render_edge_context(
        Classification.EDGE, 4.2, 'HIGH', 'CALIBRATED', 4.2,
        [ExecutionConstraint.HIGH_VOLATILITY]
    )
    assert context is not None, "EDGE with constraints should show context"
    print(f"EDGE with constraints: {context.get('notes', [''])[0] if context.get('notes') else ''}")
    assert "Edge detected but execution constraints active" in context['notes'][0]
    
    # Case 3: NO_ACTION (should show)
    context = render_edge_context(
        Classification.NO_ACTION, -0.3, 'NORMAL', 'CALIBRATED', -0.3, []
    )
    assert context is not None, "NO_ACTION should show context"
    print(f"NO_ACTION: {context.get('notes', [''])[0] if context.get('notes') else ''}")
    
    print("✅ Edge Context Notes visibility tests passed\n")
    
    print("=== All Core Tests Passed ===")
