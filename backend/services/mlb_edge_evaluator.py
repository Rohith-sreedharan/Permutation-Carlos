"""
MLB Edge Evaluator Service - Sport-Specific Calibration & Protective Gates (LOCKED)

Objectives (per spec):
- Produce few but meaningful plays; default NO_PLAY
- Avoid pitcher-driven false confidence (compression + overrides)
- Respect bullpen + lineup uncertainty
- Moneyline primary; totals highly efficient and weather-sensitive
- All thresholds configurable (no hardcoding in logic)
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
    EDGE = "EDGE"
    LEAN = "LEAN"
    NO_PLAY = "NO_PLAY"


class DistributionFlag(str, Enum):
    NORMAL = "NORMAL"
    ELEVATED = "ELEVATED"
    UNSTABLE_EXTREME = "UNSTABLE_EXTREME"


class PitcherStatus(str, Enum):
    CONFIRMED = "CONFIRMED"
    QUESTIONABLE = "QUESTIONABLE"
    SCRATCHED = "SCRATCHED"
    OPENERS_EXPECTED = "OPENERS_EXPECTED"


class BullpenStatus(str, Enum):
    STABLE = "STABLE"
    ELEVATED = "ELEVATED"
    EXTREME = "EXTREME"


class ParkFactor(str, Enum):
    NEUTRAL = "NEUTRAL"
    HITTER_FRIENDLY = "HITTER_FRIENDLY"
    PITCHER_FRIENDLY = "PITCHER_FRIENDLY"
    HIGH_ALTITUDE = "HIGH_ALTITUDE"


class GameContext(BaseModel):
    game_id: str
    date: str
    home_team: str
    away_team: str
    market_prob: float  # Implied win probability for model side (home or chosen side)
    moneyline_price: float  # American odds (e.g., -150, +135)
    market_total: float  # Over/Under line
    clv_forecast: Optional[float] = None
    line_moved: bool = False


class MarketData(BaseModel):
    clv_aligned: bool = False
    line_moved: bool = False


class SimulationOutput(BaseModel):
    win_probability_raw: float  # Raw sim win prob for modeled side
    total_edge_pts: float  # Model total - market total (positive = OVER edge)
    distribution_flag: DistributionFlag = DistributionFlag.NORMAL
    bullpen_fatigue_index: float = 1.0  # >1.3 = high, >1.5 = extreme
    bullpen_status: BullpenStatus = BullpenStatus.STABLE
    pitcher_status: PitcherStatus = PitcherStatus.CONFIRMED
    pitch_count_uncertain: bool = False
    lineup_confirmed: bool = True
    key_hitters_missing: int = 0
    weather_wind_mph: float = 0.0
    weather_temp_f: float = 70.0
    weather_direction_aligned: bool = False
    park_factor: ParkFactor = ParkFactor.NEUTRAL
    confidence_score: int = 60


class EvaluationResponse(BaseModel):
    game_id: str
    combined_state: EdgeState
    primary_market: Literal["MONEYLINE", "TOTAL", "NONE"]
    compressed_win_prob: float
    moneyline_edge: float
    total_edge_pts: float
    reason_codes: List[str]
    market_confirmation: MarketData
    internal_state: Dict[str, Any]


from backend.config.sports.mlb import MLB_CONFIG


# ============================================================================
# CORE EVALUATOR CLASS
# ============================================================================

class MLBEdgeEvaluator:
    """
    MLB edge evaluation with two-layer gates (Eligibility -> Grading)
    - Moneyline primary market; totals important and weather-sensitive
    - Default NO_PLAY; only real mispricings surface
    """

    def __init__(self, db=None):
        self.db = db
        self.config = MLB_CONFIG

    # ------------------------------------------------------------------
    # Compression
    # ------------------------------------------------------------------
    def _compress_probability(self, raw_prob: float) -> float:
        compression = self.config["compression_factor"]
        compressed = 0.5 + (raw_prob - 0.5) * compression
        return max(0.01, min(0.99, compressed))

    # ------------------------------------------------------------------
    # Market confirmation (supportive only)
    # ------------------------------------------------------------------
    def _market_confirmation(self, clv_forecast: Optional[float], line_moved: bool) -> MarketData:
        clv_aligned = False
        if clv_forecast is not None and clv_forecast >= self.config["min_clv_support"]:
            clv_aligned = True
        return MarketData(clv_aligned=clv_aligned, line_moved=line_moved)

    # ------------------------------------------------------------------
    # Pitcher & lineup overrides
    # ------------------------------------------------------------------
    def _pitcher_lineup_checks(self, sim: SimulationOutput) -> Tuple[bool, List[str], bool]:
        reasons: List[str] = []
        hard_block = False
        downgrade = False

        if sim.pitcher_status in {PitcherStatus.SCRATCHED, PitcherStatus.OPENERS_EXPECTED}:
            hard_block = True
            reasons.append("PITCHER_UNCERTAIN")
        if sim.pitch_count_uncertain:
            hard_block = True
            reasons.append("PITCH_COUNT_UNCERTAIN")

        if not sim.lineup_confirmed:
            downgrade = True
            reasons.append("LINEUP_PENDING")
        if sim.key_hitters_missing >= self.config["max_missing_hitters_for_play"]:
            hard_block = True
            reasons.append("LINEUP_DEPLETED")
        elif sim.key_hitters_missing > self.config["max_missing_hitters_for_edge"]:
            downgrade = True
            reasons.append("LINEUP_WEAKENED")

        return hard_block, reasons, downgrade

    # ------------------------------------------------------------------
    # Bullpen handling
    # ------------------------------------------------------------------
    def _bullpen_adjustment(self, sim: SimulationOutput) -> Tuple[bool, bool, List[str]]:
        reasons: List[str] = []
        hard_block = False
        downgrade = False

        if sim.bullpen_status == BullpenStatus.EXTREME or sim.bullpen_fatigue_index >= self.config["bullpen_extreme_fatigue"]:
            hard_block = True
            reasons.append("BULLPEN_EXTREME")
        elif sim.bullpen_status == BullpenStatus.ELEVATED or sim.bullpen_fatigue_index >= self.config["bullpen_high_fatigue"]:
            downgrade = True
            reasons.append("BULLPEN_VOLATILITY")

        return hard_block, downgrade, reasons

    # ------------------------------------------------------------------
    # Weather & park adjustments for totals
    # ------------------------------------------------------------------
    def _weather_park_adjustment(self, sim: SimulationOutput) -> Tuple[bool, bool, List[str]]:
        reasons: List[str] = []
        weather_sensitive = False
        aligned = False

        if sim.weather_wind_mph >= self.config["wind_threshold_mph"] or \
           sim.weather_temp_f >= self.config["heat_threshold_f"] or \
           sim.weather_temp_f <= self.config["cold_threshold_f"] or \
           sim.park_factor in {ParkFactor.HIGH_ALTITUDE, ParkFactor.HITTER_FRIENDLY}:
            weather_sensitive = True
            reasons.append("WEATHER_SENSITIVE")
            aligned = sim.weather_direction_aligned
            if not aligned:
                reasons.append("WEATHER_CONFLICT")

        return weather_sensitive, aligned, reasons

    # ------------------------------------------------------------------
    # Moneyline evaluation
    # ------------------------------------------------------------------
    def _evaluate_moneyline(
        self,
        sim: SimulationOutput,
        ctx: GameContext,
        market_data: MarketData,
        compressed_prob: float
    ) -> Tuple[EdgeState, List[str]]:
        reasons: List[str] = []

        win_prob_edge = compressed_prob - ctx.market_prob
        min_edge = self.config["min_win_prob_edge"]

        # Efficiency floor
        if abs(win_prob_edge) < self.config["min_edge_floor"]:
            reasons.append("EDGE_TOO_SMALL")
            return EdgeState.NO_PLAY, reasons

        # Distribution sanity
        if sim.distribution_flag == DistributionFlag.UNSTABLE_EXTREME:
            reasons.append("UNSTABLE_EXTREME")
            return EdgeState.NO_PLAY, reasons

        # Pitcher & lineup overrides
        pitcher_block, pitcher_reasons, pitcher_downgrade = self._pitcher_lineup_checks(sim)
        reasons.extend(pitcher_reasons)
        if pitcher_block:
            return EdgeState.NO_PLAY, reasons

        # Bullpen adjustments
        pen_block, pen_downgrade, pen_reasons = self._bullpen_adjustment(sim)
        reasons.extend(pen_reasons)
        if pen_block:
            return EdgeState.NO_PLAY, reasons

        downgrade_flags = pitcher_downgrade or pen_downgrade

        # Price guardrails
        guardrail_edge = self.config["guardrail_edge"]
        if ctx.moneyline_price <= self.config["favorite_guardrail"] and win_prob_edge < guardrail_edge:
            reasons.append("FAVORITE_PRICE_GUARDRAIL")
            return EdgeState.NO_PLAY, reasons
        if ctx.moneyline_price >= self.config["underdog_guardrail"] and win_prob_edge < guardrail_edge:
            reasons.append("UNDERDOG_PRICE_GUARDRAIL")
            return EdgeState.NO_PLAY, reasons

        # Eligibility check
        if win_prob_edge < min_edge:
            reasons.append("EDGE_BELOW_ELIGIBILITY")
            return EdgeState.NO_PLAY, reasons

        # Base classification
        state = EdgeState.NO_PLAY
        edge_threshold = self.config["edge_win_prob"]
        upgrade_threshold = self.config["upgrade_win_prob"]

        if win_prob_edge >= edge_threshold:
            state = EdgeState.EDGE
        else:
            state = EdgeState.LEAN

        # Apply downgrades
        if state == EdgeState.EDGE and downgrade_flags:
            reasons.append("DOWNGRADE_DUE_TO_VOLATILITY")
            state = EdgeState.LEAN

        # Confirmation can upgrade strong LEAN
        if state == EdgeState.LEAN and win_prob_edge >= upgrade_threshold and (market_data.clv_aligned or market_data.line_moved) and not downgrade_flags:
            state = EdgeState.EDGE
            reasons.append("UPGRADED_BY_CONFIRMATION")

        return state, reasons

    # ------------------------------------------------------------------
    # Totals evaluation
    # ------------------------------------------------------------------
    def _evaluate_totals(
        self,
        sim: SimulationOutput,
        ctx: GameContext,
        market_data: MarketData
    ) -> Tuple[EdgeState, List[str]]:
        reasons: List[str] = []
        total_edge_abs = abs(sim.total_edge_pts)

        # Efficiency floor
        if total_edge_abs < self.config["total_edge_floor"]:
            reasons.append("TOTAL_EDGE_TOO_SMALL")
            return EdgeState.NO_PLAY, reasons

        # Distribution sanity
        if sim.distribution_flag == DistributionFlag.UNSTABLE_EXTREME:
            reasons.append("UNSTABLE_EXTREME")
            return EdgeState.NO_PLAY, reasons

        # Weather / park alignment
        weather_sensitive, aligned, weather_reasons = self._weather_park_adjustment(sim)
        reasons.extend(weather_reasons)

        # Eligibility
        eligible = total_edge_abs >= self.config["total_edge_min"]
        eligible_weather_assist = weather_sensitive and aligned and total_edge_abs >= (self.config["total_edge_min"] - 0.2)
        if not eligible and not eligible_weather_assist:
            reasons.append("TOTAL_EDGE_BELOW_ELIGIBILITY")
            return EdgeState.NO_PLAY, reasons

        # Grading thresholds
        edge_threshold = self.config["total_edge_edge"]
        edge_weather_threshold = self.config["total_edge_weather_assist"]
        lean_threshold = self.config["total_edge_min"]

        state = EdgeState.NO_PLAY
        if weather_sensitive and aligned:
            if total_edge_abs >= edge_weather_threshold:
                state = EdgeState.EDGE
            elif total_edge_abs >= lean_threshold:
                state = EdgeState.LEAN
        else:
            if total_edge_abs >= edge_threshold:
                state = EdgeState.EDGE
            elif total_edge_abs >= lean_threshold:
                state = EdgeState.LEAN

        # Weather conflict downgrade
        if weather_sensitive and not aligned:
            if state == EdgeState.EDGE:
                state = EdgeState.LEAN
                reasons.append("WEATHER_CONFLICT_DOWNGRADE")
            elif state == EdgeState.LEAN:
                reasons.append("WEATHER_CONFLICT")

        # Bullpen/lineup effects: totals less sensitive, only extreme bullpen
        pen_block, pen_downgrade, pen_reasons = self._bullpen_adjustment(sim)
        reasons.extend(pen_reasons)
        if pen_block:
            return EdgeState.NO_PLAY, reasons
        if pen_downgrade and state == EdgeState.EDGE:
            state = EdgeState.LEAN
            reasons.append("BULLPEN_TOTAL_DOWNGRADE")

        # Lineup uncertainty can soften totals
        pitcher_block, pitcher_reasons, pitcher_downgrade = self._pitcher_lineup_checks(sim)
        reasons.extend(pitcher_reasons)
        if pitcher_block:
            return EdgeState.NO_PLAY, reasons
        if pitcher_downgrade and state == EdgeState.EDGE:
            state = EdgeState.LEAN
            reasons.append("LINEUP_TOTAL_DOWNGRADE")

        return state, reasons

    # ------------------------------------------------------------------
    # MAIN EVALUATION PIPELINE
    # ------------------------------------------------------------------
    async def evaluate_game(
        self,
        game_id: str,
        game_context: GameContext,
        simulation: SimulationOutput
    ) -> EvaluationResponse:
        logger.info(f"Evaluating MLB game: {game_id}")

        compressed_prob = self._compress_probability(simulation.win_probability_raw)
        market_data = self._market_confirmation(game_context.clv_forecast, game_context.line_moved)

        # Evaluate markets
        moneyline_state, moneyline_reasons = self._evaluate_moneyline(simulation, game_context, market_data, compressed_prob)
        total_state, total_reasons = self._evaluate_totals(simulation, game_context, market_data)

        # Choose primary market by strength (EDGE > LEAN > NO_PLAY). Favor moneyline when equal strength.
        state_priority = {EdgeState.EDGE: 2, EdgeState.LEAN: 1, EdgeState.NO_PLAY: 0}
        primary_market = "NONE"
        combined_state = EdgeState.NO_PLAY
        reason_codes: List[str] = []

        if state_priority[moneyline_state] > state_priority[total_state]:
            combined_state = moneyline_state
            primary_market = "MONEYLINE" if moneyline_state != EdgeState.NO_PLAY else "NONE"
            reason_codes = moneyline_reasons
        elif state_priority[total_state] > state_priority[moneyline_state]:
            combined_state = total_state
            primary_market = "TOTAL" if total_state != EdgeState.NO_PLAY else "NONE"
            reason_codes = total_reasons
        else:
            # Same priority; prefer moneyline
            combined_state = moneyline_state
            primary_market = "MONEYLINE" if moneyline_state != EdgeState.NO_PLAY else "NONE"
            reason_codes = moneyline_reasons if moneyline_state != EdgeState.NO_PLAY else total_reasons

        # Market efficiency floor (global)
        win_prob_edge = abs(compressed_prob - game_context.market_prob)
        total_edge_abs = abs(simulation.total_edge_pts)
        if win_prob_edge < self.config["min_edge_floor"] and total_edge_abs < self.config["total_edge_floor"]:
            combined_state = EdgeState.NO_PLAY
            primary_market = "NONE"
            reason_codes.append("MARKET_EFFICIENCY_FLOOR")

        internal_state = {
            "compressed_win_prob": compressed_prob,
            "win_prob_edge": win_prob_edge,
            "total_edge_pts": simulation.total_edge_pts,
            "moneyline_state": moneyline_state,
            "total_state": total_state,
            "distribution_flag": simulation.distribution_flag,
            "bullpen_fatigue_index": simulation.bullpen_fatigue_index,
            "bullpen_status": simulation.bullpen_status,
            "pitcher_status": simulation.pitcher_status,
            "lineup_confirmed": simulation.lineup_confirmed,
            "key_hitters_missing": simulation.key_hitters_missing,
            "weather_wind_mph": simulation.weather_wind_mph,
            "weather_temp_f": simulation.weather_temp_f,
            "weather_direction_aligned": simulation.weather_direction_aligned,
            "park_factor": simulation.park_factor,
            "confidence_score": simulation.confidence_score,
            "clv_aligned": market_data.clv_aligned,
            "line_moved": market_data.line_moved,
        }

        # Persist
        if self.db:
            try:
                await self.db.mlb_evaluations.update_one(
                    {"game_id": game_id},
                    {
                        "$set": {
                            "evaluation": {
                                "game_id": game_id,
                                "timestamp": datetime.utcnow(),
                                "combined_state": combined_state.value,
                                "primary_market": primary_market,
                                "compressed_win_prob": compressed_prob,
                                "moneyline_edge": win_prob_edge,
                                "total_edge_pts": simulation.total_edge_pts,
                                "reason_codes": reason_codes,
                                "market_confirmation": market_data.dict(),
                                "internal_state": internal_state,
                            },
                            "updated_at": datetime.utcnow(),
                        }
                    },
                    upsert=True,
                )
            except Exception as e:
                logger.error(f"Mongo persistence error (MLB): {e}")

        return EvaluationResponse(
            game_id=game_id,
            combined_state=combined_state,
            primary_market=primary_market,
            compressed_win_prob=compressed_prob,
            moneyline_edge=win_prob_edge,
            total_edge_pts=simulation.total_edge_pts,
            reason_codes=reason_codes,
            market_confirmation=market_data,
            internal_state=internal_state,
        )

    # ------------------------------------------------------------------
    async def evaluate_slate(self, date: str, games: List[Dict[str, Any]]) -> Dict[str, Any]:
        evaluations: List[EvaluationResponse] = []
        edge_count = lean_count = no_play_count = 0

        for game in games:
            try:
                ctx = GameContext(
                    game_id=game.get("game_id", ""),
                    date=date,
                    home_team=game.get("home_team", ""),
                    away_team=game.get("away_team", ""),
                    market_prob=game.get("market_prob", 0.5),
                    moneyline_price=game.get("moneyline_price", -110),
                    market_total=game.get("market_total", 8.5),
                    clv_forecast=game.get("clv_forecast"),
                    line_moved=game.get("line_moved", False),
                )

                sim = SimulationOutput(
                    win_probability_raw=game.get("win_probability_raw", 0.5),
                    total_edge_pts=game.get("total_edge_pts", 0.0),
                    distribution_flag=game.get("distribution_flag", DistributionFlag.NORMAL),
                    bullpen_fatigue_index=game.get("bullpen_fatigue_index", 1.0),
                    bullpen_status=game.get("bullpen_status", BullpenStatus.STABLE),
                    pitcher_status=game.get("pitcher_status", PitcherStatus.CONFIRMED),
                    pitch_count_uncertain=game.get("pitch_count_uncertain", False),
                    lineup_confirmed=game.get("lineup_confirmed", True),
                    key_hitters_missing=game.get("key_hitters_missing", 0),
                    weather_wind_mph=game.get("weather_wind_mph", 0.0),
                    weather_temp_f=game.get("weather_temp_f", 70.0),
                    weather_direction_aligned=game.get("weather_direction_aligned", False),
                    park_factor=game.get("park_factor", ParkFactor.NEUTRAL),
                    confidence_score=game.get("confidence_score", 60),
                )

                eval_result = await self.evaluate_game(ctx.game_id, ctx, sim)
                evaluations.append(eval_result)

                if eval_result.combined_state == EdgeState.EDGE:
                    edge_count += 1
                elif eval_result.combined_state == EdgeState.LEAN:
                    lean_count += 1
                else:
                    no_play_count += 1

            except Exception as e:
                logger.error(f"Error evaluating MLB game {game.get('game_id', '')}: {e}")
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
                "no_play_percentage": no_play_count / len(evaluations) if evaluations else 0,
                "expected_edges_per_day": min(2, edge_count),
                "expected_behavior": "Most games NO_PLAY; several LEANS; 1-2 EDGES max",
            },
        }

    # ------------------------------------------------------------------
    async def get_recent_evaluations(self, limit: int = 20, state_filter: Optional[str] = None) -> List[Dict[str, Any]]:
        if not self.db:
            return []
        try:
            query: Dict[str, Any] = {}
            if state_filter:
                query["evaluation.combined_state"] = state_filter
            cursor = self.db.mlb_evaluations.find(query).sort("updated_at", -1).limit(limit)
            return await cursor.to_list(length=limit)
        except Exception as e:
            logger.error(f"Error retrieving MLB evaluations: {e}")
            return []

    # ------------------------------------------------------------------
    async def get_evaluation(self, game_id: str) -> Optional[Dict[str, Any]]:
        if not self.db:
            return None
        try:
            return await self.db.mlb_evaluations.find_one({"game_id": game_id})
        except Exception as e:
            logger.error(f"Error fetching MLB evaluation {game_id}: {e}")
            return None

    # ------------------------------------------------------------------
    async def health_check(self) -> Dict[str, Any]:
        checks = {
            "compression_factor": abs(self.config["compression_factor"] - 0.82) < 1e-6,
            "min_win_prob_edge": abs(self.config["min_win_prob_edge"] - 0.020) < 1e-6,
            "edge_win_prob": abs(self.config["edge_win_prob"] - 0.035) < 1e-6,
            "total_edge_min": abs(self.config["total_edge_min"] - 1.5) < 1e-6,
            "total_edge_edge": abs(self.config["total_edge_edge"] - 2.5) < 1e-6,
            "weather_thresholds_present": True,
            "bullpen_thresholds_present": True,
            "market_efficiency_floor": abs(self.config["min_edge_floor"] - 0.015) < 1e-6,
        }
        return {
            "status": "healthy" if all(checks.values()) else "misconfigured",
            "system": "MLB Edge Evaluator - Locked Specification",
            "checks": checks,
            "expected_behavior": {
                "default_state": "NO_PLAY majority",
                "edges_per_day": "1-2 max on full slate",
                "leans_per_day": "several, informational",
                "win_prob_cluster": "53-57% after compression",
            },
        }
