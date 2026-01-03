"""
Signal Lifecycle & Locking System

Implements immutable signal architecture to prevent re-simulation confusion.

Three-Wave Architecture:
- Wave 1 (T-6h): Discovery - internal only
- Wave 2 (T-120min): Validation - stability check  
- Wave 3 (T-60min): Publish gate - final decision

Critical Rules:
1. Signals are immutable once published
2. Entry snapshots capture price at decision time
3. Market snapshots preserve context
4. Action freeze windows prevent re-sim spam
5. Append-only audit trail
"""
from datetime import datetime, timedelta
from typing import Dict, Optional, List, Tuple
from dataclasses import dataclass, field
from enum import Enum


class SignalWave(Enum):
    """Three-wave simulation lifecycle"""
    WAVE_1_DISCOVERY = "WAVE_1_DISCOVERY"  # T-6h, internal only
    WAVE_2_VALIDATION = "WAVE_2_VALIDATION"  # T-120min, stability check
    WAVE_3_PUBLISH = "WAVE_3_PUBLISH"  # T-60min, publish decision


class SignalStatus(Enum):
    """Signal lifecycle states"""
    DISCOVERED = "DISCOVERED"  # Wave 1 complete
    VALIDATING = "VALIDATING"  # Wave 2 in progress
    VALIDATED = "VALIDATED"  # Wave 2 passed stability
    UNSTABLE = "UNSTABLE"  # Wave 2 failed stability
    PUBLISHED = "PUBLISHED"  # Wave 3 published to users
    WITHDRAWN = "WITHDRAWN"  # Withdrawn before publish
    LOCKED = "LOCKED"  # Game started, immutable
    GRADED = "GRADED"  # Final result recorded


class SignalIntent(Enum):
    """Signal intent tags for filtering"""
    TRUTH_MODE = "TRUTH_MODE"  # Sharp Pass users (strict)
    PARLAY_MODE = "PARLAY_MODE"  # Parlay Builder (penalties, not blocks)
    B2B_SIMSPORTS = "B2B_SIMSPORTS"  # SimSports Terminal


@dataclass
class MarketSnapshot:
    """Immutable snapshot of market at decision time"""
    timestamp: datetime
    wave: SignalWave
    
    # Market prices
    team_a_spread: float
    team_a_spread_odds: int
    team_b_spread: float
    team_b_spread_odds: int
    over_line: float
    over_odds: int
    under_line: float
    under_odds: int
    team_a_ml_odds: Optional[int] = None
    team_b_ml_odds: Optional[int] = None
    
    # Sportsbook source
    sportsbook: str = "DraftKings"
    
    # Delta from previous snapshot
    spread_delta: Optional[float] = None
    total_delta: Optional[float] = None


@dataclass
class EntrySnapshot:
    """Entry price snapshot - the edge is the price we captured"""
    sharp_side: str
    market_type: str  # SPREAD, TOTAL, MONEYLINE
    entry_spread: Optional[float] = None
    entry_odds: int = -110
    entry_total: Optional[float] = None
    max_acceptable_spread: Optional[float] = None  # Worst spread still acceptable
    max_acceptable_total: Optional[float] = None  # Worst total still acceptable
    max_acceptable_odds: Optional[int] = None  # Worst odds still acceptable
    
    # Context
    captured_at: datetime = field(default_factory=datetime.now)
    captured_wave: SignalWave = SignalWave.WAVE_3_PUBLISH


@dataclass
class SimulationRun:
    """Single simulation run metadata"""
    sim_run_id: str
    wave: SignalWave
    timestamp: datetime
    
    # Simulation parameters
    num_simulations: int
    model_version: str
    sport: str
    
    # Results
    edge_state: str  # EDGE, LEAN, NO_PLAY
    compressed_edge: float
    raw_edge: float
    volatility: str
    distribution_flag: str
    
    # Market evaluation
    sharp_side: Optional[str] = None
    favored_team: Optional[str] = None
    points_side: Optional[str] = None
    
    # Full result data (JSON)
    result_data: Optional[Dict] = None


@dataclass
class Signal:
    """Immutable signal record"""
    signal_id: str
    game_id: str
    sport: str
    
    # Teams
    team_a: str
    team_b: str
    game_time: datetime
    
    # Market type
    market_type: Optional[str] = None  # SPREAD, TOTAL, MONEYLINE
    
    # Edge data
    edge_state: Optional[str] = None  # EDGE, LEAN, NO_PLAY
    compressed_edge: Optional[float] = None
    sharp_side: Optional[str] = None
    
    # Signal metadata
    status: SignalStatus = SignalStatus.DISCOVERED
    intent: SignalIntent = SignalIntent.TRUTH_MODE
    created_at: datetime = field(default_factory=datetime.now)
    published_at: Optional[datetime] = None
    locked_at: Optional[datetime] = None
    
    # Simulation runs (append-only)
    simulation_runs: List[SimulationRun] = field(default_factory=list)
    
    # Market snapshots (append-only)
    market_snapshots: List[MarketSnapshot] = field(default_factory=list)
    
    # Entry snapshot (set at publish, immutable)
    entry_snapshot: Optional[EntrySnapshot] = None
    
    # Final result
    final_score_team_a: Optional[int] = None
    final_score_team_b: Optional[int] = None
    result: Optional[str] = None  # WIN, LOSS, PUSH
    graded_at: Optional[datetime] = None
    
    # Action freeze (prevent re-sim spam)
    freeze_until: Optional[datetime] = None
    freeze_reason: Optional[str] = None


def create_signal(
    game_id: str,
    sport: str,
    team_a: str,
    team_b: str,
    game_time: datetime,
    intent: SignalIntent = SignalIntent.TRUTH_MODE
) -> Signal:
    """
    Create new signal for a game
    
    Args:
        game_id: Unique game identifier
        sport: Sport (MLB, NFL, etc.)
        team_a: Team A name
        team_b: Team B name
        game_time: Scheduled game start time
        intent: Signal intent (TRUTH_MODE, PARLAY_MODE, etc.)
    
    Returns: Signal object
    """
    signal_id = f"{game_id}_{intent.value}_{int(datetime.now().timestamp())}"
    
    return Signal(
        signal_id=signal_id,
        game_id=game_id,
        sport=sport,
        team_a=team_a,
        team_b=team_b,
        game_time=game_time,
        intent=intent
    )


def add_simulation_run(
    signal: Signal,
    sim_run: SimulationRun
) -> Signal:
    """
    Append simulation run to signal (immutable append)
    
    Args:
        signal: Signal object
        sim_run: Simulation run to append
    
    Returns: Updated signal
    """
    signal.simulation_runs.append(sim_run)
    return signal


def add_market_snapshot(
    signal: Signal,
    snapshot: MarketSnapshot
) -> Signal:
    """
    Append market snapshot to signal (immutable append)
    
    Calculates delta from previous snapshot
    
    Args:
        signal: Signal object
        snapshot: Market snapshot to append
    
    Returns: Updated signal
    """
    # Calculate delta from previous snapshot
    if signal.market_snapshots:
        prev = signal.market_snapshots[-1]
        snapshot.spread_delta = snapshot.team_a_spread - prev.team_a_spread
        snapshot.total_delta = snapshot.over_line - prev.over_line
    
    signal.market_snapshots.append(snapshot)
    return signal


def lock_signal_with_entry(
    signal: Signal,
    entry_snapshot: EntrySnapshot
) -> Signal:
    """
    Lock signal with entry snapshot (publish decision)
    
    This is the critical step where we capture the edge
    
    Args:
        signal: Signal object
        entry_snapshot: Entry price snapshot
    
    Returns: Updated signal
    """
    signal.entry_snapshot = entry_snapshot
    signal.published_at = datetime.now()
    signal.status = SignalStatus.PUBLISHED
    
    return signal


def freeze_signal(
    signal: Signal,
    freeze_duration_minutes: int,
    reason: str
) -> Signal:
    """
    Freeze signal to prevent re-simulation spam
    
    Args:
        signal: Signal object
        freeze_duration_minutes: How long to freeze
        reason: Why freezing
    
    Returns: Updated signal
    """
    signal.freeze_until = datetime.now() + timedelta(minutes=freeze_duration_minutes)
    signal.freeze_reason = reason
    
    return signal


def is_frozen(signal: Signal) -> bool:
    """Check if signal is frozen"""
    if signal.freeze_until is None:
        return False
    
    return datetime.now() < signal.freeze_until


def lock_signal_at_game_start(signal: Signal) -> Signal:
    """
    Lock signal when game starts (immutable from this point)
    
    Args:
        signal: Signal object
    
    Returns: Updated signal
    """
    signal.locked_at = datetime.now()
    signal.status = SignalStatus.LOCKED
    
    return signal


def grade_signal(
    signal: Signal,
    final_score_team_a: int,
    final_score_team_b: int,
    result: str
) -> Signal:
    """
    Grade signal with final result
    
    Args:
        signal: Signal object
        final_score_team_a: Team A final score
        final_score_team_b: Team B final score
        result: WIN, LOSS, or PUSH
    
    Returns: Updated signal
    """
    signal.final_score_team_a = final_score_team_a
    signal.final_score_team_b = final_score_team_b
    signal.result = result
    signal.graded_at = datetime.now()
    signal.status = SignalStatus.GRADED
    
    return signal


def calculate_wave_timing(game_time: datetime) -> Dict[str, datetime]:
    """
    Calculate wave execution times
    
    Args:
        game_time: Scheduled game start time
    
    Returns: Dictionary with wave timings
    """
    return {
        "wave_1_start": game_time - timedelta(hours=6),
        "wave_2_start": game_time - timedelta(minutes=120),
        "wave_3_start": game_time - timedelta(minutes=60),
        "lock_time": game_time
    }


def check_stability_wave1_to_wave2(
    wave1_run: SimulationRun,
    wave2_run: SimulationRun,
    max_edge_drift: float = 1.5
) -> Tuple[bool, Optional[str]]:
    """
    Check if edge remained stable from Wave 1 to Wave 2
    
    Args:
        wave1_run: Wave 1 simulation run
        wave2_run: Wave 2 simulation run
        max_edge_drift: Maximum allowed edge drift (percentage points)
    
    Returns: (is_stable, reason)
    """
    edge_drift = abs(wave2_run.compressed_edge - wave1_run.compressed_edge)
    
    if edge_drift > max_edge_drift:
        return False, f"EDGE_DRIFT_{edge_drift:.1f}%"
    
    # Check if edge state changed
    if wave1_run.edge_state != wave2_run.edge_state:
        return False, f"EDGE_STATE_CHANGED_{wave1_run.edge_state}_TO_{wave2_run.edge_state}"
    
    # Check if sharp side flipped
    if wave1_run.sharp_side != wave2_run.sharp_side:
        return False, f"SHARP_SIDE_FLIPPED_{wave1_run.sharp_side}_TO_{wave2_run.sharp_side}"
    
    return True, None


def should_publish_wave3(
    signal: Signal,
    wave3_run: SimulationRun,
    min_edge_for_publish: float = 3.0
) -> Tuple[bool, Optional[str]]:
    """
    Decide if signal should be published after Wave 3
    
    Args:
        signal: Signal object
        wave3_run: Wave 3 simulation run
        min_edge_for_publish: Minimum edge to publish
    
    Returns: (should_publish, reason)
    """
    # Must have EDGE or LEAN state
    if wave3_run.edge_state == "NO_PLAY":
        return False, "EDGE_STATE_NO_PLAY"
    
    # Must meet minimum edge threshold
    if wave3_run.compressed_edge < min_edge_for_publish:
        return False, f"EDGE_BELOW_MINIMUM_{wave3_run.compressed_edge:.1f}%"
    
    # Check distribution flag
    if wave3_run.distribution_flag == "UNSTABLE_EXTREME":
        return False, "DISTRIBUTION_UNSTABLE_EXTREME"
    
    # Verify sharp side is set
    if not wave3_run.sharp_side:
        return False, "SHARP_SIDE_NOT_SET"
    
    return True, None


# Example usage:
"""
# Create signal
signal = create_signal(
    game_id="NBA_20250315_LAL_BOS",
    sport="NBA",
    team_a="Los Angeles Lakers",
    team_b="Boston Celtics",
    game_time=datetime(2025, 3, 15, 19, 30),
    intent=SignalIntent.TRUTH_MODE
)

# Wave 1: Discovery (T-6h)
wave1_snapshot = MarketSnapshot(
    timestamp=datetime.now(),
    wave=SignalWave.WAVE_1_DISCOVERY,
    team_a_spread=-3.5,
    team_a_spread_odds=-110,
    team_b_spread=+3.5,
    team_b_spread_odds=-110,
    over_line=220.5,
    over_odds=-110,
    under_line=220.5,
    under_odds=-110
)

signal = add_market_snapshot(signal, wave1_snapshot)

wave1_run = SimulationRun(
    sim_run_id="wave1_123",
    wave=SignalWave.WAVE_1_DISCOVERY,
    timestamp=datetime.now(),
    num_simulations=50000,
    model_version="v2.1",
    sport="NBA",
    edge_state="EDGE",
    compressed_edge=4.8,
    raw_edge=5.7,
    volatility="MEDIUM",
    distribution_flag="STABLE",
    sharp_side="Boston Celtics",
    favored_team="Boston Celtics",
    points_side="UNDERDOG"
)

signal = add_simulation_run(signal, wave1_run)

# Wave 2: Validation (T-120min)
# ... similar process

# Wave 3: Publish (T-60min)
entry = EntrySnapshot(
    sharp_side="Boston Celtics",
    market_type="SPREAD",
    entry_spread=+3.5,
    entry_odds=-110,
    max_acceptable_spread=+3.0,  # Can move to +3.0 before NO_PLAY
    captured_wave=SignalWave.WAVE_3_PUBLISH
)

signal = lock_signal_with_entry(signal, entry)

# Game starts
signal = lock_signal_at_game_start(signal)

# Grade result
signal = grade_signal(signal, 112, 108, "WIN")  # Celtics won
"""
