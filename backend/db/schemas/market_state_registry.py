"""
Market State Registry Schema
SINGLE SOURCE OF TRUTH for all market states

🚨 CRITICAL: This registry is the ONLY place market states should be read from.
No feature may infer state independently.

All downstream features MUST read from this table:
- Telegram posting
- Parlay builder
- War Room
- Daily picks
- Any UI showing edge/lean/no_play states
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Literal
from datetime import datetime
from enum import Enum
import hashlib
import json


# ============================================================================
# ENUMS
# ============================================================================

class MarketState(str, Enum):
    """Canonical market states - no other states allowed"""
    EDGE = "EDGE"           # Full actionable edge - Telegram/Daily Pick eligible
    LEAN = "LEAN"           # Model signal but blocked by risk controls
    NO_PLAY = "NO_PLAY"     # No actionable signal


class MarketType(str, Enum):
    """Supported market types"""
    SPREAD = "SPREAD"
    TOTAL = "TOTAL"
    ML = "ML"
    PROP = "PROP"
    FIRST_HALF_SPREAD = "FIRST_HALF_SPREAD"
    FIRST_HALF_TOTAL = "FIRST_HALF_TOTAL"


class VolatilityFlag(str, Enum):
    """Volatility classification"""
    STABLE = "STABLE"       # Low variance, high confidence
    MODERATE = "MODERATE"   # Medium variance
    VOLATILE = "VOLATILE"   # High variance, low confidence


class ReasonCode(str, Enum):
    """Why a market is in its current state"""
    # EDGE reasons
    EDGE_CONFIRMED = "EDGE_CONFIRMED"
    STRONG_MODEL_SIGNAL = "STRONG_MODEL_SIGNAL"
    
    # LEAN reasons (blocked from EDGE)
    PROBABILITY_BELOW_THRESHOLD = "PROBABILITY_BELOW_THRESHOLD"
    EDGE_BELOW_THRESHOLD = "EDGE_BELOW_THRESHOLD"
    CONFIDENCE_BELOW_THRESHOLD = "CONFIDENCE_BELOW_THRESHOLD"
    VOLATILITY_TOO_HIGH = "VOLATILITY_TOO_HIGH"
    RISK_SCORE_EXCEEDED = "RISK_SCORE_EXCEEDED"
    SHARP_SIDE_CONFLICTED = "SHARP_SIDE_CONFLICTED"
    
    # NO_PLAY reasons
    NO_MODEL_SIGNAL = "NO_MODEL_SIGNAL"
    DATA_INCOMPLETE = "DATA_INCOMPLETE"
    MARKET_SUSPENDED = "MARKET_SUSPENDED"
    GAME_STARTED = "GAME_STARTED"
    LINE_STALE = "LINE_STALE"
    SIM_CONVERGENCE_FAILED = "SIM_CONVERGENCE_FAILED"
    
    # Invalidation reasons
    INVALIDATED_INJURY = "INVALIDATED_INJURY"
    INVALIDATED_LINEUP = "INVALIDATED_LINEUP"
    INVALIDATED_LINE_MOVE = "INVALIDATED_LINE_MOVE"


# ============================================================================
# VISIBILITY FLAGS
# ============================================================================

class VisibilityFlags(BaseModel):
    """
    Explicit flags for where this market state can appear
    
    These are DECOUPLED - each feature has independent visibility rules
    """
    telegram_allowed: bool = Field(
        default=False,
        description="Can be posted to Telegram (requires EDGE)"
    )
    parlay_allowed: bool = Field(
        default=False,
        description="Can be included in parlay builder (EDGE or LEAN)"
    )
    war_room_visible: bool = Field(
        default=False,
        description="Shows in War Room (EDGE or LEAN)"
    )
    daily_pick_allowed: bool = Field(
        default=False,
        description="Can be shown as daily pick (requires EDGE)"
    )


# ============================================================================
# THRESHOLD CONFIGS (EXPLICIT DECOUPLING)
# ============================================================================

class SinglePickThresholds(BaseModel):
    """
    Thresholds for Telegram / Daily Pick posting
    These are STRICTER than parlay thresholds
    """
    state_required: MarketState = MarketState.EDGE
    probability_min: float = 0.58   # 58%
    edge_min: float = 4.0           # 4+ points
    confidence_min: int = 65        # 65+


class ParlayThresholds(BaseModel):
    """
    Thresholds for parlay leg eligibility
    These are LOOSER than single pick thresholds
    
    🚨 NEVER reuse SinglePickThresholds for parlays
    """
    states_allowed: List[MarketState] = Field(
        default=[MarketState.EDGE, MarketState.LEAN]
    )
    probability_min: float = 0.53   # 53%
    edge_min: float = 1.5           # 1.5+ points
    confidence_min: int = 50        # 50+
    risk_score_max: float = 0.55    # Max 55% risk


# Global threshold instances
SINGLE_PICK_THRESHOLDS = SinglePickThresholds()
PARLAY_THRESHOLDS = ParlayThresholds()


# ============================================================================
# MARKET STATE REGISTRY SCHEMA
# ============================================================================

class MarketStateRegistry(BaseModel):
    """
    🚨 SINGLE SOURCE OF TRUTH for market states
    
    All downstream features MUST read from this registry.
    States are immutable per evaluation cycle.
    """
    # Identity
    registry_id: str = Field(..., description="Unique ID for this registry entry")
    game_id: str = Field(..., description="Game identifier")
    sport: str = Field(..., description="Sport key (e.g., basketball_nba)")
    market_type: MarketType = Field(..., description="Market type")
    
    # Core state (THE source of truth)
    state: MarketState = Field(..., description="Canonical market state")
    reason_codes: List[ReasonCode] = Field(
        default_factory=list,
        description="Why market is in this state"
    )
    
    # Metrics (frozen at evaluation time)
    probability: Optional[float] = Field(None, ge=0, le=1, description="Win probability")
    edge_points: Optional[float] = Field(None, description="Edge in points")
    confidence_score: Optional[int] = Field(None, ge=0, le=100, description="Confidence 0-100")
    risk_score: Optional[float] = Field(None, ge=0, le=1, description="Risk score 0-1")
    
    # Volatility
    volatility_flag: VolatilityFlag = Field(
        default=VolatilityFlag.MODERATE,
        description="Volatility classification"
    )
    
    # Visibility flags (DECOUPLED)
    visibility_flags: VisibilityFlags = Field(
        default_factory=VisibilityFlags,
        description="Where this market can appear"
    )
    
    # Selection info
    selection: Optional[str] = Field(None, description="e.g., 'Bulls +6.5'")
    line_value: Optional[float] = Field(None, description="Market line")
    
    # Versioning
    state_version_hash: str = Field(
        ...,
        description="Hash of state for change detection"
    )
    evaluation_cycle_id: str = Field(
        ...,
        description="Which simulation cycle produced this state"
    )
    
    # Timestamps
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(),
        description="When registry entry was created"
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(),
        description="Last update timestamp"
    )
    expires_at: Optional[datetime] = Field(
        None,
        description="When this state expires (game start time)"
    )
    
    def compute_visibility_flags(self) -> VisibilityFlags:
        """
        Compute visibility flags based on state and metrics
        
        🚨 CRITICAL: These rules are EXPLICIT and DECOUPLED
        """
        flags = VisibilityFlags()
        
        # War Room: EDGE or LEAN
        if self.state in [MarketState.EDGE, MarketState.LEAN]:
            flags.war_room_visible = True
        
        # Parlay: EDGE or LEAN with looser thresholds
        if (
            self.state in [MarketState.EDGE, MarketState.LEAN] and
            (self.probability or 0) >= PARLAY_THRESHOLDS.probability_min and
            (self.edge_points or 0) >= PARLAY_THRESHOLDS.edge_min and
            (self.confidence_score or 0) >= PARLAY_THRESHOLDS.confidence_min and
            (self.risk_score or 0) <= PARLAY_THRESHOLDS.risk_score_max
        ):
            flags.parlay_allowed = True
        
        # Telegram/Daily Pick: EDGE only with strict thresholds
        if (
            self.state == MarketState.EDGE and
            (self.probability or 0) >= SINGLE_PICK_THRESHOLDS.probability_min and
            (self.edge_points or 0) >= SINGLE_PICK_THRESHOLDS.edge_min and
            (self.confidence_score or 0) >= SINGLE_PICK_THRESHOLDS.confidence_min
        ):
            flags.telegram_allowed = True
            flags.daily_pick_allowed = True
        
        return flags
    
    @staticmethod
    def compute_state_hash(
        game_id: str,
        market_type: str,
        state: str,
        probability: Optional[float],
        edge_points: Optional[float],
        confidence_score: Optional[int]
    ) -> str:
        """Compute deterministic hash for state versioning"""
        data = {
            "game_id": game_id,
            "market_type": market_type,
            "state": state,
            "probability": round(probability or 0, 4),
            "edge_points": round(edge_points or 0, 2),
            "confidence_score": confidence_score or 0
        }
        return hashlib.sha256(
            json.dumps(data, sort_keys=True).encode()
        ).hexdigest()[:16]


# ============================================================================
# PARLAY ELIGIBILITY RESULT
# ============================================================================

class ParlayEligibilityResult(BaseModel):
    """
    Result of checking parlay eligibility
    
    🚨 PARLAY FAILURE IS NOT AN ERROR - it's a valid state
    """
    is_eligible: bool
    state: Literal["ELIGIBLE", "PARLAY_BLOCKED", "INSUFFICIENT_LEGS"]
    passed_checks: List[str] = Field(default_factory=list)
    failed_checks: List[str] = Field(default_factory=list)
    reason_codes: List[str] = Field(default_factory=list)
    
    # For PARLAY_BLOCKED state
    passed_legs: int = 0
    failed_legs: int = 0
    next_refresh_eta: Optional[datetime] = None
    
    # Fallback suggestions
    best_single_pick: Optional[str] = Field(
        None,
        description="Best single pick if parlay not available"
    )
    alternative_sports: List[str] = Field(
        default_factory=list,
        description="Sports with more eligible markets"
    )


# ============================================================================
# COLLECTION NAME
# ============================================================================

MARKET_STATE_COLLECTION = "market_state_registry"
