"""
Signal Manager Service
Handles immutable signal creation, locking, delta computation, and robustness scoring
"""
import uuid
import hashlib
import json
from typing import Optional, List, Dict, Any, Tuple, cast, Literal
from datetime import datetime, timezone, timedelta
from pymongo.database import Database

from db.schemas.signal_schemas import (
    Signal,
    MarketSnapshot,
    SimulationRun,
    LockedSignal,
    SignalDelta,
    SignalState,
    SignalIntent,
    FinalStatus,
    VolatilityBucket,
    ConfidenceBand,
    RobustnessLabel,
    ReasonCode,
    GateEvaluation,
    GateResult,
    SIGNAL_COLLECTIONS
)


class SignalManager:
    """
    Core signal lifecycle manager
    Enforces immutability, locking, and delta tracking
    """
    
    def __init__(self, db: Database):
        self.db = db
    
    # ========================================================================
    # MARKET SNAPSHOT CREATION
    # ========================================================================
    
    async def create_market_snapshot(
        self,
        game_id: str,
        spread_line: Optional[float] = None,
        spread_home_price: Optional[int] = None,
        spread_away_price: Optional[int] = None,
        total_line: Optional[float] = None,
        total_over_price: Optional[int] = None,
        total_under_price: Optional[int] = None,
        ml_home_price: Optional[int] = None,
        ml_away_price: Optional[int] = None,
        book_prices: Optional[Dict] = None,
        source: str = "odds_api"
    ) -> MarketSnapshot:
        """
        Create immutable market snapshot
        Returns existing snapshot if identical data already captured
        """
        # Create snapshot data
        snapshot_data = {
            "game_id": game_id,
            "spread_line": spread_line,
            "spread_home_price": spread_home_price,
            "spread_away_price": spread_away_price,
            "total_line": total_line,
            "total_over_price": total_over_price,
            "total_under_price": total_under_price,
            "ml_home_price": ml_home_price,
            "ml_away_price": ml_away_price,
            "book_prices": book_prices or {}
        }
        
        # Generate hash for deduplication
        snapshot_hash = hashlib.sha256(
            json.dumps(snapshot_data, sort_keys=True).encode()
        ).hexdigest()[:16]
        
        # Check if identical snapshot exists (within last hour)
        one_hour_ago = datetime.now(timezone.utc) - timedelta(hours=1)
        existing = self.db[SIGNAL_COLLECTIONS["market_snapshots"]].find_one({
            "snapshot_hash": snapshot_hash,
            "captured_at": {"$gte": one_hour_ago}
        })
        
        if existing:
            return MarketSnapshot(**existing)
        
        # Create new snapshot
        snapshot = MarketSnapshot(
            market_snapshot_id=f"snap_{uuid.uuid4().hex[:12]}",
            game_id=game_id,
            captured_at=datetime.now(timezone.utc),
            source=source,
            spread_line=spread_line,
            spread_home_price=spread_home_price,
            spread_away_price=spread_away_price,
            total_line=total_line,
            total_over_price=total_over_price,
            total_under_price=total_under_price,
            ml_home_price=ml_home_price,
            ml_away_price=ml_away_price,
            book_prices=book_prices or {},
            snapshot_hash=snapshot_hash
        )
        
        self.db[SIGNAL_COLLECTIONS["market_snapshots"]].insert_one(
            snapshot.model_dump()
        )
        
        return snapshot
    
    # ========================================================================
    # SIMULATION RUN RECORDING
    # ========================================================================
    
    async def record_simulation_run(
        self,
        game_id: str,
        model_version: str,
        inputs_version: str,
        seed: int,
        num_sims: int,
        distribution: Dict[str, float],
        execution_time_ms: Optional[int] = None
    ) -> SimulationRun:
        """Record simulation execution for replay"""
        sim_run = SimulationRun(
            sim_run_id=f"sim_{uuid.uuid4().hex[:12]}",
            game_id=game_id,
            model_version=model_version,
            inputs_version=inputs_version,
            seed=seed,
            num_sims=num_sims,
            distribution=distribution,
            created_at=datetime.now(timezone.utc),
            execution_time_ms=execution_time_ms
        )
        
        self.db[SIGNAL_COLLECTIONS["simulation_runs"]].insert_one(
            sim_run.model_dump()
        )
        
        return sim_run
    
    # ========================================================================
    # SIGNAL CREATION (CORE IMMUTABLE OPERATION)
    # ========================================================================
    
    async def create_signal(
        self,
        game_id: str,
        sport: str,
        market_key: str,
        selection: str,
        line_value: float,
        market_snapshot_id: str,
        sim_run_id: str,
        model_version: str,
        intent: SignalIntent,
        edge_points: float,
        win_prob: float,
        volatility_score: float,
        volatility_bucket: VolatilityBucket,
        confidence_band: ConfidenceBand,
        gates: GateEvaluation,
        explain_summary: str,
        odds_price: Optional[int] = None,
        ev: Optional[float] = None,
        book_key: str = "CONSENSUS"
    ) -> Signal:
        """
        Create NEW immutable signal
        NEVER overwrites existing signals
        """
        # Determine signal state from gates
        if gates.all_passed():
            # Classify as PICK or LEAN based on confidence
            if win_prob >= 0.58 and abs(edge_points) >= 3.0:
                state = SignalState.PICK
            elif win_prob >= 0.54 and abs(edge_points) >= 1.5:
                state = SignalState.LEAN
            else:
                state = SignalState.NO_PLAY
        else:
            state = SignalState.NO_PLAY
        
        # Collect all reason codes
        reason_codes = gates.get_all_reasons()
        
        # Create signal
        signal = Signal(
            signal_id=f"sig_{uuid.uuid4().hex[:12]}",
            game_id=game_id,
            sport=sport,
            market_key=cast(Literal["SPREAD", "TOTAL", "ML", "PROP"], market_key),
            selection=selection,
            book_key=book_key,
            line_value=line_value,
            odds_price=odds_price,
            market_snapshot_id=market_snapshot_id,
            model_version=model_version,
            sim_run_id=sim_run_id,
            created_at=datetime.now(timezone.utc),
            intent=intent,
            edge_points=edge_points,
            win_prob=win_prob,
            ev=ev,
            volatility_score=volatility_score,
            volatility_bucket=volatility_bucket,
            confidence_band=confidence_band,
            state=state,
            gates=gates,
            reason_codes=reason_codes,
            explain_summary=explain_summary,
            robustness_score=None  # Will be computed below
        )
        
        # Compute robustness if previous signals exist
        robustness = await self._compute_robustness(game_id, market_key)
        if robustness:
            signal.robustness_label = robustness["label"]
            signal.robustness_score = robustness["score"]
        else:
            signal.robustness_score = None
        
        # Save signal
        self.db[SIGNAL_COLLECTIONS["signals"]].insert_one(
            signal.model_dump()
        )
        
        # Log event
        await self._log_signal_event("signal_created", signal.signal_id, game_id)
        
        # Check if should auto-lock
        if state in [SignalState.PICK, SignalState.LEAN]:
            await self._check_auto_lock(signal)
        
        return signal
    
    # ========================================================================
    # SIGNAL LOCKING (ACTION FREEZE)
    # ========================================================================
    
    async def lock_signal(
        self,
        signal_id: str,
        lock_type: str = "AUTO",
        freeze_duration_minutes: int = 60,
        lock_reason: str = "ACTIONABLE_FIRST_HIT"
    ) -> LockedSignal:
        """
        Lock a signal to prevent churn
        Enforces action freeze window
        """
        signal = await self.get_signal(signal_id)
        if not signal:
            raise ValueError(f"Signal {signal_id} not found")
        
        # Check if already locked
        existing_lock = self.db[SIGNAL_COLLECTIONS["locked_signals"]].find_one({
            "game_id": signal.game_id,
            "market_key": signal.market_key,
            "unlocked_at": None
        })
        
        if existing_lock:
            return LockedSignal(**existing_lock)
        
        # Create lock
        locked = LockedSignal(
            locked_signal_id=f"lock_{uuid.uuid4().hex[:12]}",
            signal_id=signal_id,
            game_id=signal.game_id,
            market_key=signal.market_key,
            lock_type=cast(Literal['AUTO', 'MANUAL'], lock_type),
            locked_at=datetime.now(timezone.utc),
            lock_expiry=None,  # Can be set based on game start time
            lock_reason=lock_reason,
            freeze_duration_minutes=freeze_duration_minutes
        )
        
        self.db[SIGNAL_COLLECTIONS["locked_signals"]].insert_one(
            locked.model_dump()
        )
        
        await self._log_signal_event("signal_locked", signal_id, signal.game_id)
        
        return locked
    
    async def check_lock_status(
        self,
        game_id: str,
        market_key: str
    ) -> Tuple[bool, Optional[LockedSignal]]:
        """
        Check if market is locked and whether freeze window is active
        Returns (is_locked, lock_record)
        """
        lock_doc = self.db[SIGNAL_COLLECTIONS["locked_signals"]].find_one({
            "game_id": game_id,
            "market_key": market_key,
            "unlocked_at": None
        })
        
        if not lock_doc:
            return False, None
        
        lock = LockedSignal(**lock_doc)
        
        # Check if freeze window expired
        freeze_end = lock.locked_at + timedelta(minutes=lock.freeze_duration_minutes)
        if datetime.now(timezone.utc) > freeze_end:
            return False, lock
        
        return True, lock
    
    async def check_material_move(
        self,
        lock: LockedSignal,
        new_snapshot: MarketSnapshot
    ) -> Tuple[bool, Optional[str]]:
        """
        Check if market moved enough to break freeze
        Returns (should_unlock, reason)
        """
        # Get original snapshot
        original_signal = await self.get_signal(lock.signal_id)
        if not original_signal:
            return False, None
        
        original_snapshot_doc = self.db[SIGNAL_COLLECTIONS["market_snapshots"]].find_one({
            "market_snapshot_id": original_signal.market_snapshot_id
        })
        
        if not original_snapshot_doc:
            return False, None
        
        original_snapshot = MarketSnapshot(**original_snapshot_doc)
        
        # Check thresholds based on market type
        if original_signal.market_key == "SPREAD":
            if original_snapshot.spread_line and new_snapshot.spread_line:
                move = abs(original_snapshot.spread_line - new_snapshot.spread_line)
                if move >= lock.material_move_threshold["spread_points"]:
                    return True, f"Spread moved {move} points"
        
        elif original_signal.market_key == "TOTAL":
            if original_snapshot.total_line and new_snapshot.total_line:
                move = abs(original_snapshot.total_line - new_snapshot.total_line)
                if move >= lock.material_move_threshold["total_points"]:
                    return True, f"Total moved {move} points"
        
        return False, None
    
    # ========================================================================
    # DELTA COMPUTATION
    # ========================================================================
    
    async def compute_delta(
        self,
        from_signal_id: str,
        to_signal_id: str
    ) -> SignalDelta:
        """
        Compute what changed between two signals
        Critical for "What changed?" UI panel
        """
        from_signal = await self.get_signal(from_signal_id)
        to_signal = await self.get_signal(to_signal_id)
        
        if not from_signal or not to_signal:
            raise ValueError("Both signals must exist")
        
        # Compute numerical deltas
        delta_edge = to_signal.edge_points - from_signal.edge_points
        delta_prob = to_signal.win_prob - from_signal.win_prob
        delta_vol = to_signal.volatility_score - from_signal.volatility_score
        
        # State changes
        state_changed = from_signal.state != to_signal.state
        
        # Bucket changes
        vol_changed = from_signal.volatility_bucket != to_signal.volatility_bucket
        
        # Gate changes
        gate_changes = []
        if from_signal.gates.data_integrity.pass_gate != to_signal.gates.data_integrity.pass_gate:
            gate_changes.append("data_integrity")
        if from_signal.gates.sim_power.pass_gate != to_signal.gates.sim_power.pass_gate:
            gate_changes.append("sim_power")
        if from_signal.gates.model_validity.pass_gate != to_signal.gates.model_validity.pass_gate:
            gate_changes.append("model_validity")
        if from_signal.gates.volatility.pass_gate != to_signal.gates.volatility.pass_gate:
            gate_changes.append("volatility")
        if from_signal.gates.publish_rcl.pass_gate != to_signal.gates.publish_rcl.pass_gate:
            gate_changes.append("publish_rcl")
        
        # Line movement
        line_moved = from_signal.line_value != to_signal.line_value
        line_move_points = to_signal.line_value - from_signal.line_value if line_moved else None
        
        # Generate summary
        change_parts = []
        if line_moved and line_move_points is not None:
            change_parts.append(f"Line moved {abs(line_move_points):.1f} points")
        if abs(delta_prob) >= 0.03:
            change_parts.append(f"Win prob {'+' if delta_prob > 0 else ''}{delta_prob*100:.1f}%")
        if state_changed:
            change_parts.append(f"{from_signal.state.value} → {to_signal.state.value}")
        if gate_changes:
            change_parts.append(f"Gates changed: {', '.join(gate_changes)}")
        
        change_summary = "; ".join(change_parts) if change_parts else "Minor updates"
        
        # Create delta
        delta = SignalDelta(
            delta_id=f"delta_{uuid.uuid4().hex[:12]}",
            from_signal_id=from_signal_id,
            to_signal_id=to_signal_id,
            game_id=to_signal.game_id,
            market_key=to_signal.market_key,
            computed_at=datetime.now(timezone.utc),
            delta_edge_points=delta_edge,
            delta_win_prob=delta_prob,
            delta_volatility_score=delta_vol,
            state_changed=state_changed,
            previous_state=from_signal.state,
            new_state=to_signal.state,
            volatility_bucket_changed=vol_changed,
            previous_volatility=from_signal.volatility_bucket if vol_changed else None,
            new_volatility=to_signal.volatility_bucket if vol_changed else None,
            gate_changes=gate_changes,
            line_moved=line_moved,
            line_move_points=line_move_points,
            change_summary=change_summary
        )
        
        self.db[SIGNAL_COLLECTIONS["signal_deltas"]].insert_one(
            delta.model_dump()
        )
        
        return delta
    
    # ========================================================================
    # ROBUSTNESS SCORING
    # ========================================================================
    
    async def _compute_robustness(
        self,
        game_id: str,
        market_key: str,
        lookback: int = 5
    ) -> Optional[Dict[str, Any]]:
        """
        Compute signal robustness from recent history
        Robust = survives re-sim + line movement
        """
        # Get last N signals for this market
        cursor = self.db[SIGNAL_COLLECTIONS["signals"]].find({
            "game_id": game_id,
            "market_key": market_key
        }).sort("created_at", -1).limit(lookback)
        
        signals = []
        for doc in list(cursor):
            signals.append(Signal(**doc))
        
        if len(signals) < 3:
            return None
        
        # Compute stability metrics
        states = [s.state for s in signals]
        state_stability = len([s for s in states if s == states[0]]) / len(states)
        
        edges = [s.edge_points for s in signals]
        edge_std = sum((e - sum(edges)/len(edges))**2 for e in edges) ** 0.5 / len(edges)
        
        vol_buckets = [s.volatility_bucket for s in signals]
        vol_stability = len([v for v in vol_buckets if v == vol_buckets[0]]) / len(vol_buckets)
        
        # Score: 0-100
        score = int(
            (state_stability * 40) +
            (max(0, 1 - edge_std/5) * 30) +
            (vol_stability * 30)
        )
        
        label = RobustnessLabel.ROBUST if score >= 70 else RobustnessLabel.FRAGILE
        
        return {
            "label": label,
            "score": score
        }
    
    # ========================================================================
    # HELPER METHODS
    # ========================================================================
    
    async def get_signal(self, signal_id: str) -> Optional[Signal]:
        """Get signal by ID"""
        doc = self.db[SIGNAL_COLLECTIONS["signals"]].find_one({
            "signal_id": signal_id
        })
        return Signal(**doc) if doc else None
    
    async def get_latest_signal(
        self,
        game_id: str,
        market_key: str
    ) -> Optional[Signal]:
        """Get most recent signal for market"""
        doc = self.db[SIGNAL_COLLECTIONS["signals"]].find_one(
            {"game_id": game_id, "market_key": market_key},
            sort=[("created_at", -1)]
        )
        return Signal(**doc) if doc else None
    
    async def get_signal_history(
        self,
        game_id: str,
        market_key: str,
        limit: int = 10
    ) -> List[Signal]:
        """Get signal history for a market"""
        cursor = self.db[SIGNAL_COLLECTIONS["signals"]].find({
            "game_id": game_id,
            "market_key": market_key
        }).sort("created_at", -1).limit(limit)
        
        signals = []
        for doc in list(cursor):
            signals.append(Signal(**doc))
        
        return signals
    
    async def _check_auto_lock(self, signal: Signal):
        """Check if signal should be auto-locked"""
        if signal.state in [SignalState.PICK, SignalState.LEAN]:
            is_locked, _ = await self.check_lock_status(signal.game_id, signal.market_key)
            if not is_locked:
                await self.lock_signal(signal.signal_id)
    
    async def _log_signal_event(
        self,
        event_type: str,
        signal_id: str,
        game_id: str,
        metadata: Optional[Dict] = None
    ):
        """Log signal lifecycle event"""
        event = {
            "event_id": f"evt_{uuid.uuid4().hex[:12]}",
            "event_type": event_type,
            "signal_id": signal_id,
            "game_id": game_id,
            "created_at": datetime.now(timezone.utc),
            "metadata": metadata or {}
        }
        
        self.db[SIGNAL_COLLECTIONS["signal_events"]].insert_one(event)
    
    async def settle_signal(
        self,
        signal_id: str,
        outcome: str,
        actual_result: Optional[float] = None
    ):
        """Mark signal as settled with outcome"""
        self.db[SIGNAL_COLLECTIONS["signals"]].update_one(
            {"signal_id": signal_id},
            {
                "$set": {
                    "final_status": FinalStatus.SETTLED.value,
                    "settled_at": datetime.now(timezone.utc),
                    "outcome": outcome,
                    "actual_result": actual_result
                }
            }
        )
        
        await self._log_signal_event("signal_settled", signal_id, "", {
            "outcome": outcome,
            "actual_result": actual_result
        })
