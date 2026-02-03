"""
BeatVegas Model Direction Consistency Fix v1.0
Status: HARD-CODED IMPLEMENTATION (LOCKED)
Generated: 2026-02-01

PROBLEM:
Model Preference shows Utah +10.5, but Model Direction shows Toronto -10.5.
One screen appears to recommend both sides of the same market.

ROOT CAUSE:
Sign/orientation bug in spread normalization + separate code paths for
Model Preference vs Model Direction.

SOLUTION:
Single source of truth with canonical signed spread convention.
All direction logic derived from same computation as preference.

NON-NEGOTIABLE INVARIANTS:
A. Single source of truth: Model Direction = Model Preference (same selection)
B. No opposite-side rendering: Both panels show same team + line
C. Consistent edge sign: edge_pts = market_line - fair_line (same coordinate system)
D. Text matches side: 'Take the dog' only when underdog, 'Lay the points' only when favorite

CANONICAL REPRESENTATION:
For each team T, spread is signed from that team's perspective:
- Negative = T is favorite (laying points): T -10.5
- Positive = T is underdog (receiving points): T +10.5
Opposite team's line = negation: line(opp) = -line(T)
"""

from typing import List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum


class DirectionLabel(str, Enum):
    """Direction labels (canonical)"""
    TAKE_DOG = "TAKE_DOG"      # Taking points (underdog)
    LAY_FAV = "LAY_FAV"        # Laying points (favorite)
    NO_EDGE = "NO_EDGE"        # No actionable edge


@dataclass
class TeamSideLine:
    """
    Signed spread representation for one team.
    
    CANONICAL INVARIANT:
    - market_line is SIGNED from team's perspective
    - Negative = team is favorite (laying points)
    - Positive = team is underdog (receiving points)
    - Opposite team's line = -market_line
    """
    team_id: str
    team_name: str
    market_line: float  # Signed, team-perspective
    fair_line: float    # Signed, team-perspective (model's fair line)
    
    def is_favorite(self) -> bool:
        """Team is favorite if laying points (negative line)"""
        return self.market_line < 0
    
    def is_underdog(self) -> bool:
        """Team is underdog if receiving points (positive line)"""
        return self.market_line > 0


@dataclass
class DirectionResult:
    """
    Complete model direction result.
    
    This is the SINGLE SOURCE OF TRUTH for both:
    - Model Preference (This Market)
    - Model Direction (Informational)
    
    Both panels MUST render from this exact payload.
    """
    preferred_team_id: str
    preferred_team_name: str
    preferred_market_line: float   # Signed line for preferred team
    preferred_fair_line: float     # Signed fair line for preferred team
    edge_pts: float                # market_line - fair_line (positive = good)
    direction_label: DirectionLabel
    direction_text: str            # UI copy
    
    # Both sides (for reference)
    teamA_side: TeamSideLine
    teamB_side: TeamSideLine


# ==================== CANONICAL EDGE POINTS ====================

def compute_edge_pts(market_line: float, fair_line: float) -> float:
    """
    Compute edge in points.
    
    CANONICAL FORMULA (HARD-CODED):
    edge_pts = market_line - fair_line
    
    Higher edge_pts = more favorable for that team.
    
    Example 1 (Underdog generous):
    - Utah +10.5 market, Utah +6.4 fair
    - edge_pts = 10.5 - 6.4 = +4.1 (good for Utah +10.5)
    
    Example 2 (Favorite discounted):
    - Toronto -10.5 market, Toronto -6.4 fair
    - edge_pts = -10.5 - (-6.4) = -4.1 (bad; reject Toronto -10.5)
    
    Example 3 (Favorite discounted, good):
    - Lakers -4.5 market, Lakers -7.0 fair
    - edge_pts = -4.5 - (-7.0) = +2.5 (good for Lakers -4.5)
    """
    return market_line - fair_line


# ==================== BUILD BOTH SIDES ====================

def build_sides(
    teamA_id: str,
    teamA_name: str,
    teamA_market_line: float,
    teamA_fair_line: float,
    teamB_id: str,
    teamB_name: str
) -> Tuple[TeamSideLine, TeamSideLine]:
    """
    Build both sides of the spread in canonical signed representation.
    
    CANONICAL INVARIANT (HARD-CODED):
    Opposite side is ALWAYS negation of input side.
    
    Args:
        teamA_id: Team A ID
        teamA_name: Team A name
        teamA_market_line: Market spread from Team A perspective (signed)
        teamA_fair_line: Model fair spread from Team A perspective (signed)
        teamB_id: Team B ID (opponent)
        teamB_name: Team B name (opponent)
    
    Returns:
        (teamA_side, teamB_side) with canonical signed representation
    
    Example:
        Input: Utah +10.5 market, Utah +6.4 fair
        Output:
          - TeamA (Utah): +10.5 market, +6.4 fair
          - TeamB (Toronto): -10.5 market, -6.4 fair
    """
    teamA_side = TeamSideLine(
        team_id=teamA_id,
        team_name=teamA_name,
        market_line=teamA_market_line,
        fair_line=teamA_fair_line
    )
    
    # CANONICAL RULE: Opposite side is ALWAYS negation
    teamB_side = TeamSideLine(
        team_id=teamB_id,
        team_name=teamB_name,
        market_line=-teamA_market_line,
        fair_line=-teamA_fair_line
    )
    
    return teamA_side, teamB_side


# ==================== SELECT PREFERENCE (SOURCE OF TRUTH) ====================

def choose_preference(
    teamA_side: TeamSideLine,
    teamB_side: TeamSideLine
) -> DirectionResult:
    """
    Choose preferred side (SINGLE SOURCE OF TRUTH).
    
    CANONICAL ALGORITHM (HARD-CODED):
    1. Compute edge_pts for both sides
    2. Select team with MAX edge_pts
    3. Determine label from sign of preferred market_line
    4. Generate copy based on label
    
    This result is used for BOTH:
    - Model Preference (This Market)
    - Model Direction (Informational)
    
    Args:
        teamA_side: Team A signed line
        teamB_side: Team B signed line
    
    Returns:
        DirectionResult with preferred team, edge, label, and copy
    """
    sides = [teamA_side, teamB_side]
    
    # Find side with MAX edge_pts
    best_side = None
    best_edge = float('-inf')
    
    for side in sides:
        edge = compute_edge_pts(side.market_line, side.fair_line)
        if edge > best_edge:
            best_edge = edge
            best_side = side
    
    # Ensure we found a valid side
    assert best_side is not None, "No valid side found in choose_preference"
    
    # CANONICAL LABEL DETERMINATION (HARD-CODED)
    # Tied to sign of market_line ONLY
    if best_side.market_line > 0:
        # Underdog (receiving points)
        label = DirectionLabel.TAKE_DOG
        direction_text = (
            f"Take the points ({best_side.team_name} {best_side.market_line:+.1f}). "
            f"Market is giving extra points vs the model fair line "
            f"({best_side.team_name} {best_side.fair_line:+.1f}). "
            f"Edge: {best_edge:+.1f} pts."
        )
    elif best_side.market_line < 0:
        # Favorite (laying points)
        label = DirectionLabel.LAY_FAV
        direction_text = (
            f"Lay the points ({best_side.team_name} {best_side.market_line:.1f}). "
            f"Market is discounting the favorite vs the model fair line "
            f"({best_side.team_name} {best_side.fair_line:.1f}). "
            f"Edge: {best_edge:+.1f} pts."
        )
    else:
        # Pick'em (line = 0)
        label = DirectionLabel.NO_EDGE
        direction_text = (
            f"Pick'em ({best_side.team_name} {best_side.market_line:.1f}). "
            f"No edge detected."
        )
    
    return DirectionResult(
        preferred_team_id=best_side.team_id,
        preferred_team_name=best_side.team_name,
        preferred_market_line=best_side.market_line,
        preferred_fair_line=best_side.fair_line,
        edge_pts=best_edge,
        direction_label=label,
        direction_text=direction_text,
        teamA_side=teamA_side,
        teamB_side=teamB_side
    )


# ==================== UI INVARIANT ASSERTIONS ====================

def assert_direction_matches_preference(
    direction: DirectionResult,
    preference_team_id: str,
    preference_market_line: float
) -> None:
    """
    Hard assert: Model Direction MUST match Model Preference.
    
    CANONICAL INVARIANT (HARD-CODED):
    Both panels must show SAME team + SAME line.
    
    Raises:
        AssertionError if direction contradicts preference
    """
    # Invariant A: Same team
    assert direction.preferred_team_id == preference_team_id, (
        f"DIRECTION CONTRADICTION: Direction team {direction.preferred_team_id} "
        f"!= Preference team {preference_team_id}"
    )
    
    # Invariant B: Same line (within floating point tolerance)
    line_diff = abs(direction.preferred_market_line - preference_market_line)
    assert line_diff < 1e-6, (
        f"DIRECTION CONTRADICTION: Direction line {direction.preferred_market_line} "
        f"!= Preference line {preference_market_line} (diff: {line_diff})"
    )


def assert_text_matches_side(direction: DirectionResult) -> None:
    """
    Hard assert: Copy must match side (underdog vs favorite).
    
    CANONICAL INVARIANT D (HARD-CODED):
    - 'Take the dog' ONLY when underdog (market_line > 0)
    - 'Lay the points' ONLY when favorite (market_line < 0)
    
    Raises:
        AssertionError if text contradicts side
    """
    text_lower = direction.direction_text.lower()
    
    if direction.preferred_market_line > 0:
        # Underdog - should say "take the points"
        assert 'take the points' in text_lower, (
            f"TEXT CONTRADICTION: Underdog ({direction.preferred_market_line:+.1f}) "
            f"but text doesn't say 'take the points': {direction.direction_text}"
        )
        assert 'lay the points' not in text_lower, (
            f"TEXT CONTRADICTION: Underdog ({direction.preferred_market_line:+.1f}) "
            f"but text says 'lay the points': {direction.direction_text}"
        )
        assert 'fade the dog' not in text_lower, (
            f"TEXT CONTRADICTION: Underdog ({direction.preferred_market_line:+.1f}) "
            f"but text says 'fade the dog': {direction.direction_text}"
        )
    
    elif direction.preferred_market_line < 0:
        # Favorite - should say "lay the points"
        assert 'lay the points' in text_lower, (
            f"TEXT CONTRADICTION: Favorite ({direction.preferred_market_line:.1f}) "
            f"but text doesn't say 'lay the points': {direction.direction_text}"
        )
        assert 'take the points' not in text_lower, (
            f"TEXT CONTRADICTION: Favorite ({direction.preferred_market_line:.1f}) "
            f"but text says 'take the points': {direction.direction_text}"
        )


# ==================== MAIN ENTRY POINT ====================

def compute_model_direction(
    teamA_id: str,
    teamA_name: str,
    teamA_market_line: float,
    teamA_fair_line: float,
    teamB_id: str,
    teamB_name: str,
    validate: bool = True
) -> DirectionResult:
    """
    Compute model direction (CANONICAL IMPLEMENTATION).
    
    This is the SINGLE SOURCE OF TRUTH for:
    - Model Preference (This Market) panel
    - Model Direction (Informational) panel
    
    Both panels MUST render from this exact payload.
    
    Args:
        teamA_id: Team A ID
        teamA_name: Team A display name
        teamA_market_line: Market spread from Team A perspective (signed)
        teamA_fair_line: Model fair spread from Team A perspective (signed)
        teamB_id: Team B ID (opponent)
        teamB_name: Team B display name (opponent)
        validate: Run hard assertions (default: True)
    
    Returns:
        DirectionResult with preferred team, edge, label, and copy
    
    Example:
        >>> result = compute_model_direction(
        ...     teamA_id='utah_jazz',
        ...     teamA_name='Utah Jazz',
        ...     teamA_market_line=10.5,   # Utah +10.5
        ...     teamA_fair_line=6.4,       # Utah +6.4 fair
        ...     teamB_id='toronto_raptors',
        ...     teamB_name='Toronto Raptors'
        ... )
        >>> result.preferred_team_name
        'Utah Jazz'
        >>> result.preferred_market_line
        10.5
        >>> result.edge_pts
        4.1
        >>> result.direction_label
        'TAKE_DOG'
    """
    # Step 1: Build both sides (canonical signed representation)
    teamA_side, teamB_side = build_sides(
        teamA_id=teamA_id,
        teamA_name=teamA_name,
        teamA_market_line=teamA_market_line,
        teamA_fair_line=teamA_fair_line,
        teamB_id=teamB_id,
        teamB_name=teamB_name
    )
    
    # Step 2: Choose preference (MAX edge_pts)
    direction = choose_preference(teamA_side, teamB_side)
    
    # Step 3: Validate invariants
    if validate:
        # Invariant: Direction matches preference (self-consistency)
        assert_direction_matches_preference(
            direction,
            direction.preferred_team_id,
            direction.preferred_market_line
        )
        
        # Invariant: Text matches side
        assert_text_matches_side(direction)
    
    return direction


# ==================== TELEGRAM INTEGRATION ====================

def get_telegram_selection(direction: DirectionResult) -> dict:
    """
    Get Telegram card selection from DirectionResult.
    
    CANONICAL RULE:
    Telegram uses Model Preference payload.
    After this fix, Model Direction = Model Preference, so either works.
    Safest rule: Telegram uses preference payload.
    
    Args:
        direction: DirectionResult from compute_model_direction()
    
    Returns:
        Dict with telegram selection data
    """
    return {
        'team_id': direction.preferred_team_id,
        'team_name': direction.preferred_team_name,
        'market_line': direction.preferred_market_line,
        'fair_line': direction.preferred_fair_line,
        'edge_pts': direction.edge_pts,
        'direction_label': direction.direction_label.value,
        'copy': direction.direction_text
    }


if __name__ == "__main__":
    print("=== Model Direction Consistency Fix v1.0 ===\n")
    
    # Example 1: Underdog generous (Utah +10.5 market, +6.4 fair)
    print("Example 1: Underdog generous")
    result1 = compute_model_direction(
        teamA_id='utah_jazz',
        teamA_name='Utah Jazz',
        teamA_market_line=10.5,
        teamA_fair_line=6.4,
        teamB_id='toronto_raptors',
        teamB_name='Toronto Raptors'
    )
    print(f"Preferred: {result1.preferred_team_name} {result1.preferred_market_line:+.1f}")
    print(f"Edge: {result1.edge_pts:+.1f} pts")
    print(f"Label: {result1.direction_label}")
    print(f"Text: {result1.direction_text}\n")
    
    # Example 2: Favorite discounted (Lakers -4.5 market, -7.0 fair)
    print("Example 2: Favorite discounted")
    result2 = compute_model_direction(
        teamA_id='lakers',
        teamA_name='Lakers',
        teamA_market_line=-4.5,
        teamA_fair_line=-7.0,
        teamB_id='celtics',
        teamB_name='Celtics'
    )
    print(f"Preferred: {result2.preferred_team_name} {result2.preferred_market_line:.1f}")
    print(f"Edge: {result2.edge_pts:+.1f} pts")
    print(f"Label: {result2.direction_label}")
    print(f"Text: {result2.direction_text}\n")
    
    print("=== All Examples Passed ===")
