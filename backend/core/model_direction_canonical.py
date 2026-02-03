"""
BeatVegas Model Direction Consistency — HARD-CODED & LOCKED
===========================================================

This module is the SINGLE SOURCE OF TRUTH for Model Direction and Model Preference.

Version: 1.0
Generated: 2026-02-02

INVARIANTS (NON-NEGOTIABLE):
---------------------------
A. Single source of truth: Model Direction derived from SAME selection as Model Preference
B. No opposite-side rendering: If Preference is Team X +L, Direction MUST also be Team X +L
C. Consistent edge sign: edge_pts = market_line - fair_line (same coordinate system)
D. Text matches side: 'Take the dog' only when recommended side is underdog

CANONICAL REPRESENTATION:
------------------------
Every spread is normalized into signed lines for each team:
• Negative = Team is laying points (favorite): Team -10.5
• Positive = Team is receiving points (underdog): Team +10.5

Opposite team's line is the negation: line(opp) = -line(T)

🔒 LOCKED: Do NOT modify without explicit approval.
"""

from dataclasses import dataclass
from typing import Literal, Optional
from enum import Enum


class DirectionLabel(str, Enum):
    """Direction label for copy generation"""
    TAKE_DOG = "TAKE_DOG"
    LAY_FAV = "LAY_FAV"
    NO_PLAY = "NO_PLAY"


@dataclass
class TeamSideLine:
    """
    Represents a team's side of the spread market
    
    Attributes:
        team_id: Team identifier (name or ID)
        market_line: Signed market spread from team's perspective
        fair_line: Signed fair spread from team's perspective
    """
    team_id: str
    market_line: float  # Signed, team-perspective
    fair_line: float    # Signed, team-perspective


@dataclass
class DirectionResult:
    """
    Canonical model direction result
    
    This MUST be the ONLY payload used for both Model Preference and Model Direction.
    """
    preferred_team_id: str
    preferred_market_line: float
    preferred_fair_line: float
    edge_pts: float  # market_line - fair_line
    direction_label: DirectionLabel
    direction_text: str


def compute_edge_pts(market_line: float, fair_line: float) -> float:
    """
    CANONICAL EDGE POINTS FORMULA (HARD-CODED)
    
    For a given team, more favorable = higher market_line relative to fair_line.
    
    edge_pts = market_line - fair_line
    
    Example (Utah +10.5 market, Utah +6.4 fair):
        edge_pts = 10.5 - 6.4 = +4.1 (good for Utah +10.5)
    
    Example (Toronto -10.5 market, Toronto -6.4 fair):
        edge_pts = -10.5 - (-6.4) = -4.1 (bad; reject Toronto -10.5)
    
    Args:
        market_line: Market spread (signed, team-perspective)
        fair_line: Fair spread (signed, team-perspective)
    
    Returns:
        Edge in points (positive = favorable)
    """
    return market_line - fair_line


def build_sides(
    team_a_id: str,
    team_a_market_line: float,
    team_a_fair_line: float,
    team_b_id: str
) -> list[TeamSideLine]:
    """
    BUILD BOTH SIDES (NO HEURISTICS)
    
    Inputs must supply market spread for ONE side with team_id.
    Opposite side is ALWAYS derived as negation.
    
    Args:
        team_a_id: First team identifier
        team_a_market_line: Market spread from team A perspective
        team_a_fair_line: Fair spread from team A perspective
        team_b_id: Second team identifier (opponent)
    
    Returns:
        List of both team sides [teamA, teamB]
    
    Example:
        team_a_id = "Utah Jazz"
        team_a_market_line = +10.5
        team_a_fair_line = +6.4
        team_b_id = "Toronto Raptors"
        
        Returns:
        [
            TeamSideLine("Utah Jazz", +10.5, +6.4),
            TeamSideLine("Toronto Raptors", -10.5, -6.4)
        ]
    """
    return [
        TeamSideLine(
            team_id=team_a_id,
            market_line=team_a_market_line,
            fair_line=team_a_fair_line
        ),
        TeamSideLine(
            team_id=team_b_id,
            market_line=-team_a_market_line,
            fair_line=-team_a_fair_line
        )
    ]


def choose_preference(sides: list[TeamSideLine]) -> DirectionResult:
    """
    SELECT PREFERENCE (SOURCE OF TRUTH)
    
    Preferred side is the team with MAX edge_pts.
    
    This function determines BOTH Model Preference AND Model Direction.
    They are IDENTICAL by construction.
    
    Args:
        sides: List of both team sides (from build_sides)
    
    Returns:
        DirectionResult with preferred team, line, edge, and copy
    
    Raises:
        ValueError: If sides list is empty or invalid
    """
    if not sides:
        raise ValueError("Sides list cannot be empty")
    
    best = None
    best_edge = float('-inf')
    
    for side in sides:
        edge = compute_edge_pts(side.market_line, side.fair_line)
        if edge > best_edge:
            best_edge = edge
            best = side
    
    if best is None:
        raise ValueError("Could not determine best side")
    
    # Determine label for copy
    # If market_line is positive => underdog (taking points)
    # If market_line is negative => favorite (laying points)
    if best.market_line > 0:
        label = DirectionLabel.TAKE_DOG
        text = f"Take the points ({best.team_id}). Market is giving extra points vs the model fair line."
    elif best.market_line < 0:
        label = DirectionLabel.LAY_FAV
        text = f"Lay the points ({best.team_id}). Market is discounting the favorite vs the model fair line."
    else:
        # Exactly 0 (pick'em) - rare but handle it
        label = DirectionLabel.NO_PLAY
        text = f"Pick'em game ({best.team_id}). No line advantage."
    
    return DirectionResult(
        preferred_team_id=best.team_id,
        preferred_market_line=best.market_line,
        preferred_fair_line=best.fair_line,
        edge_pts=best_edge,
        direction_label=label,
        direction_text=text
    )


def assert_direction_matches_preference(
    direction: DirectionResult,
    preference_team_id: str,
    preference_market_line: float
) -> None:
    """
    UI INVARIANT (HARD ASSERT)
    
    Model Direction MUST match Model Preference side + line.
    
    Args:
        direction: DirectionResult from choose_preference
        preference_team_id: Team ID from Model Preference
        preference_market_line: Market line from Model Preference
    
    Raises:
        AssertionError: If direction doesn't match preference
    """
    assert direction.preferred_team_id == preference_team_id, \
        f"Direction team ({direction.preferred_team_id}) != Preference team ({preference_team_id})"
    
    assert abs(direction.preferred_market_line - preference_market_line) < 1e-6, \
        f"Direction line ({direction.preferred_market_line}) != Preference line ({preference_market_line})"


def calculate_model_direction(
    home_team: str,
    away_team: str,
    market_spread_home: float,
    fair_spread_home: float
) -> DirectionResult:
    """
    MAIN API: Calculate model direction (and preference)
    
    This is the ONLY function that should be called to determine
    Model Direction and Model Preference.
    
    Args:
        home_team: Home team name
        away_team: Away team name
        market_spread_home: Market spread from home team perspective
                           (negative = home favored)
        fair_spread_home: Fair spread from home team perspective
                         (negative = home favored by model)
    
    Returns:
        DirectionResult with canonical direction/preference
    
    Example:
        home_team = "Toronto Raptors"
        away_team = "Utah Jazz"
        market_spread_home = -10.5  (Toronto favored by 10.5)
        fair_spread_home = -6.4     (Toronto favored by 6.4 per model)
        
        Sides:
        - Toronto: market=-10.5, fair=-6.4, edge=-4.1 ❌
        - Utah: market=+10.5, fair=+6.4, edge=+4.1 ✅
        
        Result:
        - preferred_team_id: "Utah Jazz"
        - preferred_market_line: +10.5
        - direction_label: TAKE_DOG
        - edge_pts: +4.1
    """
    # Build both sides with canonical signed representation
    sides = build_sides(
        team_a_id=home_team,
        team_a_market_line=market_spread_home,
        team_a_fair_line=fair_spread_home,
        team_b_id=away_team
    )
    
    # Choose preference (max edge_pts)
    direction = choose_preference(sides)
    
    return direction


def format_display_line(team: str, line: float) -> str:
    """
    Format team + line for display
    
    Args:
        team: Team name
        line: Signed spread
    
    Returns:
        Formatted string like "Utah Jazz +10.5" or "Toronto Raptors -6.4"
    """
    if line >= 0:
        return f"{team} +{line:.1f}"
    else:
        return f"{team} {line:.1f}"


def validate_text_copy(
    direction: DirectionResult,
    rendered_text: str
) -> tuple[bool, Optional[str]]:
    """
    TEXT TEMPLATE SAFETY
    
    Validates that rendered text doesn't contradict the direction label.
    
    Args:
        direction: DirectionResult with direction_label
        rendered_text: Actual text being rendered in UI
    
    Returns:
        (is_valid, error_message)
    
    Rules:
        - TAKE_DOG: Text must NOT mention "favorite" or "fade the dog"
        - LAY_FAV: Text must NOT mention "underdog getting too many points" or "take the dog"
    """
    text_lower = rendered_text.lower()
    
    if direction.direction_label == DirectionLabel.TAKE_DOG:
        if "fade the dog" in text_lower:
            return False, f"TAKE_DOG label cannot use 'fade the dog' text"
        if "favorite" in text_lower and "discount" not in text_lower:
            return False, f"TAKE_DOG label should not emphasize favorite"
    
    elif direction.direction_label == DirectionLabel.LAY_FAV:
        if "take the dog" in text_lower or "take the points" in text_lower:
            return False, f"LAY_FAV label cannot use 'take the dog/points' text"
        if "underdog getting too many" in text_lower:
            return False, f"LAY_FAV should not use confusing 'underdog getting too many' phrasing"
    
    return True, None


# ==============================================================================
# INTEGRATION HELPERS (for existing codebase)
# ==============================================================================

def get_selection_id_from_direction(direction: DirectionResult, home_team: str) -> Literal["home", "away", "no_selection"]:
    """
    Map DirectionResult to legacy selection_id format
    
    Args:
        direction: DirectionResult from calculate_model_direction
        home_team: Home team name
    
    Returns:
        "home", "away", or "no_selection"
    """
    if direction.preferred_team_id == home_team:
        return "home"
    else:
        return "away"


def to_legacy_format(direction: DirectionResult, home_team: str, away_team: str) -> dict:
    """
    Convert DirectionResult to legacy format for backward compatibility
    
    Args:
        direction: DirectionResult from calculate_model_direction
        home_team: Home team name
        away_team: Away team name
    
    Returns:
        Dictionary with legacy keys for existing code
    """
    selection_id = get_selection_id_from_direction(direction, home_team)
    
    return {
        "selection_id": selection_id,
        "preferred_team": direction.preferred_team_id,
        "preferred_line": direction.preferred_market_line,
        "edge_pts": direction.edge_pts,
        "direction_label": direction.direction_label.value,
        "direction_text": direction.direction_text,
        "display": format_display_line(direction.preferred_team_id, direction.preferred_market_line),
        "model_preference": {
            "team": direction.preferred_team_id,
            "line": direction.preferred_market_line,
            "edge_pts": direction.edge_pts
        },
        "model_direction": {
            "team": direction.preferred_team_id,
            "line": direction.preferred_market_line,
            "label": direction.direction_label.value,
            "text": direction.direction_text
        }
    }
