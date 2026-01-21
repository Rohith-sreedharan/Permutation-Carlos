"""
Logging & Calibration System - Database Schemas
================================================
Implements the canonical data model for exit-grade prediction tracking,
grading, and calibration as specified in the dev brief.

Core Principles:
1. Append-only truth: never overwrite historical inputs/outputs
2. Exact lineage: every published prediction references exact snapshots + versions
3. One source of truth: only published records count for grading
4. Grade everything: all published records settle into win/loss/push/void with CLV
5. Calibration is versioned and gated: no silent changes

Collections:
- events: canonical game records
- odds_snapshots: immutable market snapshots (raw + normalized)
- injury_snapshots: injury report captures
- sim_runs: immutable simulation execution records
- sim_run_inputs: lineage tracking (joins snapshots to sim_runs)
- predictions: what the engine believed at that run
- published_predictions: official predictions (THE ONLY ONES THAT COUNT)
- event_results: final game outcomes
- grading: settlement + scoring metrics
- calibration_versions: versioned calibration models
- calibration_segments: calibration by cohort
- performance_rollups: materialized performance metrics
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any, Literal
from datetime import datetime, timezone
from enum import Enum


# ============================================================================
# CANONICAL IDENTIFIERS
# ============================================================================

class MarketKey(str, Enum):
    """Canonical market definitions (your system controls these)"""
    # Full game markets
    SPREAD_FULL_GAME = "SPREAD:FULL_GAME"
    TOTAL_FULL_GAME = "TOTAL:FULL_GAME"
    MONEYLINE_FULL_GAME = "MONEYLINE:FULL_GAME"
    
    # Half markets
    SPREAD_1H = "SPREAD:1H"
    TOTAL_1H = "TOTAL:1H"
    MONEYLINE_1H = "MONEYLINE:1H"
    
    # Quarter markets
    SPREAD_1Q = "SPREAD:1Q"
    TOTAL_1Q = "TOTAL:1Q"
    
    # Props (format: PROP:player_id:stat:side)
    # Example: PROP:lebron_james:PTS:OVER


class BetStatus(str, Enum):
    """Bet settlement status"""
    PENDING = "PENDING"
    SETTLED = "SETTLED"
    VOID = "VOID"
    NO_ACTION = "NO_ACTION"


class ResultCode(str, Enum):
    """Final result classification"""
    WIN = "WIN"
    LOSS = "LOSS"
    PUSH = "PUSH"
    VOID = "VOID"


class EventStatus(str, Enum):
    """Event completion status"""
    SCHEDULED = "SCHEDULED"
    IN_PROGRESS = "IN_PROGRESS"
    FINAL = "FINAL"
    POSTPONED = "POSTPONED"
    CANCELLED = "CANCELLED"
    SUSPENDED = "SUSPENDED"


class RecommendationState(str, Enum):
    """State produced by simulation output (Trust Loop v1)"""
    OFFICIAL_EDGE = "OFFICIAL_EDGE"  # Only this can be published as official
    MODEL_LEAN = "MODEL_LEAN"  # Informational only
    WAIT_LIVE = "WAIT_LIVE"  # Informational only
    NO_PLAY = "NO_PLAY"  # Informational only


class PublishType(str, Enum):
    """Publish type (Trust Loop v1)"""
    OFFICIAL_EDGE = "OFFICIAL_EDGE"  # Counts in official record
    INFORMATIONAL = "INFORMATIONAL"  # Lean/wait/no-play content


class Visibility(str, Enum):
    """Prediction visibility level"""
    FREE = "FREE"
    PREMIUM = "PREMIUM"
    TRUTH = "TRUTH"
    INTERNAL = "INTERNAL"


class Channel(str, Enum):
    """Publishing channel"""
    TELEGRAM = "TELEGRAM"
    APP = "APP"
    WEB = "WEB"
    INTERNAL = "INTERNAL"


class CalibrationStatus(str, Enum):
    """Calibration version activation status"""
    CANDIDATE = "CANDIDATE"
    ACTIVE = "ACTIVE"
    REJECTED = "REJECTED"


# ============================================================================
# EVENTS
# ============================================================================

class Event(BaseModel):
    """
    Canonical game/event record
    event_id is stable identifier (e.g., nba_lakers_spurs_2026_01_11)
    """
    event_id: str = Field(..., description="Stable canonical event identifier")
    league: str = Field(..., description="NBA, NFL, MLB, NHL, NCAAF, NCAAB")
    season: str = Field(..., description="2025-2026, 2026, etc.")
    start_time_utc: datetime
    home_team: str
    away_team: str
    venue: Optional[str] = None
    status: EventStatus = EventStatus.SCHEDULED
    
    # Metadata
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


# ============================================================================
# ODDS SNAPSHOTS
# ============================================================================

class OddsSnapshot(BaseModel):
    """
    Immutable market state capture
    Purpose: reproduce market state and compute CLV correctly
    """
    snapshot_id: str = Field(..., description="UUID for this snapshot")
    event_id: str
    timestamp_utc: datetime
    
    # Provider/book identity
    provider: str = Field(..., description="OddsAPI, etc.")
    book: str = Field(..., description="DK, FD, MGM, etc.")
    raw_market_id: Optional[str] = Field(None, description="Provider's market id")
    raw_selection_id: Optional[str] = Field(None, description="Provider's selection id")
    
    # Canonical market
    market_key: str = Field(..., description="Your canonical market key")
    selection: str = Field(..., description="HOME/AWAY/OVER/UNDER or player side")
    
    # Line and price
    line: Optional[float] = Field(None, description="Spread/total line (decimal)")
    price_american: Optional[int] = Field(None, description="American odds")
    price_decimal: Optional[float] = Field(None, description="Decimal odds")
    
    # Context
    is_live: bool = False
    period: str = Field(default="FG", description="FG/1H/1Q etc.")
    is_close_candidate: bool = Field(False, description="Is this a closing line?")
    
    # Integrity
    raw_payload: Dict[str, Any] = Field(default_factory=dict, description="Store to survive provider schema changes")
    integrity_flags: Dict[str, Any] = Field(default_factory=dict, description="stale, missing, outlier, etc.")
    
    class Config:
        json_schema_extra = {
            "indexes": [
                {"keys": [("event_id", 1), ("market_key", 1), ("book", 1), ("timestamp_utc", -1)]},
                {"keys": [("event_id", 1), ("timestamp_utc", -1)]},
                {"keys": [("snapshot_id", 1)], "unique": True},
                {"keys": [("is_close_candidate", 1)]},
            ]
        }


# ============================================================================
# INJURY SNAPSHOTS
# ============================================================================

class InjurySnapshot(BaseModel):
    """
    Immutable injury report capture
    """
    injury_snapshot_id: str = Field(..., description="UUID")
    timestamp_utc: datetime
    league: str
    team: str
    
    # Derived impact metrics
    net_impact_pts: Optional[float] = None
    off_delta: Optional[float] = None
    def_delta: Optional[float] = None
    pace_delta: Optional[float] = None
    
    # Raw data
    raw_payload: Dict[str, Any] = Field(default_factory=dict, description="Raw injury data")
    
    class Config:
        json_schema_extra = {
            "indexes": [
                {"keys": [("injury_snapshot_id", 1)], "unique": True},
                {"keys": [("league", 1), ("team", 1), ("timestamp_utc", -1)]},
            ]
        }


# ============================================================================
# SIM RUNS
# ============================================================================

class SimRun(BaseModel):
    """
    Immutable record that a simulation occurred
    Purpose: guarantee exact lineage
    """
    sim_run_id: str = Field(..., description="UUID")
    event_id: str
    created_at_utc: datetime = Field(default_factory=datetime.utcnow)
    
    # Trigger context
    trigger: Literal["auto_internal", "user_click", "scheduled"]
    
    # Versioning (critical for reproducibility)
    engine_version: str = Field(..., description="Git hash or version tag")
    model_version: str = Field(..., description="Weights/config id")
    feature_set_version: str = Field(..., description="Feature engineering version")
    decision_policy_version: str = Field(..., description="Decision policy version")
    calibration_version_applied: Optional[str] = None
    
    # Simulation config
    sim_count: int = Field(..., description="100K public, 1M internal")
    seed_policy: Literal["fixed", "rolled"]
    seed_value: Optional[int] = None
    
    # Status
    status: Literal["SUCCESS", "FAILED", "TIMEOUT"] = "SUCCESS"
    error_code: Optional[str] = None
    runtime_ms: Optional[int] = None
    
    class Config:
        json_schema_extra = {
            "indexes": [
                {"keys": [("sim_run_id", 1)], "unique": True},
                {"keys": [("event_id", 1), ("created_at_utc", -1)]},
                {"keys": [("trigger", 1)]},
                {"keys": [("calibration_version_applied", 1)]},
            ]
        }


# ============================================================================
# SIM RUN INPUTS (lineage join table)
# ============================================================================

class SimRunInput(BaseModel):
    """
    Links sim_run to exact snapshots used
    Purpose: exact lineage tracking
    """
    sim_run_id: str
    
    # Snapshot references
    snapshot_id: Optional[str] = Field(None, description="Odds snapshot used")
    injury_snapshot_id_home: Optional[str] = None
    injury_snapshot_id_away: Optional[str] = None
    weather_snapshot_id: Optional[str] = None
    
    class Config:
        json_schema_extra = {
            "indexes": [
                {"keys": [("sim_run_id", 1)]},
                {"keys": [("snapshot_id", 1)]},
            ]
        }


# ============================================================================
# PREDICTIONS
# ============================================================================

class Prediction(BaseModel):
    """
    What the engine believed at that sim run
    NOT public until published
    """
    prediction_id: str = Field(..., description="UUID")
    sim_run_id: str
    event_id: str
    market_key: str
    selection: str = Field(..., description="HOME/AWAY/OVER/UNDER")
    
    # Snapshot used for this prediction
    market_snapshot_id_used: str = Field(..., description="FK to odds_snapshots")
    
    # Model output
    model_line: Optional[float] = None
    p_raw: Optional[float] = Field(None, description="0-1 probability before calibration")
    p_calibrated: Optional[float] = Field(None, description="0-1 probability after calibration")
    p_win: Optional[float] = None
    p_cover: Optional[float] = None
    p_over: Optional[float] = None
    ev_units: Optional[float] = Field(None, description="EV vs snapshot's line+price")
    edge_points: Optional[float] = None
    
    # Uncertainty
    uncertainty: Optional[float] = Field(None, description="Std dev / CI width")
    distribution_summary: Dict[str, Any] = Field(default_factory=dict, description="mean, p10/p50/p90")
    
    # Gates
    rcl_gate_pass: bool = False
    
    # Decision (Trust Loop v1: OFFICIAL_EDGE, MODEL_LEAN, WAIT_LIVE, NO_PLAY)
    recommendation_state: Literal["OFFICIAL_EDGE", "MODEL_LEAN", "WAIT_LIVE", "NO_PLAY", "EDGE", "PICK", "LEAN"]
    tier: Optional[str] = None  # EDGE/PICK/LEAN for backwards compatibility
    confidence_index: Optional[float] = None
    variance_bucket: Optional[str] = Field(None, description="LOW/MEDIUM/HIGH")
    
    class Config:
        json_schema_extra = {
            "indexes": [
                {"keys": [("prediction_id", 1)], "unique": True},
                {"keys": [("sim_run_id", 1)]},
                {"keys": [("event_id", 1)]},
                {"keys": [("market_snapshot_id_used", 1)]},
                {"keys": [("recommendation_state", 1)]},
            ]
        }


# ============================================================================
# PUBLISHED PREDICTIONS (the only record that "counts" publicly)
# ============================================================================

class PublishedPrediction(BaseModel):
    """
    Official predictions published to users (Trust Loop v1)
    THE ONLY RECORDS THAT COUNT FOR OFFICIAL TRACK RECORD
    
    Locked fields are immutable - corrections are additive (new publish), not updates
    Only publish_type=OFFICIAL_EDGE with is_official=true count in official track record
    """
    publish_id: str = Field(..., description="UUID")
    prediction_id: str = Field(..., description="FK to predictions")
    event_id: str
    published_at_utc: datetime = Field(default_factory=datetime.utcnow)
    
    # Distribution channel
    channel: Channel
    
    # Trust Loop v1: publish_type determines if this counts in official record
    publish_type: PublishType = Field(default=PublishType.OFFICIAL_EDGE)
    is_official: bool = Field(True, description="True only for OFFICIAL_EDGE publishes")
    
    # LOCKED SNAPSHOT FIELDS (immutable per Trust Loop v1)
    locked_market_snapshot_id: str = Field(..., description="Snapshot at publish time")
    locked_injury_snapshot_ids: List[str] = Field(default_factory=list)
    locked_line_at_publish: Optional[float] = None
    locked_price_at_publish: Optional[int] = None  # American odds
    
    # LOCKED MODEL FIELDS (immutable per Trust Loop v1)
    locked_engine_version: str = Field(..., description="Git hash")
    locked_model_version: str = Field(..., description="Model version")
    locked_calibration_version: Optional[str] = None
    locked_decision_policy_version: str = Field(..., description="Decision policy version")
    
    # LOCKED PREDICTION FIELDS (immutable per Trust Loop v1)
    locked_p_calibrated: Optional[float] = Field(None, description="Calibrated probability 0-1")
    locked_edge_points: Optional[float] = None
    locked_variance_bucket: Optional[str] = None
    locked_market_key: str = Field(..., description="Market type")
    locked_selection: str = Field(..., description="HOME/AWAY/OVER/UNDER")
    
    # Optional metadata
    visibility: Optional[Visibility] = None  # For access control (separate from publish_type)
    copy_template_id: Optional[str] = None
    decision_reason_codes: List[str] = Field(default_factory=list, description="Machine-readable reasons")
    ticket_terms: Dict[str, Any] = Field(
        default_factory=dict,
        description="line, price, book if stated"
    )
    
    class Config:
        json_schema_extra = {
            "indexes": [
                {"keys": [("publish_id", 1)], "unique": True},
                {"keys": [("prediction_id", 1)]},
                {"keys": [("event_id", 1)]},
                {"keys": [("published_at_utc", -1)]},
                {"keys": [("is_official", 1), ("publish_type", 1)]},  # Trust Loop queries
                {"keys": [("visibility", 1), ("published_at_utc", -1)]},
                {"keys": [("channel", 1)]},
            ]
        }


# ============================================================================
# EVENT RESULTS
# ============================================================================

class EventResult(BaseModel):
    """
    Final game outcomes
    """
    event_id: str
    
    # Scores
    home_score: Optional[int] = None
    away_score: Optional[int] = None
    total_score: Optional[int] = None
    margin: Optional[float] = None
    
    # Additional periods
    home_score_1h: Optional[int] = None
    away_score_1h: Optional[int] = None
    home_score_1q: Optional[int] = None
    away_score_1q: Optional[int] = None
    
    # Status
    status: EventStatus = EventStatus.FINAL
    official_source: str = Field(..., description="ESPN, OddsAPI, etc.")
    official_timestamp: datetime
    
    class Config:
        json_schema_extra = {
            "indexes": [
                {"keys": [("event_id", 1)], "unique": True},
                {"keys": [("status", 1)]},
                {"keys": [("official_timestamp", -1)]},
            ]
        }


# ============================================================================
# GRADING
# ============================================================================

class Grading(BaseModel):
    """
    Settlement + scoring metrics (Trust Loop v1)
    Purpose: grade publishes, not raw predictions
    Only graded for is_official=true publishes
    """
    graded_id: str = Field(..., description="UUID")
    publish_id: str = Field(..., description="FK to published_predictions")
    prediction_id: str = Field(..., description="FK to predictions")
    event_id: str
    
    # Settlement (Trust Loop v1: SETTLED/VOID/NO_ACTION)
    bet_status: BetStatus = BetStatus.PENDING
    result_code: Optional[ResultCode] = None
    units_returned: Optional[float] = Field(None, description="Assume 1 unit at locked_price_at_publish")
    unit_return: Optional[float] = Field(None, description="Alias for units_returned (backwards compat)")
    
    # CLV (Trust Loop v1: deterministic close snapshot + clv_points)
    close_snapshot_id: Optional[str] = Field(None, description="FK to odds_snapshots (last before start_time_utc)")
    clv_points: Optional[float] = Field(None, description="Sign-corrected line difference vs close")
    clv: Optional[float] = Field(None, description="Alias for clv_points (backwards compat)")
    
    # Calibration metric (Trust Loop v1: brier_component)
    brier_component: Optional[float] = Field(None, description="(locked_p_calibrated - y)^2 where y=1 for WIN else 0")
    brier: Optional[float] = Field(None, description="Alias for brier_component (backwards compat)")
    
    # Scoring metrics
    brier_component: Optional[float] = None
    logloss_component: Optional[float] = None
    
    # Cohort tags (copied at grade time)
    cohort_tags: Dict[str, Any] = Field(
        default_factory=dict,
        description="league/market/edge_bucket/variance_bucket"
    )
    
    # Grading timestamp
    graded_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        json_schema_extra = {
            "indexes": [
                {"keys": [("graded_id", 1)], "unique": True},
                {"keys": [("publish_id", 1)]},
                {"keys": [("prediction_id", 1)]},
                {"keys": [("event_id", 1)]},
                {"keys": [("bet_status", 1)]},
                {"keys": [("result_code", 1)]},
                {"keys": [("graded_at", -1)]},
            ]
        }


# ============================================================================
# USER PICK TRACKS (Trust Loop v1 - Follow/Track)
# ============================================================================

class UserPickTrack(BaseModel):
    """
    User Follow/Track (Trust Loop v1)
    Lets users save official picks to a personal watchlist
    
    NOT execution - just tracking for informational purposes
    Label: 'Tracked pick (not a verified bet)'
    """
    user_pick_track_id: str = Field(..., description="UUID")
    user_id: str = Field(..., description="FK to users")
    publish_id: str = Field(..., description="FK to published_predictions")
    tracked_at_utc: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    status: Literal["ACTIVE", "REMOVED"] = "ACTIVE"
    
    class Config:
        json_schema_extra = {
            "indexes": [
                {"keys": [("user_pick_track_id", 1)], "unique": True},
                {"keys": [("user_id", 1), ("publish_id", 1)], "unique": True},  # One track per user+pick
                {"keys": [("user_id", 1), ("status", 1), ("tracked_at_utc", -1)]},
                {"keys": [("publish_id", 1)]},
            ]
        }


# ============================================================================
# CALIBRATION VERSIONS
# ============================================================================

class CalibrationVersion(BaseModel):
    """
    Versioned calibration models
    """
    calibration_version: str = Field(..., description="Version identifier")
    
    # Training period
    trained_on_start: datetime
    trained_on_end: datetime
    created_at_utc: datetime = Field(default_factory=datetime.utcnow)
    
    # Method
    method: Literal["isotonic", "platt", "temperature", "beta"]
    min_samples_required: int = 500
    
    # Activation
    activation_status: CalibrationStatus = CalibrationStatus.CANDIDATE
    notes: Optional[str] = None
    
    # Metrics (aggregate across all segments)
    overall_ece: Optional[float] = None
    overall_brier: Optional[float] = None
    overall_mce: Optional[float] = None
    
    class Config:
        json_schema_extra = {
            "indexes": [
                {"keys": [("calibration_version", 1)], "unique": True},
                {"keys": [("activation_status", 1)]},
                {"keys": [("created_at_utc", -1)]},
            ]
        }


# ============================================================================
# CALIBRATION SEGMENTS
# ============================================================================

class CalibrationSegment(BaseModel):
    """
    Calibration by cohort (league, market, edge_bucket, etc.)
    """
    calibration_version: str
    segment_key: str = Field(..., description="NBA|TOTAL:FULL_GAME")
    
    # Sample size
    n_samples: int
    
    # Mapping params (JSON-serialized calibration function)
    mapping_params: Dict[str, Any] = Field(default_factory=dict)
    
    # Metrics
    ece: Optional[float] = None
    brier_mean: Optional[float] = None
    mce: Optional[float] = None
    reliability_diagram: Optional[Dict[str, Any]] = None
    
    class Config:
        json_schema_extra = {
            "indexes": [
                {"keys": [("calibration_version", 1), ("segment_key", 1)], "unique": True},
                {"keys": [("segment_key", 1)]},
            ]
        }


# ============================================================================
# PERFORMANCE ROLLUPS (materialized)
# ============================================================================

class PerformanceRollup(BaseModel):
    """
    Materialized performance metrics
    Roll up only from published_predictions joined to grading
    """
    rollup_id: str = Field(..., description="UUID")
    
    # Cohort definition
    cohort_key: str = Field(..., description="league|market|edge_bucket|etc.")
    
    # Time window
    window_start: datetime
    window_end: datetime
    
    # Sample size
    n_total: int
    n_graded: int
    n_settled: int
    
    # Performance metrics
    win_rate: Optional[float] = None
    roi: Optional[float] = None
    avg_clv: Optional[float] = None
    
    # Scoring
    avg_brier: Optional[float] = None
    avg_logloss: Optional[float] = None
    ece: Optional[float] = None
    
    # Risk
    max_drawdown: Optional[float] = None
    sharpe_ratio: Optional[float] = None
    
    # Updated timestamp
    computed_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        json_schema_extra = {
            "indexes": [
                {"keys": [("rollup_id", 1)], "unique": True},
                {"keys": [("cohort_key", 1), ("window_end", -1)]},
                {"keys": [("computed_at", -1)]},
            ]
        }


# ============================================================================
# INDEX CREATION FUNCTIONS
# ============================================================================

def create_all_indexes(db):
    """
    Create all indexes for logging & calibration system
    
    Args:
        db: MongoDB database instance
    """
    import logging
    logger = logging.getLogger(__name__)
    
    # Events
    db.events.create_index("event_id", unique=True)
    db.events.create_index([("league", 1), ("start_time_utc", 1)])
    db.events.create_index([("status", 1)])
    
    # Odds Snapshots (partition by month recommended)
    db.odds_snapshots.create_index("snapshot_id", unique=True)
    db.odds_snapshots.create_index([("event_id", 1), ("market_key", 1), ("book", 1), ("timestamp_utc", -1)])
    db.odds_snapshots.create_index([("event_id", 1), ("timestamp_utc", -1)])
    db.odds_snapshots.create_index([("is_close_candidate", 1)])
    
    # Injury Snapshots
    db.injury_snapshots.create_index("injury_snapshot_id", unique=True)
    db.injury_snapshots.create_index([("league", 1), ("team", 1), ("timestamp_utc", -1)])
    
    # Sim Runs
    db.sim_runs.create_index("sim_run_id", unique=True)
    db.sim_runs.create_index([("event_id", 1), ("created_at_utc", -1)])
    db.sim_runs.create_index([("trigger", 1)])
    db.sim_runs.create_index([("calibration_version_applied", 1)])
    
    # Sim Run Inputs
    db.sim_run_inputs.create_index([("sim_run_id", 1)])
    db.sim_run_inputs.create_index([("snapshot_id", 1)])
    
    # Predictions (use sparse index to allow null values in existing docs)
    try:
        db.predictions.create_index("prediction_id", unique=True, sparse=True)
    except Exception as e:
        logger.warning(f"Predictions index already exists or error: {e}")
    
    db.predictions.create_index([("sim_run_id", 1)])
    db.predictions.create_index([("event_id", 1)])
    db.predictions.create_index([("market_snapshot_id_used", 1)])
    db.predictions.create_index([("recommendation_state", 1)])
    
    # Published Predictions (Trust Loop v1: add publish_type index)
    db.published_predictions.create_index("publish_id", unique=True)
    db.published_predictions.create_index([("prediction_id", 1)])
    db.published_predictions.create_index([("event_id", 1)])
    db.published_predictions.create_index([("published_at_utc", -1)])
    db.published_predictions.create_index([("is_official", 1), ("publish_type", 1)])  # Trust Loop queries
    db.published_predictions.create_index([("is_official", 1)])
    db.published_predictions.create_index([("visibility", 1), ("published_at_utc", -1)])
    db.published_predictions.create_index([("channel", 1)])
    
    # Event Results
    db.event_results.create_index("event_id", unique=True)
    db.event_results.create_index([("status", 1)])
    db.event_results.create_index([("official_timestamp", -1)])
    
    # Grading
    db.grading.create_index("graded_id", unique=True)
    db.grading.create_index([("publish_id", 1)])
    db.grading.create_index([("prediction_id", 1)])
    db.grading.create_index([("event_id", 1)])
    db.grading.create_index([("bet_status", 1)])
    db.grading.create_index([("result_code", 1)])
    db.grading.create_index([("graded_at", -1)])
    
    # User Pick Tracks (Trust Loop v1: Follow/Track)
    db.user_pick_tracks.create_index("user_pick_track_id", unique=True)
    db.user_pick_tracks.create_index([("user_id", 1), ("publish_id", 1)], unique=True)
    db.user_pick_tracks.create_index([("user_id", 1), ("status", 1), ("tracked_at_utc", -1)])
    db.user_pick_tracks.create_index([("publish_id", 1)])
    
    # Calibration Versions
    db.calibration_versions.create_index("calibration_version", unique=True)
    db.calibration_versions.create_index([("activation_status", 1)])
    db.calibration_versions.create_index([("created_at_utc", -1)])
    
    # Calibration Segments
    db.calibration_segments.create_index([("calibration_version", 1), ("segment_key", 1)], unique=True)
    db.calibration_segments.create_index([("segment_key", 1)])
    
    # Performance Rollups
    db.performance_rollups.create_index("rollup_id", unique=True)
    db.performance_rollups.create_index([("cohort_key", 1), ("window_end", -1)])
    db.performance_rollups.create_index([("computed_at", -1)])
    
    print("✅ All indexes created for logging & calibration system")
