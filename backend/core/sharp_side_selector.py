"""
SHARP SIDE SELECTOR — UNIVERSAL IMPLEMENTATION
===============================================
Determines the "sharp side" for any game/market combination.

Sharp side selection is the FINAL determination of which side to back.
This runs AFTER edge evaluation and BEFORE signal posting.

SELECTION HIERARCHY (in order of priority):
1. Consensus Direction — If all models agree, follow consensus
2. RCL Override — Regression model can override if confidence > 75%
3. Home/Away Bias — Sport-specific bias for spread markets
4. Efficient Market Default — If split, lean toward efficient market

SPORTS-SPECIFIC RULES:
- NFL: Home field advantage matters, key number protection
- NBA: Road favorites often undervalued
- MLB: Home underdogs historically profitable
- NHL: Road favorites in back-to-backs have edge
- NCAAF: Home dogs > +7 have historical edge
- NCAAB: Conference familiarity matters

CRITICAL CONSTRAINT:
Sharp side MUST be the side that is ACTIONABLE.
If our model says "take the under" but the only EDGE is on the over,
we do NOT post (NO_PLAY). We never flip sides to fit an edge.
"""

from typing import Dict, Any, Optional, Tuple, List
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
import logging

logger = logging.getLogger(__name__)


# ============================================================================
# ENUMS
# ============================================================================

class SelectionSource(str, Enum):
    """Source of sharp side selection"""
    CONSENSUS = "CONSENSUS"           # All models agree
    RCL_OVERRIDE = "RCL_OVERRIDE"     # RCL model override
    HISTORICAL_BIAS = "HISTORICAL_BIAS"  # Sport-specific bias
    EFFICIENT_MARKET = "EFFICIENT_MARKET"  # Market efficiency default
    CLV_OPTIMIZED = "CLV_OPTIMIZED"   # CLV signal override


class Side(str, Enum):
    """Market sides"""
    HOME = "HOME"
    AWAY = "AWAY"
    OVER = "OVER"
    UNDER = "UNDER"


# ============================================================================
# DATA MODELS
# ============================================================================

@dataclass
class ModelPrediction:
    """Single model's prediction"""
    model_name: str
    predicted_side: Side
    confidence: float  # 0.0 - 1.0
    edge_points: float
    win_prob: float


@dataclass
class GameContext:
    """Context about the game"""
    sport: str
    game_id: str
    home_team: str
    away_team: str
    game_time: datetime
    
    # Team metrics
    home_win_pct: float = 0.5
    away_win_pct: float = 0.5
    home_ats_record: float = 0.5  # Against the spread
    away_ats_record: float = 0.5
    
    # Situational
    is_back_to_back_home: bool = False
    is_back_to_back_away: bool = False
    is_divisional: bool = False
    is_conference: bool = False
    is_rivalry: bool = False
    
    # Market
    home_is_favorite: bool = True
    spread_value: float = 0.0
    total_value: float = 0.0


@dataclass
class SharpSideSelection:
    """Result of sharp side selection"""
    market_type: str  # SPREAD, TOTAL, MONEYLINE
    selected_side: Side
    source: SelectionSource
    confidence: float
    
    # Details
    consensus_count: int = 0
    total_models: int = 0
    override_reason: Optional[str] = None
    
    # Validation
    is_actionable: bool = True
    edge_on_selected_side: bool = True
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "market_type": self.market_type,
            "selected_side": self.selected_side.value,
            "source": self.source.value,
            "confidence": self.confidence,
            "consensus_count": self.consensus_count,
            "total_models": self.total_models,
            "override_reason": self.override_reason,
            "is_actionable": self.is_actionable,
            "edge_on_selected_side": self.edge_on_selected_side,
        }


# ============================================================================
# SPORT-SPECIFIC BIASES (HISTORICAL DATA)
# ============================================================================

HISTORICAL_BIASES = {
    # NFL - Home field ~3 points, but road favorites often undervalued
    "americanfootball_nfl": {
        "home_advantage": 2.5,
        "road_favorite_edge": True,  # Road favorites cover more than expected
        "key_numbers": [3.0, 7.0, 10.0],
        "dog_threshold": 7.0,  # Home dogs > +7 have edge
    },
    
    # NBA - Road favorites historically profitable
    "basketball_nba": {
        "home_advantage": 2.5,
        "road_favorite_edge": True,
        "back_to_back_penalty": 3.0,  # Teams on B2B lose ~3 points
    },
    
    # MLB - Home underdogs profitable, especially vs high-priced favorites
    "baseball_mlb": {
        "home_advantage": 0.5,  # MLB has less home advantage
        "home_underdog_edge": True,  # Home dogs +150 or worse have edge
        "price_threshold": 150,  # +150 underdog threshold
    },
    
    # NHL - Road favorites on back-to-backs
    "icehockey_nhl": {
        "home_advantage": 0.15,  # ~0.15 goals
        "road_favorite_edge": True,
        "goalie_matters": True,  # Backup vs starter is critical
    },
    
    # NCAAF - Home dogs > +7 profitable, especially in conference
    "americanfootball_ncaaf": {
        "home_advantage": 3.0,
        "home_dog_edge": True,
        "dog_threshold": 7.0,
        "conference_matters": True,
    },
    
    # NCAAB - Conference familiarity, home court strong
    "basketball_ncaab": {
        "home_advantage": 4.0,  # Stronger in college
        "conference_edge": True,
        "tournament_adjustment": True,
    },
}


# ============================================================================
# SHARP SIDE SELECTOR
# ============================================================================

class SharpSideSelector:
    """
    Determines the sharp side for betting
    
    This is the final arbiter of which side to back.
    """
    
    def __init__(self, db=None):
        self.db = db
    
    # ========================================================================
    # MAIN SELECTION METHOD
    # ========================================================================
    
    def select_sharp_side(
        self,
        market_type: str,
        predictions: List[ModelPrediction],
        context: GameContext,
        edge_result: Optional[Dict[str, Any]] = None
    ) -> SharpSideSelection:
        """
        Select the sharp side for a market
        
        Args:
            market_type: SPREAD, TOTAL, MONEYLINE
            predictions: List of model predictions
            context: Game context
            edge_result: Edge evaluation result (if available)
        
        Returns:
            SharpSideSelection with final determination
        """
        # Step 1: Check consensus
        consensus_side, consensus_count = self._check_consensus(predictions)
        total_models = len(predictions)
        
        if consensus_side and consensus_count == total_models:
            # Full consensus - use it
            avg_confidence = sum(p.confidence for p in predictions) / total_models
            return SharpSideSelection(
                market_type=market_type,
                selected_side=consensus_side,
                source=SelectionSource.CONSENSUS,
                confidence=avg_confidence,
                consensus_count=consensus_count,
                total_models=total_models,
            )
        
        # Step 2: Check for RCL override
        rcl_override = self._check_rcl_override(predictions)
        if rcl_override:
            return SharpSideSelection(
                market_type=market_type,
                selected_side=rcl_override[0],
                source=SelectionSource.RCL_OVERRIDE,
                confidence=rcl_override[1],
                consensus_count=consensus_count or 0,
                total_models=total_models,
                override_reason="RCL model confidence > 75%",
            )
        
        # Step 3: Check historical bias
        bias_side = self._apply_historical_bias(market_type, context)
        if bias_side:
            return SharpSideSelection(
                market_type=market_type,
                selected_side=bias_side[0],
                source=SelectionSource.HISTORICAL_BIAS,
                confidence=bias_side[1],
                consensus_count=consensus_count or 0,
                total_models=total_models,
                override_reason=bias_side[2],
            )
        
        # Step 4: Efficient market default
        default_side = self._efficient_market_default(market_type, predictions, context)
        return SharpSideSelection(
            market_type=market_type,
            selected_side=default_side,
            source=SelectionSource.EFFICIENT_MARKET,
            confidence=0.50,  # No edge in tie
            consensus_count=consensus_count or 0,
            total_models=total_models,
            override_reason="Split decision - market default",
        )
    
    # ========================================================================
    # CONSENSUS DETECTION
    # ========================================================================
    
    def _check_consensus(
        self,
        predictions: List[ModelPrediction]
    ) -> Tuple[Optional[Side], int]:
        """Check if models have consensus"""
        if not predictions:
            return None, 0
        
        # Count sides
        side_counts: Dict[Side, int] = {}
        for pred in predictions:
            side_counts[pred.predicted_side] = side_counts.get(pred.predicted_side, 0) + 1
        
        # Find majority
        max_count = max(side_counts.values())
        majority_side = None
        for side, count in side_counts.items():
            if count == max_count:
                majority_side = side
                break
        
        return majority_side, max_count
    
    # ========================================================================
    # RCL OVERRIDE CHECK
    # ========================================================================
    
    def _check_rcl_override(
        self,
        predictions: List[ModelPrediction]
    ) -> Optional[Tuple[Side, float]]:
        """Check if RCL model should override"""
        for pred in predictions:
            if pred.model_name.lower() in ("rcl", "regression", "rcl_model"):
                if pred.confidence >= 0.75:
                    return pred.predicted_side, pred.confidence
        return None
    
    # ========================================================================
    # HISTORICAL BIAS APPLICATION
    # ========================================================================
    
    def _apply_historical_bias(
        self,
        market_type: str,
        context: GameContext
    ) -> Optional[Tuple[Side, float, str]]:
        """Apply sport-specific historical bias"""
        bias_config = HISTORICAL_BIASES.get(context.sport)
        if not bias_config:
            return None
        
        # NFL/NCAAF: Home dogs > threshold
        if context.sport in ("americanfootball_nfl", "americanfootball_ncaaf"):
            threshold = bias_config.get("dog_threshold", 7.0)
            if market_type == "SPREAD" and not context.home_is_favorite:
                if context.spread_value >= threshold:
                    return Side.HOME, 0.55, f"Home dog +{context.spread_value} (historical edge)"
        
        # MLB: Home underdogs at big prices
        if context.sport == "baseball_mlb":
            if market_type == "MONEYLINE" and not context.home_is_favorite:
                if bias_config.get("home_underdog_edge"):
                    # Would need odds data - simplified check
                    return Side.HOME, 0.52, "Home underdog (MLB historical edge)"
        
        # NBA/NHL: Road favorites
        if context.sport in ("basketball_nba", "icehockey_nhl"):
            if market_type == "SPREAD" and not context.home_is_favorite:
                # Away team is favorite
                if bias_config.get("road_favorite_edge"):
                    return Side.AWAY, 0.53, "Road favorite (historical edge)"
        
        return None
    
    # ========================================================================
    # EFFICIENT MARKET DEFAULT
    # ========================================================================
    
    def _efficient_market_default(
        self,
        market_type: str,
        predictions: List[ModelPrediction],
        context: GameContext
    ) -> Side:
        """Default to efficient market side when split"""
        if market_type in ("SPREAD", "MONEYLINE"):
            # Default to home in splits
            return Side.HOME
        else:
            # Totals - slight lean toward under (more efficient historically)
            return Side.UNDER
    
    # ========================================================================
    # VALIDATION
    # ========================================================================
    
    def validate_selection_vs_edge(
        self,
        selection: SharpSideSelection,
        edge_side: Optional[Side]
    ) -> SharpSideSelection:
        """
        Validate that selected side matches edge side
        
        CRITICAL: We do NOT flip sides to match edges.
        If selection != edge side, this is a NO_PLAY.
        """
        if edge_side is None:
            selection.edge_on_selected_side = False
            selection.is_actionable = False
            return selection
        
        if selection.selected_side != edge_side:
            selection.edge_on_selected_side = False
            selection.is_actionable = False
            logger.info(
                f"Sharp side ({selection.selected_side.value}) != edge side ({edge_side.value}). "
                f"This is a NO_PLAY - we don't flip sides."
            )
        
        return selection


# ============================================================================
# SPREAD SELECTION HELPERS
# ============================================================================

def select_spread_side(
    model_line: float,
    market_line: float,
    home_team: str,
    away_team: str
) -> Tuple[str, Side]:
    """
    Select the sharp side on a spread
    
    Model line is what we think fair is.
    Market line is what the book is offering.
    
    Example:
        Model: Home -4.5
        Market: Home -6.5
        → We take Home (model says they're better than market thinks)
        
        Model: Away +3.0
        Market: Away +4.5
        → We take Away (getting more points than model says fair)
    """
    # Edge = Market - Model (for home perspective)
    # Positive edge = market overvalues home = take away
    # Negative edge = market undervalues home = take home
    
    edge = market_line - model_line
    
    if edge > 0:
        # Market giving away points vs model → take away side
        return f"{away_team} +{abs(market_line)}", Side.AWAY
    else:
        # Market taking points vs model → take home side
        if market_line < 0:
            return f"{home_team} {market_line}", Side.HOME
        else:
            return f"{home_team} +{market_line}", Side.HOME


def select_total_side(
    model_total: float,
    market_total: float
) -> Tuple[str, Side]:
    """
    Select the sharp side on a total
    
    Model total is what we project.
    Market total is what the book is offering.
    
    If model > market → Over
    If model < market → Under
    """
    if model_total > market_total:
        return f"Over {market_total}", Side.OVER
    else:
        return f"Under {market_total}", Side.UNDER


def select_moneyline_side(
    model_home_prob: float,
    market_home_prob: float,
    home_team: str,
    away_team: str
) -> Tuple[str, Side]:
    """
    Select the sharp side on a moneyline
    
    If model thinks home is more likely than market → Home
    If model thinks home is less likely than market → Away
    """
    edge = model_home_prob - market_home_prob
    
    if edge > 0:
        # Model likes home more than market
        return f"{home_team} ML", Side.HOME
    else:
        return f"{away_team} ML", Side.AWAY


# ============================================================================
# KEY NUMBER PROTECTION (NFL/NCAAF)
# ============================================================================

KEY_NUMBERS = {
    "americanfootball_nfl": [3.0, 7.0, 10.0, 14.0],
    "americanfootball_ncaaf": [3.0, 7.0, 10.0, 14.0, 17.0],
}


def check_key_number_protection(
    sport: str,
    line_value: float,
    edge_points: float
) -> bool:
    """
    Check if edge is strong enough to cross key numbers
    
    NFL key numbers: 3, 7, 10, 14
    NCAAF key numbers: 3, 7, 10, 14, 17
    
    Crossing a key number requires higher edge threshold.
    """
    key_nums = KEY_NUMBERS.get(sport, [])
    if not key_nums:
        return True  # No key number protection for this sport
    
    abs_line = abs(line_value)
    
    for key in key_nums:
        # Check if line is near key number
        if abs(abs_line - key) <= 0.5:
            # Line is on or near key number
            # Require +1.5 additional edge to cross
            required_edge = 4.5 + 1.5  # Base + key number premium
            if edge_points < required_edge:
                logger.info(
                    f"Key number protection: line {line_value} near {key}, "
                    f"edge {edge_points} < required {required_edge}"
                )
                return False
    
    return True
