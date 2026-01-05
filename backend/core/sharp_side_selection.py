"""
Universal Sharp Side Selection — LOCKED DEFINITION

■ FINAL CLARIFICATION — MODEL SPREAD SIGN (LOCKED DEFINITION)

Canonical Rule (THIS IS THE SOURCE OF TRUTH):
Model Spread is a SIGNED value relative to TEAM DIRECTION.
• Positive (+) Model Spread → Underdog
• Negative (−) Model Spread → Favorite

It is NOT:
• a delta vs market
• a probability
• a generic "edge score"

It IS a model-implied spread direction and magnitude.

■ UNIVERSAL SHARP SIDE SELECTION RULE (NON-NEGOTIABLE):
• If model_spread > market_spread → Sharp side = FAVORITE
• If model_spread < market_spread → Sharp side = UNDERDOG

Critical Rules:
1. Edges are prices, not teams
2. Sharp side determined by model_spread vs market_spread comparison
3. Volatility penalties applied AFTER sharp side selection
4. Separate logic for spread/total/moneyline markets
"""
from typing import Tuple, Optional, Dict
from dataclasses import dataclass
from .sport_configs import EdgeState, MarketType, VolatilityLevel


@dataclass
class SharpSideSelection:
    """Result of sharp side selection algorithm"""
    sharp_side: str  # Team name + line (e.g., "Knicks -5.5")
    recommended_bet: str  # Full description
    sharp_action: str  # "LAY_POINTS", "TAKE_POINTS", "OVER", "UNDER", "ML"
    
    # Market context
    market_spread: float  # Market spread value
    model_spread: float  # Model spread (SIGNED: + = underdog, - = favorite)
    
    # Teams
    market_favorite: str
    market_underdog: str
    
    # Edge metrics
    edge_magnitude: float  # Absolute difference between model and market
    volatility_penalty: float  # Points deducted for volatility
    edge_after_penalty: float  # Edge remaining after adjustment
    
    # Display strings (MANDATORY)
    market_spread_display: str  # "Hawks +5.5"
    model_spread_display: str   # "Hawks +12.3" (with team!)
    sharp_side_display: str     # "Knicks -5.5" (explicit!)
    
    # Context for logging/debugging
    reasoning: str


def select_sharp_side_spread(
    home_team: str,
    away_team: str,
    market_spread_home: float,
    model_spread: float,
    volatility: VolatilityLevel,
    market_odds_home: int = -110,
    market_odds_away: int = -110
) -> SharpSideSelection:
    """
    Select sharp side for spread market using LOCKED MODEL SPREAD LOGIC
    
    LOCKED LOGIC:
    - Model spread is SIGNED (+ = underdog, - = favorite)
    - If model_spread > market_spread → Sharp side = FAVORITE
    - If model_spread < market_spread → Sharp side = UNDERDOG
    
    Args:
        home_team: Home team name
        away_team: Away team name
        market_spread_home: Market spread from HOME perspective (negative = home favored)
        model_spread: SIGNED model spread (+ = underdog, - = favorite)
        volatility: Volatility level
        market_odds_home: Home team odds (default -110)
        market_odds_away: Away team odds (default -110)
    
    Returns:
        SharpSideSelection with all context and display strings
    
    Example:
        Market: Hawks +5.5, Knicks -5.5
        Model Spread: +12.3
        
        model_spread (+12.3) > market_spread (+5.5) → Sharp = FAVORITE (Knicks -5.5)
    """
    # Calculate away spread (always opposite of home)
    market_spread_away = -market_spread_home
    
    # Determine market favorite/underdog
    if market_spread_home < 0:
        # Home team is favorite
        market_favorite = home_team
        market_underdog = away_team
        market_spread_underdog = market_spread_away  # Positive
        market_spread_favorite = market_spread_home  # Negative
    else:
        # Away team is favorite (or pick'em)
        market_favorite = away_team
        market_underdog = home_team
        market_spread_underdog = market_spread_home  # Positive
        market_spread_favorite = market_spread_away  # Negative
    
    # PRIMARY SHARP RULE (LOCKED)
    # Normalize model_spread to absolute value for comparison
    # model_spread sign indicates direction: + underdog, - favorite
    model_spread_abs = abs(model_spread)
    
    edge_magnitude = abs(model_spread_abs - market_spread_underdog)
    
    if model_spread_abs > market_spread_underdog:
        # Model expects larger margin than market → Sharp side = FAVORITE
        sharp_side_team = market_favorite
        sharp_side_line = market_spread_favorite
        sharp_action = "LAY_POINTS"
        reason = f"Model projects {market_underdog} to lose by more ({model_spread_abs:.1f} pts) than market prices ({market_spread_underdog:.1f} pts). Sharp side = FAVORITE."
        
    elif model_spread_abs < market_spread_underdog:
        # Model expects smaller margin than market → Sharp side = UNDERDOG
        sharp_side_team = market_underdog
        sharp_side_line = market_spread_underdog
        sharp_action = "TAKE_POINTS"
        reason = f"Model projects {market_underdog} to lose by less ({model_spread_abs:.1f} pts) than market prices ({market_spread_underdog:.1f} pts). Sharp side = UNDERDOG."
        
    else:
        # Model agrees with market → NO PLAY
        return SharpSideSelection(
            sharp_side="NO_SHARP_PLAY",
            recommended_bet="NO PLAY (model agrees with market)",
            sharp_action="NO_SHARP_PLAY",
            market_spread=market_spread_underdog,
            model_spread=model_spread,
            market_favorite=market_favorite,
            market_underdog=market_underdog,
            edge_magnitude=0.0,
            volatility_penalty=0.0,
            edge_after_penalty=0.0,
            market_spread_display=f"{market_underdog} +{market_spread_underdog:.1f}",
            model_spread_display=f"{market_underdog} {model_spread:+.1f}",
            sharp_side_display="NO PLAY",
            reasoning="Model spread matches market spread"
        )
    
    # Apply volatility penalty if laying points
    penalty = 0.0
    if sharp_action == "LAY_POINTS":
        spread_size = abs(sharp_side_line)
        
        # Penalty increases with volatility
        if volatility == VolatilityLevel.LOW:
            penalty = 0.0
        elif volatility == VolatilityLevel.MEDIUM:
            penalty = 0.5
        elif volatility == VolatilityLevel.HIGH:
            penalty = 1.0
        elif volatility == VolatilityLevel.EXTREME:
            penalty = 2.0
        
        # Additional penalty for large spreads
        if spread_size > 10.0:
            penalty += 0.5
        elif spread_size > 7.0:
            penalty += 0.25
        
        if penalty > 0:
            reason += f" | Volatility penalty: -{penalty:.1f} pts (laying points with {volatility.value} volatility)"
    
    edge_after_penalty = edge_magnitude - penalty
    
    # Check if edge remains after penalty
    if edge_after_penalty <= 0:
        return SharpSideSelection(
            sharp_side="NO_SHARP_PLAY",
            recommended_bet=f"NO PLAY (edge eliminated by volatility penalty: {edge_magnitude:.1f} - {penalty:.1f} = {edge_after_penalty:.1f})",
            sharp_action="NO_SHARP_PLAY",
            market_spread=market_spread_underdog,
            model_spread=model_spread,
            market_favorite=market_favorite,
            market_underdog=market_underdog,
            edge_magnitude=edge_magnitude,
            volatility_penalty=penalty,
            edge_after_penalty=edge_after_penalty,
            market_spread_display=f"{market_underdog} +{market_spread_underdog:.1f}",
            model_spread_display=f"{market_underdog} {model_spread:+.1f}",
            sharp_side_display="NO PLAY",
            reasoning=reason
        )
    
    # Build display strings (MANDATORY)
    market_spread_display = f"{market_underdog} +{market_spread_underdog:.1f}"
    model_spread_display = f"{market_underdog} {model_spread:+.1f}"
    sharp_side_display = f"{sharp_side_team} {sharp_side_line:+.1f}"
    
    # Build recommended bet
    sharp_odds = market_odds_home if sharp_side_team == home_team else market_odds_away
    recommended_bet = f"{sharp_side_team} {sharp_side_line:+.1f} ({sharp_odds:+d})"
    
    return SharpSideSelection(
        sharp_side=sharp_side_display,
        recommended_bet=recommended_bet,
        sharp_action=sharp_action,
        market_spread=market_spread_underdog,
        model_spread=model_spread,
        market_favorite=market_favorite,
        market_underdog=market_underdog,
        edge_magnitude=edge_magnitude,
        volatility_penalty=penalty,
        edge_after_penalty=edge_after_penalty,
        market_spread_display=market_spread_display,
        model_spread_display=model_spread_display,
        sharp_side_display=sharp_side_display,
        reasoning=reason
    )


def determine_favored_team_spread(
    team_a_cover_prob: float,
    team_b_cover_prob: float,
    team_a_name: str,
    team_b_name: str,
    spread_team_a: float,
    spread_team_b: float
) -> Tuple[str, str, str]:
    """
    DEPRECATED: Use select_sharp_side_spread() instead
    
    This function used old logic. New logic uses model_spread directly.
    """
    raise DeprecationWarning("Use select_sharp_side_spread() with model_spread parameter")


def apply_volatility_penalty(
    compressed_edge: float,
    points_side: str,
    volatility: VolatilityLevel,
    spread_size: float
) -> Tuple[float, float]:
    """
    DEPRECATED: Volatility penalty now integrated into select_sharp_side_spread()
    """
    raise DeprecationWarning("Volatility penalty integrated into select_sharp_side_spread()")


def select_sharp_side_total(
    over_prob: float,
    under_prob: float,
    total_line: float,
    compressed_edge: float,
    volatility: VolatilityLevel,
    over_odds: int = -110,
    under_odds: int = -110
) -> SharpSideSelection:
    """
    Select sharp side for totals market
    
    Totals don't have model_spread concept - use probability directly
    """
    # Determine which side model favors
    if over_prob > under_prob:
        favored_side = "OVER"
        sharp_action = "OVER"
        sharp_odds = over_odds
        reasoning = f"Model favors OVER {total_line} with {over_prob*100:.1f}% probability"
    else:
        favored_side = "UNDER"
        sharp_action = "UNDER"
        sharp_odds = under_odds
        reasoning = f"Model favors UNDER {total_line} with {under_prob*100:.1f}% probability"
    
    recommended_bet = f"{favored_side} {total_line} ({sharp_odds:+d})"
    
    # Display strings
    market_spread_display = f"Total: {total_line}"
    model_spread_display = f"Model favors: {favored_side}"
    sharp_side_display = f"{favored_side} {total_line}"
    
    return SharpSideSelection(
        sharp_side=sharp_side_display,
        recommended_bet=recommended_bet,
        sharp_action=sharp_action,
        market_spread=total_line,
        model_spread=0.0,  # N/A for totals
        market_favorite="N/A",
        market_underdog="N/A",
        edge_magnitude=compressed_edge,
        volatility_penalty=0.0,
        edge_after_penalty=compressed_edge,
        market_spread_display=market_spread_display,
        model_spread_display=model_spread_display,
        sharp_side_display=sharp_side_display,
        reasoning=reasoning
    )


def select_sharp_side_moneyline(
    team_a_win_prob: float,
    team_b_win_prob: float,
    team_a_name: str,
    team_b_name: str,
    compressed_edge: float,
    team_a_odds: int = -110,
    team_b_odds: int = -110
) -> SharpSideSelection:
    """
    Select sharp side for moneyline market
    
    Moneyline is straightforward - bet the team model favors
    """
    # Determine which team model favors
    if team_a_win_prob > team_b_win_prob:
        favored_team = team_a_name
        sharp_odds = team_a_odds
        reasoning = f"Model favors {team_a_name} to win with {team_a_win_prob*100:.1f}% probability"
    else:
        favored_team = team_b_name
        sharp_odds = team_b_odds
        reasoning = f"Model favors {team_b_name} to win with {team_b_win_prob*100:.1f}% probability"
    
    recommended_bet = f"{favored_team} ML ({sharp_odds:+d})"
    
    # Display strings
    market_spread_display = f"{team_a_name} ({team_a_odds:+d}) vs {team_b_name} ({team_b_odds:+d})"
    model_spread_display = f"Model favors: {favored_team}"
    sharp_side_display = f"{favored_team} ML"
    
    return SharpSideSelection(
        sharp_side=sharp_side_display,
        recommended_bet=recommended_bet,
        sharp_action="ML",
        market_spread=0.0,  # N/A for ML
        model_spread=0.0,  # N/A for ML
        market_favorite="N/A",
        market_underdog="N/A",
        edge_magnitude=compressed_edge,
        volatility_penalty=0.0,
        edge_after_penalty=compressed_edge,
        market_spread_display=market_spread_display,
        model_spread_display=model_spread_display,
        sharp_side_display=sharp_side_display,
        reasoning=reasoning
    )


def validate_sharp_side_alignment(
    edge_state: EdgeState,
    sharp_side_selection: Optional[SharpSideSelection]
) -> Tuple[bool, Optional[str]]:
    """
    Validate that sharp_side is set when edge_state is EDGE or LEAN
    
    Critical validation to prevent posting EDGE without sharp side
    
    Returns: (is_valid, error_message)
    """
    if edge_state in [EdgeState.EDGE, EdgeState.LEAN]:
        if sharp_side_selection is None:
            return False, "CRITICAL: edge_state is EDGE/LEAN but sharp_side not selected"
        
        if not sharp_side_selection.sharp_side or sharp_side_selection.sharp_side == "NO_SHARP_PLAY":
            return False, f"CRITICAL: edge_state is {edge_state.value} but sharp_side is {sharp_side_selection.sharp_side}"
        
        if sharp_side_selection.edge_after_penalty <= 0:
            return False, f"WARNING: edge_after_penalty is {sharp_side_selection.edge_after_penalty:.2f} but edge_state is {edge_state.value}"
    
    elif edge_state == EdgeState.NO_PLAY:
        if sharp_side_selection is not None and sharp_side_selection.sharp_side != "NO_SHARP_PLAY":
            return False, f"CRITICAL: edge_state is NO_PLAY but sharp_side is set to {sharp_side_selection.sharp_side}"
    
    return True, None


# Example usage patterns for documentation:
"""
■ SPREAD MARKET EXAMPLES

Example 1 — Positive Model Spread (Sharp = FAVORITE)
Market: Hawks +5.5, Knicks -5.5
Model Spread: +12.3

selection = select_sharp_side_spread(
    home_team="New York Knicks",
    away_team="Atlanta Hawks",
    market_spread_home=-5.5,  # Knicks are favorite
    model_spread=12.3,  # Positive = underdog (Hawks)
    volatility=VolatilityLevel.MEDIUM
)

# Result:
# sharp_side = "New York Knicks -5.5"
# sharp_action = "LAY_POINTS"
# market_spread_display = "Atlanta Hawks +5.5"
# model_spread_display = "Atlanta Hawks +12.3"
# sharp_side_display = "New York Knicks -5.5"
# reasoning = "Model projects Hawks to lose by more (12.3 pts) than market prices (5.5 pts). Sharp side = FAVORITE."

Example 2 — Negative Model Spread (Sharp = UNDERDOG)
Market: Hawks +5.5, Knicks -5.5
Model Spread: −3.2

selection = select_sharp_side_spread(
    home_team="New York Knicks",
    away_team="Atlanta Hawks",
    market_spread_home=-5.5,
    model_spread=-3.2,  # Negative = favorite (Knicks)
    volatility=VolatilityLevel.LOW
)

# Result:
# sharp_side = "Atlanta Hawks +5.5"
# sharp_action = "TAKE_POINTS"
# market_spread_display = "Atlanta Hawks +5.5"
# model_spread_display = "Atlanta Hawks -3.2"
# sharp_side_display = "Atlanta Hawks +5.5"
# reasoning = "Model projects Hawks to lose by less (3.2 pts) than market prices (5.5 pts). Sharp side = UNDERDOG."

■ TOTAL MARKET EXAMPLE

selection = select_sharp_side_total(
    over_prob=0.58,
    under_prob=0.42,
    total_line=220.5,
    compressed_edge=5.1,
    volatility=VolatilityLevel.LOW
)

# Result:
# sharp_side = "OVER 220.5"
# sharp_action = "OVER"

■ MONEYLINE MARKET EXAMPLE

selection = select_sharp_side_moneyline(
    team_a_win_prob=0.56,
    team_b_win_prob=0.44,
    team_a_name="New York Yankees",
    team_b_name="Boston Red Sox",
    compressed_edge=3.8,
    team_a_odds=-140,
    team_b_odds=+120
)

# Result:
# sharp_side = "New York Yankees ML"
# sharp_action = "ML"
"""
