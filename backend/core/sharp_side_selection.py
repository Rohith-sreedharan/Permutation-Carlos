"""
Universal Sharp Side Selection

Prevents contradictions between model state and sharp side selection.
Solves the OKC/Spurs bug where model favored underdog but UI showed favorite.

Critical Rules:
1. Edges are prices, not teams
2. Sharp side determined by: favored_team + points_side
3. Volatility penalties for laying points
4. Separate logic for spread/total/moneyline markets
"""
from typing import Tuple, Optional, Dict
from dataclasses import dataclass
from .sport_configs import EdgeState, MarketType, VolatilityLevel


@dataclass
class SharpSideSelection:
    """Result of sharp side selection algorithm"""
    sharp_side: str  # Team name or OVER/UNDER
    recommended_bet: str  # Full description
    favored_team: str  # Which team model favors
    points_side: str  # FAVORITE or UNDERDOG for spreads
    volatility_penalty: float  # Points added for volatility
    edge_after_penalty: float  # Edge remaining after volatility adjustment
    
    # Context for logging/debugging
    raw_model_favorite: str
    market_odds: str
    reasoning: str


def determine_favored_team_spread(
    team_a_cover_prob: float,
    team_b_cover_prob: float,
    team_a_name: str,
    team_b_name: str,
    spread_team_a: float,
    spread_team_b: float
) -> Tuple[str, str, str]:
    """
    Determine which team the model favors and on which side
    
    Args:
        team_a_cover_prob: Probability team A covers their spread
        team_b_cover_prob: Probability team B covers their spread
        team_a_name: Team A name
        team_b_name: Team B name
        spread_team_a: Team A spread (negative if favorite)
        spread_team_b: Team B spread (positive if underdog)
    
    Returns: (favored_team, points_side, reasoning)
        favored_team: Which team model favors
        points_side: "FAVORITE" or "UNDERDOG"
        reasoning: Explanation
    """
    # Identify which team is the favorite by spread
    if spread_team_a < 0:
        market_favorite = team_a_name
        market_underdog = team_b_name
    else:
        market_favorite = team_b_name
        market_underdog = team_a_name
    
    # Determine which team model favors
    if team_a_cover_prob > team_b_cover_prob:
        favored_team = team_a_name
        cover_advantage = team_a_cover_prob - team_b_cover_prob
    else:
        favored_team = team_b_name
        cover_advantage = team_b_cover_prob - team_a_cover_prob
    
    # Determine points_side
    if favored_team == market_favorite:
        points_side = "FAVORITE"
        reasoning = f"Model favors {favored_team} (market favorite) covering {spread_team_a if favored_team == team_a_name else spread_team_b}"
    else:
        points_side = "UNDERDOG"
        reasoning = f"Model favors {favored_team} (market underdog) getting {spread_team_a if favored_team == team_a_name else spread_team_b} points"
    
    return favored_team, points_side, reasoning


def apply_volatility_penalty(
    compressed_edge: float,
    points_side: str,
    volatility: VolatilityLevel,
    spread_size: float
) -> Tuple[float, float]:
    """
    Apply volatility penalty when laying points
    
    Critical: Laying points with high volatility is dangerous
    
    Args:
        compressed_edge: Edge after compression
        points_side: "FAVORITE" or "UNDERDOG"
        volatility: Volatility level
        spread_size: Absolute spread size
    
    Returns: (penalty_points, edge_after_penalty)
    """
    penalty = 0.0
    
    # Only apply penalty when LAYING points (betting favorite)
    if points_side == "FAVORITE":
        # Penalty increases with volatility
        if volatility == VolatilityLevel.LOW:
            penalty = 0.0
        elif volatility == VolatilityLevel.MEDIUM:
            penalty = 0.5  # 0.5% penalty
        elif volatility == VolatilityLevel.HIGH:
            penalty = 1.0  # 1.0% penalty
        elif volatility == VolatilityLevel.EXTREME:
            penalty = 2.0  # 2.0% penalty
        
        # Additional penalty for large spreads (blowout risk)
        if spread_size > 10.0:
            penalty += 0.5
        elif spread_size > 7.0:
            penalty += 0.25
    
    edge_after_penalty = compressed_edge - penalty
    
    return penalty, edge_after_penalty


def select_sharp_side_spread(
    team_a_cover_prob: float,
    team_b_cover_prob: float,
    team_a_name: str,
    team_b_name: str,
    spread_team_a: float,
    spread_team_b: float,
    compressed_edge: float,
    volatility: VolatilityLevel,
    market_odds_team_a: int,
    market_odds_team_b: int
) -> SharpSideSelection:
    """
    Select sharp side for spread market
    
    Returns: SharpSideSelection with all context
    """
    # Determine favored team and points side
    favored_team, points_side, reasoning = determine_favored_team_spread(
        team_a_cover_prob,
        team_b_cover_prob,
        team_a_name,
        team_b_name,
        spread_team_a,
        spread_team_b
    )
    
    # Determine spread size
    spread_size = abs(spread_team_a)
    
    # Apply volatility penalty
    penalty, edge_after_penalty = apply_volatility_penalty(
        compressed_edge,
        points_side,
        volatility,
        spread_size
    )
    
    # Build sharp side recommendation
    if favored_team == team_a_name:
        sharp_spread = spread_team_a
        sharp_odds = market_odds_team_a
    else:
        sharp_spread = spread_team_b
        sharp_odds = market_odds_team_b
    
    recommended_bet = f"{favored_team} {sharp_spread:+.1f} ({sharp_odds:+d})"
    market_odds_display = f"{team_a_name} {spread_team_a:+.1f} ({market_odds_team_a:+d}) vs {team_b_name} {spread_team_b:+.1f} ({market_odds_team_b:+d})"
    
    # Add penalty context to reasoning
    if penalty > 0:
        reasoning += f" | Volatility penalty: -{penalty:.1f}% (laying points with {volatility.value} volatility)"
    
    return SharpSideSelection(
        sharp_side=favored_team,
        recommended_bet=recommended_bet,
        favored_team=favored_team,
        points_side=points_side,
        volatility_penalty=penalty,
        edge_after_penalty=edge_after_penalty,
        raw_model_favorite=favored_team,
        market_odds=market_odds_display,
        reasoning=reasoning
    )


def select_sharp_side_total(
    over_prob: float,
    under_prob: float,
    total_line: float,
    compressed_edge: float,
    volatility: VolatilityLevel,
    over_odds: int,
    under_odds: int
) -> SharpSideSelection:
    """
    Select sharp side for totals market
    
    Totals don't have "laying points" concept, so no volatility penalty
    """
    # Determine which side model favors
    if over_prob > under_prob:
        favored_side = "OVER"
        prob_advantage = over_prob - under_prob
        sharp_odds = over_odds
        reasoning = f"Model favors OVER {total_line} with {over_prob*100:.1f}% probability"
    else:
        favored_side = "UNDER"
        prob_advantage = under_prob - over_prob
        sharp_odds = under_odds
        reasoning = f"Model favors UNDER {total_line} with {under_prob*100:.1f}% probability"
    
    recommended_bet = f"{favored_side} {total_line} ({sharp_odds:+d})"
    market_odds_display = f"OVER {total_line} ({over_odds:+d}) / UNDER {total_line} ({under_odds:+d})"
    
    return SharpSideSelection(
        sharp_side=favored_side,
        recommended_bet=recommended_bet,
        favored_team=favored_side,  # OVER or UNDER
        points_side="N/A",
        volatility_penalty=0.0,
        edge_after_penalty=compressed_edge,
        raw_model_favorite=favored_side,
        market_odds=market_odds_display,
        reasoning=reasoning
    )


def select_sharp_side_moneyline(
    team_a_win_prob: float,
    team_b_win_prob: float,
    team_a_name: str,
    team_b_name: str,
    compressed_edge: float,
    team_a_odds: int,
    team_b_odds: int
) -> SharpSideSelection:
    """
    Select sharp side for moneyline market
    
    Moneyline is straightforward - bet the team model favors
    """
    # Determine which team model favors
    if team_a_win_prob > team_b_win_prob:
        favored_team = team_a_name
        win_advantage = team_a_win_prob - team_b_win_prob
        sharp_odds = team_a_odds
        reasoning = f"Model favors {team_a_name} to win with {team_a_win_prob*100:.1f}% probability"
    else:
        favored_team = team_b_name
        win_advantage = team_b_win_prob - team_a_win_prob
        sharp_odds = team_b_odds
        reasoning = f"Model favors {team_b_name} to win with {team_b_win_prob*100:.1f}% probability"
    
    recommended_bet = f"{favored_team} ML ({sharp_odds:+d})"
    market_odds_display = f"{team_a_name} ML ({team_a_odds:+d}) vs {team_b_name} ML ({team_b_odds:+d})"
    
    return SharpSideSelection(
        sharp_side=favored_team,
        recommended_bet=recommended_bet,
        favored_team=favored_team,
        points_side="N/A",
        volatility_penalty=0.0,
        edge_after_penalty=compressed_edge,
        raw_model_favorite=favored_team,
        market_odds=market_odds_display,
        reasoning=reasoning
    )


def validate_sharp_side_alignment(
    edge_state: EdgeState,
    sharp_side_selection: Optional[SharpSideSelection]
) -> Tuple[bool, Optional[str]]:
    """
    Validate that sharp_side is set when edge_state is EDGE or LEAN
    
    Critical validation to prevent OKC/Spurs type bugs
    
    Returns: (is_valid, error_message)
    """
    if edge_state in [EdgeState.EDGE, EdgeState.LEAN]:
        if sharp_side_selection is None:
            return False, "CRITICAL: edge_state is EDGE/LEAN but sharp_side not selected"
        
        if not sharp_side_selection.sharp_side:
            return False, "CRITICAL: edge_state is EDGE/LEAN but sharp_side is empty"
        
        if sharp_side_selection.edge_after_penalty <= 0:
            return False, f"WARNING: edge_after_penalty is {sharp_side_selection.edge_after_penalty:.2f}% but edge_state is {edge_state.value}"
    
    elif edge_state == EdgeState.NO_PLAY:
        if sharp_side_selection is not None and sharp_side_selection.sharp_side:
            return False, f"CRITICAL: edge_state is NO_PLAY but sharp_side is set to {sharp_side_selection.sharp_side}"
    
    return True, None


# Example usage patterns for documentation:
"""
# SPREAD MARKET EXAMPLE
# Game: Oklahoma City Thunder @ San Antonio Spurs
# Market: Spurs -2.5 (-110) vs Thunder +2.5 (-110)
# Simulation: Thunder 53% to cover, Spurs 47% to cover

selection = select_sharp_side_spread(
    team_a_cover_prob=0.47,  # Spurs
    team_b_cover_prob=0.53,  # Thunder
    team_a_name="San Antonio Spurs",
    team_b_name="Oklahoma City Thunder",
    spread_team_a=-2.5,  # Spurs are favorite
    spread_team_b=+2.5,  # Thunder are underdog
    compressed_edge=4.2,  # 4.2% edge after compression
    volatility=VolatilityLevel.MEDIUM,
    market_odds_team_a=-110,
    market_odds_team_b=-110
)

# Result:
# sharp_side = "Oklahoma City Thunder"
# favored_team = "Oklahoma City Thunder"
# points_side = "UNDERDOG"
# recommended_bet = "Oklahoma City Thunder +2.5 (-110)"
# reasoning = "Model favors Oklahoma City Thunder (market underdog) getting +2.5 points"

# TOTAL MARKET EXAMPLE
selection = select_sharp_side_total(
    over_prob=0.58,
    under_prob=0.42,
    total_line=220.5,
    compressed_edge=5.1,
    volatility=VolatilityLevel.LOW,
    over_odds=-110,
    under_odds=-110
)

# Result:
# sharp_side = "OVER"
# recommended_bet = "OVER 220.5 (-110)"

# MONEYLINE MARKET EXAMPLE
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
# sharp_side = "New York Yankees"
# recommended_bet = "New York Yankees ML (-140)"
"""
