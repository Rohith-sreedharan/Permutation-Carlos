"""
NFL Edge Evaluator Service
Implements two-layer NFL edge evaluation with key-number protection and injury handling
Locked specification for production use

NFL Market Specifics:
- Lower game counts → scarcity matters
- Key numbers (3, 7, 10) are critical
- QB injuries have outsized impact
- Weather is NOT optional
- Spreads max out at ±7.5/-8.5
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
    TIGHT = "TIGHT"  # ≤4 pts
    MEDIUM = "MEDIUM"  # 4-7 pts
    STABLE = "STABLE"  # >7 pts
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
    "KEY_NUMBER_PENALTY": "Spread near ±3/±7/±10 key number",
    "VOLATILITY_HIGH": "Elevated volatility",
    "QB_UNCERTAIN": "Starting QB questionable/late/new",
    "WEATHER_DOWNGRADED": "Weather impact requires higher edge",
    "DISTRIBUTION_UNSTABLE": "UNSTABLE_EXTREME flag",
    "BLOWOUT_GUARD": "Spread beyond guardrails",
    "INJURY_IMPACT": "Key injury (OL/starters) limits confidence",
    "MARKET_ALIGNED": "Market confirmation present",
    "SPREAD_TOO_LARGE": "Spread > max allowed",
}


# ====== INPUT SCHEMAS ======

class SimulationOutput(BaseModel):
    """Simulation results from Monte Carlo"""
    spread_win_prob: float = Field(..., ge=0, le=1)
    total_over_prob: float = Field(..., ge=0, le=1)
    spread_edge_pts: float  # Model prediction - market line
    total_edge_pts: float  # Model total - market total
    distribution_std: float = Field(default=2.0, ge=0)  # Standard deviation


class MarketData(BaseModel):
    """Live market conditions"""
    spread_line: float
    total_line: float
    clv_forecast: float = Field(default=0, ge=-2, le=2)  # Percent
    line_move_toward_model: bool = Field(default=False)


class GameContext(BaseModel):
    """NFL-specific game context"""
    game_id: str
    home_team: str
    away_team: str
    week: int = Field(default=1, ge=1, le=18)
    qb_status: Literal["confirmed", "questionable", "late", "new_insert"] = "confirmed"
    key_injuries_out: int = Field(default=0, ge=0)  # Count of key starters out
    wind_mph: float = Field(default=5, ge=0)  # Wind speed
    precipitation: Literal["none", "rain", "snow", "heavy"] = "none"
    temperature: float = Field(default=70)  # Fahrenheit


class NFLGameEvaluation(BaseModel):
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

NFL_CONFIG = {
    # Spread thresholds
    "spread_eligibility_min": 3.0,  # Lower than college (key numbers)
    "spread_edge_min": 4.5,  # Minimum for EDGE
    "spread_lean_min": 3.0,  # Minimum for LEAN
    
    # Key number protection
    "key_numbers": [3, 7, 10],  # NFL key numbers
    "key_number_penalty": 0.5,  # Additional edge required
    
    # Spread size guardrails
    "max_favorite_guardrail": -7.5,  # Auto-allowed favorites
    "max_dog_guardrail": 8.5,  # Auto-allowed dogs
    "large_spread_edge_min": 6.0,  # Required if beyond guardrails
    
    # Totals thresholds
    "total_eligibility_min": 3.5,
    "total_edge_min": 5.0,  # More stringent than spreads
    "total_lean_min": 3.5,
    
    # Weather adjustment
    "weather_edge_penalty": 1.0,  # Additional edge required
    "high_wind_threshold": 15,  # mph
    "extreme_temp_threshold": 20,  # Below 20 or above high summer
    
    # Probability normalization
    "compression_factor": 0.85,  # NFL = moderate (less aggressive)
    
    # Volatility & distribution
    "distribution_tight_max": 4.0,
    "distribution_medium_max": 7.0,
    
    # Confidence ranges
    "optimal_prob_min": 0.54,
    "optimal_prob_max": 0.59,
    
    # Market confirmation
    "clv_confirmation_threshold": 0.25,  # +0.25%
}


# ====== CORE LOGIC ======

class NFLEdgeEvaluator:
    """Two-layer NFL edge evaluation"""
    
    def __init__(self, db):
        self.db = db
        self.config = NFL_CONFIG
    
    def _compress_probability(self, raw_prob: float) -> float:
        """
        NFL compression to prevent false certainty.
        compressed = 0.5 + (raw - 0.5) * compression_factor
        NFL uses 0.85 (less aggressive than college)
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
    
    def _is_near_key_number(self, spread: float) -> bool:
        """Check if spread is near a key number (within ±0.5)"""
        for key_num in self.config["key_numbers"]:
            if abs(abs(spread) - key_num) <= 0.5:
                return True
        return False
    
    def _has_weather_impact(self, game_context: GameContext) -> bool:
        """Determine if weather requires adjustment"""
        # High wind
        if game_context.wind_mph >= self.config["high_wind_threshold"]:
            return True
        # Heavy precipitation
        if game_context.precipitation in ["snow", "heavy"]:
            return True
        # Extreme temperature
        if game_context.temperature < 0 or game_context.temperature > 90:
            return True
        return False
    
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
        spread_line: float = 0,
        game_context: Optional[GameContext] = None,
        volatility_level: str = "LOW"
    ) -> tuple[str, list[str]]:
        """
        Layer B: Classification as EDGE | LEAN | NO_PLAY
        Returns (state, reason_codes)
        """
        reasons = []
        
        if market_type == "SPREAD":
            # Check spread size guardrails first
            if spread_line < self.config["max_favorite_guardrail"] or spread_line > self.config["max_dog_guardrail"]:
                # Outside guardrails: need very strong edge
                if edge_pts < self.config["large_spread_edge_min"]:
                    reasons.append("BLOWOUT_GUARD")
                    return "NO_PLAY", reasons
                else:
                    reasons.append("SPREAD_TOO_LARGE")
            
            # Check key number penalty
            required_edge = self.config["spread_edge_min"]
            if self._is_near_key_number(spread_line):
                required_edge += self.config["key_number_penalty"]
                reasons.append("KEY_NUMBER_PENALTY")
            
            # Standard grading
            if edge_pts >= required_edge and distribution_flag != "UNSTABLE_EXTREME":
                # Could be EDGE — check volatility
                if volatility_level in ["HIGH", "EXTREME"]:
                    reasons.append("VOLATILITY_HIGH")
                    return "LEAN", reasons
                
                # Check QB status
                if game_context and game_context.qb_status != "confirmed":
                    reasons.append("QB_UNCERTAIN")
                    return "LEAN", reasons
                
                # Check key injuries
                if game_context and game_context.key_injuries_out >= 2:
                    reasons.append("INJURY_IMPACT")
                    return "LEAN", reasons
                
                return "EDGE", reasons
            
            elif edge_pts >= self.config["spread_lean_min"]:
                if "KEY_NUMBER_PENALTY" not in reasons:
                    reasons.append("EDGE_TOO_SMALL")
                return "LEAN", reasons
            
            else:
                reasons.append("EDGE_TOO_SMALL")
                return "NO_PLAY", reasons
        
        elif market_type == "TOTAL":
            # Totals are more stringent in NFL
            required_edge = self.config["total_edge_min"]
            
            # Weather adjustment (MANDATORY)
            if game_context and self._has_weather_impact(game_context):
                required_edge += self.config["weather_edge_penalty"]
                reasons.append("WEATHER_DOWNGRADED")
            
            if edge_pts >= required_edge and distribution_flag != "UNSTABLE_EXTREME":
                # Could be EDGE
                if volatility_level in ["HIGH", "EXTREME"]:
                    reasons.append("VOLATILITY_HIGH")
                    return "LEAN", reasons
                
                return "EDGE", reasons
            
            elif edge_pts >= self.config["total_lean_min"]:
                if "WEATHER_DOWNGRADED" not in reasons:
                    reasons.append("EDGE_TOO_SMALL")
                return "LEAN", reasons
            
            else:
                reasons.append("EDGE_TOO_SMALL")
                return "NO_PLAY", reasons
        
        return "NO_PLAY", ["Invalid market"]
    
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
    ) -> NFLGameEvaluation:
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
        
        # Step 7: Market confirmation (supportive only)
        primary_state = spread_state if spread_state == "EDGE" else total_state
        if primary_state not in ["EDGE", "LEAN", "NO_PLAY"]:
            primary_state = "NO_PLAY"
        clv_aligned, line_moved, conf_reasons = self._market_confirmation(
            primary_state,
            market_data.clv_forecast,
            market_data.line_move_toward_model
        )
        
        # Step 8: Determine combined state & primary market
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
        evaluation = NFLGameEvaluation(
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
                "raw_total_prob": simulation_output.total_over_prob,
                "near_key_number": self._is_near_key_number(market_data.spread_line),
                "weather_impact": self._has_weather_impact(game_context) if game_context else False
            }
        )
        
        # Step 9: Persist to MongoDB
        await self.db.nfl_evaluations.update_one(
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
        slate_week: int,
        games: list[dict]
    ) -> dict:
        """Evaluate entire weekly slate"""
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
            "slate_week": slate_week,
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
        """Fetch recent NFL evaluations"""
        query = {}
        if state_filter:
            query["evaluation.combined_state"] = state_filter
        
        evaluations = await self.db.nfl_evaluations.find(query).sort(
            "evaluation.timestamp", -1
        ).limit(limit).to_list(None)
        
        return evaluations or []
    
    async def get_evaluation(self, game_id: str) -> Optional[dict]:
        """Fetch specific game evaluation"""
        return await self.db.nfl_evaluations.find_one({"game_id": game_id})
    
    async def health_check(self) -> dict:
        """Sanity check: Is system behaving correctly?"""
        try:
            recent = await self.db.nfl_evaluations.find({}).sort(
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
            
            # Expected behavior (more selective than college)
            edge_pct = edge_count / len(states) * 100
            lean_pct = lean_count / len(states) * 100
            no_play_pct = no_play_count / len(states) * 100
            
            health_warnings = []
            
            if edge_pct > 15:
                health_warnings.append(f"⚠️ Too many EDGES ({edge_pct:.1f}%) — thresholds too loose")
            if edge_pct < 1 and len(states) > 20:
                health_warnings.append(f"⚠️ Too few EDGES ({edge_pct:.1f}%) — thresholds too tight")
            if no_play_pct < 75:
                health_warnings.append(f"⚠️ Too many plays ({no_play_pct:.1f}% NO_PLAY) — default should be NO_PLAY")
            
            # Probability analysis
            all_spread_probs = []
            for r in recent:
                prob = r["evaluation"]["compressed_spread_prob"]
                all_spread_probs.append(prob)
            
            avg_prob = sum(all_spread_probs) / len(all_spread_probs) if all_spread_probs else 0
            probs_in_range = sum(1 for p in all_spread_probs if 0.54 <= p <= 0.59)
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
                    "probs_54_59_percentage": f"{probs_in_range_pct:.1f}%"
                },
                "warnings": health_warnings
            }
        
        except Exception as e:
            return {
                "status": "error",
                "message": str(e)
            }
