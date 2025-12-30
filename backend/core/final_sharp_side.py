"""
FINAL SHARP SIDE — SINGLE SOURCE OF TRUTH
==========================================
This module is the AUTHORITATIVE source for all sharp side decisions.

FINAL_SHARP_SIDE is the ONLY field that:
- UI displays
- Telegram posts
- AI references
- Users see

NO OTHER FIELD should be used for user-facing decisions.

FINAL_SHARP_SIDE = FAVORITE | UNDERDOG | NONE
"""

from typing import Dict, Any, Optional, Tuple, List
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import logging

logger = logging.getLogger(__name__)


# ============================================================================
# ENUMS — LOCKED DEFINITIONS
# ============================================================================

class FinalSharpSide(str, Enum):
    """
    The ONLY three values for sharp side.
    This is the single source of truth.
    """
    FAVORITE = "FAVORITE"
    UNDERDOG = "UNDERDOG"
    NONE = "NONE"


class EdgeState(str, Enum):
    """
    Official edge classification states.
    """
    OFFICIAL_EDGE = "OFFICIAL_EDGE"  # Confidence above threshold, volatility acceptable
    MODEL_LEAN = "MODEL_LEAN"        # Informational only
    NO_ACTION = "NO_ACTION"          # Blocked


class MispricingLabel(str, Enum):
    """
    Human-readable mispricing labels.
    REPLACES raw Model Spread +/- values in UI.
    """
    MARKET_OVERPRICES_FAVORITE = "Market Overprices Favorite"
    MARKET_UNDERVALUES_FAVORITE = "Market Undervalues Favorite"
    SPREAD_MISPRICING_DETECTED = "Spread Mispricing Detected"
    NO_SIGNIFICANT_MISPRICING = "No Significant Mispricing"


# ============================================================================
# CONFIGURATION
# ============================================================================

@dataclass
class SharpSideConfig:
    """Configuration for sharp side determination"""
    # Edge thresholds
    edge_confidence_threshold: float = 0.55
    lean_confidence_threshold: float = 0.52
    
    # Volatility thresholds
    max_volatility_for_edge: float = 0.25
    max_volatility_for_lean: float = 0.35
    
    # Stability requirements (N-of-M)
    stability_runs_required: int = 2
    stability_runs_window: int = 3
    
    # Minimum edge points by market
    min_spread_edge: float = 2.0
    min_total_edge: float = 2.5
    min_ml_edge_pct: float = 0.02


DEFAULT_CONFIG = SharpSideConfig()


# ============================================================================
# FINAL OUTPUT DATA CLASS
# ============================================================================

@dataclass
class FinalSharpOutput:
    """
    The FINAL output structure for all sharp side decisions.
    
    This is what UI, Telegram, and AI consume.
    NO OTHER DATA STRUCTURE should be used for user-facing decisions.
    """
    # Core identification
    game_id: str
    sport: str
    market_type: str
    
    # THE SINGLE SOURCE OF TRUTH
    final_sharp_side: FinalSharpSide
    edge_state: EdgeState
    
    # Human-readable labels (NO raw math)
    mispricing_label: MispricingLabel
    selection_display: str  # e.g., "Bulls +6.5" or "Lakers -3.5"
    
    # Confidence (0-100 for display)
    confidence_display: int  # Integer percentage
    
    # Edge description (human-readable)
    edge_description: str  # e.g., "4.5 point edge detected"
    
    # Telegram eligibility
    telegram_eligible: bool
    
    # Stability tracking
    is_stable: bool
    stability_runs: int
    
    # Timestamps
    locked_at: Optional[datetime] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    # Internal tracking (NOT for UI)
    _raw_model_line: float = field(default=0.0, repr=False)
    _raw_market_line: float = field(default=0.0, repr=False)
    _raw_edge_points: float = field(default=0.0, repr=False)
    
    def to_ui_dict(self) -> Dict[str, Any]:
        """
        Returns ONLY the fields safe for UI display.
        NO raw math values included.
        """
        return {
            "game_id": self.game_id,
            "sport": self.sport,
            "market_type": self.market_type,
            "final_sharp_side": self.final_sharp_side.value,
            "edge_state": self.edge_state.value,
            "mispricing_label": self.mispricing_label.value,
            "selection_display": self.selection_display,
            "confidence_display": self.confidence_display,
            "edge_description": self.edge_description,
            "is_stable": self.is_stable,
            "locked_at": self.locked_at.isoformat() if self.locked_at else None,
        }
    
    def to_telegram_dict(self) -> Dict[str, Any]:
        """
        Returns ONLY the fields for Telegram posting.
        Telegram reads ONLY final_sharp_side + state.
        """
        return {
            "game_id": self.game_id,
            "final_sharp_side": self.final_sharp_side.value,
            "edge_state": self.edge_state.value,
            "selection_display": self.selection_display,
            "confidence_display": self.confidence_display,
            "telegram_eligible": self.telegram_eligible,
        }
    
    def to_ai_dict(self) -> Dict[str, Any]:
        """
        Returns ONLY the fields for AI Assistant.
        AI mirrors final_sharp_side and state only.
        NO recomputation. NO contradictions.
        """
        return {
            "final_sharp_side": self.final_sharp_side.value,
            "edge_state": self.edge_state.value,
            "mispricing_label": self.mispricing_label.value,
            "selection_display": self.selection_display,
            "confidence_display": self.confidence_display,
            "edge_description": self.edge_description,
        }


# ============================================================================
# FINAL SHARP SIDE CALCULATOR
# ============================================================================

class FinalSharpSideCalculator:
    """
    Calculates FINAL_SHARP_SIDE using locked logic.
    
    FINAL SHARP SIDE LOGIC:
    - If model favors underdog AND market gives points → UNDERDOG +points
    - If model favors favorite AND market gives minus → FAVORITE -points
    - Else → NONE
    """
    
    def __init__(self, config: Optional[SharpSideConfig] = None):
        self.config = config or DEFAULT_CONFIG
        self._stability_tracker: Dict[str, List[FinalSharpSide]] = {}
    
    def calculate(
        self,
        game_id: str,
        sport: str,
        market_type: str,
        home_team: str,
        away_team: str,
        model_line: float,
        market_line: float,
        model_win_prob: float,
        confidence: float,
        volatility: float,
        home_is_favorite: bool,
    ) -> FinalSharpOutput:
        """
        Calculate the FINAL sharp side output.
        
        This is the ONLY method that should be called for sharp side decisions.
        
        Args:
            game_id: Unique game identifier
            sport: Sport key
            market_type: SPREAD, TOTAL, or MONEYLINE
            home_team: Home team name
            away_team: Away team name
            model_line: Model's projected line
            market_line: Market's current line
            model_win_prob: Model's win probability
            confidence: Confidence score (0-1)
            volatility: Volatility score (0-1)
            home_is_favorite: Whether home team is favored
        
        Returns:
            FinalSharpOutput with all user-facing fields populated
        """
        # Step 1: Calculate edge
        edge_points = self._calculate_edge(model_line, market_line, market_type)
        
        # Step 2: Determine FINAL_SHARP_SIDE
        final_side = self._determine_sharp_side(
            model_line=model_line,
            market_line=market_line,
            model_win_prob=model_win_prob,
            home_is_favorite=home_is_favorite,
            market_type=market_type,
        )
        
        # Step 3: Determine edge state
        edge_state = self._determine_edge_state(
            confidence=confidence,
            volatility=volatility,
            edge_points=edge_points,
            market_type=market_type,
            final_side=final_side,
        )
        
        # Step 4: Generate human-readable labels (NO raw math)
        mispricing_label = self._get_mispricing_label(
            model_line=model_line,
            market_line=market_line,
            home_is_favorite=home_is_favorite,
        )
        
        selection_display = self._build_selection_display(
            final_side=final_side,
            home_team=home_team,
            away_team=away_team,
            market_line=market_line,
            home_is_favorite=home_is_favorite,
            market_type=market_type,
        )
        
        edge_description = self._build_edge_description(edge_points, market_type)
        
        # Step 5: Check stability
        is_stable, stability_runs = self._check_stability(game_id, final_side)
        
        # Step 6: Determine Telegram eligibility
        telegram_eligible = self._is_telegram_eligible(edge_state, is_stable)
        
        # Step 7: Build final output
        output = FinalSharpOutput(
            game_id=game_id,
            sport=sport,
            market_type=market_type,
            final_sharp_side=final_side,
            edge_state=edge_state,
            mispricing_label=mispricing_label,
            selection_display=selection_display,
            confidence_display=int(confidence * 100),
            edge_description=edge_description,
            telegram_eligible=telegram_eligible,
            is_stable=is_stable,
            stability_runs=stability_runs,
            locked_at=datetime.now(timezone.utc) if telegram_eligible else None,
            _raw_model_line=model_line,
            _raw_market_line=market_line,
            _raw_edge_points=edge_points,
        )
        
        logger.info(
            f"FINAL_SHARP_SIDE: {game_id} → {final_side.value} | "
            f"State: {edge_state.value} | Stable: {is_stable}"
        )
        
        return output
    
    # ========================================================================
    # CORE LOGIC — LOCKED
    # ========================================================================
    
    def _determine_sharp_side(
        self,
        model_line: float,
        market_line: float,
        model_win_prob: float,
        home_is_favorite: bool,
        market_type: str,
    ) -> FinalSharpSide:
        """
        FINAL SHARP SIDE LOGIC — LOCKED
        
        If model favors underdog AND market gives points → UNDERDOG +points
        If model favors favorite AND market gives minus → FAVORITE -points
        Else → NONE
        """
        if market_type == "TOTAL":
            # For totals, use OVER/UNDER logic (mapped to FAVORITE/UNDERDOG)
            model_favors_over = model_line > market_line
            if model_favors_over:
                return FinalSharpSide.FAVORITE  # OVER mapped to FAVORITE
            elif model_line < market_line:
                return FinalSharpSide.UNDERDOG  # UNDER mapped to UNDERDOG
            return FinalSharpSide.NONE
        
        # For SPREAD and MONEYLINE
        edge = model_line - market_line
        
        # Model favors underdog = model thinks underdog is better than market thinks
        model_favors_underdog = (
            (home_is_favorite and edge > 0) or
            (not home_is_favorite and edge < 0)
        )
        
        # Model favors favorite = model thinks favorite is better than market thinks
        model_favors_favorite = (
            (home_is_favorite and edge < 0) or
            (not home_is_favorite and edge > 0)
        )
        
        # Market gives points to underdog (positive spread for underdog)
        market_gives_points = market_line > 0 if not home_is_favorite else market_line < 0
        
        # Apply the locked logic
        if model_favors_underdog and market_gives_points:
            return FinalSharpSide.UNDERDOG
        elif model_favors_favorite and not market_gives_points:
            return FinalSharpSide.FAVORITE
        
        return FinalSharpSide.NONE
    
    def _determine_edge_state(
        self,
        confidence: float,
        volatility: float,
        edge_points: float,
        market_type: str,
        final_side: FinalSharpSide,
    ) -> EdgeState:
        """
        Determine edge state: OFFICIAL_EDGE | MODEL_LEAN | NO_ACTION
        
        OFFICIAL_EDGE: confidence above threshold, volatility acceptable
        MODEL_LEAN: informational only
        NO_ACTION: blocked
        """
        # No side = No action
        if final_side == FinalSharpSide.NONE:
            return EdgeState.NO_ACTION
        
        # Get minimum edge for market type
        min_edge = {
            "SPREAD": self.config.min_spread_edge,
            "TOTAL": self.config.min_total_edge,
            "MONEYLINE": self.config.min_ml_edge_pct * 100,  # Convert to points
        }.get(market_type, self.config.min_spread_edge)
        
        # Check for OFFICIAL_EDGE
        if (
            confidence >= self.config.edge_confidence_threshold and
            volatility <= self.config.max_volatility_for_edge and
            abs(edge_points) >= min_edge
        ):
            return EdgeState.OFFICIAL_EDGE
        
        # Check for MODEL_LEAN
        if (
            confidence >= self.config.lean_confidence_threshold and
            volatility <= self.config.max_volatility_for_lean
        ):
            return EdgeState.MODEL_LEAN
        
        return EdgeState.NO_ACTION
    
    def _calculate_edge(
        self,
        model_line: float,
        market_line: float,
        market_type: str,
    ) -> float:
        """Calculate edge points"""
        return abs(model_line - market_line)
    
    # ========================================================================
    # HUMAN-READABLE LABELS — NO RAW MATH
    # ========================================================================
    
    def _get_mispricing_label(
        self,
        model_line: float,
        market_line: float,
        home_is_favorite: bool,
    ) -> MispricingLabel:
        """
        Generate human-readable mispricing label.
        REPLACES raw Model Spread +/- values.
        """
        edge = model_line - market_line
        
        if abs(edge) < 1.0:
            return MispricingLabel.NO_SIGNIFICANT_MISPRICING
        
        if home_is_favorite:
            if edge > 0:
                # Model line > market line for favorite = market overprices
                return MispricingLabel.MARKET_OVERPRICES_FAVORITE
            else:
                # Model line < market line = market undervalues
                return MispricingLabel.MARKET_UNDERVALUES_FAVORITE
        else:
            if edge < 0:
                return MispricingLabel.MARKET_OVERPRICES_FAVORITE
            else:
                return MispricingLabel.MARKET_UNDERVALUES_FAVORITE
        
        return MispricingLabel.SPREAD_MISPRICING_DETECTED
    
    def _build_selection_display(
        self,
        final_side: FinalSharpSide,
        home_team: str,
        away_team: str,
        market_line: float,
        home_is_favorite: bool,
        market_type: str,
    ) -> str:
        """
        Build human-readable selection display.
        e.g., "Bulls +6.5" or "Lakers -3.5"
        """
        if final_side == FinalSharpSide.NONE:
            return "No Selection"
        
        if market_type == "TOTAL":
            if final_side == FinalSharpSide.FAVORITE:
                return f"Over {market_line}"
            else:
                return f"Under {market_line}"
        
        # Determine which team based on FAVORITE/UNDERDOG
        if final_side == FinalSharpSide.FAVORITE:
            team = home_team if home_is_favorite else away_team
            line = market_line if home_is_favorite else -market_line
        else:  # UNDERDOG
            team = away_team if home_is_favorite else home_team
            line = -market_line if home_is_favorite else market_line
        
        # Format line with sign
        if market_type == "MONEYLINE":
            return f"{team} ML"
        else:
            line_str = f"+{line}" if line > 0 else str(line)
            return f"{team} {line_str}"
    
    def _build_edge_description(
        self,
        edge_points: float,
        market_type: str,
    ) -> str:
        """
        Build human-readable edge description.
        """
        if edge_points < 1.0:
            return "Minimal edge detected"
        elif edge_points < 2.5:
            return f"{edge_points:.1f} point edge detected"
        elif edge_points < 4.5:
            return f"Strong {edge_points:.1f} point edge"
        else:
            return f"Significant {edge_points:.1f} point edge"
    
    # ========================================================================
    # STABILITY TRACKING — PREVENTS FLIP-FLOPPING
    # ========================================================================
    
    def _check_stability(
        self,
        game_id: str,
        current_side: FinalSharpSide,
    ) -> Tuple[bool, int]:
        """
        Check if output is stable across N runs.
        Prevents flip-flopping outputs.
        
        Returns:
            (is_stable, consecutive_runs)
        """
        key = game_id
        
        if key not in self._stability_tracker:
            self._stability_tracker[key] = []
        
        history = self._stability_tracker[key]
        history.append(current_side)
        
        # Keep only last N runs
        if len(history) > self.config.stability_runs_window:
            history.pop(0)
        
        # Count consecutive same-side runs
        consecutive = 0
        for side in reversed(history):
            if side == current_side:
                consecutive += 1
            else:
                break
        
        is_stable = consecutive >= self.config.stability_runs_required
        
        return is_stable, consecutive
    
    def reset_stability(self, game_id: str):
        """Reset stability tracking for a game"""
        key = game_id
        if key in self._stability_tracker:
            del self._stability_tracker[key]
    
    # ========================================================================
    # TELEGRAM ELIGIBILITY
    # ========================================================================
    
    def _is_telegram_eligible(
        self,
        edge_state: EdgeState,
        is_stable: bool,
    ) -> bool:
        """
        Determine if signal is eligible for Telegram posting.
        
        Telegram rules:
        - OFFICIAL_EDGE: Always posts (if stable)
        - MODEL_LEAN: Optional (configurable)
        - NO_ACTION: NEVER posts
        """
        if edge_state == EdgeState.NO_ACTION:
            return False
        
        if edge_state == EdgeState.OFFICIAL_EDGE and is_stable:
            return True
        
        # MODEL_LEAN could be configurable, default to not posting
        return False


# ============================================================================
# SINGLETON INSTANCE
# ============================================================================

_calculator_instance: Optional[FinalSharpSideCalculator] = None


def get_calculator(config: Optional[SharpSideConfig] = None) -> FinalSharpSideCalculator:
    """Get or create the singleton calculator instance"""
    global _calculator_instance
    if _calculator_instance is None:
        _calculator_instance = FinalSharpSideCalculator(config)
    return _calculator_instance


# ============================================================================
# CONVENIENCE FUNCTIONS
# ============================================================================

def calculate_final_sharp_side(
    game_id: str,
    sport: str,
    market_type: str,
    home_team: str,
    away_team: str,
    model_line: float,
    market_line: float,
    model_win_prob: float,
    confidence: float,
    volatility: float,
    home_is_favorite: bool,
) -> FinalSharpOutput:
    """
    Convenience function to calculate final sharp side.
    
    Use this as the single entry point for all sharp side calculations.
    """
    calculator = get_calculator()
    return calculator.calculate(
        game_id=game_id,
        sport=sport,
        market_type=market_type,
        home_team=home_team,
        away_team=away_team,
        model_line=model_line,
        market_line=market_line,
        model_win_prob=model_win_prob,
        confidence=confidence,
        volatility=volatility,
        home_is_favorite=home_is_favorite,
    )


def get_ui_output(final_output: FinalSharpOutput) -> Dict[str, Any]:
    """Get UI-safe output (no raw math)"""
    return final_output.to_ui_dict()


def get_telegram_output(final_output: FinalSharpOutput) -> Dict[str, Any]:
    """Get Telegram output (only final_sharp_side + state)"""
    return final_output.to_telegram_dict()


def get_ai_output(final_output: FinalSharpOutput) -> Dict[str, Any]:
    """Get AI Assistant output (mirrors final_sharp_side only)"""
    return final_output.to_ai_dict()
