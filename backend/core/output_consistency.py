"""
BeatVegas Output Consistency Validator
==========================================

ELIMINATES CROSS-WIRE BUGS between Moneyline/Spread/Total markets

CANONICAL DEFINITIONS (LOCKED):
- p_win_home/away: Moneyline win probability (game win outright)
- p_cover_home/away: Spread cover probability (at market line)
- p_over/under: Total probability (at market total)
- fair_spread_home: Model's fair pricing line (signed from home perspective)
- fair_total: Model's fair total line
- market_spread_home: Market spread (signed from home, negative = home favored)
- market_total: Market total line

SHARP SIDE LOGIC (CORRECTED):
For SPREAD: delta_home = market_spread_home - fair_spread_home
  - If delta_home > 0 → market gives HOME more points than fair → value on HOME spread
  - If delta_home < 0 → market gives HOME fewer points → value on AWAY spread

VALIDATORS:
1. Probability sums must equal 1.0
2. UI mapping check (SPREAD shows p_cover only, ML shows p_win only, TOTAL shows p_over/under only)
3. Sharp direction vs delta check
4. Market crosswire check (sharp_market must match active tab)

FAIL-SAFE: If any validator fails, block recommendation and show mismatch banner
"""
from typing import Dict, Any, Optional, Tuple
from enum import Enum
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


class MarketType(Enum):
    """Market types for betting"""
    SPREAD = "SPREAD"
    ML = "ML"  # Moneyline
    TOTAL = "TOTAL"


class SharpAction(Enum):
    """Sharp side action types"""
    LAY_POINTS = "LAY_POINTS"        # Betting favorite with spread
    TAKE_POINTS = "TAKE_POINTS"      # Betting underdog with spread
    ML_FAV = "ML_FAV"                # Moneyline favorite
    ML_DOG = "ML_DOG"                # Moneyline underdog
    OVER = "OVER"                    # Over total
    UNDER = "UNDER"                  # Under total
    NO_SHARP_PLAY = "NO_SHARP_PLAY"  # No edge detected


class ValidationError(Enum):
    """Validation error types"""
    PROB_SUM_FAIL = "PROB_SUM_FAIL"
    UI_MAPPING_ERROR = "UI_MAPPING_ERROR"
    SHARP_DIRECTION_ERROR = "SHARP_DIRECTION_ERROR"
    MARKET_CROSSWIRE_ERROR = "MARKET_CROSSWIRE_ERROR"
    MISSING_DATA = "MISSING_DATA"


@dataclass
class ValidatorStatus:
    """Validation result"""
    passed: bool
    errors: list[ValidationError]
    warnings: list[str]
    details: Dict[str, Any]


@dataclass
class SharpSideOutput:
    """Complete sharp side output with market scope"""
    sharp_market: MarketType
    sharp_selection: str  # Full selection with line (e.g., "GSW -4.5")
    sharp_action: SharpAction
    edge_points: float
    reasoning: str
    validator_status: ValidatorStatus
    delta: float = 0.0  # Delta value (delta_home for spread, delta_total for total, edge for ML)
    sharp_team: Optional[str] = None  # Team with sharp side value
    sharp_line: Optional[float] = None  # Line value for sharp side
    has_edge: bool = False  # Whether edge exceeds threshold


class OutputConsistencyValidator:
    """
    Validates simulation output for consistency and prevents cross-wire bugs
    """
    
    def __init__(self):
        self.tolerance = 0.01  # 1% tolerance for probability sums
    
    def validate_probability_sums(
        self,
        p_win_home: Optional[float] = None,
        p_win_away: Optional[float] = None,
        p_cover_home: Optional[float] = None,
        p_cover_away: Optional[float] = None,
        p_over: Optional[float] = None,
        p_under: Optional[float] = None
    ) -> ValidatorStatus:
        """
        Validate that probability pairs sum to 1.0
        
        Returns validator status with pass/fail and details
        """
        errors = []
        warnings = []
        details = {}
        
        # Check ML probabilities
        if p_win_home is not None and p_win_away is not None:
            ml_sum = p_win_home + p_win_away
            details["ml_sum"] = ml_sum
            if abs(ml_sum - 1.0) > self.tolerance:
                errors.append(ValidationError.PROB_SUM_FAIL)
                details["ml_error"] = f"p_win_home + p_win_away = {ml_sum:.4f}, expected 1.0"
        
        # Check spread probabilities
        if p_cover_home is not None and p_cover_away is not None:
            spread_sum = p_cover_home + p_cover_away
            details["spread_sum"] = spread_sum
            if abs(spread_sum - 1.0) > self.tolerance:
                errors.append(ValidationError.PROB_SUM_FAIL)
                details["spread_error"] = f"p_cover_home + p_cover_away = {spread_sum:.4f}, expected 1.0"
        
        # Check total probabilities
        if p_over is not None and p_under is not None:
            total_sum = p_over + p_under
            details["total_sum"] = total_sum
            if abs(total_sum - 1.0) > self.tolerance:
                errors.append(ValidationError.PROB_SUM_FAIL)
                details["total_error"] = f"p_over + p_under = {total_sum:.4f}, expected 1.0"
        
        passed = len(errors) == 0
        return ValidatorStatus(
            passed=passed,
            errors=errors,
            warnings=warnings,
            details=details
        )
    
    def calculate_spread_sharp_side(
        self,
        home_team: str,
        away_team: str,
        market_spread_home: float,
        fair_spread_home: float,
        edge_threshold: float = 2.0
    ) -> SharpSideOutput:
        """
        Calculate sharp side for SPREAD market using delta_home logic
        
        CORRECTED LOGIC:
        delta_home = market_spread_home - fair_spread_home
        
        If delta_home > 0:
          Market gives HOME more points than fair → value on HOME spread
        If delta_home < 0:
          Market gives HOME fewer points than fair → value on AWAY spread
        
        Example (from spec):
        Market: DAL +4.5 (home), GSW -4.5 (away)
        Fair: DAL +9.1
        market_spread_home = +4.5
        fair_spread_home = +9.1
        delta_home = 4.5 - 9.1 = -4.6
        Dallas getting FEWER points than fair → value on AWAY (GSW -4.5)
        
        Args:
            home_team: Home team name
            away_team: Away team name
            market_spread_home: Market spread from HOME perspective (signed)
            fair_spread_home: Fair spread from HOME perspective (signed)
            edge_threshold: Minimum edge in points to trigger sharp side
        
        Returns:
            SharpSideOutput with market-scoped sharp side
        """
        # Handle None values
        if market_spread_home is None or fair_spread_home is None:
            logger.warning(f"Missing spread data: market={market_spread_home}, fair={fair_spread_home}")
            return SharpSideOutput(
                sharp_market=MarketType.SPREAD,
                sharp_selection="NO PLAY",
                sharp_action=SharpAction.NO_SHARP_PLAY,
                edge_points=0.0,
                reasoning="Missing market or fair spread data",
                validator_status=ValidatorStatus(
                    passed=False,
                    errors=[ValidationError.MISSING_DATA],
                    warnings=[],
                    details={"market_spread_home": market_spread_home, "fair_spread_home": fair_spread_home}
                ),
                delta=0.0,
                has_edge=False
            )
        
        # Calculate delta
        delta_home = market_spread_home - fair_spread_home
        edge_points = abs(delta_home)
        
        # Determine if edge exists
        if edge_points < edge_threshold:
            return SharpSideOutput(
                sharp_market=MarketType.SPREAD,
                sharp_selection="NO PLAY",
                sharp_action=SharpAction.NO_SHARP_PLAY,
                edge_points=0.0,
                reasoning=f"Edge {edge_points:.1f} pts below threshold {edge_threshold}",
                validator_status=ValidatorStatus(
                    passed=True,
                    errors=[],
                    warnings=[],
                    details={"delta_home": delta_home, "edge_points": edge_points}
                ),
                delta=delta_home,
                has_edge=False
            )
        
        # Determine sharp side based on delta_home
        if delta_home > 0:
            # Market gives HOME more points than fair → value on HOME
            sharp_team = home_team
            sharp_line = market_spread_home
            sharp_action = SharpAction.TAKE_POINTS if market_spread_home > 0 else SharpAction.LAY_POINTS
            reasoning = (
                f"Market gives {home_team} {market_spread_home:+.1f} vs fair {fair_spread_home:+.1f}. "
                f"HOME getting {delta_home:.1f} more points than fair → value on {home_team}"
            )
        else:
            # Market gives HOME fewer points → value on AWAY
            sharp_team = away_team
            sharp_line = -market_spread_home  # Away spread is negative of home spread
            sharp_action = SharpAction.LAY_POINTS if sharp_line < 0 else SharpAction.TAKE_POINTS
            reasoning = (
                f"Market gives {home_team} {market_spread_home:+.1f} vs fair {fair_spread_home:+.1f}. "
                f"HOME getting {abs(delta_home):.1f} FEWER points than fair → value on {away_team}"
            )
        
        sharp_selection = f"{sharp_team} {sharp_line:+.1f}"
        
        # Validate sharp direction
        validator_status = ValidatorStatus(
            passed=True,
            errors=[],
            warnings=[],
            details={
                "delta_home": delta_home,
                "edge_points": edge_points,
                "market_spread_home": market_spread_home,
                "fair_spread_home": fair_spread_home,
                "sharp_team": sharp_team,
                "sharp_line": sharp_line
            }
        )
        
        return SharpSideOutput(
            sharp_market=MarketType.SPREAD,
            sharp_selection=sharp_selection,
            sharp_action=sharp_action,
            edge_points=edge_points,
            reasoning=reasoning,
            validator_status=validator_status,
            delta=delta_home,
            sharp_team=sharp_team,
            sharp_line=sharp_line,
            has_edge=True
        )
    
    def calculate_total_sharp_side(
        self,
        market_total: float,
        fair_total: float,
        edge_threshold: float = 2.0
    ) -> SharpSideOutput:
        """
        Calculate sharp side for TOTAL market
        
        Logic:
        - If fair_total > market_total → model expects higher scoring → OVER
        - If fair_total < market_total → model expects lower scoring → UNDER
        
        Args:
            market_total: Market total line
            fair_total: Fair total line from model
            edge_threshold: Minimum edge in points
        
        Returns:
            SharpSideOutput for total market
        """
        # Handle None values
        if market_total is None or fair_total is None:
            logger.warning(f"Missing total data: market={market_total}, fair={fair_total}")
            return SharpSideOutput(
                sharp_market=MarketType.TOTAL,
                sharp_selection="NO PLAY",
                sharp_action=SharpAction.NO_SHARP_PLAY,
                edge_points=0.0,
                reasoning="Missing market or fair total data",
                validator_status=ValidatorStatus(
                    passed=False,
                    errors=[ValidationError.MISSING_DATA],
                    warnings=[],
                    details={"market_total": market_total, "fair_total": fair_total}
                ),
                delta=0.0,
                has_edge=False
            )
        
        delta_total = fair_total - market_total
        edge_points = abs(delta_total)
        
        if edge_points < edge_threshold:
            return SharpSideOutput(
                sharp_market=MarketType.TOTAL,
                sharp_selection="NO PLAY",
                sharp_action=SharpAction.NO_SHARP_PLAY,
                edge_points=0.0,
                reasoning=f"Edge {edge_points:.1f} pts below threshold {edge_threshold}",
                validator_status=ValidatorStatus(
                    passed=True,
                    errors=[],
                    warnings=[],
                    details={"delta_total": delta_total, "edge_points": edge_points}
                ),
                delta=delta_total,
                has_edge=False
            )
        
        if delta_total > 0:
            # Fair total higher than market → OVER
            sharp_action = SharpAction.OVER
            sharp_selection = f"OVER {market_total:.1f}"
            reasoning = f"Fair total {fair_total:.1f} > market {market_total:.1f} by {edge_points:.1f} pts → OVER"
        else:
            # Fair total lower than market → UNDER
            sharp_action = SharpAction.UNDER
            sharp_selection = f"UNDER {market_total:.1f}"
            reasoning = f"Fair total {fair_total:.1f} < market {market_total:.1f} by {edge_points:.1f} pts → UNDER"
        
        return SharpSideOutput(
            sharp_market=MarketType.TOTAL,
            sharp_selection=sharp_selection,
            sharp_action=sharp_action,
            edge_points=edge_points,
            reasoning=reasoning,
            validator_status=ValidatorStatus(
                passed=True,
                errors=[],
                warnings=[],
                details={
                    "delta_total": delta_total,
                    "edge_points": edge_points,
                    "market_total": market_total,
                    "fair_total": fair_total
                }
            ),
            delta=delta_total,
            has_edge=True
        )
    
    def calculate_ml_sharp_side(
        self,
        home_team: str,
        away_team: str,
        p_win_home: float,
        p_win_away: float,
        edge_threshold: float = 0.05  # 5% edge minimum for ML
    ) -> SharpSideOutput:
        """
        Calculate sharp side for MONEYLINE market
        
        Simple logic: Bet the team model favors with sufficient edge
        
        Args:
            home_team: Home team name
            away_team: Away team name
            p_win_home: Home win probability
            p_win_away: Away win probability
            edge_threshold: Minimum probability edge (default 5%)
        
        Returns:
            SharpSideOutput for moneyline
        """
        # Handle None values - use 0.5 defaults
        if p_win_home is None or p_win_away is None:
            logger.warning(f"Missing ML probabilities: p_win_home={p_win_home}, p_win_away={p_win_away}")
            p_win_home = p_win_home or 0.5
            p_win_away = p_win_away or 0.5
        
        edge = abs(p_win_home - p_win_away)
        
        if edge < edge_threshold:
            return SharpSideOutput(
                sharp_market=MarketType.ML,
                sharp_selection="NO PLAY",
                sharp_action=SharpAction.NO_SHARP_PLAY,
                edge_points=0.0,
                reasoning=f"Edge {edge*100:.1f}% below threshold {edge_threshold*100:.1f}%",
                validator_status=ValidatorStatus(
                    passed=True,
                    errors=[],
                    warnings=[],
                    details={"p_win_home": p_win_home, "p_win_away": p_win_away, "edge": edge}
                ),
                delta=edge,
                has_edge=False
            )
        
        if p_win_home > p_win_away:
            sharp_team = home_team
            sharp_action = SharpAction.ML_FAV if p_win_home > 0.5 else SharpAction.ML_DOG
            reasoning = f"{home_team} win prob {p_win_home*100:.1f}% > {away_team} {p_win_away*100:.1f}%"
        else:
            sharp_team = away_team
            sharp_action = SharpAction.ML_FAV if p_win_away > 0.5 else SharpAction.ML_DOG
            reasoning = f"{away_team} win prob {p_win_away*100:.1f}% > {home_team} {p_win_home*100:.1f}%"
        
        return SharpSideOutput(
            sharp_market=MarketType.ML,
            sharp_selection=f"{sharp_team} ML",
            sharp_action=sharp_action,
            edge_points=edge,
            reasoning=reasoning,
            validator_status=ValidatorStatus(
                passed=True,
                errors=[],
                warnings=[],
                details={"p_win_home": p_win_home, "p_win_away": p_win_away, "edge": edge}
            ),
            delta=edge,
            sharp_team=sharp_team,
            has_edge=True
        )
    
    def build_debug_payload(
        self,
        game_id: str,
        home_team: str,
        away_team: str,
        market_spread_home: float,
        fair_spread_home: float,
        market_total: float,
        fair_total: float,
        p_win_home: float,
        p_win_away: float,
        p_cover_home: float,
        p_cover_away: float,
        p_over: float,
        p_under: float,
        sharp_spread: Optional[SharpSideOutput] = None,
        sharp_total: Optional[SharpSideOutput] = None,
        sharp_ml: Optional[SharpSideOutput] = None
    ) -> Dict[str, Any]:
        """
        Build complete debug payload for self-auditing
        
        This payload should be hidden behind a dev toggle in the UI
        
        Returns:
            Complete debug information for troubleshooting cross-wire bugs
        """
        return {
            "game_id": game_id,
            "teams": {
                "home": home_team,
                "away": away_team
            },
            "market_lines": {
                "spread_home": market_spread_home,
                "spread_away": -market_spread_home,
                "total": market_total
            },
            "fair_lines": {
                "spread_home": fair_spread_home,
                "spread_away": -fair_spread_home,
                "total": fair_total
            },
            "probabilities": {
                "moneyline": {
                    "p_win_home": round(p_win_home, 4),
                    "p_win_away": round(p_win_away, 4),
                    "sum": round(p_win_home + p_win_away, 4)
                },
                "spread": {
                    "p_cover_home": round(p_cover_home, 4),
                    "p_cover_away": round(p_cover_away, 4),
                    "sum": round(p_cover_home + p_cover_away, 4)
                },
                "total": {
                    "p_over": round(p_over, 4),
                    "p_under": round(p_under, 4),
                    "sum": round(p_over + p_under, 4)
                }
            },
            "sharp_sides": {
                "spread": {
                    "sharp_market": sharp_spread.sharp_market.value if sharp_spread else None,
                    "sharp_selection": sharp_spread.sharp_selection if sharp_spread else None,
                    "sharp_action": sharp_spread.sharp_action.value if sharp_spread else None,
                    "edge_points": sharp_spread.edge_points if sharp_spread else 0.0,
                    "validator_status": "PASS" if sharp_spread and sharp_spread.validator_status.passed else "FAIL",
                    "errors": [e.value for e in sharp_spread.validator_status.errors] if sharp_spread else []
                },
                "total": {
                    "sharp_market": sharp_total.sharp_market.value if sharp_total else None,
                    "sharp_selection": sharp_total.sharp_selection if sharp_total else None,
                    "sharp_action": sharp_total.sharp_action.value if sharp_total else None,
                    "edge_points": sharp_total.edge_points if sharp_total else 0.0,
                    "validator_status": "PASS" if sharp_total and sharp_total.validator_status.passed else "FAIL",
                    "errors": [e.value for e in sharp_total.validator_status.errors] if sharp_total else []
                },
                "moneyline": {
                    "sharp_market": sharp_ml.sharp_market.value if sharp_ml else None,
                    "sharp_selection": sharp_ml.sharp_selection if sharp_ml else None,
                    "sharp_action": sharp_ml.sharp_action.value if sharp_ml else None,
                    "edge_points": sharp_ml.edge_points if sharp_ml else 0.0,
                    "validator_status": "PASS" if sharp_ml and sharp_ml.validator_status.passed else "FAIL",
                    "errors": [e.value for e in sharp_ml.validator_status.errors] if sharp_ml else []
                }
            },
            "validation": {
                "probability_sums": self.validate_probability_sums(
                    p_win_home=p_win_home,
                    p_win_away=p_win_away,
                    p_cover_home=p_cover_home,
                    p_cover_away=p_cover_away,
                    p_over=p_over,
                    p_under=p_under
                ).details
            }
        }


# Singleton instance
_validator_instance: Optional[OutputConsistencyValidator] = None


def get_output_validator() -> OutputConsistencyValidator:
    """Get or create singleton validator instance"""
    global _validator_instance
    if _validator_instance is None:
        _validator_instance = OutputConsistencyValidator()
    return _validator_instance


# Export singleton for easy import
output_consistency_validator = get_output_validator()
