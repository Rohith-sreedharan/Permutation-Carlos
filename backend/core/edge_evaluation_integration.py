"""
EDGE EVALUATION INTEGRATION — MASTER ORCHESTRATOR
==================================================
This module orchestrates all edge evaluation components:
1. Sport Sanity Config — Thresholds and compression factors
2. Universal Edge Evaluator — Two-layer evaluation
3. Sharp Side Selector — Final side selection
4. Signal Locking — Immutable signal management
5. Sanity Check Service — Post-launch monitoring

USE THIS MODULE for all edge evaluation workflows.
Do NOT call component modules directly unless extending.

WORKFLOW:
1. Game data comes in
2. Compression applied (sport-specific)
3. Eligibility check (Layer A)
4. Edge grading (Layer B) → EDGE/LEAN/NO_PLAY
5. Sharp side selection
6. Signal locking (if EDGE)
7. Sanity check recording
8. Return final result
"""

from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime, timezone
from dataclasses import dataclass, field
import logging

# Import all component modules
from core.sport_sanity_config import (
    get_sport_sanity_config,
    compress_probability,
    EdgeState,
    SPORT_SANITY_CONFIGS,
)
from core.universal_edge_evaluator import (
    UniversalEdgeEvaluator,
    GameContext,
    SimulationOutput,
    EvaluationResult,
    VolatilityBucket,
)
from core.sharp_side_selector import (
    SharpSideSelector,
    ModelPrediction,
    SharpSideSelection,
    Side,
    SelectionSource,
    select_spread_side,
    select_total_side,
    select_moneyline_side,
    check_key_number_protection,
)

# FINAL SHARP SIDE — SINGLE SOURCE OF TRUTH
from core.final_sharp_side import (
    calculate_final_sharp_side,
    FinalSharpOutput,
    FinalSharpSide,
    EdgeState as FinalEdgeState,
    MispricingLabel,
    get_ui_output,
    get_telegram_output,
    get_ai_output,
)

logger = logging.getLogger(__name__)


# ============================================================================
# MASTER RESULT DATA CLASS
# ============================================================================

@dataclass
class EdgeEvaluationResult:
    """
    Complete result of edge evaluation pipeline
    
    This is the FINAL output that goes to:
    - Signal posting
    - Telegram integration
    - UI display
    - AI Analyzer
    """
    # Core identification
    game_id: str
    sport: str
    market_type: str
    
    # Classification
    edge_state: EdgeState
    is_telegram_worthy: bool
    
    # Edge metrics
    raw_edge: float
    compressed_edge: float
    raw_win_prob: float
    compressed_win_prob: float
    confidence: float
    
    # Selection
    selection: str  # e.g., "Bulls +6.5"
    selection_side: Side
    selection_source: SelectionSource
    
    # Line information
    model_line: float
    market_line: float
    
    # Reason codes (for debugging and AI explanation)
    reason_codes: List[str] = field(default_factory=list)
    
    # Override tracking
    override_active: bool = False
    override_type: Optional[str] = None
    
    # Volatility and distribution
    volatility_level: str = "LOW"
    distribution_flag: str = "STABLE"
    
    # Timestamps
    evaluated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    # Simulation details
    sim_count: int = 10000
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "game_id": self.game_id,
            "sport": self.sport,
            "market_type": self.market_type,
            "edge_state": self.edge_state.value,
            "is_telegram_worthy": self.is_telegram_worthy,
            "raw_edge": self.raw_edge,
            "compressed_edge": self.compressed_edge,
            "raw_win_prob": self.raw_win_prob,
            "compressed_win_prob": self.compressed_win_prob,
            "confidence": self.confidence,
            "selection": self.selection,
            "selection_side": self.selection_side.value,
            "selection_source": self.selection_source.value,
            "model_line": self.model_line,
            "market_line": self.market_line,
            "reason_codes": self.reason_codes,
            "override_active": self.override_active,
            "override_type": self.override_type,
            "volatility_level": self.volatility_level,
            "distribution_flag": self.distribution_flag,
            "evaluated_at": self.evaluated_at.isoformat(),
            "sim_count": self.sim_count,
        }


# ============================================================================
# MASTER ORCHESTRATOR
# ============================================================================

class EdgeEvaluationOrchestrator:
    """
    Master orchestrator for edge evaluation pipeline
    
    This is the SINGLE ENTRY POINT for all edge evaluations.
    Do NOT instantiate component classes directly.
    """
    
    def __init__(self, db=None):
        self.db = db
        self.evaluator = UniversalEdgeEvaluator(db)
        self.sharp_selector = SharpSideSelector(db)
        self._sanity_service = None  # Lazy load
    
    @property
    def sanity_service(self):
        """Lazy load sanity service to avoid circular imports"""
        if self._sanity_service is None:
            from services.sanity_check_service import SanityCheckService
            self._sanity_service = SanityCheckService(self.db)
        return self._sanity_service
    
    # ========================================================================
    # MAIN EVALUATION METHOD
    # ========================================================================
    
    def evaluate_game(
        self,
        game_data: Dict[str, Any],
        simulation_output: Dict[str, Any],
        market_data: Dict[str, Any],
        market_type: str = "SPREAD",
        return_final_sharp: bool = True
    ) -> FinalSharpOutput:
        """
        Main entry point for edge evaluation
        
        Args:
            game_data: Game information (teams, time, etc.)
            simulation_output: Output from simulation engine
            market_data: Current market lines and odds
            market_type: SPREAD, TOTAL, or MONEYLINE
        
        Returns:
            FinalSharpOutput with complete evaluation
        """
        # Extract basic info
        game_id = game_data.get("game_id", "unknown")
        sport = game_data.get("sport", "unknown")
        
        # Get sport config
        config = get_sport_sanity_config(sport)
        if not config:
            logger.warning(f"No config for sport {sport}, using defaults")
            return self._create_no_play_final_sharp(game_id, sport, market_type, "NO_SPORT_CONFIG", game_data, market_data)
        
        # Build context objects
        game_ctx = self._build_game_context(game_data)
        sim_output = self._build_simulation_output(simulation_output, market_type)
        
        # Step 1: Run universal edge evaluation
        eval_result = self.evaluator.evaluate(
            context=game_ctx,
            simulation=sim_output
        )
        
        # Step 2: Extract model lines for FINAL_SHARP_SIDE calculation
        model_line = sim_output.model_spread if market_type == "SPREAD" else sim_output.model_total
        market_line = game_ctx.market_spread_home if market_type == "SPREAD" else game_ctx.market_total
        model_win_prob = sim_output.win_prob_home_raw
        
        # Step 3: Build FINAL_SHARP_SIDE output (single source of truth)
        final_sharp = calculate_final_sharp_side(
            game_id=game_id,
            sport=sport,
            market_type=market_type,
            home_team=game_data.get("home_team", "Home"),
            away_team=game_data.get("away_team", "Away"),
            model_line=model_line,
            market_line=market_line,
            model_win_prob=model_win_prob,
            confidence=sim_output.confidence_score / 100.0,  # Convert to 0-1 scale
            volatility=self._volatility_to_float(sim_output.volatility_bucket),
            home_is_favorite=market_line < 0 if market_type == "SPREAD" else True,
        )

        # Step 4: Record for sanity monitoring
        self._record_for_sanity_final(final_sharp, eval_result)

        # Return only the FINAL_SHARP_SIDE output for all user-facing consumers
        return final_sharp
    
    # ========================================================================
    # CONTEXT BUILDERS
    # ========================================================================
    
    def _build_game_context(self, game_data: Dict[str, Any]) -> GameContext:
        """Build GameContext from raw game data"""
        return GameContext(
            game_id=game_data.get("game_id", "unknown"),
            sport=game_data.get("sport", "unknown"),
            date=game_data.get("date", datetime.now(timezone.utc).strftime("%Y-%m-%d")),
            home_team=game_data.get("home_team", "Home"),
            away_team=game_data.get("away_team", "Away"),
            
            # Market lines
            market_spread_home=game_data.get("market_spread", 0.0),
            market_total=game_data.get("market_total", 0.0),
            market_ml_home=game_data.get("market_ml_home", 0.0),
            market_ml_away=game_data.get("market_ml_away", 0.0),
            
            # Market confirmation
            clv_forecast=game_data.get("clv_forecast"),
            line_moved_toward_model=game_data.get("line_moved_toward_model", False),
        )
    
    def _build_simulation_output(
        self,
        sim_data: Dict[str, Any],
        market_type: str
    ) -> SimulationOutput:
        """Build SimulationOutput from raw simulation data"""
        return SimulationOutput(
            # Core probabilities
            win_prob_home_raw=sim_data.get("win_prob_home", 0.5),
            win_prob_away_raw=sim_data.get("win_prob_away", 0.5),
            
            # Model projections
            model_spread=sim_data.get("model_spread", 0.0),
            model_total=sim_data.get("model_total", 0.0),
            
            # Edge calculations
            spread_edge_pts=sim_data.get("spread_edge_pts", 0.0),
            total_edge_pts=sim_data.get("total_edge_pts", 0.0),
            ml_edge_pct=sim_data.get("ml_edge_pct", 0.0),
            
            # Volatility & distribution
            volatility_bucket=sim_data.get("volatility_bucket", VolatilityBucket.MEDIUM),
            distribution_width=sim_data.get("distribution_width", 0.0),
            ot_frequency=sim_data.get("ot_frequency", 0.0),
            one_goal_games=sim_data.get("one_goal_games", 0.0),
            goal_differential=sim_data.get("goal_differential", 0.0),
            
            # Confidence
            confidence_score=sim_data.get("confidence_score", 70),
            sim_count=sim_data.get("sim_count", 10000),
            
            # Sport-specific context
            pitcher_confirmed=sim_data.get("pitcher_confirmed", True),
            lineup_confirmed=sim_data.get("lineup_confirmed", True),
            bullpen_fatigue_index=sim_data.get("bullpen_fatigue_index", 1.0),
            qb_status=sim_data.get("qb_status", "CONFIRMED"),
            goalie_confirmed=sim_data.get("goalie_confirmed", True),
            
            # Weather/park
            weather_impacted=sim_data.get("weather_impacted", False),
            weather_direction_aligned=sim_data.get("weather_direction_aligned", True),
            
            # Pace/scheme
            pace_driven_edge=sim_data.get("pace_driven_edge", False),
            scheme_variance_flag=sim_data.get("scheme_variance_flag", False),
        )
    
    # ========================================================================
    # HELPER METHODS
    # ========================================================================
    
    def _volatility_to_float(self, volatility_bucket) -> float:
        """Convert volatility bucket to float for FINAL_SHARP_SIDE"""
        if isinstance(volatility_bucket, float):
            return volatility_bucket
        
        # Convert enum to float
        volatility_map = {
            "LOW": 0.15,
            "MEDIUM": 0.25,
            "HIGH": 0.35,
            "EXTREME": 0.50,
        }
        
        if hasattr(volatility_bucket, 'value'):
            return volatility_map.get(volatility_bucket.value, 0.25)
        
        return volatility_map.get(str(volatility_bucket), 0.25)
    
    # ========================================================================
    # SANITY RECORDING
    # ========================================================================
    
    def _record_for_sanity_final(self, final_sharp: FinalSharpOutput, eval_result: EvaluationResult):
        """Record result for sanity monitoring using FinalSharpOutput"""
        try:
            today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            
            # Convert FinalSharpOutput.edge_state to EdgeState for sanity service
            edge_state_map = {
                "OFFICIAL_EDGE": EdgeState.EDGE,
                "MODEL_LEAN": EdgeState.LEAN,
                "NO_ACTION": EdgeState.NO_PLAY,
            }
            
            sanity_edge_state = edge_state_map.get(final_sharp.edge_state.value, EdgeState.NO_PLAY)
            
            self.sanity_service.record_evaluation(
                sport=final_sharp.sport,
                date=today,
                state=sanity_edge_state,
                compressed_prob=final_sharp.confidence_display / 100.0,
                reason_codes=eval_result.reason_codes,
                was_override=False,  # FinalSharpOutput doesn't track overrides directly
                was_volatility_downgrade="VOLATILITY" in str(eval_result.reason_codes),
            )
        except Exception as e:
            logger.error(f"Failed to record sanity check: {e}")
    
    # ========================================================================
    # NO PLAY HELPER
    # ========================================================================
    
    def _create_no_play_final_sharp(
        self,
        game_id: str,
        sport: str,
        market_type: str,
        reason: str,
        game_data: Dict[str, Any],
        market_data: Dict[str, Any]
    ) -> FinalSharpOutput:
        """Create a NO_ACTION FinalSharpOutput for error cases"""
        return FinalSharpOutput(
            game_id=game_id,
            sport=sport,
            market_type=market_type,
            final_sharp_side=FinalSharpSide.NONE,
            edge_state=FinalEdgeState.NO_ACTION,
            mispricing_label=MispricingLabel.NO_SIGNIFICANT_MISPRICING,
            selection_display="No Selection",
            confidence_display=0,
            edge_description="No edge detected",
            telegram_eligible=False,
            is_stable=False,
            stability_runs=0,
            _raw_model_line=0.0,
            _raw_market_line=0.0,
            _raw_edge_points=0.0,
        )


# ============================================================================
# CONVENIENCE FUNCTIONS
# ============================================================================

def evaluate_game(
    game_data: Dict[str, Any],
    simulation_output: Dict[str, Any],
    market_data: Dict[str, Any],
    market_type: str = "SPREAD",
    db=None,
    return_final_sharp: bool = True
) -> FinalSharpOutput:
    """
    Convenience function for edge evaluation
    Returns FINAL_SHARP_SIDE output only.
    """
    orchestrator = EdgeEvaluationOrchestrator(db)
    return orchestrator.evaluate_game(
        game_data=game_data,
        simulation_output=simulation_output,
        market_data=market_data,
        market_type=market_type,
        return_final_sharp=return_final_sharp,
    )


def get_all_sport_configs() -> Dict[str, Any]:
    """Get all sport configurations for debugging/display"""
    return {
        sport: config.to_dict()
        for sport, config in SPORT_SANITY_CONFIGS.items()
    }


def get_compression_factor(sport: str) -> float:
    """Get compression factor for a sport"""
    config = get_sport_sanity_config(sport)
    return config.compression_factor if config else 1.0
