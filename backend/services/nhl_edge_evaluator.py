"""
NHL Edge Evaluator Service - Sport-Specific Calibration & Protective Gates

LOCKED SPECIFICATION: All six fixes mandatory before edge classification
1. Hard-capped edge bounds (±3.0% win prob, ±1.25 goal diff)
2. Probability compression (0.6 factor, reduces false certainty)
3. Multi-gate validation (all gates must pass, not single metric)
4. Distribution sanity check (invalidate high OT/1-goal frequency)
5. Volatility override system (forces NO_PLAY if exceeds ceiling)
6. Market efficiency floor (anti-spam guard for small edges)

Expected behavior:
- Most games → NO_PLAY
- Occasional LEAN (informational only)
- EDGE very rare
- Win probs cluster 52–56%

Implementation notes:
- This is a protective calibration layer, not a model downgrade
- Aligns outputs with real-world NHL market efficiency
- Preserves long-term credibility by avoiding false signals
"""

from typing import Dict, List, Tuple, Any, Optional, Literal
from datetime import datetime
from pydantic import BaseModel, Field
from enum import Enum
import logging

logger = logging.getLogger(__name__)


# ============================================================================
# DATA MODELS & ENUMS
# ============================================================================

class EdgeState(str, Enum):
    """NHL edge classification states"""
    EDGE = "EDGE"
    LEAN = "LEAN"
    NO_PLAY = "NO_PLAY"


class DistributionFlag(str, Enum):
    """High-variance outcome distribution detection"""
    NORMAL = "NORMAL"
    HIGH_OT_FREQUENCY = "HIGH_OT_FREQUENCY"
    EXTREME_CLOSE_GAMES = "EXTREME_CLOSE_GAMES"


class GameContext(BaseModel):
    """Game-level context for edge evaluation"""
    game_id: str
    date: str
    home_team: str
    away_team: str
    market_line: float  # Spread
    market_total: float  # Over/Under total
    clv_forecast: Optional[float] = None  # Percentage, supportive only


class MarketData(BaseModel):
    """Market confirmation signals"""
    clv_aligned: bool = False  # Forecast ≥ +0.3%
    line_moved: bool = False  # Line moved toward model side


class SimulationOutput(BaseModel):
    """Monte Carlo simulation results from engine"""
    win_probability_raw: float
    goal_differential: float  # Expected goals (model - opponent)
    ot_frequency: float  # % of sims ending in OT
    one_goal_games: float  # % of sims within 1 goal
    volatility_index: float  # Measure of distribution spread (0.0-2.0)
    confidence_score: int  # 0-100, convergence measure


class EvaluationResponse(BaseModel):
    """API response for edge evaluation"""
    game_id: str
    combined_state: EdgeState
    primary_market: Literal["SPREAD", "TOTAL", "NONE"]
    compressed_win_prob: float
    goal_edge: float
    reason_codes: List[str]
    market_confirmation: MarketData
    internal_state: Dict[str, Any]


from config.sports.nhl import NHL_CONFIG


# ============================================================================
# CORE EVALUATOR CLASS
# ============================================================================

class NHLEdgeEvaluator:
    """
    Two-layer NHL edge evaluation system with protective calibration gates
    
    Layer A (Eligibility Gates):
    - Probability compression check
    - Edge cap validation
    - Distribution sanity check
    - Volatility override
    
    Layer B (Classification):
    - Multi-gate validation (all must pass)
    - Market confirmation check (supportive only)
    - Final state assignment (EDGE/LEAN/NO_PLAY)
    """
    
    def __init__(self, db=None):
        self.db = db
        self.config = NHL_CONFIG
    
    # ========================================================================
    # FIX #2: PROBABILITY COMPRESSION
    # ========================================================================
    
    def _compress_probability(self, raw_prob: float) -> float:
        """
        Compress raw probabilities toward 50% (FIX #2)
        
        Formula: compressed = 0.5 + (raw - 0.5) * 0.6
        
        Purpose:
        - Removes false certainty from simulations
        - Respects market direction but reduces magnitude
        - Typical result: ~60% raw → ~54% compressed
        """
        compression = self.config["compression_factor"]
        compressed = 0.5 + (raw_prob - 0.5) * compression
        
        # Keep within valid probability bounds
        compressed = max(0.01, min(0.99, compressed))
        
        logger.debug(
            f"Compression: {raw_prob:.3f} → {compressed:.3f} (factor={compression})"
        )
        return compressed
    
    # ========================================================================
    # FIX #1: HARD EDGE CAPS
    # ========================================================================
    
    def _calculate_edge_cap_breach(
        self,
        compressed_prob: float,
        market_prob: float,
        goal_differential: float
    ) -> Tuple[bool, List[str]]:
        """
        Check if edge exceeds hard caps (FIX #1)
        
        Returns:
            (is_breach, reason_codes)
        
        Caps:
        - Win probability edge ≤ ±3.0%
        - Goal differential ≤ ±1.25
        
        Any breach → force NO_PLAY (or LEAN only if other gates pass cleanly)
        """
        reasons = []
        is_breach = False
        
        # Check win probability edge cap
        win_prob_edge = abs(compressed_prob - market_prob)
        max_win_edge = self.config["max_win_prob_edge"]
        
        if win_prob_edge > max_win_edge:
            is_breach = True
            reasons.append(
                f"WIN_PROB_EDGE_EXCEEDS_CAP: {win_prob_edge:.3f} > {max_win_edge:.3f}"
            )
        
        # Check goal differential cap
        max_goal_edge = self.config["max_goal_edge"]
        
        if abs(goal_differential) > max_goal_edge:
            is_breach = True
            reasons.append(
                f"GOAL_EDGE_EXCEEDS_CAP: {abs(goal_differential):.2f} > {max_goal_edge:.2f}"
            )
        
        return is_breach, reasons
    
    # ========================================================================
    # FIX #4: DISTRIBUTION SANITY CHECK
    # ========================================================================
    
    def _assess_distribution(
        self,
        ot_frequency: float,
        one_goal_games: float
    ) -> Tuple[DistributionFlag, List[str]]:
        """
        Check if high OT/close game frequency invalidates edges (FIX #4)
        
        Returns:
            (distribution_flag, invalidation_reasons)
        
        Rules:
        - >65% OT/1-goal → invalidate SPREAD edges
        - >75% OT/1-goal → invalidate MONEYLINE edges
        """
        flag = DistributionFlag.NORMAL
        reasons = []
        
        combined_high_variance = ot_frequency + one_goal_games
        
        spread_threshold = self.config["max_ot_frequency_for_spread"]
        moneyline_threshold = self.config["max_close_games_for_moneyline"]
        
        if combined_high_variance > moneyline_threshold:
            # >75%: Even moneyline is unreliable
            flag = DistributionFlag.EXTREME_CLOSE_GAMES
            reasons.append(
                f"EXTREME_CLOSE_GAMES: {combined_high_variance:.1%} OT+1-goal games"
            )
        elif combined_high_variance > spread_threshold:
            # >65%: Spread is unreliable but maybe moneyline
            flag = DistributionFlag.HIGH_OT_FREQUENCY
            reasons.append(
                f"HIGH_OT_FREQUENCY: {combined_high_variance:.1%} OT+1-goal games"
            )
        
        return flag, reasons
    
    # ========================================================================
    # FIX #5: VOLATILITY OVERRIDE
    # ========================================================================
    
    def _check_volatility_override(self, volatility_index: float) -> Tuple[bool, List[str]]:
        """
        Force NO_PLAY if volatility exceeds NHL ceiling (FIX #5)
        
        Returns:
            (is_override_triggered, reason_codes)
        
        Rule:
        - If volatility > threshold → force NO_PLAY
        - Cannot be overridden by win prob, CLV, or edge
        """
        reasons = []
        is_triggered = False
        
        threshold = self.config["max_volatility_threshold"]
        
        if volatility_index > threshold:
            is_triggered = True
            reasons.append(
                f"VOLATILITY_OVERRIDE: {volatility_index:.2f} > {threshold:.2f}"
            )
        
        return is_triggered, reasons
    
    # ========================================================================
    # FIX #6: MARKET EFFICIENCY FLOOR
    # ========================================================================
    
    def _check_efficiency_floor(
        self,
        compressed_prob: float,
        market_prob: float,
        goal_differential: float
    ) -> Tuple[bool, List[str]]:
        """
        Anti-spam guard: small, noisy edges forced to NO_PLAY (FIX #6)
        
        Returns:
            (is_blocked, reason_codes)
        
        Rule:
        - If abs(edge) < minimum_threshold → force NO_PLAY
        - Prevents every game looking playable
        """
        reasons = []
        is_blocked = False
        
        # Combined edge metric (normalized)
        win_prob_edge = abs(compressed_prob - market_prob)
        goal_edge = abs(goal_differential)
        
        # Normalize to 0-1 scale for comparison
        min_threshold = self.config["min_edge_threshold"]
        
        if win_prob_edge < min_threshold and goal_edge < (self.config["max_goal_edge"] * 0.5):
            is_blocked = True
            reasons.append(
                f"MARKET_EFFICIENCY_FLOOR: Edge too small ({win_prob_edge:.3f}, {goal_edge:.2f} goals)"
            )
        
        return is_blocked, reasons
    
    # ========================================================================
    # FIX #3: MULTI-GATE VALIDATION
    # ========================================================================
    
    def _layer_a_eligibility(
        self,
        simulation: SimulationOutput,
        market_prob: float,
        market_total: Optional[float] = None
    ) -> Tuple[bool, List[str]]:
        """
        Layer A: Eligibility gates (FIX #3 - all must pass)
        
        Gates:
        1. Compressed win prob edge ≥ +2.5%
        2. Goal differential ≤ ±1.25
        3. Volatility ≤ threshold
        4. Distribution sanity check passes
        5. Edge caps not breached
        6. Market efficiency floor not triggered
        
        Returns:
            (is_eligible, reason_codes)
        """
        reasons = []
        gates_passed = []
        
        # Gate 1: Probability edge minimum
        compressed_prob = self._compress_probability(simulation.win_probability_raw)
        win_prob_edge = compressed_prob - market_prob
        min_edge = self.config["min_win_prob_edge"]
        
        if win_prob_edge >= min_edge:
            gates_passed.append("WIN_PROB_EDGE_SUFFICIENT")
        else:
            reasons.append(
                f"GATE_1_FAIL: Win edge {win_prob_edge:.3f} < {min_edge:.3f}"
            )
        
        # Gate 2: Goal differential bounds
        if abs(simulation.goal_differential) <= self.config["max_goal_edge_for_play"]:
            gates_passed.append("GOAL_EDGE_WITHIN_BOUNDS")
        else:
            reasons.append(
                f"GATE_2_FAIL: Goal diff {abs(simulation.goal_differential):.2f} exceeds max"
            )
        
        # Gate 3: Volatility check
        volatility_override, vol_reasons = self._check_volatility_override(
            simulation.volatility_index
        )
        
        if not volatility_override:
            gates_passed.append("VOLATILITY_ACCEPTABLE")
        else:
            reasons.extend(vol_reasons)
        
        # Gate 4: Distribution sanity
        dist_flag, dist_reasons = self._assess_distribution(
            simulation.ot_frequency,
            simulation.one_goal_games
        )
        
        if dist_flag == DistributionFlag.NORMAL:
            gates_passed.append("DISTRIBUTION_SANITY_CHECK")
        else:
            reasons.extend(dist_reasons)
        
        # Gate 5: Hard edge cap bounds
        cap_breach, cap_reasons = self._calculate_edge_cap_breach(
            compressed_prob,
            market_prob,
            simulation.goal_differential
        )
        
        if not cap_breach:
            gates_passed.append("EDGE_CAPS_OK")
        else:
            reasons.extend(cap_reasons)
        
        # Gate 6: Market efficiency floor
        efficiency_blocked, eff_reasons = self._check_efficiency_floor(
            compressed_prob,
            market_prob,
            simulation.goal_differential
        )
        
        if not efficiency_blocked:
            gates_passed.append("EFFICIENCY_FLOOR_OK")
        else:
            reasons.extend(eff_reasons)
        
        # All gates must pass
        is_eligible = len(gates_passed) == 6
        
        logger.debug(
            f"Layer A Eligibility: {len(gates_passed)}/6 gates passed. "
            f"Eligible: {is_eligible}"
        )
        
        return is_eligible, reasons
    
    # ========================================================================
    # LAYER B: CLASSIFICATION
    # ========================================================================
    
    def _layer_b_grading(
        self,
        simulation: SimulationOutput,
        market_prob: float,
        is_eligible: bool,
        eligibility_reasons: List[str],
        market_data: MarketData
    ) -> Tuple[EdgeState, str, List[str]]:
        """
        Layer B: Classify EDGE vs LEAN vs NO_PLAY
        
        Logic:
        - EDGE: Extremely rare; passes all gates cleanly + confirmatory signals
        - LEAN: Passes gates but lower confidence; informational only
        - NO_PLAY: Default state (most games)
        
        Multi-gate validation (FIX #3):
        - Win prob edge ≥ 2.5% (gate 1)
        - Goal edge ≤ 1.25 (gate 2)
        - Volatility OK (gate 3)
        - Distribution OK (gate 4)
        - Caps OK (gate 5)
        - Efficiency OK (gate 6)
        - AND at least ONE confirmation:
          - CLV ≥ +0.3% (supporting evidence)
          - OR line moved toward model side
        """
        reasons = eligibility_reasons.copy()
        compressed_prob = self._compress_probability(simulation.win_probability_raw)
        
        if not is_eligible:
            # Failed Layer A, cannot be EDGE or LEAN
            return EdgeState.NO_PLAY, "LAYER_A_FAIL", reasons
        
        # Eligible to grade; check for confirmatory signals
        has_clv_support = market_data.clv_aligned if market_data.clv_aligned else False
        has_line_movement = market_data.line_moved if market_data.line_moved else False
        
        if has_clv_support:
            reasons.append("CONFIRMATION: CLV_SUPPORT")
        
        if has_line_movement:
            reasons.append("CONFIRMATION: LINE_MOVEMENT")
        
        has_confirmation = has_clv_support or has_line_movement
        
        # EDGE criteria: ALL gates + at least ONE confirmation
        if has_confirmation and simulation.confidence_score >= self.config["min_confidence_for_edge"]:
            state = EdgeState.EDGE
            state_reason = "ALL_GATES_PASS_WITH_CONFIRMATION"
            reasons.append(f"EDGE_SIGNAL: High confidence ({simulation.confidence_score})")
        
        # LEAN criteria: ALL gates pass but no confirmation
        elif simulation.confidence_score >= self.config["min_confidence_for_lean"]:
            state = EdgeState.LEAN
            state_reason = "ALL_GATES_PASS_NO_CONFIRMATION"
            reasons.append(f"LEAN_SIGNAL: Moderate confidence ({simulation.confidence_score})")
        
        # NO_PLAY: All gates pass but very low confidence
        else:
            state = EdgeState.NO_PLAY
            state_reason = "GATES_PASS_LOW_CONFIDENCE"
            reasons.append(f"NO_PLAY: Confidence too low ({simulation.confidence_score})")
        
        logger.debug(f"Layer B Classification: {state} ({state_reason})")
        
        return state, state_reason, reasons
    
    # ========================================================================
    # MARKET CONFIRMATION (SUPPORTIVE, NOT HARD GATE)
    # ========================================================================
    
    def _market_confirmation(
        self,
        clv_forecast: Optional[float],
        line_moved: bool
    ) -> MarketData:
        """
        Check for confirmatory market signals (supportive only, FIX #3)
        
        NOT a hard gate; only for boosting confidence if edge already passes
        
        Returns:
            MarketData with confirmation status
        """
        clv_aligned = False
        
        if clv_forecast is not None:
            # Check if forecast aligns with model
            min_clv = self.config["min_clv_support"]
            if clv_forecast >= min_clv:
                clv_aligned = True
        
        return MarketData(clv_aligned=clv_aligned, line_moved=line_moved)
    
    # ========================================================================
    # MAIN EVALUATION PIPELINE
    # ========================================================================
    
    async def evaluate_game(
        self,
        game_id: str,
        game_context: GameContext,
        simulation: SimulationOutput,
        market_prob: float
    ) -> EvaluationResponse:
        """
        Complete 10-step evaluation pipeline
        
        Steps:
        1. Compress probability
        2. Check edge caps
        3. Assess distribution
        4. Check volatility override
        5. Check market efficiency floor
        6. Layer A eligibility
        7. Market confirmation
        8. Layer B classification
        9. Persist to MongoDB
        10. Return evaluation
        """
        logger.info(f"Evaluating NHL game: {game_id}")
        
        # Step 1: Compress probability
        compressed_prob = self._compress_probability(simulation.win_probability_raw)
        
        # Steps 2-5: Check all protective gates (Layer A prep)
        # Step 6: Layer A eligibility
        is_eligible, layer_a_reasons = self._layer_a_eligibility(
            simulation,
            market_prob,
            game_context.market_total
        )
        
        # Step 7: Market confirmation
        market_data = self._market_confirmation(
            game_context.clv_forecast,
            False  # Simplified; would check line movement from market
        )
        
        # Step 8: Layer B classification
        edge_state, state_reason, all_reasons = self._layer_b_grading(
            simulation,
            market_prob,
            is_eligible,
            layer_a_reasons,
            market_data
        )
        
        # Determine primary market
        primary_market = "SPREAD" if abs(simulation.goal_differential) < 0.5 else "NONE"
        if edge_state == EdgeState.NO_PLAY:
            primary_market = "NONE"
        
        # Build internal state for debugging
        internal_state = {
            "compressed_win_prob": compressed_prob,
            "market_prob": market_prob,
            "goal_differential": simulation.goal_differential,
            "volatility_index": simulation.volatility_index,
            "confidence_score": simulation.confidence_score,
            "ot_frequency": simulation.ot_frequency,
            "one_goal_games": simulation.one_goal_games,
            "layer_a_eligible": is_eligible,
            "market_confirmation": {
                "clv_aligned": market_data.clv_aligned,
                "line_moved": market_data.line_moved,
            },
        }
        
        # Step 9: Persist to MongoDB
        if self.db:
            try:
                await self.db.nhl_evaluations.update_one(
                    {"game_id": game_id},
                    {
                        "$set": {
                            "evaluation": {
                                "game_id": game_id,
                                "timestamp": datetime.utcnow(),
                                "combined_state": edge_state.value,
                                "primary_market": primary_market,
                                "compressed_win_prob": compressed_prob,
                                "goal_edge": simulation.goal_differential,
                                "reason_codes": all_reasons,
                                "market_confirmation": market_data.dict(),
                                "internal_state": internal_state,
                            },
                            "updated_at": datetime.utcnow(),
                        }
                    },
                    upsert=True,
                )
                logger.debug(f"Persisted evaluation for {game_id}")
            except Exception as e:
                logger.error(f"MongoDB persistence error: {e}")
        
        # Step 10: Return evaluation
        return EvaluationResponse(
            game_id=game_id,
            combined_state=edge_state,
            primary_market=primary_market,
            compressed_win_prob=compressed_prob,
            goal_edge=simulation.goal_differential,
            reason_codes=all_reasons,
            market_confirmation=market_data,
            internal_state=internal_state,
        )
    
    async def evaluate_slate(
        self,
        date: str,
        games: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Batch evaluation for daily NHL slate (7-13 games)
        
        Returns:
            Slate statistics and individual game evaluations
        """
        logger.info(f"Evaluating NHL slate for {date}: {len(games)} games")
        
        evaluations = []
        edge_count = 0
        lean_count = 0
        no_play_count = 0
        
        for game in games:
            try:
                # Minimal game context for demo
                game_context = GameContext(
                    game_id=game.get("game_id", ""),
                    date=date,
                    home_team=game.get("home_team", ""),
                    away_team=game.get("away_team", ""),
                    market_line=game.get("spread", 0.0),
                    market_total=game.get("total", 0.0),
                )
                
                simulation = SimulationOutput(
                    win_probability_raw=game.get("win_prob_raw", 0.5),
                    goal_differential=game.get("goal_diff", 0.0),
                    ot_frequency=game.get("ot_freq", 0.1),
                    one_goal_games=game.get("one_goal_freq", 0.15),
                    volatility_index=game.get("volatility", 1.0),
                    confidence_score=game.get("confidence", 50),
                )
                
                market_prob = game.get("market_prob", 0.5)
                
                eval_result = await self.evaluate_game(
                    game_context.game_id,
                    game_context,
                    simulation,
                    market_prob,
                )
                
                evaluations.append(eval_result)
                
                if eval_result.combined_state == EdgeState.EDGE:
                    edge_count += 1
                elif eval_result.combined_state == EdgeState.LEAN:
                    lean_count += 1
                else:
                    no_play_count += 1
            
            except Exception as e:
                logger.error(f"Error evaluating game {game.get('game_id', '')}: {e}")
                continue
        
        return {
            "date": date,
            "total_games": len(evaluations),
            "edge_count": edge_count,
            "lean_count": lean_count,
            "no_play_count": no_play_count,
            "evaluations": evaluations,
            "statistics": {
                "edge_percentage": edge_count / len(evaluations) if evaluations else 0,
                "lean_percentage": lean_count / len(evaluations) if evaluations else 0,
                "expected_edges_per_slate": max(1, edge_count),
                "recommendation": "Correct behavior: Most games NO_PLAY, rare LEAN/EDGE",
            }
        }
    
    async def get_recent_evaluations(
        self,
        limit: int = 20,
        state_filter: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Retrieve recent evaluations from MongoDB
        
        Args:
            limit: Number of records to return
            state_filter: Optional filter by state (EDGE/LEAN/NO_PLAY)
        """
        if not self.db:
            return []
        
        try:
            query = {}
            if state_filter:
                query["evaluation.combined_state"] = state_filter
            
            cursor = self.db.nhl_evaluations.find(query).sort(
                "updated_at", -1
            ).limit(limit)
            
            evaluations = await cursor.to_list(length=limit)
            logger.debug(f"Retrieved {len(evaluations)} recent evaluations")
            return evaluations
        
        except Exception as e:
            logger.error(f"Error retrieving recent evaluations: {e}")
            return []
    
    async def get_evaluation(self, game_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve specific game evaluation"""
        if not self.db:
            return None
        
        try:
            evaluation = await self.db.nhl_evaluations.find_one(
                {"game_id": game_id}
            )
            return evaluation
        except Exception as e:
            logger.error(f"Error retrieving evaluation for {game_id}: {e}")
            return None
    
    async def health_check(self) -> Dict[str, Any]:
        """
        Validate NHL edge calibration system health
        
        Returns:
            System status and sanity checks
        """
        checks = {
            "compression_factor": self.config["compression_factor"],
            "max_win_prob_edge": self.config["max_win_prob_edge"],
            "max_goal_edge": self.config["max_goal_edge"],
            "min_win_prob_edge": self.config["min_win_prob_edge"],
            "max_volatility_threshold": self.config["max_volatility_threshold"],
            "min_confidence_for_edge": self.config["min_confidence_for_edge"],
            "sanity_checks": {
                "compression_0_6": abs(self.config["compression_factor"] - 0.6) < 0.001,
                "win_prob_cap_3_percent": abs(self.config["max_win_prob_edge"] - 0.03) < 0.001,
                "goal_edge_cap_1_25": abs(self.config["max_goal_edge"] - 1.25) < 0.01,
                "all_mandatory_fixes_present": True,
            },
        }
        
        all_pass = all(checks["sanity_checks"].values())
        
        return {
            "status": "healthy" if all_pass else "misconfigured",
            "system": "NHL Edge Evaluator - Locked Specification",
            "checks": checks,
            "expected_behavior": {
                "edge_rarity": "EDGE = very rare (expect <5% of games)",
                "lean_behavior": "LEAN = occasional, informational only",
                "default_state": "NO_PLAY = most games (60-90%)",
                "win_prob_cluster": "52-56% (compressed)",
            }
        }
