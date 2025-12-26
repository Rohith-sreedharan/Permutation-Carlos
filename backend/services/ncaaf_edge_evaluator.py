"""
NCAAF Edge Evaluator Service
Implements two-layer college football edge evaluation with NCAAF-specific calibration
Locked specification for production use

College Football Specifics:
- Massive talent disparities → probability compression mandatory
- Extreme blowouts → large spread guardrails critical
- Less efficient markets → smaller thresholds acceptable
- Scheme/tempo impact → QB/pace volatility override required
- Default state: NO_PLAY (not NO_EDGE)
"""

from typing import Optional, Literal
from dataclasses import dataclass, asdict
from datetime import datetime
from enum import Enum
import math
from pydantic import BaseModel, Field


# ====== ENUMS & TYPES ======

class DistributionFlag(str, Enum):
    """Distribution assessment for edge stability"""
    TIGHT = "TIGHT"  # ≤5 pts
    MEDIUM = "MEDIUM"  # 5-8.5 pts
    STABLE = "STABLE"  # >8.5 pts
    UNSTABLE_EXTREME = "UNSTABLE_EXTREME"  # Volatile/unreliable


class EdgeState(str, Enum):
    """Final classification for a game"""
    EDGE = "EDGE"  # Telegram-worthy
    LEAN = "LEAN"  # Informational / optional
    NO_PLAY = "NO_PLAY"  # Default


class MarketType(str, Enum):
    """Market being evaluated"""
    SPREAD = "SPREAD"
    TOTAL = "TOTAL"
    NONE = "NONE"


# Reason codes for debugging and trust
REASON_CODES = {
    "EDGE_TOO_SMALL": "Edge below threshold",
    "VOLATILITY_HIGH": "Elevated volatility",
    "QB_UNCERTAIN": "Starting QB questionable/GTD/new",
    "BLOWOUT_NOISE": "Large spread triggers guardrail",
    "SCHEME_VARIANCE": "Triple-option/tempo/new OC",
    "MARKET_ALIGNED": "Market confirmation present",
    "DISTRIBUTION_UNSTABLE": "UNSTABLE_EXTREME flag",
    "LARGE_UNDERDOG": "Dog +24 or higher",
    "RIVALRY_DOWNGRADE": "Rivalry situation",
    "LOOKAHEAD_SPOT": "Look-ahead positioning",
}


# ====== INPUT SCHEMAS ======

class SimulationOutput(BaseModel):
    """Simulation results from Monte Carlo"""
    spread_win_prob: float = Field(..., ge=0, le=1)
    total_over_prob: float = Field(..., ge=0, le=1)
    spread_edge_pts: float  # Model prediction - market line
    total_edge_pts: float  # Model total - market total
    distribution_std: float = Field(default=2.5, ge=0)  # Standard deviation


class MarketData(BaseModel):
    """Live market conditions"""
    spread_line: float
    total_line: float
    clv_forecast: float = Field(default=0, ge=-2, le=2)  # Percent
    line_move_toward_model: bool = Field(default=False)


class GameContext(BaseModel):
    """College-specific game context"""
    game_id: str
    home_team: str
    away_team: str
    week: int = Field(default=1, ge=1, le=15)
    is_rivalry: bool = Field(default=False)
    is_lookahead_spot: bool = Field(default=False)
    is_bowl_game: bool = Field(default=False)
    qb_status: Literal["confirmed", "questionable", "gtd", "new_insert"] = "confirmed"
    is_triple_option: bool = Field(default=False)
    tempo_mismatch: bool = Field(default=False)
    new_offensive_coordinator: bool = Field(default=False)


class NCAAFGameEvaluation(BaseModel):
    """Output: Full game evaluation"""
    game_id: str
    timestamp: datetime
    spread_result: dict  # {state, primary_market, reason_codes}
    total_result: dict  # {state, primary_market, reason_codes}
    combined_state: str  # EDGE | LEAN | NO_PLAY
    primary_market: str  # SPREAD | TOTAL | NONE
    compressed_spread_prob: float
    compressed_total_prob: float
    reason_codes: list[str]
    market_confirmation: dict  # {clv_aligned, line_moved}
    internal_state: dict  # For debugging


# ====== CONFIGURATION (TUNABLE) ======

NCAAF_CONFIG = {
    # Spread thresholds
    "spread_eligibility_min": 4.0,  # Minimum edge for consideration
    "spread_edge_min": 6.0,  # Threshold for EDGE classification
    "spread_lean_min": 4.0,  # Threshold for LEAN
    
    # Large spread guardrails
    "large_favorite_threshold": -21.0,  # Spreads more extreme require higher edge
    "large_favorite_edge_min": 8.0,  # Required edge when favorite > -21
    "large_underdog_threshold": 24.0,  # Dogs +24+ allowed but flagged
    
    # Totals thresholds
    "total_eligibility_min": 4.5,
    "total_edge_min": 6.5,  # More stringent than spreads
    "total_lean_min": 4.5,
    
    # Probability normalization
    "compression_factor": 0.80,  # College = 0.80 (more aggressive)
    
    # Volatility & distribution
    "distribution_tight_max": 5.0,
    "distribution_medium_max": 8.5,
    
    # Confidence ranges
    "optimal_prob_min": 0.54,
    "optimal_prob_max": 0.60,
    
    # Market confirmation
    "clv_confirmation_threshold": 0.30,  # +0.30%
}


# ====== CORE LOGIC ======

class NCAAFEdgeEvaluator:
    """Two-layer NCAAF edge evaluation"""
    
    def __init__(self, db):
        self.db = db
        self.config = NCAAF_CONFIG
    
    def _compress_probability(self, raw_prob: float) -> float:
        """
        Mandatory compression to prevent fake certainty from blowouts.
        compressed = 0.5 + (raw - 0.5) * compression_factor
        """
        if not (0 <= raw_prob <= 1):
            return raw_prob
        return 0.5 + (raw_prob - 0.5) * self.config["compression_factor"]
    
    def _assess_distribution(self, std_dev: float) -> str:
        """Classify distribution stability"""
        if std_dev <= self.config["distribution_tight_max"]:
            return "TIGHT"
        elif std_dev <= self.config["distribution_medium_max"]:
            return "MEDIUM"
        else:
            return "STABLE"
    
    def _layer_a_eligibility(
        self,
        market_type: str,
        edge_pts: float,
        distribution_flag: str
    ) -> tuple[bool, list[str]]:
        """
        Layer A: Gate 1 — Is this game worth considering?
        Returns (eligible, reason_codes)
        """
        reasons = []
        
        # Check distribution first
        if distribution_flag == "UNSTABLE_EXTREME":
            reasons.append("DISTRIBUTION_UNSTABLE")
            return False, reasons
        
        # Check market-specific eligibility
        if market_type == "SPREAD":
            if edge_pts < self.config["spread_eligibility_min"]:
                reasons.append("EDGE_TOO_SMALL")
                return False, reasons
            return True, []
        
        elif market_type == "TOTAL":
            if edge_pts < self.config["total_eligibility_min"]:
                reasons.append("EDGE_TOO_SMALL")
                return False, reasons
            return True, []
        
        return False, ["Invalid market type"]
    
    def _layer_b_grading(
        self,
        market_type: str,
        edge_pts: float,
        distribution_flag: str,
        compressed_prob: float,
        spread_line: float = 0,  # For large spread guardrails
        game_context: Optional[GameContext] = None,
        volatility_level: str = "LOW"  # LOW, MEDIUM, HIGH, EXTREME
    ) -> tuple[str, list[str]]:
        """
        Layer B: Classification as EDGE | LEAN | NO_PLAY
        Returns (state, reason_codes)
        """
        reasons = []
        
        if market_type == "SPREAD":
            # Check large spread guardrails first
            if spread_line <= self.config["large_favorite_threshold"]:
                # Large favorite: needs stronger edge
                if edge_pts < self.config["large_favorite_edge_min"]:
                    reasons.append("BLOWOUT_NOISE")
                    return "NO_PLAY", reasons
            
            elif spread_line >= self.config["large_underdog_threshold"]:
                # Large underdog: allowed but flagged
                reasons.append("LARGE_UNDERDOG")
            
            # Standard grading
            if edge_pts >= self.config["spread_edge_min"] and distribution_flag != "UNSTABLE_EXTREME":
                # Could be EDGE — check volatility
                if volatility_level in ["HIGH", "EXTREME"]:
                    reasons.append("VOLATILITY_HIGH")
                    return "LEAN", reasons
                
                # Check QB status
                if game_context and game_context.qb_status != "confirmed":
                    reasons.append("QB_UNCERTAIN")
                    return "LEAN", reasons
                
                return "EDGE", reasons
            
            elif edge_pts >= self.config["spread_lean_min"]:
                reasons.append("EDGE_TOO_SMALL")
                return "LEAN", reasons
            
            else:
                reasons.append("EDGE_TOO_SMALL")
                return "NO_PLAY", reasons
        
        elif market_type == "TOTAL":
            # Totals are more stringent
            if edge_pts >= self.config["total_edge_min"] and distribution_flag != "UNSTABLE_EXTREME":
                # Could be EDGE — check pace/scheme
                if game_context and (game_context.tempo_mismatch or game_context.is_triple_option):
                    reasons.append("SCHEME_VARIANCE")
                    return "LEAN", reasons
                
                if volatility_level in ["HIGH", "EXTREME"]:
                    reasons.append("VOLATILITY_HIGH")
                    return "LEAN", reasons
                
                return "EDGE", reasons
            
            elif edge_pts >= self.config["total_lean_min"]:
                # Pace/scheme downgrade but keep LEAN valid
                if game_context and (game_context.tempo_mismatch or game_context.is_triple_option):
                    reasons.append("SCHEME_VARIANCE")
                return "LEAN", reasons
            
            else:
                reasons.append("EDGE_TOO_SMALL")
                return "NO_PLAY", reasons
        
        return "NO_PLAY", ["Invalid market"]
    
    def _apply_context_overrides(
        self,
        spread_state: str,
        spread_reasons: list[str],
        total_state: str,
        total_reasons: list[str],
        game_context: GameContext
    ) -> tuple[str, list[str], str, list[str]]:
        """Apply college-specific context overrides"""
        
        # Rivalry downgrade
        if game_context.is_rivalry and spread_state == "EDGE":
            spread_reasons.append("RIVALRY_DOWNGRADE")
            spread_state = "LEAN"
        
        # Look-ahead spot downgrade
        if game_context.is_lookahead_spot and spread_state == "EDGE":
            spread_reasons.append("LOOKAHEAD_SPOT")
            spread_state = "LEAN"
        
        # Bowl game special handling (looser standards)
        # No special downgrade — bowl edges are valuable
        
        return spread_state, spread_reasons, total_state, total_reasons
    
    def _market_confirmation(
        self,
        state: str,
        clv_forecast: float,
        line_moved: bool
    ) -> tuple[bool, bool, list[str]]:
        """
        Optional confirmation (supportive only)
        Returns (clv_aligned, line_moved, confirmation_codes)
        """
        clv_aligned = clv_forecast >= self.config["clv_confirmation_threshold"]
        reasons = []
        
        if clv_aligned or line_moved:
            reasons.append("MARKET_ALIGNED")
        
        return clv_aligned, line_moved, reasons
    
    async def evaluate_game(
        self,
        game_id: str,
        game_context: GameContext,
        simulation_output: SimulationOutput,
        market_data: MarketData,
        volatility_level: str = "LOW"
    ) -> NCAAFGameEvaluation:
        """Main evaluation pipeline"""
        
        # Step 1: Probability compression
        compressed_spread_prob = self._compress_probability(simulation_output.spread_win_prob)
        compressed_total_prob = self._compress_probability(simulation_output.total_over_prob)
        
        # Step 2: Distribution assessment
        distribution_flag = self._assess_distribution(simulation_output.distribution_std)
        
        # Step 3: Layer A — Eligibility for SPREAD
        spread_eligible, spread_ineligible_reasons = self._layer_a_eligibility(
            "SPREAD",
            simulation_output.spread_edge_pts,
            distribution_flag
        )
        
        # Step 4: Layer A — Eligibility for TOTAL
        total_eligible, total_ineligible_reasons = self._layer_a_eligibility(
            "TOTAL",
            simulation_output.total_edge_pts,
            distribution_flag
        )
        
        # Step 5: Layer B — Grading for SPREAD (if eligible)
        if spread_eligible:
            spread_state, spread_reasons = self._layer_b_grading(
                "SPREAD",
                simulation_output.spread_edge_pts,
                distribution_flag,
                compressed_spread_prob,
                spread_line=market_data.spread_line,
                game_context=game_context,
                volatility_level=volatility_level
            )
        else:
            spread_state, spread_reasons = "NO_PLAY", spread_ineligible_reasons
        
        # Step 6: Layer B — Grading for TOTAL (if eligible)
        if total_eligible:
            total_state, total_reasons = self._layer_b_grading(
                "TOTAL",
                simulation_output.total_edge_pts,
                distribution_flag,
                compressed_total_prob,
                spread_line=market_data.spread_line,
                game_context=game_context,
                volatility_level=volatility_level
            )
        else:
            total_state, total_reasons = "NO_PLAY", total_ineligible_reasons
        
        # Step 7: Apply context overrides (rivalry, look-ahead, etc.)
        spread_state, spread_reasons, total_state, total_reasons = self._apply_context_overrides(
            spread_state, spread_reasons,
            total_state, total_reasons,
            game_context
        )
        
        # Step 8: Market confirmation (supportive only)
        primary_state = spread_state if spread_state == "EDGE" else total_state
        if primary_state not in ["EDGE", "LEAN", "NO_PLAY"]:
            primary_state = "NO_PLAY"
        clv_aligned, line_moved, conf_reasons = self._market_confirmation(
            primary_state,
            market_data.clv_forecast,
            market_data.line_move_toward_model
        )
        
        # Step 9: Determine combined state & primary market
        if spread_state == "EDGE" or total_state == "EDGE":
            combined_state_str = "EDGE"
            primary_market_str = "SPREAD" if spread_state == "EDGE" else "TOTAL"
            all_reasons = spread_reasons if spread_state == "EDGE" else total_reasons
        elif spread_state == "LEAN" or total_state == "LEAN":
            combined_state_str = "LEAN"
            primary_market_str = "SPREAD" if spread_state == "LEAN" else "TOTAL"
            all_reasons = spread_reasons if spread_state == "LEAN" else total_reasons
        else:
            combined_state_str = "NO_PLAY"
            primary_market_str = "NONE"
            all_reasons = spread_reasons + total_reasons
        
        # Add confirmation reasons
        all_reasons.extend(conf_reasons)
        all_reasons = list(set(all_reasons))  # Remove duplicates
        
        # Build output
        evaluation = NCAAFGameEvaluation(
            game_id=game_id,
            timestamp=datetime.utcnow(),
            spread_result={
                "state": spread_state,
                "primary_market": "SPREAD",
                "reason_codes": spread_reasons
            },
            total_result={
                "state": total_state,
                "primary_market": "TOTAL",
                "reason_codes": total_reasons
            },
            combined_state=combined_state_str,
            primary_market=primary_market_str,
            compressed_spread_prob=compressed_spread_prob,
            compressed_total_prob=compressed_total_prob,
            reason_codes=all_reasons,
            market_confirmation={
                "clv_aligned": clv_aligned,
                "line_moved": line_moved
            },
            internal_state={
                "distribution_flag": distribution_flag,
                "spread_edge_pts": simulation_output.spread_edge_pts,
                "total_edge_pts": simulation_output.total_edge_pts,
                "spread_line": market_data.spread_line,
                "total_line": market_data.total_line,
                "raw_spread_prob": simulation_output.spread_win_prob,
                "raw_total_prob": simulation_output.total_over_prob
            }
        )
        
        # Step 10: Persist to MongoDB
        await self.db.ncaaf_evaluations.update_one(
            {"game_id": game_id},
            {
                "$set": {
                    "evaluation": evaluation.model_dump(),
                    "updated_at": datetime.utcnow()
                }
            },
            upsert=True
        )
        
        return evaluation
    
    async def evaluate_slate(
        self,
        slate_date: str,
        games: list[dict]
    ) -> dict:
        """Evaluate entire Saturday slate"""
        results = []
        edge_count = 0
        lean_count = 0
        no_play_count = 0
        
        for game in games:
            eval_result = await self.evaluate_game(
                game_id=game["game_id"],
                game_context=GameContext(**game["game_context"]),
                simulation_output=SimulationOutput(**game["simulation_output"]),
                market_data=MarketData(**game["market_data"]),
                volatility_level=game.get("volatility_level", "LOW")
            )
            
            results.append(eval_result.model_dump())
            
            if eval_result.combined_state == "EDGE":
                edge_count += 1
            elif eval_result.combined_state == "LEAN":
                lean_count += 1
            else:
                no_play_count += 1
        
        return {
            "slate_date": slate_date,
            "total_games": len(games),
            "evaluations": results,
            "summary": {
                "edges": edge_count,
                "leans": lean_count,
                "no_plays": no_play_count,
                "edge_percentage": edge_count / len(games) * 100 if games else 0
            }
        }
    
    async def get_recent_evaluations(
        self,
        limit: int = 20,
        state_filter: Optional[str] = None
    ) -> list[dict]:
        """Fetch recent NCAAF evaluations"""
        query = {}
        if state_filter:
            query["evaluation.combined_state"] = state_filter
        
        evaluations = await self.db.ncaaf_evaluations.find(query).sort(
            "evaluation.timestamp", -1
        ).limit(limit).to_list(None)
        
        return evaluations or []
    
    async def get_evaluation(self, game_id: str) -> Optional[dict]:
        """Fetch specific game evaluation"""
        return await self.db.ncaaf_evaluations.find_one({"game_id": game_id})
    
    async def health_check(self) -> dict:
        """Sanity check: Is system behaving correctly?"""
        try:
            recent = await self.db.ncaaf_evaluations.find({}).sort(
                "evaluation.timestamp", -1
            ).limit(50).to_list(None)
            
            if not recent:
                return {
                    "status": "no_data",
                    "message": "No evaluations in database yet"
                }
            
            states = [r["evaluation"]["combined_state"] for r in recent]
            edge_count = states.count("EDGE")
            lean_count = states.count("LEAN")
            no_play_count = states.count("NO_PLAY")
            
            # Expected behavior
            edge_pct = edge_count / len(states) * 100
            lean_pct = lean_count / len(states) * 100
            no_play_pct = no_play_count / len(states) * 100
            
            health_warnings = []
            
            if edge_pct > 20:
                health_warnings.append(f"⚠️ Too many EDGES ({edge_pct:.1f}%) — thresholds too loose")
            if edge_pct < 2:
                health_warnings.append(f"⚠️ Too few EDGES ({edge_pct:.1f}%) — thresholds too tight")
            if no_play_pct < 50:
                health_warnings.append(f"⚠️ Too many plays ({no_play_pct:.1f}% NO_PLAY) — default should be NO_PLAY")
            
            # Probability analysis
            all_spread_probs = []
            for r in recent:
                prob = r["evaluation"]["compressed_spread_prob"]
                all_spread_probs.append(prob)
            
            avg_prob = sum(all_spread_probs) / len(all_spread_probs) if all_spread_probs else 0
            probs_in_range = sum(1 for p in all_spread_probs if 0.54 <= p <= 0.60)
            probs_in_range_pct = probs_in_range / len(all_spread_probs) * 100 if all_spread_probs else 0
            
            return {
                "status": "healthy" if not health_warnings else "warning",
                "total_evaluations": len(states),
                "distribution": {
                    "edges": edge_count,
                    "leans": lean_count,
                    "no_plays": no_play_count,
                    "edge_percentage": f"{edge_pct:.1f}%",
                    "lean_percentage": f"{lean_pct:.1f}%",
                    "no_play_percentage": f"{no_play_pct:.1f}%"
                },
                "probability_analysis": {
                    "average_compressed_prob": f"{avg_prob:.3f}",
                    "probs_54_60_percentage": f"{probs_in_range_pct:.1f}%"
                },
                "warnings": health_warnings
            }
        
        except Exception as e:
            return {
                "status": "error",
                "message": str(e)
            }
