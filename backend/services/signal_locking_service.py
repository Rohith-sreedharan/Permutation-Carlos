"""
Signal Locking Service
Implements proper signal locking per decision-time snapshot architecture

CORE RULES (NON-NEGOTIABLE):
1. Signal locking: First signal crossing threshold gets LOCKED and POSTED
2. Confirmation window: N-of-M confirmation before locking (anti-noise filter)
3. Subsequent simulations CANNOT retract/flip/replace locked signals
4. Later sims may only: downgrade confidence, mark as monitoring, invalidate via explicit rules
5. The FIRST qualifying simulation is the source of truth, NOT the latest

Signal States:
- PENDING: Created, awaiting confirmation
- ACTIVE_EDGE: Posted, this is what users bet
- ACTIVE_MONITORING: Still valid but variance rising (no new add)
- INVALIDATED: Injury/lineup/market snap (explicit post explaining why)
- WEAKENED: Confidence dropped but still valid
- SETTLED: Game completed, graded
"""
from typing import Optional, List, Dict, Any, Tuple, Literal
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass, field
from enum import Enum
import uuid
from pymongo.database import Database


# ============================================================================
# ENUMS & CONSTANTS
# ============================================================================

class LockedSignalState(str, Enum):
    """States for locked signals (post-confirmation)"""
    ACTIVE_EDGE = "ACTIVE_EDGE"           # Posted, users should bet
    ACTIVE_MONITORING = "ACTIVE_MONITORING"  # Still valid, variance rising
    WEAKENED = "WEAKENED"                 # Confidence dropped
    INVALIDATED = "INVALIDATED"           # Explicit invalidation
    SETTLED = "SETTLED"                   # Game completed


class ConfirmationStatus(str, Enum):
    """Status of confirmation window"""
    PENDING = "PENDING"           # Awaiting N-of-M confirmations
    CONFIRMED = "CONFIRMED"       # Met threshold, ready to lock
    REJECTED = "REJECTED"         # Failed to confirm
    EXPIRED = "EXPIRED"           # Window expired without confirmation


class InvalidationReason(str, Enum):
    """Explicit reasons for signal invalidation"""
    INJURY_UPDATE = "INJURY_UPDATE"
    LINEUP_CHANGE = "LINEUP_CHANGE"
    MARKET_SUSPENSION = "MARKET_SUSPENSION"
    LINE_MOVED_MATERIALLY = "LINE_MOVED_MATERIALLY"  # >1.5 pts spread, >3 pts total
    GAME_POSTPONED = "GAME_POSTPONED"
    DATA_INTEGRITY_FAILURE = "DATA_INTEGRITY_FAILURE"
    MANUAL_INVALIDATION = "MANUAL_INVALIDATION"


# ============================================================================
# CONFIRMATION WINDOW CONFIG
# ============================================================================

@dataclass
class ConfirmationConfig:
    """Configuration for N-of-M confirmation"""
    num_required: int = 2           # N (must see edge N times)
    num_runs: int = 3               # M (out of M consecutive runs)
    max_wait_minutes: int = 15      # Max time to gather M runs
    edge_threshold: float = 3.0     # Minimum edge points
    confidence_threshold: float = 0.50  # Minimum confidence (50%)
    
    # Anti-noise parameters
    max_variance_between_runs: float = 0.15  # Max allowed variance in win_prob


# ============================================================================
# DATA STRUCTURES
# ============================================================================

@dataclass
class ConfirmationRun:
    """Record of a single confirmation run"""
    run_id: str
    signal_id: str
    sim_run_id: str
    edge_points: float
    win_prob: float
    confidence_score: float
    created_at: datetime
    passes_threshold: bool
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "signal_id": self.signal_id,
            "sim_run_id": self.sim_run_id,
            "edge_points": self.edge_points,
            "win_prob": self.win_prob,
            "confidence_score": self.confidence_score,
            "created_at": self.created_at,
            "passes_threshold": self.passes_threshold
        }


@dataclass
class ConfirmationWindow:
    """Tracks confirmation status for a game/market"""
    window_id: str
    game_id: str
    market_key: str
    
    # Configuration
    config: ConfirmationConfig
    
    # State
    status: ConfirmationStatus = ConfirmationStatus.PENDING
    runs: List[ConfirmationRun] = field(default_factory=list)
    
    # Timestamps
    opened_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    closed_at: Optional[datetime] = None
    
    # Result
    confirmed_signal_id: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "window_id": self.window_id,
            "game_id": self.game_id,
            "market_key": self.market_key,
            "config": {
                "num_required": self.config.num_required,
                "num_runs": self.config.num_runs,
                "max_wait_minutes": self.config.max_wait_minutes,
                "edge_threshold": self.config.edge_threshold,
                "confidence_threshold": self.config.confidence_threshold
            },
            "status": self.status.value,
            "runs": [r.to_dict() for r in self.runs],
            "opened_at": self.opened_at,
            "closed_at": self.closed_at,
            "confirmed_signal_id": self.confirmed_signal_id
        }


@dataclass
class LockedSignalRecord:
    """
    Immutable record of a LOCKED signal
    This is the source of truth for Telegram posting
    
    CRITICAL: Once created, only state can change.
    Never change: edge_points, line_value, selection, locked_signal_id
    """
    locked_signal_id: str
    original_signal_id: str
    game_id: str
    market_key: str
    sport: str
    
    # Frozen at lock time (IMMUTABLE)
    selection: str              # e.g., "Bulls +6.5"
    line_value: float           # Market line at decision time
    edge_points: float          # Edge at decision time
    win_prob: float             # Win prob at decision time
    confidence_score: float     # Confidence at decision time
    sim_count: int              # Sim count at decision time
    market_snapshot_id: str     # Reference to market state
    
    # Timestamps
    locked_at: datetime
    decision_timestamp: datetime  # When signal first crossed threshold
    
    # Current state (MUTABLE)
    state: LockedSignalState = LockedSignalState.ACTIVE_EDGE
    current_confidence: Optional[float] = None
    current_win_prob: Optional[float] = None
    
    # Telegram
    telegram_posted: bool = False
    telegram_message_ids: Dict[str, str] = field(default_factory=dict)
    telegram_posted_at: Optional[datetime] = None
    
    # State change history
    state_history: List[Dict[str, Any]] = field(default_factory=list)
    
    # Invalidation (only if state = INVALIDATED)
    invalidation_reason: Optional[InvalidationReason] = None
    invalidation_explanation: Optional[str] = None
    invalidated_at: Optional[datetime] = None
    
    # Settlement
    settled_at: Optional[datetime] = None
    outcome: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "locked_signal_id": self.locked_signal_id,
            "original_signal_id": self.original_signal_id,
            "game_id": self.game_id,
            "market_key": self.market_key,
            "sport": self.sport,
            "selection": self.selection,
            "line_value": self.line_value,
            "edge_points": self.edge_points,
            "win_prob": self.win_prob,
            "confidence_score": self.confidence_score,
            "sim_count": self.sim_count,
            "market_snapshot_id": self.market_snapshot_id,
            "locked_at": self.locked_at,
            "decision_timestamp": self.decision_timestamp,
            "state": self.state.value,
            "current_confidence": self.current_confidence,
            "current_win_prob": self.current_win_prob,
            "telegram_posted": self.telegram_posted,
            "telegram_message_ids": self.telegram_message_ids,
            "telegram_posted_at": self.telegram_posted_at,
            "state_history": self.state_history,
            "invalidation_reason": self.invalidation_reason.value if self.invalidation_reason else None,
            "invalidation_explanation": self.invalidation_explanation,
            "invalidated_at": self.invalidated_at,
            "settled_at": self.settled_at,
            "outcome": self.outcome
        }


# ============================================================================
# COLLECTION NAMES
# ============================================================================

LOCKING_COLLECTIONS = {
    "confirmation_windows": "signal_confirmation_windows",
    "locked_signals": "locked_signals_v2",  # v2 to avoid collision
    "locking_events": "signal_locking_events"
}


# ============================================================================
# SIGNAL LOCKING SERVICE
# ============================================================================

class SignalLockingService:
    """
    Manages signal confirmation and locking lifecycle
    
    WORKFLOW:
    1. New simulation creates signal → check if market already locked
    2. If not locked, add to confirmation window
    3. If N-of-M confirmations achieved → LOCK signal
    4. Post FIRST locked signal to Telegram
    5. Subsequent sims can only UPDATE state, not replace
    """
    
    def __init__(self, db: Database, config: Optional[ConfirmationConfig] = None):
        self.db = db
        self.config = config or ConfirmationConfig()
    
    # ========================================================================
    # LOCK STATUS CHECK (CRITICAL - CALL FIRST)
    # ========================================================================
    
    async def is_market_locked(
        self,
        game_id: str,
        market_key: str
    ) -> Tuple[bool, Optional[LockedSignalRecord]]:
        """
        Check if market is already locked
        
        CRITICAL: Call this BEFORE processing any new simulation
        If locked, the locked signal is the ONLY signal that matters
        
        Returns:
            (is_locked, locked_record)
        """
        doc = self.db[LOCKING_COLLECTIONS["locked_signals"]].find_one({
            "game_id": game_id,
            "market_key": market_key,
            "state": {"$nin": [LockedSignalState.SETTLED.value]}  # Exclude settled
        })
        
        if not doc:
            return False, None
        
        return True, self._doc_to_locked_record(doc)
    
    # ========================================================================
    # CONFIRMATION WINDOW MANAGEMENT
    # ========================================================================
    
    async def process_signal(
        self,
        signal_id: str,
        game_id: str,
        market_key: str,
        sport: str,
        selection: str,
        line_value: float,
        edge_points: float,
        win_prob: float,
        confidence_score: float,
        sim_count: int,
        sim_run_id: str,
        market_snapshot_id: str
    ) -> Tuple[str, Optional[LockedSignalRecord]]:
        """
        Process a new signal through the locking pipeline
        
        Returns:
            (status, locked_record)
            status: "ALREADY_LOCKED" | "ADDED_TO_WINDOW" | "LOCKED" | "REJECTED"
        """
        # Step 1: Check if already locked
        is_locked, existing_lock = await self.is_market_locked(game_id, market_key)
        
        if is_locked and existing_lock:
            # Market already locked - update monitoring only
            await self._update_locked_signal_monitoring(
                existing_lock,
                edge_points,
                win_prob,
                confidence_score
            )
            return "ALREADY_LOCKED", existing_lock
        
        # Step 2: Check if signal meets threshold
        passes_threshold = (
            edge_points >= self.config.edge_threshold and
            confidence_score >= self.config.confidence_threshold
        )
        
        # Step 3: Get or create confirmation window
        window = await self._get_or_create_window(game_id, market_key)
        
        # Step 4: Add run to window
        run = ConfirmationRun(
            run_id=f"run_{uuid.uuid4().hex[:8]}",
            signal_id=signal_id,
            sim_run_id=sim_run_id,
            edge_points=edge_points,
            win_prob=win_prob,
            confidence_score=confidence_score,
            created_at=datetime.now(timezone.utc),
            passes_threshold=passes_threshold
        )
        
        window.runs.append(run)
        
        # Step 5: Evaluate confirmation status
        confirmation_result = self._evaluate_confirmation(window)
        
        if confirmation_result == "CONFIRMED":
            # LOCK the signal!
            locked_record = await self._lock_signal(
                window=window,
                signal_id=signal_id,
                game_id=game_id,
                market_key=market_key,
                sport=sport,
                selection=selection,
                line_value=line_value,
                edge_points=edge_points,
                win_prob=win_prob,
                confidence_score=confidence_score,
                sim_count=sim_count,
                market_snapshot_id=market_snapshot_id
            )
            
            window.status = ConfirmationStatus.CONFIRMED
            window.confirmed_signal_id = signal_id
            window.closed_at = datetime.now(timezone.utc)
            
            await self._save_window(window)
            return "LOCKED", locked_record
        
        elif confirmation_result == "REJECTED":
            window.status = ConfirmationStatus.REJECTED
            window.closed_at = datetime.now(timezone.utc)
            await self._save_window(window)
            return "REJECTED", None
        
        else:
            # Still pending
            await self._save_window(window)
            return "ADDED_TO_WINDOW", None
    
    def _evaluate_confirmation(self, window: ConfirmationWindow) -> str:
        """
        Evaluate if confirmation window meets N-of-M threshold
        
        Returns: "CONFIRMED" | "REJECTED" | "PENDING"
        """
        # Check if window expired
        window_age = (datetime.now(timezone.utc) - window.opened_at).total_seconds() / 60
        if window_age > window.config.max_wait_minutes:
            # Count passing runs
            passing = sum(1 for r in window.runs if r.passes_threshold)
            if passing >= window.config.num_required:
                return "CONFIRMED"
            return "REJECTED"
        
        # Check if we have enough runs
        if len(window.runs) < window.config.num_runs:
            return "PENDING"
        
        # Get last M runs
        recent_runs = window.runs[-window.config.num_runs:]
        
        # Count passing runs
        passing = sum(1 for r in recent_runs if r.passes_threshold)
        
        # Check for excessive variance between runs (anti-noise)
        if len(recent_runs) >= 2:
            probs = [r.win_prob for r in recent_runs]
            variance = max(probs) - min(probs)
            if variance > window.config.max_variance_between_runs:
                # Too noisy - need more confirmation
                return "PENDING"
        
        # N-of-M check
        if passing >= window.config.num_required:
            return "CONFIRMED"
        
        # Not enough passing
        if len(window.runs) >= window.config.num_runs:
            # We have M runs but didn't hit N - reject
            return "REJECTED"
        
        return "PENDING"
    
    async def _get_or_create_window(
        self,
        game_id: str,
        market_key: str
    ) -> ConfirmationWindow:
        """Get existing window or create new one"""
        doc = self.db[LOCKING_COLLECTIONS["confirmation_windows"]].find_one({
            "game_id": game_id,
            "market_key": market_key,
            "status": ConfirmationStatus.PENDING.value
        })
        
        if doc:
            return ConfirmationWindow(
                window_id=doc["window_id"],
                game_id=doc["game_id"],
                market_key=doc["market_key"],
                config=ConfirmationConfig(
                    num_required=doc["config"]["num_required"],
                    num_runs=doc["config"]["num_runs"],
                    max_wait_minutes=doc["config"]["max_wait_minutes"],
                    edge_threshold=doc["config"]["edge_threshold"],
                    confidence_threshold=doc["config"]["confidence_threshold"]
                ),
                status=ConfirmationStatus(doc["status"]),
                runs=[ConfirmationRun(**r) for r in doc.get("runs", [])],
                opened_at=doc["opened_at"],
                closed_at=doc.get("closed_at"),
                confirmed_signal_id=doc.get("confirmed_signal_id")
            )
        
        # Create new window
        window = ConfirmationWindow(
            window_id=f"win_{uuid.uuid4().hex[:12]}",
            game_id=game_id,
            market_key=market_key,
            config=self.config
        )
        
        return window
    
    async def _save_window(self, window: ConfirmationWindow):
        """Save confirmation window"""
        self.db[LOCKING_COLLECTIONS["confirmation_windows"]].update_one(
            {"window_id": window.window_id},
            {"$set": window.to_dict()},
            upsert=True
        )
    
    # ========================================================================
    # SIGNAL LOCKING
    # ========================================================================
    
    async def _lock_signal(
        self,
        window: ConfirmationWindow,
        signal_id: str,
        game_id: str,
        market_key: str,
        sport: str,
        selection: str,
        line_value: float,
        edge_points: float,
        win_prob: float,
        confidence_score: float,
        sim_count: int,
        market_snapshot_id: str
    ) -> LockedSignalRecord:
        """
        Lock a signal after confirmation
        
        This is the FIRST signal that crossed threshold and confirmed.
        It becomes the OFFICIAL signal for Telegram posting.
        """
        # Find the first run that passed threshold (decision time)
        first_passing_run = next(
            (r for r in window.runs if r.passes_threshold),
            window.runs[0]
        )
        
        locked_record = LockedSignalRecord(
            locked_signal_id=f"locked_{uuid.uuid4().hex[:12]}",
            original_signal_id=first_passing_run.signal_id,
            game_id=game_id,
            market_key=market_key,
            sport=sport,
            selection=selection,
            line_value=line_value,
            edge_points=first_passing_run.edge_points,  # Use FIRST passing edge
            win_prob=first_passing_run.win_prob,        # Use FIRST passing prob
            confidence_score=first_passing_run.confidence_score,
            sim_count=sim_count,
            market_snapshot_id=market_snapshot_id,
            locked_at=datetime.now(timezone.utc),
            decision_timestamp=first_passing_run.created_at,
            state=LockedSignalState.ACTIVE_EDGE,
            current_confidence=confidence_score,
            current_win_prob=win_prob,
            state_history=[{
                "state": LockedSignalState.ACTIVE_EDGE.value,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "reason": "Signal confirmed and locked"
            }]
        )
        
        # Save to database
        self.db[LOCKING_COLLECTIONS["locked_signals"]].insert_one(
            locked_record.to_dict()
        )
        
        # Log event
        await self._log_event(
            event_type="SIGNAL_LOCKED",
            game_id=game_id,
            market_key=market_key,
            locked_signal_id=locked_record.locked_signal_id,
            metadata={
                "original_signal_id": first_passing_run.signal_id,
                "edge_points": edge_points,
                "confidence_score": confidence_score,
                "confirmation_runs": len(window.runs)
            }
        )
        
        return locked_record
    
    # ========================================================================
    # LOCKED SIGNAL STATE UPDATES
    # ========================================================================
    
    async def _update_locked_signal_monitoring(
        self,
        locked_record: LockedSignalRecord,
        new_edge: float,
        new_win_prob: float,
        new_confidence: float
    ):
        """
        Update monitoring data on locked signal
        
        IMPORTANT: This does NOT change the locked values.
        It only updates current_confidence and current_win_prob for monitoring.
        """
        # Calculate if confidence weakened significantly
        confidence_drop = locked_record.confidence_score - new_confidence
        
        updates: Dict[str, Any] = {
            "current_confidence": new_confidence,
            "current_win_prob": new_win_prob
        }
        
        # Check if should transition to MONITORING or WEAKENED
        new_state = None
        
        if confidence_drop >= 0.15:  # 15% drop
            new_state = LockedSignalState.WEAKENED
        elif confidence_drop >= 0.05:  # 5% drop
            new_state = LockedSignalState.ACTIVE_MONITORING
        
        if new_state and locked_record.state == LockedSignalState.ACTIVE_EDGE:
            updates["state"] = new_state.value
            updates["$push"] = {
                "state_history": {
                    "state": new_state.value,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "reason": f"Confidence dropped by {confidence_drop*100:.1f}%",
                    "new_confidence": new_confidence,
                    "previous_confidence": locked_record.confidence_score
                }
            }
        
        # Update in database
        if "$push" in updates:
            push_update = updates.pop("$push")
            self.db[LOCKING_COLLECTIONS["locked_signals"]].update_one(
                {"locked_signal_id": locked_record.locked_signal_id},
                {"$set": updates, "$push": push_update}
            )
        else:
            self.db[LOCKING_COLLECTIONS["locked_signals"]].update_one(
                {"locked_signal_id": locked_record.locked_signal_id},
                {"$set": updates}
            )
    
    async def invalidate_signal(
        self,
        locked_signal_id: str,
        reason: InvalidationReason,
        explanation: str
    ) -> bool:
        """
        Explicitly invalidate a locked signal
        
        This is the ONLY way to remove a signal from active status.
        An explanation MUST be provided and will be posted to Telegram.
        """
        result = self.db[LOCKING_COLLECTIONS["locked_signals"]].update_one(
            {"locked_signal_id": locked_signal_id},
            {
                "$set": {
                    "state": LockedSignalState.INVALIDATED.value,
                    "invalidation_reason": reason.value,
                    "invalidation_explanation": explanation,
                    "invalidated_at": datetime.now(timezone.utc)
                },
                "$push": {
                    "state_history": {
                        "state": LockedSignalState.INVALIDATED.value,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "reason": reason.value,
                        "explanation": explanation
                    }
                }
            }
        )
        
        if result.modified_count > 0:
            await self._log_event(
                event_type="SIGNAL_INVALIDATED",
                game_id="",
                market_key="",
                locked_signal_id=locked_signal_id,
                metadata={
                    "reason": reason.value,
                    "explanation": explanation
                }
            )
            return True
        
        return False
    
    # ========================================================================
    # TELEGRAM INTEGRATION
    # ========================================================================
    
    async def get_signals_to_post(self) -> List[LockedSignalRecord]:
        """
        Get locked signals that need to be posted to Telegram
        
        Returns signals that are:
        - ACTIVE_EDGE state
        - Not yet posted to Telegram
        """
        cursor = self.db[LOCKING_COLLECTIONS["locked_signals"]].find({
            "state": LockedSignalState.ACTIVE_EDGE.value,
            "telegram_posted": False
        }).sort("locked_at", 1)
        
        signals = []
        for doc in list(cursor):
            signals.append(self._doc_to_locked_record(doc))
        
        return signals
    
    async def mark_as_posted(
        self,
        locked_signal_id: str,
        telegram_message_ids: Dict[str, str]
    ):
        """Mark signal as posted to Telegram"""
        self.db[LOCKING_COLLECTIONS["locked_signals"]].update_one(
            {"locked_signal_id": locked_signal_id},
            {
                "$set": {
                    "telegram_posted": True,
                    "telegram_message_ids": telegram_message_ids,
                    "telegram_posted_at": datetime.now(timezone.utc)
                }
            }
        )
    
    async def get_signals_needing_update(self) -> List[LockedSignalRecord]:
        """
        Get signals whose state changed and need Telegram update
        
        Returns signals that are:
        - Posted to Telegram
        - State changed to MONITORING, WEAKENED, or INVALIDATED
        """
        cursor = self.db[LOCKING_COLLECTIONS["locked_signals"]].find({
            "telegram_posted": True,
            "state": {"$in": [
                LockedSignalState.ACTIVE_MONITORING.value,
                LockedSignalState.WEAKENED.value,
                LockedSignalState.INVALIDATED.value
            ]}
        })
        
        signals = []
        for doc in list(cursor):
            signals.append(self._doc_to_locked_record(doc))
        
        return signals
    
    # ========================================================================
    # QUERY METHODS
    # ========================================================================
    
    async def get_locked_signal(
        self,
        locked_signal_id: str
    ) -> Optional[LockedSignalRecord]:
        """Get a locked signal by ID"""
        doc = self.db[LOCKING_COLLECTIONS["locked_signals"]].find_one({
            "locked_signal_id": locked_signal_id
        })
        
        if not doc:
            return None
        
        return self._doc_to_locked_record(doc)
    
    async def get_active_signals_for_game(
        self,
        game_id: str
    ) -> List[LockedSignalRecord]:
        """Get all active locked signals for a game"""
        cursor = self.db[LOCKING_COLLECTIONS["locked_signals"]].find({
            "game_id": game_id,
            "state": {"$in": [
                LockedSignalState.ACTIVE_EDGE.value,
                LockedSignalState.ACTIVE_MONITORING.value,
                LockedSignalState.WEAKENED.value
            ]}
        })
        
        signals = []
        for doc in list(cursor):
            signals.append(self._doc_to_locked_record(doc))
        
        return signals
    
    # ========================================================================
    # HELPERS
    # ========================================================================
    
    def _doc_to_locked_record(self, doc: Dict[str, Any]) -> LockedSignalRecord:
        """Convert MongoDB document to LockedSignalRecord"""
        return LockedSignalRecord(
            locked_signal_id=doc["locked_signal_id"],
            original_signal_id=doc["original_signal_id"],
            game_id=doc["game_id"],
            market_key=doc["market_key"],
            sport=doc["sport"],
            selection=doc["selection"],
            line_value=doc["line_value"],
            edge_points=doc["edge_points"],
            win_prob=doc["win_prob"],
            confidence_score=doc["confidence_score"],
            sim_count=doc["sim_count"],
            market_snapshot_id=doc["market_snapshot_id"],
            locked_at=doc["locked_at"],
            decision_timestamp=doc["decision_timestamp"],
            state=LockedSignalState(doc["state"]),
            current_confidence=doc.get("current_confidence"),
            current_win_prob=doc.get("current_win_prob"),
            telegram_posted=doc.get("telegram_posted", False),
            telegram_message_ids=doc.get("telegram_message_ids", {}),
            telegram_posted_at=doc.get("telegram_posted_at"),
            state_history=doc.get("state_history", []),
            invalidation_reason=InvalidationReason(doc["invalidation_reason"]) if doc.get("invalidation_reason") else None,
            invalidation_explanation=doc.get("invalidation_explanation"),
            invalidated_at=doc.get("invalidated_at"),
            settled_at=doc.get("settled_at"),
            outcome=doc.get("outcome")
        )
    
    async def _log_event(
        self,
        event_type: str,
        game_id: str,
        market_key: str,
        locked_signal_id: str,
        metadata: Optional[Dict] = None
    ):
        """Log locking event"""
        event = {
            "event_id": f"evt_{uuid.uuid4().hex[:12]}",
            "event_type": event_type,
            "game_id": game_id,
            "market_key": market_key,
            "locked_signal_id": locked_signal_id,
            "created_at": datetime.now(timezone.utc),
            "metadata": metadata or {}
        }
        
        self.db[LOCKING_COLLECTIONS["locking_events"]].insert_one(event)


# ============================================================================
# TELEGRAM MESSAGE FORMATTER (FOR LOCKED SIGNALS)
# ============================================================================

class LockedSignalFormatter:
    """
    Formats locked signals for Telegram posting
    
    Signal states produce different message formats:
    - ACTIVE_EDGE: Full signal with entry line
    - ACTIVE_MONITORING: "Still holding [selection], no add"
    - WEAKENED: "Signal weakened, reduce exposure"
    - INVALIDATED: Explicit retraction with reason
    """
    
    SPORT_EMOJI = {
        "basketball_nba": "🏀",
        "basketball_ncaab": "🏀",
        "football_nfl": "🏈",
        "football_ncaaf": "🏈",
        "hockey_nhl": "🏒",
        "baseball_mlb": "⚾",
        "soccer": "⚽"
    }
    
    def format_active_edge(self, signal: LockedSignalRecord) -> str:
        """Format ACTIVE_EDGE signal for initial post"""
        emoji = self.SPORT_EMOJI.get(signal.sport, "🎯")
        
        # Format edge
        edge_str = f"+{signal.edge_points:.1f}" if signal.edge_points > 0 else f"{signal.edge_points:.1f}"
        
        message = f"""
{emoji} **OFFICIAL EDGE DETECTED**

**{signal.selection}**
Line: {signal.line_value:+.1f}
Edge: {edge_str} pts
Confidence: {signal.confidence_score*100:.0f}%

📊 Model Win Prob: {signal.win_prob*100:.1f}%
🎰 Sims: {signal.sim_count:,}

⏱️ Decision Time: {signal.decision_timestamp.strftime('%I:%M %p ET')}

_Signal locked and verified. This is the official call._
"""
        return message.strip()
    
    def format_monitoring(self, signal: LockedSignalRecord) -> str:
        """Format ACTIVE_MONITORING update"""
        return f"""
⚠️ **SIGNAL UPDATE**

{signal.selection}
Status: MONITORING

Still holding position. Variance rising.
Current confidence: {(signal.current_confidence or signal.confidence_score)*100:.0f}%

_No additional entry recommended._
""".strip()
    
    def format_weakened(self, signal: LockedSignalRecord) -> str:
        """Format WEAKENED signal update"""
        return f"""
⚠️ **SIGNAL WEAKENED**

{signal.selection}
Status: REDUCED CONFIDENCE

Original confidence: {signal.confidence_score*100:.0f}%
Current confidence: {(signal.current_confidence or signal.confidence_score)*100:.0f}%

_Consider reducing exposure. Do not add._
""".strip()
    
    def format_invalidated(self, signal: LockedSignalRecord) -> str:
        """Format INVALIDATED signal notification"""
        reason_map = {
            InvalidationReason.INJURY_UPDATE: "Key injury update",
            InvalidationReason.LINEUP_CHANGE: "Significant lineup change",
            InvalidationReason.MARKET_SUSPENSION: "Market suspended",
            InvalidationReason.LINE_MOVED_MATERIALLY: "Line moved beyond threshold",
            InvalidationReason.GAME_POSTPONED: "Game postponed",
            InvalidationReason.DATA_INTEGRITY_FAILURE: "Data integrity issue",
            InvalidationReason.MANUAL_INVALIDATION: "Manual invalidation"
        }
        
        reason_text = "Unknown"
        if signal.invalidation_reason is not None:
            reason_text = reason_map.get(signal.invalidation_reason, "Unknown")
        
        return f"""
🚫 **SIGNAL INVALIDATED**

{signal.selection}
Status: VOIDED

Reason: {reason_text}
{signal.invalidation_explanation or ''}

_Original signal at {signal.decision_timestamp.strftime('%I:%M %p ET')} is no longer valid._
_Do not place this bet._
""".strip()
    
    def format_for_state(self, signal: LockedSignalRecord) -> str:
        """Format signal based on current state"""
        if signal.state == LockedSignalState.ACTIVE_EDGE:
            return self.format_active_edge(signal)
        elif signal.state == LockedSignalState.ACTIVE_MONITORING:
            return self.format_monitoring(signal)
        elif signal.state == LockedSignalState.WEAKENED:
            return self.format_weakened(signal)
        elif signal.state == LockedSignalState.INVALIDATED:
            return self.format_invalidated(signal)
        else:
            return ""
