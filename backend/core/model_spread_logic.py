"""
MODEL SPREAD & SHARP SIDE LOGIC — LOCKED DEFINITION
====================================================
This module is the SINGLE SOURCE OF TRUTH for model spread interpretation.

🚨 LOCKED: Do NOT modify this logic without explicit approval.

CANONICAL RULE:
--------------
Model Spread is a SIGNED value relative to TEAM DIRECTION:
• Positive (+) Model Spread → Underdog spread
• Negative (−) Model Spread → Favorite spread

It is NOT:
• a delta vs market
• a probability
• a generic "edge score"

It IS: the model's implied spread direction and magnitude.

SHARP SIDE SELECTION (NON-NEGOTIABLE):
--------------------------------------
Let:
• market_spread = current betting line (favorite negative, underdog positive)
• model_spread = signed model output

Then:
• If model_spread > market_spread → market underestimates margin → Sharp side = FAVORITE
• If model_spread < market_spread → market overestimates margin → Sharp side = UNDERDOG

EXAMPLES:
---------
Example 1 — Positive Model Spread
  Market: Hawks +5.5, Knicks -5.5
  Model Spread: +12.3 (from underdog perspective)
  
  Interpretation:
  - Model expects Hawks to lose by ~12
  - Market only pricing them to lose by ~5.5
  - Market is too generous to the underdog
  - model_spread (+12.3) > market_spread (+5.5) → Sharp side = FAVORITE (Knicks -5.5)

Example 2 — Negative Model Spread
  Market: Hawks +5.5, Knicks -5.5
  Model Spread: −3.2 (from favorite perspective)
  
  Interpretation:
  - Model thinks Knicks win by only ~3 points
  - Market has Knicks -5.5
  - Market is overpricing the favorite
  - model_spread (-3.2) < market_spread (0) → Sharp side = UNDERDOG (Hawks +5.5)
"""

from typing import Dict, Any, Optional, Literal, Tuple
from dataclasses import dataclass
from enum import Enum


class SharpSide(str, Enum):
    """Sharp side designation"""
    FAVORITE = "FAV"
    UNDERDOG = "DOG"


@dataclass
class SpreadContext:
    """
    Complete spread context with team labels
    
    MANDATORY FIELDS for display:
    - market_spread_display: "Hawks +5.5" or "Knicks -5.5"
    - model_spread_display: "Hawks +12.3" (with team label!)
    - sharp_side_display: "Knicks -5.5" (explicit pick!)
    """
    # Team info
    home_team: str
    away_team: str
    
    # Market spreads (from home team perspective by convention)
    market_spread_home: float  # e.g., -5.5 (home is favorite)
    market_spread_away: float  # e.g., +5.5 (away is underdog)
    
    # Model spread (signed, from underdog perspective)
    model_spread: float  # Positive = underdog, Negative = favorite
    
    # Derived: Which team is favored
    market_favorite: str
    market_underdog: str
    
    # Derived: Sharp side
    sharp_side: SharpSide
    sharp_side_team: str
    sharp_side_line: float
    
    # Display strings (MANDATORY)
    market_spread_display: str    # "Hawks +5.5"
    model_spread_display: str     # "Hawks +12.3" (with team!)
    sharp_side_display: str       # "Knicks -5.5" (explicit!)
    
    # Edge metrics
    edge_points: float
    edge_direction: str  # "FAV" or "DOG"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "home_team": self.home_team,
            "away_team": self.away_team,
            "market_spread_home": self.market_spread_home,
            "market_spread_away": self.market_spread_away,
            "model_spread": self.model_spread,
            "market_favorite": self.market_favorite,
            "market_underdog": self.market_underdog,
            "sharp_side": self.sharp_side.value,
            "sharp_side_team": self.sharp_side_team,
            "sharp_side_line": self.sharp_side_line,
            "market_spread_display": self.market_spread_display,
            "model_spread_display": self.model_spread_display,
            "sharp_side_display": self.sharp_side_display,
            "edge_points": self.edge_points,
            "edge_direction": self.edge_direction,
        }


def determine_sharp_side(
    model_spread: float,
    market_spread_underdog: float
) -> SharpSide:
    """
    UNIVERSAL SHARP SIDE SELECTION RULE (NON-NEGOTIABLE)
    
    Args:
        model_spread: Signed model output (+underdog, -favorite)
        market_spread_underdog: Market spread from underdog perspective (always positive)
    
    Returns:
        SharpSide.FAVORITE or SharpSide.UNDERDOG
    
    Rule:
        If model_spread > market_spread → Sharp side = FAVORITE
        If model_spread < market_spread → Sharp side = UNDERDOG
    """
    if model_spread > market_spread_underdog:
        # Model expects bigger loss for underdog than market prices
        # → Market is too generous to underdog
        # → Sharp side = FAVORITE
        return SharpSide.FAVORITE
    else:
        # Model expects smaller loss for underdog than market prices
        # → Market is overpricing the favorite
        # → Sharp side = UNDERDOG
        return SharpSide.UNDERDOG


def calculate_spread_context(
    home_team: str,
    away_team: str,
    market_spread_home: float,
    model_spread: float
) -> SpreadContext:
    """
    Calculate complete spread context with team labels and sharp side
    
    Args:
        home_team: Home team name
        away_team: Away team name
        market_spread_home: Market spread from HOME team perspective (negative = home favored)
        model_spread: Signed model spread (+underdog, -favorite)
    
    Returns:
        SpreadContext with all required display strings
    
    Example:
        home_team = "Knicks"
        away_team = "Hawks"
        market_spread_home = -5.5 (Knicks favored by 5.5)
        model_spread = +12.3 (model thinks underdog loses by 12)
        
        Returns context showing:
        - Market: Hawks +5.5
        - Model: Hawks +12.3
        - Sharp Side: Knicks -5.5
    """
    # Calculate away spread (always opposite of home)
    market_spread_away = -market_spread_home
    
    # Determine market favorite/underdog
    if market_spread_home < 0:
        market_favorite = home_team
        market_underdog = away_team
        market_spread_underdog = market_spread_away  # Positive
        market_spread_favorite = market_spread_home  # Negative
    else:
        market_favorite = away_team
        market_underdog = home_team
        market_spread_underdog = market_spread_home  # Positive
        market_spread_favorite = market_spread_away  # Negative
    
    # Determine sharp side using LOCKED RULE
    sharp_side = determine_sharp_side(model_spread, market_spread_underdog)
    
    # Calculate edge
    edge_points = abs(model_spread - market_spread_underdog)
    
    # Determine sharp side team and line
    if sharp_side == SharpSide.FAVORITE:
        sharp_side_team = market_favorite
        sharp_side_line = market_spread_favorite
        edge_direction = "FAV"
    else:
        sharp_side_team = market_underdog
        sharp_side_line = market_spread_underdog
        edge_direction = "DOG"
    
    # Build display strings (MANDATORY)
    def format_spread(value: float) -> str:
        return f"{'+' if value >= 0 else ''}{value:.1f}"
    
    market_spread_display = f"{market_underdog} {format_spread(market_spread_underdog)}"
    model_spread_display = f"{market_underdog} {format_spread(model_spread)}"
    sharp_side_display = f"{sharp_side_team} {format_spread(sharp_side_line)}"
    
    return SpreadContext(
        home_team=home_team,
        away_team=away_team,
        market_spread_home=market_spread_home,
        market_spread_away=market_spread_away,
        model_spread=model_spread,
        market_favorite=market_favorite,
        market_underdog=market_underdog,
        sharp_side=sharp_side,
        sharp_side_team=sharp_side_team,
        sharp_side_line=sharp_side_line,
        market_spread_display=market_spread_display,
        model_spread_display=model_spread_display,
        sharp_side_display=sharp_side_display,
        edge_points=edge_points,
        edge_direction=edge_direction
    )


def format_spread_for_telegram(context: SpreadContext, include_reasoning: bool = True) -> str:
    """
    Format spread analysis for Telegram output
    
    🚨 RULE: Telegram must ALWAYS show sharp side explicitly
    """
    lines = [
        f"📊 SPREAD ANALYSIS",
        f"",
        f"Market: {context.market_spread_display}",
        f"Model: {context.model_spread_display}",
        f"",
        f"🎯 Sharp Side: {context.sharp_side_display}",
        f"Edge: {context.edge_points:.1f} pts"
    ]
    
    if include_reasoning:
        if context.sharp_side == SharpSide.FAVORITE:
            lines.append(f"")
            lines.append(f"Reason: Lay the favorite - Model projects larger margin than market prices")
        else:
            lines.append(f"")
            lines.append(f"Reason: Take the underdog - Model projects smaller margin than market prices")
    
    return "\n".join(lines)


def format_spread_for_ai_assistant(context: SpreadContext) -> str:
    """
    Format spread analysis for AI assistant responses
    
    🚨 AI ASSISTANT RULE: Must explicitly state the Sharp Side
    """
    if context.sharp_side == SharpSide.FAVORITE:
        side_text = "FAVORITE"
        reasoning = f"The model projects {context.market_underdog} to lose by more ({abs(context.model_spread):.1f} pts) than the market prices ({abs(context.market_spread_home):.1f} pts). This means the market is being too generous to the underdog."
    else:
        side_text = "UNDERDOG"
        reasoning = f"The model projects {context.market_underdog} to lose by less ({abs(context.model_spread):.1f} pts) than the market prices ({abs(context.market_spread_home):.1f} pts). This means the market is overpricing the favorite."
    
    return f"""**Spread Analysis**

Market Spread: {context.market_spread_display}
Model Spread: {context.model_spread_display}

**Sharp Side: {side_text} ({context.sharp_side_display})**

{reasoning}

Edge: {context.edge_points:.1f} points"""


# =============================================================================
# VALIDATION HELPERS
# =============================================================================

def validate_spread_inputs(
    model_spread: Optional[float],
    market_spread: Optional[float]
) -> Tuple[bool, Optional[str]]:
    """
    Validate spread inputs before processing
    
    Returns:
        (is_valid, error_message)
    """
    if model_spread is None:
        return False, "Model spread is missing"
    
    if market_spread is None:
        return False, "Market spread is missing"
    
    if abs(market_spread) > 50:
        return False, f"Market spread {market_spread} seems invalid (>50 points)"
    
    if abs(model_spread) > 50:
        return False, f"Model spread {model_spread} seems invalid (>50 points)"
    
    return True, None


def get_spread_confidence_reason(context: SpreadContext) -> str:
    """
    Generate confidence reasoning for spread edge
    """
    magnitude = context.edge_points
    
    if magnitude >= 6.0:
        return f"Strong {magnitude:.1f}pt edge — high confidence in {context.sharp_side_display}"
    elif magnitude >= 3.0:
        return f"Moderate {magnitude:.1f}pt edge — medium confidence in {context.sharp_side_display}"
    else:
        return f"Small {magnitude:.1f}pt edge — low confidence, consider waiting for better number"


# =============================================================================
# EXPORTS FOR INTEGRATION
# =============================================================================

__all__ = [
    'SharpSide',
    'SpreadContext',
    'determine_sharp_side',
    'calculate_spread_context',
    'format_spread_for_telegram',
    'format_spread_for_ai_assistant',
    'validate_spread_inputs',
    'get_spread_confidence_reason',
]
