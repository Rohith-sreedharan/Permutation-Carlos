"""
Signal Lifecycle Schemas - Immutable Architecture
Signals are append-only records. Re-simulations create NEW signals, never overwrite.
"""
from pydantic import BaseModel, Field
from typing import Optional, Literal, List, Dict, Any
from datetime import datetime
from enum import Enum


# ============================================================================
# ENUMS & REASON CODES
# ============================================================================

class SignalState(str, Enum):
    """Signal classification state"""
    PICK = "PICK"           # High-confidence actionable
    LEAN = "LEAN"           # Medium-confidence actionable
    NO_PLAY = "NO_PLAY"     # Failed gates, not actionable


class VolatilityBucket(str, Enum):
    """Volatility classification"""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class ConfidenceBand(str, Enum):
    """Confidence interval width"""
    NARROW = "NARROW"
    MEDIUM = "MEDIUM"
    WIDE = "WIDE"


class RobustnessLabel(str, Enum):
    """Signal robustness classification"""
    ROBUST = "ROBUST"       # Survives re-sim + line movement
    FRAGILE = "FRAGILE"     # Sensitive to changes


class SignalIntent(str, Enum):
    """Signal generation timing context"""
    PRE_MARKET = "PRE_MARKET"   # Early, before lines solidify
    OPEN = "OPEN"               # Market just opened
    MIDDAY = "MIDDAY"           # Mid-day evaluation
    LATE = "LATE"               # Close to game time
    LIVE = "LIVE"               # In-game (future)


class FinalStatus(str, Enum):
    """Terminal signal state"""
    SETTLED = "SETTLED"         # Game completed, graded
    EXPIRED = "EXPIRED"         # Market closed, no action
    INVALIDATED = "INVALIDATED" # Data issue, voided


class ReasonCode(str, Enum):
    """Machine-readable gate failure reasons"""
    # Data integrity
    ODDS_MISSING = "ODDS_MISSING"
    DATA_INCOMPLETE = "DATA_INCOMPLETE"
    STALE_DATA = "STALE_DATA"
    
    # Simulation power
    SIM_TOO_LOW = "SIM_TOO_LOW"
    CONVERGENCE_FAIL = "CONVERGENCE_FAIL"
    
    # Model validity
    MODEL_INVALID = "MODEL_INVALID"
    MODEL_STALE = "MODEL_STALE"
    
    # Volatility
    VOL_HIGH = "VOL_HIGH"
    VARIANCE_UNSTABLE = "VARIANCE_UNSTABLE"
    
    # Publish/RCL gates
    CONF_LOW = "CONF_LOW"
    EDGE_TOO_SMALL = "EDGE_TOO_SMALL"
    MARKET_ALIGNED = "MARKET_ALIGNED"
    
    # Line movement
    LINE_MOVED_AGAINST = "LINE_MOVED_AGAINST"
    LINE_STALE = "LINE_STALE"
    
    # Other
    GAME_STARTED = "GAME_STARTED"
    MARKET_SUSPENDED = "MARKET_SUSPENDED"


# ============================================================================
# GATE EVALUATION
# ============================================================================

class GateResult(BaseModel):
    """Single gate evaluation result"""
    pass_gate: bool = Field(..., description="Did this gate pass?")
    reasons: List[ReasonCode] = Field(default_factory=list, description="Failure reason codes")
    bucket: Optional[str] = Field(None, description="Optional categorization (e.g., volatility bucket)")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional context")


class GateEvaluation(BaseModel):
    """Complete gate evaluation for a signal"""
    data_integrity: GateResult
    sim_power: GateResult
    model_validity: GateResult
    volatility: GateResult
    publish_rcl: GateResult
    
    def all_passed(self) -> bool:
        """Check if all gates passed"""
        return all([
            self.data_integrity.pass_gate,
            self.sim_power.pass_gate,
            self.model_validity.pass_gate,
            self.volatility.pass_gate,
            self.publish_rcl.pass_gate
        ])
    
    def get_all_reasons(self) -> List[ReasonCode]:
        """Get all failure reasons"""
        reasons = []
        for gate in [self.data_integrity, self.sim_power, self.model_validity, 
                     self.volatility, self.publish_rcl]:
            reasons.extend(gate.reasons)
        return reasons


# ============================================================================
# CORE SCHEMAS
# ============================================================================

class MarketSnapshot(BaseModel):
    """Immutable market state at signal creation time"""
    market_snapshot_id: str = Field(..., description="UUID for this snapshot")
    game_id: str
    captured_at: datetime
    source: str = Field(default="odds_api", description="Data source")
    
    # Line data
    spread_line: Optional[float] = None
    spread_home_price: Optional[int] = None
    spread_away_price: Optional[int] = None
    
    total_line: Optional[float] = None
    total_over_price: Optional[int] = None
    total_under_price: Optional[int] = None
    
    ml_home_price: Optional[int] = None
    ml_away_price: Optional[int] = None
    
    # Book-specific prices (optional)
    book_prices: Dict[str, Any] = Field(default_factory=dict)
    
    # Integrity
    snapshot_hash: str = Field(..., description="Hash of snapshot data for verification")


class SimulationRun(BaseModel):
    """Record of a single simulation execution"""
    sim_run_id: str = Field(..., description="UUID for this sim run")
    game_id: str
    model_version: str = Field(..., description="Model version identifier")
    inputs_version: str = Field(..., description="Input data hash/version")
    seed: int = Field(..., description="Random seed for reproducibility")
    num_sims: int = Field(..., description="Number of Monte Carlo iterations")
    
    # Distribution summaries
    distribution: Dict[str, float] = Field(
        default_factory=dict,
        description="Statistical summaries: mean, median, p05, p95, std_dev"
    )
    
    created_at: datetime
    execution_time_ms: Optional[int] = None


class Signal(BaseModel):
    """
    IMMUTABLE signal record
    Re-simulations create NEW signals, never overwrite existing ones
    """
    # Identity
    signal_id: str = Field(..., description="UUID for this signal")
    game_id: str
    sport: str
    market_key: Literal["SPREAD", "TOTAL", "ML", "PROP"] = Field(..., description="Market type")
    selection: str = Field(..., description="e.g., 'Bulls +6.5', 'Under 240.5'")
    book_key: str = Field(default="CONSENSUS", description="Bookmaker or CONSENSUS")
    
    # Market context (frozen at signal creation)
    line_value: float = Field(..., description="Market line (e.g., -6.5, 240.5)")
    odds_price: Optional[int] = Field(None, description="American odds (e.g., -110)")
    market_snapshot_id: str = Field(..., description="Reference to frozen market state")
    
    # Model context
    model_version: str
    sim_run_id: str = Field(..., description="Reference to simulation that generated this")
    created_at: datetime
    
    # Intent & timing
    intent: SignalIntent = Field(..., description="Why was this signal generated?")
    
    # Computed fields
    edge_points: float = Field(..., description="Model edge in points (consistent sign convention)")
    win_prob: float = Field(..., ge=0, le=1, description="Model win probability")
    ev: Optional[float] = Field(None, description="Expected value if computed")
    
    # Volatility & confidence
    volatility_score: float = Field(..., description="Numerical volatility measure")
    volatility_bucket: VolatilityBucket
    confidence_band: ConfidenceBand
    
    # State classification
    state: SignalState
    gates: GateEvaluation = Field(..., description="Gate evaluation results")
    reason_codes: List[ReasonCode] = Field(default_factory=list, description="All reason codes")
    explain_summary: str = Field(..., description="1-2 sentence human-readable explanation")
    
    # Robustness (computed from history)
    robustness_label: Optional[RobustnessLabel] = None
    robustness_score: Optional[int] = Field(None, ge=0, le=100, description="0-100 stability score")
    
    # Lifecycle
    final_status: Optional[FinalStatus] = None
    settled_at: Optional[datetime] = None
    outcome: Optional[Literal["WIN", "LOSS", "PUSH", "VOID"]] = None
    actual_result: Optional[float] = None


class LockedSignal(BaseModel):
    """
    Action freeze: prevents signal churn near execution
    Once locked, re-sims are suppressed unless material market move
    """
    locked_signal_id: str = Field(..., description="UUID for lock record")
    signal_id: str = Field(..., description="Reference to the locked signal")
    game_id: str
    market_key: str
    
    lock_type: Literal["AUTO", "MANUAL"] = Field(default="AUTO")
    locked_at: datetime
    lock_expiry: Optional[datetime] = Field(None, description="Auto-unlock time (e.g., game start)")
    lock_reason: str = Field(default="ACTIONABLE_FIRST_HIT")
    
    # Action freeze window config
    freeze_duration_minutes: int = Field(default=60, description="Cooldown before next re-sim allowed")
    material_move_threshold: Dict[str, float] = Field(
        default_factory=lambda: {
            "spread_points": 1.0,
            "total_points": 2.0,
            "odds_cents": 15
        },
        description="Thresholds to break freeze"
    )
    
    unlocked_at: Optional[datetime] = None
    unlock_reason: Optional[str] = None


class SignalDelta(BaseModel):
    """
    Tracks what changed between signals
    Critical for "What changed?" UI panel
    """
    delta_id: str = Field(..., description="UUID for this delta record")
    from_signal_id: str
    to_signal_id: str
    game_id: str
    market_key: str
    computed_at: datetime
    
    # Numerical deltas
    delta_edge_points: float
    delta_win_prob: float
    delta_volatility_score: float
    
    # State changes
    state_changed: bool
    previous_state: SignalState
    new_state: SignalState
    
    # Bucket changes
    volatility_bucket_changed: bool
    previous_volatility: Optional[VolatilityBucket] = None
    new_volatility: Optional[VolatilityBucket] = None
    
    # Gate changes
    gate_changes: List[str] = Field(default_factory=list, description="Which gates flipped")
    
    # Market movement
    line_moved: bool
    line_move_points: Optional[float] = None
    
    # Summary
    change_summary: str = Field(..., description="Human-readable delta explanation")


# ============================================================================
# COLLECTION NAMES
# ============================================================================

SIGNAL_COLLECTIONS = {
    "signals": "signals",
    "market_snapshots": "market_snapshots",
    "simulation_runs": "simulation_runs",
    "locked_signals": "locked_signals",
    "signal_deltas": "signal_deltas",
    "signal_events": "signal_events"  # For logging
}
