"""
Autonomous Edge Execution Engine
Three-wave simulation system with institutional-grade publish controls
"""
import asyncio
from typing import Optional, Dict, Any, List, Literal, cast
from datetime import datetime, timezone, timedelta
from pymongo.database import Database
import uuid

from db.schemas.signal_schemas import (
    Signal,
    MarketSnapshot,
    SignalState,
    SignalIntent,
    VolatilityBucket,
    ConfidenceBand,
    GateEvaluation,
    GateResult,
    ReasonCode
)
from services.signal_manager import SignalManager


# ============================================================================
# EDGE CLASSIFICATION ENUMS
# ============================================================================

class EdgeGrade(str):
    """Edge quality classification"""
    A_GRADE = "A_GRADE"           # Auto-post to Telegram
    STRONG_LEAN = "STRONG_LEAN"   # Optional post (Lean Floor rule)
    NO_PLAY = "NO_PLAY"           # Silence


# Wave states as string literals
WaveState = Literal["CANDIDATE_EDGE", "EDGE_CONFIRMED", "LEAN_CONFIRMED", "EDGE_REJECTED", "PUBLISHED", "BLOCKED"]


# ============================================================================
# ENTRY SNAPSHOT (IMMUTABLE TRUTH)
# ============================================================================

class EntrySnapshot:
    """
    Immutable record of bet entry conditions
    This is the OFFICIAL TRUTH for the bet
    Everything after this is noise
    """
    def __init__(
        self,
        snapshot_id: str,
        game_id: str,
        market_type: Literal["SPREAD", "TOTAL", "ML"],
        side: str,
        entry_line: float,
        entry_odds: int,
        model_fair_value: float,
        edge_gap: float,
        win_probability: float,
        clv_estimate: float,
        timestamp: datetime,
        max_acceptable_line: float,
        signal_id: str
    ):
        self.snapshot_id = snapshot_id
        self.game_id = game_id
        self.market_type = market_type
        self.side = side
        self.entry_line = entry_line
        self.entry_odds = entry_odds
        self.model_fair_value = model_fair_value
        self.edge_gap = edge_gap
        self.win_probability = win_probability
        self.clv_estimate = clv_estimate
        self.timestamp = timestamp
        self.max_acceptable_line = max_acceptable_line
        self.signal_id = signal_id
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "snapshot_id": self.snapshot_id,
            "game_id": self.game_id,
            "market_type": self.market_type,
            "side": self.side,
            "entry_line": self.entry_line,
            "entry_odds": self.entry_odds,
            "model_fair_value": self.model_fair_value,
            "edge_gap": self.edge_gap,
            "win_probability": self.win_probability,
            "clv_estimate": self.clv_estimate,
            "timestamp": self.timestamp.isoformat(),
            "max_acceptable_line": self.max_acceptable_line,
            "signal_id": self.signal_id
        }


# ============================================================================
# AUTONOMOUS EDGE ENGINE
# ============================================================================

class AutonomousEdgeEngine:
    """
    Three-wave simulation system with publish controls
    
    Philosophy:
    - Edges are prices, not teams
    - Bet judged at ENTRY, not after markets move
    - Publish ONCE, never change public state
    - Silence is a valid and correct outcome
    """
    
    def __init__(self, db: Database):
        self.db = db
        self.signal_manager = SignalManager(db)
        
        # Edge buffers for max acceptable line
        self.SPREAD_BUFFER = 1.25  # pts
        self.TOTAL_BUFFER = 2.5    # pts
        
        # Juice filter (hard block)
        self.MAX_JUICE = -120
        
        # A-Grade thresholds
        self.A_GRADE_WIN_PROB = 0.60
        self.A_GRADE_EDGE_GAP = 6.0
        self.A_GRADE_CLV = 0.002
        self.A_GRADE_VOLATILITY_OVERRIDE_EDGE = 8.5  # pts for spread
        self.A_GRADE_VOLATILITY_OVERRIDE_WIN_PROB = 0.65
        
        # Strong Lean thresholds
        self.LEAN_WIN_PROB_MIN = 0.560
        self.LEAN_WIN_PROB_MAX = 0.599
        self.LEAN_EDGE_MIN = 3.0
        self.LEAN_EDGE_MAX = 5.9
        self.LEAN_FLOOR_EDGE = 4.0
        self.LEAN_FLOOR_WIN_PROB = 0.575
        self.LEAN_MAX_JUICE = -115
    
    # ========================================================================
    # WAVE 1: PRIMARY SCAN (DISCOVERY)
    # ========================================================================
    
    async def wave_1_primary_scan(
        self,
        game_id: str,
        sport: str,
        simulation_output: Dict[str, Any],
        market_data: Dict[str, Any]
    ) -> Optional[str]:
        """
        Wave 1: Detect potential mispricing early
        
        Rules:
        - Run T-6h to T-4h before game start
        - 100K simulations
        - Store as CANDIDATE_EDGE
        - NO Telegram output
        - NO UI betting prompts
        
        Returns: candidate_id if edge detected, None otherwise
        """
        # Check timing window
        game_start = datetime.fromisoformat(market_data["commence_time"])
        now = datetime.now(timezone.utc)
        hours_until_game = (game_start - now).total_seconds() / 3600
        
        if not (4 <= hours_until_game <= 6):
            return None  # Outside Wave 1 window
        
        # Analyze simulation output
        model_spread = simulation_output.get("model_spread")
        market_spread = market_data.get("spread_line")
        
        if model_spread is None or market_spread is None:
            return None
        
        edge_gap = abs(model_spread - market_spread)
        win_prob = simulation_output.get("win_probability", 0)
        volatility = simulation_output.get("volatility_bucket", "HIGH")
        
        # Store as candidate (internal only)
        candidate_id = f"cand_{uuid.uuid4().hex[:12]}"
        
        self.db["edge_candidates"].insert_one({
            "candidate_id": candidate_id,
            "game_id": game_id,
            "sport": sport,
            "wave": 1,
            "state": "CANDIDATE_EDGE",
            "created_at": now,
            "model_spread": model_spread,
            "market_spread": market_spread,
            "edge_gap": edge_gap,
            "win_probability": win_prob,
            "volatility": volatility,
            "distribution_width": simulation_output.get("distribution_width"),
            "injury_impact": simulation_output.get("injury_impact"),
            "clv_estimate": simulation_output.get("clv_estimate", 0),
            "num_sims": simulation_output.get("num_sims", 100000),
            "publish_allowed": False  # Wave 1 NEVER publishes
        })
        
        return candidate_id
    
    # ========================================================================
    # WAVE 2: STABILITY SCAN (VALIDATION)
    # ========================================================================
    
    async def wave_2_stability_scan(
        self,
        candidate_id: str,
        new_simulation_output: Dict[str, Any],
        market_data: Dict[str, Any]
    ) -> str:
        """
        Wave 2: Confirm edge persistence
        
        Rules:
        - Run T-120 minutes before game start
        - Re-run 100K simulations
        - Compare vs Wave 1
        - Edge gap change ≤ ±1.5 pts
        - Volatility not increasing
        - Win probability ≥ threshold
        
        Returns: EDGE_CONFIRMED, LEAN_CONFIRMED, or EDGE_REJECTED
        """
        # Get Wave 1 candidate
        candidate = self.db["edge_candidates"].find_one({
            "candidate_id": candidate_id
        })
        
        if not candidate:
            return cast(WaveState, "EDGE_REJECTED")
        
        # Extract current metrics
        current_edge = abs(new_simulation_output.get("model_spread", 0) - market_data.get("spread_line", 0))
        current_win_prob = new_simulation_output.get("win_probability", 0)
        current_volatility = new_simulation_output.get("volatility_bucket", "HIGH")
        
        # Compare to Wave 1
        wave1_edge = candidate["edge_gap"]
        wave1_volatility = candidate["volatility"]
        
        edge_delta = abs(current_edge - wave1_edge)
        
        # Stability requirements
        stability_passed = (
            edge_delta <= 1.5 and  # Edge gap change ≤ ±1.5 pts
            current_volatility != "HIGH" or current_volatility == wave1_volatility and
            current_win_prob >= 0.54  # Minimum threshold
        )
        
        if not stability_passed:
            state = cast(WaveState, "EDGE_REJECTED")
        elif current_win_prob >= 0.57 and current_edge >= 4.0:
            state = cast(WaveState, "EDGE_CONFIRMED")
        elif current_win_prob >= 0.56 and current_edge >= 3.0:
            state = cast(WaveState, "LEAN_CONFIRMED")
        else:
            state = cast(WaveState, "EDGE_REJECTED")
        
        # Update candidate
        self.db["edge_candidates"].update_one(
            {"candidate_id": candidate_id},
            {
                "$set": {
                    "wave": 2,
                    "state": state,
                    "wave2_edge_gap": current_edge,
                    "wave2_win_probability": current_win_prob,
                    "wave2_volatility": current_volatility,
                    "edge_delta": edge_delta,
                    "stability_passed": stability_passed,
                    "updated_at": datetime.now(timezone.utc)
                }
            }
        )
        
        return state
    
    # ========================================================================
    # WAVE 3: FINAL LOCK SCAN (PUBLISH GATE)
    # ========================================================================
    
    async def wave_3_final_lock_scan(
        self,
        candidate_id: str,
        final_simulation_output: Dict[str, Any],
        live_market_data: Dict[str, Any],
        telegram_service: Any = None
    ) -> Optional[EntrySnapshot]:
        """
        Wave 3: Final validation + price integrity + timing control
        
        THIS IS THE ONLY RUN THAT CAN PUBLISH
        
        Rules:
        - Run T-75 to T-60 minutes before game start
        - Final 100K simulations
        - Pull live sportsbook market line
        - Apply all publish gates
        - Decide POST or SILENCE
        
        Returns: EntrySnapshot if published, None if silenced
        """
        # Check timing window (T-75 to T-60)
        game_start = datetime.fromisoformat(live_market_data["commence_time"])
        now = datetime.now(timezone.utc)
        minutes_until_game = (game_start - now).total_seconds() / 60
        
        if not (60 <= minutes_until_game <= 75):
            return None  # Outside Wave 3 window
        
        # Get candidate
        candidate = self.db["edge_candidates"].find_one({
            "candidate_id": candidate_id
        })
        
        if not candidate or candidate["state"] not in ["EDGE_CONFIRMED", "LEAN_CONFIRMED"]:
            return None  # Not validated in Wave 2
        
        # Extract final metrics
        model_spread = final_simulation_output.get("model_spread")
        market_spread = live_market_data.get("spread_line")
        market_odds = live_market_data.get("spread_odds", -110)
        win_prob = final_simulation_output.get("win_probability")
        edge_gap = abs(model_spread - market_spread) if model_spread and market_spread else 0
        clv_estimate = final_simulation_output.get("clv_estimate", 0)
        volatility = final_simulation_output.get("volatility_bucket", "MEDIUM")
        
        # Validate required fields
        if model_spread is None or market_spread is None or win_prob is None:
            await self._block_candidate(candidate_id, "Missing required simulation data")
            return None
        
        # JUICE FILTER (mandatory hard block)
        if market_odds < self.MAX_JUICE:
            await self._block_candidate(candidate_id, "Juice kills EV")
            return None
        
        # Classify edge
        edge_grade = self._classify_edge(
            win_prob=win_prob,
            edge_gap=edge_gap,
            clv_estimate=clv_estimate,
            volatility=volatility,
            odds=market_odds,
            candidate_state=candidate["state"]
        )
        
        if edge_grade == EdgeGrade.NO_PLAY:
            await self._block_candidate(candidate_id, "Failed publish gates")
            return None
        
        # Check if A-grade already posted for this game
        if edge_grade == EdgeGrade.A_GRADE:
            existing_a_grade = self.db["entry_snapshots"].find_one({
                "game_id": candidate["game_id"],
                "edge_grade": EdgeGrade.A_GRADE
            })
            if existing_a_grade:
                await self._block_candidate(candidate_id, "Max 1 A-grade per game")
                return None
        
        # Check Lean Floor rule
        if edge_grade == EdgeGrade.STRONG_LEAN:
            # Only publish lean if NO A-grade exists
            existing_a_grade = self.db["entry_snapshots"].find_one({
                "game_id": candidate["game_id"],
                "edge_grade": EdgeGrade.A_GRADE
            })
            if existing_a_grade:
                await self._block_candidate(candidate_id, "A-grade exists, lean suppressed")
                return None
            
            # Lean Floor criteria (win_prob already validated as not None above)
            if win_prob is not None and not (edge_gap >= self.LEAN_FLOOR_EDGE and win_prob >= self.LEAN_FLOOR_WIN_PROB):
                await self._block_candidate(candidate_id, "Lean Floor criteria not met")
                return None
        
        # Calculate max acceptable line
        max_acceptable_line = self._calculate_max_acceptable_line(
            market_spread,
            market_type="SPREAD"
        )
        
        # Create entry snapshot (IMMUTABLE)
        entry_snapshot = EntrySnapshot(
            snapshot_id=f"entry_{uuid.uuid4().hex[:12]}",
            game_id=candidate["game_id"],
            market_type="SPREAD",
            side="TBD",  # Determined by model
            entry_line=market_spread,
            entry_odds=market_odds,
            model_fair_value=model_spread,
            edge_gap=edge_gap,
            win_probability=win_prob,
            clv_estimate=clv_estimate,
            timestamp=now,
            max_acceptable_line=max_acceptable_line,
            signal_id=""  # Will be set below
        )
        
        # Create immutable signal
        gates = self._evaluate_gates(final_simulation_output, live_market_data)
        
        signal = await self.signal_manager.create_signal(
            game_id=candidate["game_id"],
            sport=candidate["sport"],
            market_key="SPREAD",
            selection=f"TBD {market_spread}",  # Updated with actual side
            line_value=market_spread,
            market_snapshot_id="",  # Create snapshot
            sim_run_id="",  # Create sim run
            model_version=final_simulation_output.get("model_version", "v1.0"),
            intent=SignalIntent.LATE,
            edge_points=edge_gap,
            win_prob=win_prob,
            volatility_score=final_simulation_output.get("volatility_score", 0.5),
            volatility_bucket=VolatilityBucket(volatility),
            confidence_band=ConfidenceBand.MEDIUM,
            gates=gates,
            explain_summary=f"{edge_grade} edge detected with {edge_gap:.1f}pt gap",
            odds_price=market_odds,
            ev=clv_estimate
        )
        
        entry_snapshot.signal_id = signal.signal_id
        
        # Store entry snapshot
        snapshot_doc = entry_snapshot.to_dict()
        snapshot_doc["edge_grade"] = edge_grade
        snapshot_doc["published"] = False
        
        self.db["entry_snapshots"].insert_one(snapshot_doc)
        
        # POST TO TELEGRAM (if service available)
        if telegram_service:
            message = self._format_telegram_message(entry_snapshot, edge_grade)
            await telegram_service.post_to_channel(message)
            
            # Mark as published
            self.db["entry_snapshots"].update_one(
                {"snapshot_id": entry_snapshot.snapshot_id},
                {"$set": {"published": True, "published_at": now}}
            )
            
            # Lock signal (post-publish lock)
            await self.signal_manager.lock_signal(signal.signal_id, lock_reason="PUBLISHED_TO_TELEGRAM")
        
        # Update candidate
        self.db["edge_candidates"].update_one(
            {"candidate_id": candidate_id},
            {
                "$set": {
                    "wave": 3,
                    "state": "PUBLISHED" if telegram_service else "BLOCKED",
                    "entry_snapshot_id": entry_snapshot.snapshot_id,
                    "signal_id": signal.signal_id,
                    "edge_grade": edge_grade,
                    "published_at": now if telegram_service else None
                }
            }
        )
        
        return entry_snapshot
    
    # ========================================================================
    # EDGE CLASSIFICATION
    # ========================================================================
    
    def _classify_edge(
        self,
        win_prob: float,
        edge_gap: float,
        clv_estimate: float,
        volatility: str,
        odds: int,
        candidate_state: str
    ) -> str:
        """
        Classify edge quality with institutional gates
        
        Returns: A_GRADE, STRONG_LEAN, or NO_PLAY
        """
        # A-GRADE EDGE checks
        a_grade_standard = (
            win_prob >= self.A_GRADE_WIN_PROB and
            edge_gap >= self.A_GRADE_EDGE_GAP and
            clv_estimate >= self.A_GRADE_CLV and
            odds >= self.MAX_JUICE and
            volatility != "HIGH"
        )
        
        # Volatility override for exceptional edges
        a_grade_override = (
            edge_gap >= self.A_GRADE_VOLATILITY_OVERRIDE_EDGE and
            win_prob >= self.A_GRADE_VOLATILITY_OVERRIDE_WIN_PROB and
            clv_estimate >= 0.003 and
            odds >= self.MAX_JUICE
        )
        
        if a_grade_standard or a_grade_override:
            return EdgeGrade.A_GRADE
        
        # STRONG LEAN checks
        strong_lean = (
            self.LEAN_WIN_PROB_MIN <= win_prob <= self.LEAN_WIN_PROB_MAX and
            self.LEAN_EDGE_MIN <= edge_gap <= self.LEAN_EDGE_MAX and
            odds >= self.LEAN_MAX_JUICE and
            volatility in ["LOW", "MEDIUM"] and
            candidate_state == "LEAN_CONFIRMED"
        )
        
        if strong_lean:
            return EdgeGrade.STRONG_LEAN
        
        return EdgeGrade.NO_PLAY
    
    # ========================================================================
    # PRICE VALIDATION
    # ========================================================================
    
    def _calculate_max_acceptable_line(
        self,
        entry_line: float,
        market_type: Literal["SPREAD", "TOTAL"]
    ) -> float:
        """
        Calculate maximum acceptable line to prevent chasing
        
        MAX_ACCEPTABLE_LINE = ENTRY_LINE ± EDGE_BUFFER
        """
        if market_type == "SPREAD":
            buffer = self.SPREAD_BUFFER
        else:  # TOTAL
            buffer = self.TOTAL_BUFFER
        
        # For spreads, max acceptable is entry ± buffer
        # Example: Entry -11.0 → Max -12.5
        return entry_line - buffer if entry_line < 0 else entry_line + buffer
    
    async def validate_entry_price(
        self,
        snapshot_id: str,
        current_market_line: float
    ) -> bool:
        """
        Auto-block if price degraded beyond max acceptable
        
        Returns: True if valid, False if blocked
        """
        snapshot = self.db["entry_snapshots"].find_one({
            "snapshot_id": snapshot_id
        })
        
        if not snapshot:
            return False
        
        max_acceptable = snapshot["max_acceptable_line"]
        entry_line = snapshot["entry_line"]
        
        # Check if current line exceeds max acceptable
        if entry_line < 0:  # Negative spread
            if current_market_line < max_acceptable:
                await self._log_block_reason(snapshot_id, "Price degraded beyond max acceptable")
                return False
        else:  # Positive spread
            if current_market_line > max_acceptable:
                await self._log_block_reason(snapshot_id, "Price degraded beyond max acceptable")
                return False
        
        return True
    
    # ========================================================================
    # HELPER METHODS
    # ========================================================================
    
    def _evaluate_gates(
        self,
        simulation_output: Dict[str, Any],
        market_data: Dict[str, Any]
    ) -> GateEvaluation:
        """Evaluate all publish gates"""
        volatility_bucket = simulation_output.get("volatility_bucket", "MEDIUM")
        return GateEvaluation(
            data_integrity=GateResult(pass_gate=True, bucket=None, reasons=[]),
            sim_power=GateResult(pass_gate=simulation_output.get("num_sims", 0) >= 100000, bucket=None, reasons=[]),
            model_validity=GateResult(pass_gate=True, bucket=None, reasons=[]),
            volatility=GateResult(
                pass_gate=volatility_bucket != "HIGH",
                bucket=volatility_bucket,
                reasons=[ReasonCode.VOL_HIGH] if volatility_bucket == "HIGH" else []
            ),
            publish_rcl=GateResult(pass_gate=True, bucket=None, reasons=[])
        )
    
    async def _block_candidate(self, candidate_id: str, reason: str):
        """Block candidate from publishing"""
        self.db["edge_candidates"].update_one(
            {"candidate_id": candidate_id},
            {
                "$set": {
                    "state": "BLOCKED",
                    "block_reason": reason,
                    "blocked_at": datetime.now(timezone.utc)
                }
            }
        )
    
    async def _log_block_reason(self, snapshot_id: str, reason: str):
        """Log price validation block"""
        self.db["entry_snapshots"].update_one(
            {"snapshot_id": snapshot_id},
            {
                "$set": {
                    "entry_blocked": True,
                    "block_reason": reason,
                    "blocked_at": datetime.now(timezone.utc)
                }
            }
        )
    
    def _format_telegram_message(self, snapshot: EntrySnapshot, grade: str) -> str:
        """Format Telegram post message"""
        label = "🟢 A-GRADE EDGE" if grade == EdgeGrade.A_GRADE else "🟡 STRONG LEAN — SMALL SIZE"
        
        return f"""
{label}

{snapshot.side} {snapshot.entry_line}
Odds: {snapshot.entry_odds}

Model Fair Value: {snapshot.model_fair_value:.1f}
Edge: +{snapshot.edge_gap:.1f} pts
Win Probability: {snapshot.win_probability*100:.1f}%
CLV: +{snapshot.clv_estimate*100:.2f}%

⚠️ MAX ACCEPTABLE LINE: {snapshot.max_acceptable_line}
DO NOT BET if line moves beyond this threshold

Entry Time: {snapshot.timestamp.strftime('%I:%M %p ET')}
"""
