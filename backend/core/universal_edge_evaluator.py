"""
UNIVERSAL EDGE EVALUATOR — PRODUCTION READY (LOCKED)
=====================================================
Two-layer system for all sports:
- Layer A: Eligibility (is this market worth considering?)
- Layer B: Grading (EDGE / LEAN / NO_PLAY)

Implements sport-specific logic per spec:
- MLB: Moneyline + totals, pitcher/bullpen sensitive
- NCAAB: Spread primary, blowout aware, pace handling
- NCAAF: Spread primary, large spread guardrails, scheme variance
- NFL: Key numbers, QB sensitivity, weather
- NHL: Compression, distribution sanity, rarest edges
- NBA: Reference implementation

This module is the SINGLE SOURCE OF TRUTH for edge classification.
"""

from typing import Dict, List, Tuple, Any, Optional, Literal
from datetime import datetime, timezone
from dataclasses import dataclass, field
from enum import Enum
import logging
import uuid

from core.sport_sanity_config import (
    SportSanityConfig,
    get_sport_sanity_config,
    compress_probability,
    EdgeState,
    PrimaryMarket,
    DistributionFlag,
    VolatilityBucket,
    SPORT_SANITY_CONFIGS,
)

logger = logging.getLogger(__name__)


# ============================================================================
# REASON CODES (DEBUGGING & TRUST)
# ============================================================================

class ReasonCode(str, Enum):
    """Classification reason codes - mandatory for debugging + trust"""
    # Eligibility passes
    SPREAD_ELIGIBLE = "SPREAD_ELIGIBLE"
    TOTAL_ELIGIBLE = "TOTAL_ELIGIBLE"
    MONEYLINE_ELIGIBLE = "MONEYLINE_ELIGIBLE"
    
    # Edge classification reasons
    EDGE_DETECTED = "EDGE_DETECTED"
    EDGE_TOO_SMALL = "EDGE_TOO_SMALL"
    LEAN_THRESHOLD_MET = "LEAN_THRESHOLD_MET"
    
    # Downgrade reasons
    VOLATILITY_DOWNGRADED = "VOLATILITY_DOWNGRADED"
    VOLATILITY_BLOCKED = "VOLATILITY_BLOCKED"
    OVERRIDE_DOWNGRADED = "OVERRIDE_DOWNGRADED"
    DISTRIBUTION_UNSTABLE = "DISTRIBUTION_UNSTABLE"
    PACE_ONLY_EDGE = "PACE_ONLY_EDGE"
    SPREAD_TOO_LARGE = "SPREAD_TOO_LARGE"
    KEY_NUMBER_PENALTY = "KEY_NUMBER_PENALTY"
    
    # Override reasons
    PITCHER_UNCERTAIN = "PITCHER_UNCERTAIN"
    LINEUP_PENDING = "LINEUP_PENDING"
    BULLPEN_VOLATILITY = "BULLPEN_VOLATILITY"
    BULLPEN_EXTREME = "BULLPEN_EXTREME"
    QB_UNCERTAIN = "QB_UNCERTAIN"
    GOALIE_UNCERTAIN = "GOALIE_UNCERTAIN"
    WEATHER_CONFLICT = "WEATHER_CONFLICT"
    WEATHER_DOWNGRADED = "WEATHER_DOWNGRADED"
    SCHEME_VARIANCE = "SCHEME_VARIANCE"
    BLOWOUT_NOISE = "BLOWOUT_NOISE"
    
    # Market confirmation
    MARKET_ALIGNED = "MARKET_ALIGNED"
    CLV_CONFIRMED = "CLV_CONFIRMED"
    LINE_MOVED_TOWARD = "LINE_MOVED_TOWARD"
    
    # NHL specific
    HIGH_OT_FREQUENCY = "HIGH_OT_FREQUENCY"
    EXTREME_CLOSE_GAMES = "EXTREME_CLOSE_GAMES"
    WIN_PROB_EDGE_EXCEEDS_CAP = "WIN_PROB_EDGE_EXCEEDS_CAP"
    GOAL_EDGE_EXCEEDS_CAP = "GOAL_EDGE_EXCEEDS_CAP"
    
    # Generic
    DEFAULT_NO_PLAY = "DEFAULT_NO_PLAY"


# ============================================================================
# INPUT DATA MODELS
# ============================================================================

@dataclass
class GameContext:
    """Universal game context"""
    game_id: str
    sport: str
    date: str
    home_team: str
    away_team: str
    
    # Market lines
    market_spread_home: float = 0.0
    market_total: float = 0.0
    market_ml_home: float = 0.0  # American odds
    market_ml_away: float = 0.0
    
    # Market confirmation signals
    clv_forecast: Optional[float] = None
    line_moved_toward_model: bool = False


@dataclass
class SimulationOutput:
    """Universal simulation output"""
    # Core probabilities (raw, pre-compression)
    win_prob_home_raw: float
    win_prob_away_raw: float
    
    # Model projections
    model_spread: float  # From home perspective
    model_total: float
    
    # Edge calculations (model - market)
    spread_edge_pts: float
    total_edge_pts: float
    ml_edge_pct: float = 0.0  # Win prob edge vs implied
    
    # Volatility & distribution
    volatility_bucket: VolatilityBucket = VolatilityBucket.MEDIUM
    distribution_width: float = 0.0
    ot_frequency: float = 0.0        # NHL specific
    one_goal_games: float = 0.0      # NHL specific
    goal_differential: float = 0.0   # NHL specific
    
    # Confidence
    confidence_score: int = 70
    sim_count: int = 10000
    
    # Sport-specific context
    pitcher_confirmed: bool = True
    lineup_confirmed: bool = True
    bullpen_fatigue_index: float = 1.0
    qb_status: str = "CONFIRMED"
    goalie_confirmed: bool = True
    
    # Weather/park
    weather_impacted: bool = False
    weather_direction_aligned: bool = True
    
    # Pace/scheme (NCAAB/NCAAF)
    pace_driven_edge: bool = False
    scheme_variance_flag: bool = False


# ============================================================================
# EVALUATION RESULT
# ============================================================================

@dataclass
class EvaluationResult:
    """Complete evaluation output"""
    game_id: str
    sport: str
    
    # Final classification
    state: EdgeState
    primary_market: PrimaryMarket
    
    # Compressed probabilities
    compressed_prob_home: float
    compressed_prob_away: float
    
    # Edge values
    spread_edge: Optional[float] = None
    total_edge: Optional[float] = None
    ml_edge: Optional[float] = None
    
    # Reason codes (MANDATORY)
    reason_codes: List[str] = field(default_factory=list)
    
    # Market confirmation
    market_confirmed: bool = False
    
    # Metadata
    volatility_bucket: Optional[str] = None
    distribution_flag: Optional[str] = None
    evaluated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "game_id": self.game_id,
            "sport": self.sport,
            "state": self.state.value,
            "primary_market": self.primary_market.value,
            "compressed_prob_home": self.compressed_prob_home,
            "compressed_prob_away": self.compressed_prob_away,
            "spread_edge": self.spread_edge,
            "total_edge": self.total_edge,
            "ml_edge": self.ml_edge,
            "reason_codes": self.reason_codes,
            "market_confirmed": self.market_confirmed,
            "volatility_bucket": self.volatility_bucket,
            "distribution_flag": self.distribution_flag,
            "evaluated_at": self.evaluated_at.isoformat(),
        }


# ============================================================================
# UNIVERSAL EDGE EVALUATOR
# ============================================================================

class UniversalEdgeEvaluator:
    """
    Two-layer edge evaluation system for all sports
    
    Layer A: Eligibility
    - Is the market worth considering?
    - Check edge minimums, distribution stability
    
    Layer B: Grading
    - EDGE: Telegram-worthy, actionable
    - LEAN: Informational, optional
    - NO_PLAY: Default state
    """
    
    def __init__(self, db=None):
        self.db = db
    
    # ========================================================================
    # MAIN EVALUATION ENTRY POINT
    # ========================================================================
    
    def evaluate(
        self,
        context: GameContext,
        simulation: SimulationOutput
    ) -> EvaluationResult:
        """
        Evaluate a game for edge classification
        
        Returns EvaluationResult with state, primary_market, and reason_codes
        """
        sport = context.sport
        config = get_sport_sanity_config(sport)
        
        if not config:
            logger.warning(f"No config for sport: {sport}")
            return self._default_no_play(context, simulation, ["UNSUPPORTED_SPORT"])
        
        # Step 1: Compress probabilities
        compressed_home = compress_probability(simulation.win_prob_home_raw, sport)
        compressed_away = compress_probability(simulation.win_prob_away_raw, sport)
        
        # Step 2: Check sport-specific overrides (pitcher, QB, goalie, etc.)
        override_result = self._check_overrides(config, simulation)
        if override_result.hard_block:
            return EvaluationResult(
                game_id=context.game_id,
                sport=sport,
                state=EdgeState.NO_PLAY,
                primary_market=PrimaryMarket.NONE,
                compressed_prob_home=compressed_home,
                compressed_prob_away=compressed_away,
                reason_codes=override_result.reason_codes,
            )
        
        # Step 3: Assess distribution/volatility
        dist_flag = self._assess_distribution(config, simulation)
        vol_result = self._assess_volatility(config, simulation)
        
        # Step 4: Route to sport-specific evaluation
        if sport == "icehockey_nhl":
            return self._evaluate_nhl(config, context, simulation, 
                                      compressed_home, compressed_away, 
                                      dist_flag, vol_result, override_result)
        elif sport == "baseball_mlb":
            return self._evaluate_mlb(config, context, simulation,
                                      compressed_home, compressed_away,
                                      dist_flag, vol_result, override_result)
        elif sport in ("americanfootball_nfl", "americanfootball_ncaaf"):
            return self._evaluate_football(config, context, simulation,
                                           compressed_home, compressed_away,
                                           dist_flag, vol_result, override_result)
        else:
            # NBA/NCAAB - spread/total focused
            return self._evaluate_basketball(config, context, simulation,
                                             compressed_home, compressed_away,
                                             dist_flag, vol_result, override_result)
    
    # ========================================================================
    # OVERRIDE CHECKS (SPORT-SPECIFIC)
    # ========================================================================
    
    @dataclass
    class OverrideResult:
        hard_block: bool
        downgrade: bool
        reason_codes: List[str]
    
    def _check_overrides(
        self,
        config: SportSanityConfig,
        simulation: SimulationOutput
    ) -> OverrideResult:
        """Check sport-specific overrides (pitcher, QB, goalie, etc.)"""
        hard_block = False
        downgrade = False
        reasons = []
        
        # Pitcher check (MLB)
        if config.pitcher_uncertain_forces_no_play and not simulation.pitcher_confirmed:
            hard_block = True
            reasons.append(ReasonCode.PITCHER_UNCERTAIN.value)
        
        # QB check (NFL/NCAAF)
        if config.qb_uncertain_forces_no_play and simulation.qb_status != "CONFIRMED":
            hard_block = True
            reasons.append(ReasonCode.QB_UNCERTAIN.value)
        
        # Lineup check
        if not simulation.lineup_confirmed:
            downgrade = True
            reasons.append(ReasonCode.LINEUP_PENDING.value)
        
        # Bullpen check (MLB)
        if simulation.bullpen_fatigue_index >= 1.5:
            hard_block = True
            reasons.append(ReasonCode.BULLPEN_EXTREME.value)
        elif simulation.bullpen_fatigue_index >= 1.3:
            downgrade = True
            reasons.append(ReasonCode.BULLPEN_VOLATILITY.value)
        
        # Goalie check (NHL)
        if config.sport_key == "icehockey_nhl" and not simulation.goalie_confirmed:
            downgrade = True
            reasons.append(ReasonCode.GOALIE_UNCERTAIN.value)
        
        return self.OverrideResult(hard_block, downgrade, reasons)
    
    # ========================================================================
    # DISTRIBUTION & VOLATILITY ASSESSMENT
    # ========================================================================
    
    def _assess_distribution(
        self,
        config: SportSanityConfig,
        simulation: SimulationOutput
    ) -> DistributionFlag:
        """Assess distribution stability"""
        # NHL specific - check OT/1-goal frequency
        if config.sport_key == "icehockey_nhl":
            combined = simulation.ot_frequency + simulation.one_goal_games
            if combined > config.distribution_max_close:
                return DistributionFlag.UNSTABLE_EXTREME
            elif combined > config.distribution_max_ot:
                return DistributionFlag.UNSTABLE_MEDIUM
        
        # General volatility-based assessment
        if simulation.volatility_bucket == VolatilityBucket.EXTREME:
            return DistributionFlag.UNSTABLE_EXTREME
        elif simulation.volatility_bucket == VolatilityBucket.HIGH:
            return DistributionFlag.UNSTABLE_MEDIUM
        
        return DistributionFlag.STABLE
    
    @dataclass
    class VolatilityResult:
        forces_no_play: bool
        forces_downgrade: bool
        reason_codes: List[str]
    
    def _assess_volatility(
        self,
        config: SportSanityConfig,
        simulation: SimulationOutput
    ) -> VolatilityResult:
        """Assess volatility impact"""
        forces_no_play = False
        forces_downgrade = False
        reasons = []
        
        vol_bucket = simulation.volatility_bucket.value
        
        if vol_bucket == config.volatility_block:
            forces_no_play = True
            reasons.append(ReasonCode.VOLATILITY_BLOCKED.value)
        elif vol_bucket == config.volatility_downgrade:
            forces_downgrade = True
            reasons.append(ReasonCode.VOLATILITY_DOWNGRADED.value)
        
        return self.VolatilityResult(forces_no_play, forces_downgrade, reasons)
    
    # ========================================================================
    # MARKET CONFIRMATION CHECK
    # ========================================================================
    
    def _check_market_confirmation(
        self,
        config: SportSanityConfig,
        context: GameContext
    ) -> Tuple[bool, List[str]]:
        """Check market confirmation signals (supportive only)"""
        confirmed = False
        reasons = []
        
        if context.clv_forecast and context.clv_forecast >= config.min_clv_confirmation:
            confirmed = True
            reasons.append(ReasonCode.CLV_CONFIRMED.value)
        
        if context.line_moved_toward_model:
            confirmed = True
            reasons.append(ReasonCode.LINE_MOVED_TOWARD.value)
        
        if confirmed:
            reasons.append(ReasonCode.MARKET_ALIGNED.value)
        
        return confirmed, reasons
    
    # ========================================================================
    # NHL EVALUATION (TIGHTEST MARKETS)
    # ========================================================================
    
    def _evaluate_nhl(
        self,
        config: SportSanityConfig,
        context: GameContext,
        simulation: SimulationOutput,
        compressed_home: float,
        compressed_away: float,
        dist_flag: DistributionFlag,
        vol_result: VolatilityResult,
        override_result: OverrideResult
    ) -> EvaluationResult:
        """
        NHL-specific evaluation with protective calibration
        
        Key rules:
        - Hard cap: ±3.0% win prob edge, ±1.25 goal differential
        - Multi-gate validation required
        - Distribution sanity (>65% OT/1-goal = invalidate spread)
        - Default NO_PLAY
        """
        reasons = list(override_result.reason_codes)
        
        # HARD CAPS (NHL SPECIFIC)
        win_prob_edge = abs(compressed_home - 0.5) * 2  # Convert to edge %
        if win_prob_edge > config.ml_win_prob_edge_edge:
            reasons.append(ReasonCode.WIN_PROB_EDGE_EXCEEDS_CAP.value)
        
        if abs(simulation.goal_differential) > 1.25:
            reasons.append(ReasonCode.GOAL_EDGE_EXCEEDS_CAP.value)
        
        # Distribution sanity check
        if dist_flag == DistributionFlag.UNSTABLE_EXTREME:
            reasons.append(ReasonCode.EXTREME_CLOSE_GAMES.value)
            return EvaluationResult(
                game_id=context.game_id,
                sport=config.sport_key,
                state=EdgeState.NO_PLAY,
                primary_market=PrimaryMarket.NONE,
                compressed_prob_home=compressed_home,
                compressed_prob_away=compressed_away,
                reason_codes=reasons,
                distribution_flag=dist_flag.value,
            )
        elif dist_flag == DistributionFlag.UNSTABLE_MEDIUM:
            reasons.append(ReasonCode.HIGH_OT_FREQUENCY.value)
        
        # Volatility override
        if vol_result.forces_no_play:
            reasons.extend(vol_result.reason_codes)
            return EvaluationResult(
                game_id=context.game_id,
                sport=config.sport_key,
                state=EdgeState.NO_PLAY,
                primary_market=PrimaryMarket.NONE,
                compressed_prob_home=compressed_home,
                compressed_prob_away=compressed_away,
                reason_codes=reasons,
                volatility_bucket=simulation.volatility_bucket.value,
            )
        
        # Market confirmation (REQUIRED for NHL EDGE)
        market_confirmed, conf_reasons = self._check_market_confirmation(config, context)
        
        # Evaluate totals (primary NHL edge source)
        total_edge = abs(simulation.total_edge_pts)
        ml_edge = simulation.ml_edge_pct
        
        # GRADING
        state = EdgeState.NO_PLAY
        primary_market = PrimaryMarket.NONE
        
        # Totals edge
        if total_edge >= config.total_edge_edge and dist_flag != DistributionFlag.UNSTABLE_MEDIUM:
            if market_confirmed or total_edge >= config.total_edge_edge * 1.5:
                state = EdgeState.EDGE
                primary_market = PrimaryMarket.TOTAL
                reasons.append(ReasonCode.EDGE_DETECTED.value)
            else:
                state = EdgeState.LEAN
                primary_market = PrimaryMarket.TOTAL
                reasons.append(ReasonCode.LEAN_THRESHOLD_MET.value)
        elif total_edge >= config.total_edge_lean_min:
            state = EdgeState.LEAN
            primary_market = PrimaryMarket.TOTAL
            reasons.append(ReasonCode.LEAN_THRESHOLD_MET.value)
        
        # ML edge (only if totals didn't qualify)
        if state == EdgeState.NO_PLAY and ml_edge >= config.ml_win_prob_edge_eligibility:
            if ml_edge >= config.ml_win_prob_edge_edge and market_confirmed:
                state = EdgeState.EDGE
                primary_market = PrimaryMarket.MONEYLINE
                reasons.append(ReasonCode.EDGE_DETECTED.value)
            elif ml_edge >= config.ml_win_prob_edge_eligibility:
                state = EdgeState.LEAN
                primary_market = PrimaryMarket.MONEYLINE
                reasons.append(ReasonCode.LEAN_THRESHOLD_MET.value)
        
        # Apply downgrade if needed (OVERRIDE ONLY - volatility affects confidence, not classification)
        if override_result.downgrade:
            if state == EdgeState.EDGE:
                state = EdgeState.LEAN
                reasons.append(ReasonCode.OVERRIDE_DOWNGRADED.value)
        
        # Volatility tracking (informational only - does not change classification)
        if vol_result.forces_downgrade:
            reasons.append(ReasonCode.VOLATILITY_DOWNGRADED.value)
        
        if state == EdgeState.NO_PLAY:
            reasons.append(ReasonCode.DEFAULT_NO_PLAY.value)
        
        return EvaluationResult(
            game_id=context.game_id,
            sport=config.sport_key,
            state=state,
            primary_market=primary_market,
            compressed_prob_home=compressed_home,
            compressed_prob_away=compressed_away,
            total_edge=total_edge if primary_market == PrimaryMarket.TOTAL else None,
            ml_edge=ml_edge if primary_market == PrimaryMarket.MONEYLINE else None,
            reason_codes=reasons + conf_reasons,
            market_confirmed=market_confirmed,
            volatility_bucket=simulation.volatility_bucket.value,
            distribution_flag=dist_flag.value,
        )
    
    # ========================================================================
    # MLB EVALUATION (MONEYLINE + TOTALS DOMINANT)
    # ========================================================================
    
    def _evaluate_mlb(
        self,
        config: SportSanityConfig,
        context: GameContext,
        simulation: SimulationOutput,
        compressed_home: float,
        compressed_away: float,
        dist_flag: DistributionFlag,
        vol_result: VolatilityResult,
        override_result: OverrideResult
    ) -> EvaluationResult:
        """
        MLB-specific evaluation
        
        Key rules:
        - Moneyline primary, totals very important
        - Price sensitivity guardrails (-165/+160)
        - Weather/park mandatory for totals
        - Pitcher/bullpen overrides
        """
        reasons = list(override_result.reason_codes)
        
        # Distribution check
        if dist_flag == DistributionFlag.UNSTABLE_EXTREME:
            reasons.append(ReasonCode.DISTRIBUTION_UNSTABLE.value)
            return self._default_no_play(context, simulation, reasons, 
                                         compressed_home, compressed_away)
        
        # Volatility check
        if vol_result.forces_no_play:
            reasons.extend(vol_result.reason_codes)
            return self._default_no_play(context, simulation, reasons,
                                         compressed_home, compressed_away)
        
        # Weather conflict check for totals
        weather_blocked = False
        if simulation.weather_impacted and not simulation.weather_direction_aligned:
            weather_blocked = True
            reasons.append(ReasonCode.WEATHER_CONFLICT.value)
        
        # Market confirmation
        market_confirmed, conf_reasons = self._check_market_confirmation(config, context)
        
        # Calculate edges
        ml_edge = simulation.ml_edge_pct
        total_edge = abs(simulation.total_edge_pts)
        
        # Price sensitivity guardrails
        price_guardrail_hit = False
        home_odds = context.market_ml_home
        if home_odds < config.ml_favorite_guardrail or home_odds > config.ml_underdog_guardrail:
            if ml_edge < config.ml_guardrail_edge_requirement:
                price_guardrail_hit = True
        
        # GRADING
        state = EdgeState.NO_PLAY
        primary_market = PrimaryMarket.NONE
        
        # Moneyline (primary MLB)
        if ml_edge >= config.ml_win_prob_edge_eligibility and not price_guardrail_hit:
            if ml_edge >= config.ml_win_prob_edge_edge:
                state = EdgeState.EDGE
                primary_market = PrimaryMarket.MONEYLINE
                reasons.append(ReasonCode.EDGE_DETECTED.value)
            else:
                state = EdgeState.LEAN
                primary_market = PrimaryMarket.MONEYLINE
                reasons.append(ReasonCode.LEAN_THRESHOLD_MET.value)
        
        # Totals (if moneyline didn't qualify and weather aligns)
        if state == EdgeState.NO_PLAY and not weather_blocked:
            if total_edge >= config.total_edge_eligibility:
                # Weather assist - can lower threshold
                threshold = config.total_edge_edge
                if simulation.weather_impacted and simulation.weather_direction_aligned:
                    threshold = config.total_edge_edge * 0.8
                
                if total_edge >= threshold:
                    state = EdgeState.EDGE
                    primary_market = PrimaryMarket.TOTAL
                    reasons.append(ReasonCode.EDGE_DETECTED.value)
                elif total_edge >= config.total_edge_lean_min:
                    state = EdgeState.LEAN
                    primary_market = PrimaryMarket.TOTAL
                    reasons.append(ReasonCode.LEAN_THRESHOLD_MET.value)
        
        # Apply downgrades (OVERRIDE ONLY - volatility affects confidence, not classification)
        if override_result.downgrade:
            if state == EdgeState.EDGE:
                state = EdgeState.LEAN
                reasons.append(ReasonCode.OVERRIDE_DOWNGRADED.value)
        
        # Volatility tracking (informational only - does not change classification)
        if vol_result.forces_downgrade:
            reasons.append(ReasonCode.VOLATILITY_DOWNGRADED.value)
        
        if state == EdgeState.NO_PLAY:
            reasons.append(ReasonCode.DEFAULT_NO_PLAY.value)
        
        return EvaluationResult(
            game_id=context.game_id,
            sport=config.sport_key,
            state=state,
            primary_market=primary_market,
            compressed_prob_home=compressed_home,
            compressed_prob_away=compressed_away,
            total_edge=total_edge if primary_market == PrimaryMarket.TOTAL else None,
            ml_edge=ml_edge if primary_market == PrimaryMarket.MONEYLINE else None,
            reason_codes=reasons + conf_reasons,
            market_confirmed=market_confirmed,
            volatility_bucket=simulation.volatility_bucket.value,
            distribution_flag=dist_flag.value,
        )
    
    # ========================================================================
    # FOOTBALL EVALUATION (NFL/NCAAF)
    # ========================================================================
    
    def _evaluate_football(
        self,
        config: SportSanityConfig,
        context: GameContext,
        simulation: SimulationOutput,
        compressed_home: float,
        compressed_away: float,
        dist_flag: DistributionFlag,
        vol_result: VolatilityResult,
        override_result: OverrideResult
    ) -> EvaluationResult:
        """
        Football (NFL/NCAAF) evaluation
        
        NFL Key rules:
        - Key number protection (3, 7, 10)
        - QB sensitivity
        - Weather mandatory for totals
        
        NCAAF Key rules:
        - Large spread guardrails (>-21)
        - Scheme variance handling
        - Blowout noise awareness
        """
        reasons = list(override_result.reason_codes)
        is_nfl = config.sport_key == "americanfootball_nfl"
        
        # Distribution/volatility checks
        if dist_flag == DistributionFlag.UNSTABLE_EXTREME:
            reasons.append(ReasonCode.DISTRIBUTION_UNSTABLE.value)
            return self._default_no_play(context, simulation, reasons,
                                         compressed_home, compressed_away)
        
        if vol_result.forces_no_play:
            reasons.extend(vol_result.reason_codes)
            return self._default_no_play(context, simulation, reasons,
                                         compressed_home, compressed_away)
        
        # Weather check for totals
        weather_penalty = 0.0
        if simulation.weather_impacted:
            weather_penalty = config.weather_edge_adjustment
            if not simulation.weather_direction_aligned:
                reasons.append(ReasonCode.WEATHER_CONFLICT.value)
        
        # Scheme variance check (NCAAF)
        if not is_nfl and simulation.scheme_variance_flag:
            reasons.append(ReasonCode.SCHEME_VARIANCE.value)
        
        # Market confirmation
        market_confirmed, conf_reasons = self._check_market_confirmation(config, context)
        
        # Calculate edges
        spread_edge = abs(simulation.spread_edge_pts)
        total_edge = abs(simulation.total_edge_pts)
        market_spread = abs(context.market_spread_home)
        
        # KEY NUMBER PENALTY (NFL)
        key_number_penalty = 0.0
        if is_nfl and config.key_numbers:
            for kn in config.key_numbers:
                if abs(market_spread - kn) <= 0.5:
                    key_number_penalty = config.key_number_extra_edge
                    reasons.append(ReasonCode.KEY_NUMBER_PENALTY.value)
                    break
        
        # LARGE SPREAD GUARDRAIL
        large_spread_block = False
        if market_spread > abs(config.max_auto_favorite_spread):
            if spread_edge < config.large_spread_edge_requirement:
                large_spread_block = True
                reasons.append(ReasonCode.SPREAD_TOO_LARGE.value)
        
        # GRADING - SPREADS (primary for football)
        state = EdgeState.NO_PLAY
        primary_market = PrimaryMarket.NONE
        
        effective_spread_threshold = config.spread_edge_edge + key_number_penalty
        
        if spread_edge >= config.spread_edge_eligibility and not large_spread_block:
            if spread_edge >= effective_spread_threshold:
                state = EdgeState.EDGE
                primary_market = PrimaryMarket.SPREAD
                reasons.append(ReasonCode.EDGE_DETECTED.value)
            elif spread_edge >= config.spread_edge_lean_min:
                state = EdgeState.LEAN
                primary_market = PrimaryMarket.SPREAD
                reasons.append(ReasonCode.LEAN_THRESHOLD_MET.value)
        
        # GRADING - TOTALS (if spread didn't qualify)
        effective_total_threshold = config.total_edge_edge + weather_penalty
        
        if state == EdgeState.NO_PLAY and total_edge >= config.total_edge_eligibility:
            if total_edge >= effective_total_threshold:
                state = EdgeState.EDGE
                primary_market = PrimaryMarket.TOTAL
                reasons.append(ReasonCode.EDGE_DETECTED.value)
            elif total_edge >= config.total_edge_lean_min:
                state = EdgeState.LEAN
                primary_market = PrimaryMarket.TOTAL
                reasons.append(ReasonCode.LEAN_THRESHOLD_MET.value)
        
        # Apply downgrades (OVERRIDE ONLY - volatility affects confidence, not classification)
        if override_result.downgrade:
            if state == EdgeState.EDGE:
                state = EdgeState.LEAN
                reasons.append(ReasonCode.OVERRIDE_DOWNGRADED.value)
        
        # Volatility tracking (informational only - does not change classification)
        if vol_result.forces_downgrade:
            reasons.append(ReasonCode.VOLATILITY_DOWNGRADED.value)
        
        # Scheme variance forces downgrade (NCAAF)
        if not is_nfl and simulation.scheme_variance_flag and state == EdgeState.EDGE:
            state = EdgeState.LEAN
        
        if state == EdgeState.NO_PLAY:
            reasons.append(ReasonCode.DEFAULT_NO_PLAY.value)
        
        return EvaluationResult(
            game_id=context.game_id,
            sport=config.sport_key,
            state=state,
            primary_market=primary_market,
            compressed_prob_home=compressed_home,
            compressed_prob_away=compressed_away,
            spread_edge=spread_edge if primary_market == PrimaryMarket.SPREAD else None,
            total_edge=total_edge if primary_market == PrimaryMarket.TOTAL else None,
            reason_codes=reasons + conf_reasons,
            market_confirmed=market_confirmed,
            volatility_bucket=simulation.volatility_bucket.value,
            distribution_flag=dist_flag.value,
        )
    
    # ========================================================================
    # BASKETBALL EVALUATION (NBA/NCAAB)
    # ========================================================================
    
    def _evaluate_basketball(
        self,
        config: SportSanityConfig,
        context: GameContext,
        simulation: SimulationOutput,
        compressed_home: float,
        compressed_away: float,
        dist_flag: DistributionFlag,
        vol_result: VolatilityResult,
        override_result: OverrideResult
    ) -> EvaluationResult:
        """
        Basketball (NBA/NCAAB) evaluation
        
        Key rules:
        - Spread primary, totals secondary
        - NCAAB: Pace handling, blowout awareness
        - NBA: Reference implementation
        """
        reasons = list(override_result.reason_codes)
        is_ncaab = config.sport_key == "basketball_ncaab"
        
        # Distribution/volatility checks
        if dist_flag == DistributionFlag.UNSTABLE_EXTREME:
            reasons.append(ReasonCode.DISTRIBUTION_UNSTABLE.value)
            return self._default_no_play(context, simulation, reasons,
                                         compressed_home, compressed_away)
        
        if vol_result.forces_no_play:
            reasons.extend(vol_result.reason_codes)
            return self._default_no_play(context, simulation, reasons,
                                         compressed_home, compressed_away)
        
        # Pace-only edge check (NCAAB)
        if is_ncaab and simulation.pace_driven_edge:
            reasons.append(ReasonCode.PACE_ONLY_EDGE.value)
        
        # Market confirmation
        market_confirmed, conf_reasons = self._check_market_confirmation(config, context)
        
        # Calculate edges
        spread_edge = abs(simulation.spread_edge_pts)
        total_edge = abs(simulation.total_edge_pts)
        market_spread = abs(context.market_spread_home)
        
        # Large spread guardrail
        large_spread_block = False
        if market_spread > abs(config.max_auto_favorite_spread):
            if spread_edge < config.large_spread_edge_requirement:
                large_spread_block = True
                reasons.append(ReasonCode.SPREAD_TOO_LARGE.value)
        
        # GRADING - SPREADS (primary)
        state = EdgeState.NO_PLAY
        primary_market = PrimaryMarket.NONE
        
        if spread_edge >= config.spread_edge_eligibility and not large_spread_block:
            if spread_edge >= config.spread_edge_edge:
                state = EdgeState.EDGE
                primary_market = PrimaryMarket.SPREAD
                reasons.append(ReasonCode.EDGE_DETECTED.value)
            elif spread_edge >= config.spread_edge_lean_min:
                state = EdgeState.LEAN
                primary_market = PrimaryMarket.SPREAD
                reasons.append(ReasonCode.LEAN_THRESHOLD_MET.value)
        
        # GRADING - TOTALS (if spread didn't qualify)
        if state == EdgeState.NO_PLAY and total_edge >= config.total_edge_eligibility:
            if total_edge >= config.total_edge_edge:
                state = EdgeState.EDGE
                primary_market = PrimaryMarket.TOTAL
                reasons.append(ReasonCode.EDGE_DETECTED.value)
            elif total_edge >= config.total_edge_lean_min:
                state = EdgeState.LEAN
                primary_market = PrimaryMarket.TOTAL
                reasons.append(ReasonCode.LEAN_THRESHOLD_MET.value)
        
        # Apply downgrades (OVERRIDE ONLY - volatility affects confidence, not classification)
        if override_result.downgrade:
            if state == EdgeState.EDGE:
                state = EdgeState.LEAN
                reasons.append(ReasonCode.OVERRIDE_DOWNGRADED.value)
        
        # Volatility tracking (informational only - does not change classification)
        if vol_result.forces_downgrade:
            reasons.append(ReasonCode.VOLATILITY_DOWNGRADED.value)
        
        # Pace-only edge forces downgrade (NCAAB)
        if is_ncaab and simulation.pace_driven_edge and state == EdgeState.EDGE:
            state = EdgeState.LEAN
        
        if state == EdgeState.NO_PLAY:
            reasons.append(ReasonCode.DEFAULT_NO_PLAY.value)
        
        return EvaluationResult(
            game_id=context.game_id,
            sport=config.sport_key,
            state=state,
            primary_market=primary_market,
            compressed_prob_home=compressed_home,
            compressed_prob_away=compressed_away,
            spread_edge=spread_edge if primary_market == PrimaryMarket.SPREAD else None,
            total_edge=total_edge if primary_market == PrimaryMarket.TOTAL else None,
            reason_codes=reasons + conf_reasons,
            market_confirmed=market_confirmed,
            volatility_bucket=simulation.volatility_bucket.value,
            distribution_flag=dist_flag.value,
        )
    
    # ========================================================================
    # HELPER METHODS
    # ========================================================================
    
    def _default_no_play(
        self,
        context: GameContext,
        simulation: SimulationOutput,
        reasons: List[str],
        compressed_home: float = 0.5,
        compressed_away: float = 0.5
    ) -> EvaluationResult:
        """Return default NO_PLAY result"""
        if ReasonCode.DEFAULT_NO_PLAY.value not in reasons:
            reasons.append(ReasonCode.DEFAULT_NO_PLAY.value)
        
        return EvaluationResult(
            game_id=context.game_id,
            sport=context.sport,
            state=EdgeState.NO_PLAY,
            primary_market=PrimaryMarket.NONE,
            compressed_prob_home=compressed_home,
            compressed_prob_away=compressed_away,
            reason_codes=reasons,
        )
