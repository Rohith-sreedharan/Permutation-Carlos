"""
CANONICAL MARKET DECISION CONTRACT
===================================

SINGLE SOURCE OF TRUTH for all market-level decisions.
NO OTHER CODE PATH may compute direction, preference, status, or reasons.

This object is the ONLY interface between backend simulation logic and frontend UI.
UI must render this verbatim - ZERO derivation or recomputation allowed.

All leagues (NBA/NFL/NCAAF/NHL/MLB/etc) flow through this same contract.
"""

from typing import Literal, Optional, Union
from pydantic import BaseModel, Field
from enum import Enum


class MarketType(str, Enum):
    """Market types - league-agnostic"""
    SPREAD = "spread"
    MONEYLINE = "moneyline"
    TOTAL = "total"


class Classification(str, Enum):
    """Edge classification per market"""
    EDGE = "EDGE"  # Official trade candidate
    LEAN = "LEAN"  # Info-only / low confidence
    MARKET_ALIGNED = "MARKET_ALIGNED"  # No edge detected
    NO_ACTION = "NO_ACTION"  # Blocked by risk/integrity or insufficient signal


class ReleaseStatus(str, Enum):
    """Release eligibility per market - LOCKED per Section 9"""
    APPROVED = "APPROVED"  # Eligible for release
    BLOCKED_BY_INTEGRITY = "BLOCKED_BY_INTEGRITY"  # Data integrity violation
    BLOCKED_BY_ODDS_MISMATCH = "BLOCKED_BY_ODDS_MISMATCH"  # Odds alignment failed
    BLOCKED_BY_STALE_DATA = "BLOCKED_BY_STALE_DATA"  # Simulation too old
    BLOCKED_BY_MISSING_DATA = "BLOCKED_BY_MISSING_DATA"  # Required fields missing
    PENDING_REVIEW = "PENDING_REVIEW"  # Manual review needed


class PickSpread(BaseModel):
    """Spread/ML pick - tied to team_id"""
    team_id: str = Field(..., description="Canonical team identifier")
    team_name: str = Field(..., description="Display name")
    side: Optional[Literal["HOME", "AWAY"]] = Field(None, description="Optional home/away indicator")


class PickTotal(BaseModel):
    """Total pick - OVER or UNDER"""
    side: Literal["OVER", "UNDER"] = Field(..., description="Total direction")


class MarketSpread(BaseModel):
    """Market line for spread"""
    line: float = Field(..., description="Spread line SIGNED for pick team (e.g., -6.5 for favorite)")
    odds: Optional[int] = Field(None, description="American odds if available")


class MarketMoneyline(BaseModel):
    """Market line for moneyline"""
    odds: int = Field(..., description="American odds for pick team")


class MarketTotal(BaseModel):
    """Market line for total"""
    line: float = Field(..., description="Total points line (e.g., 227.5)")
    odds: Optional[int] = Field(None, description="American odds for pick side")


class ModelSpread(BaseModel):
    """Model fair line for spread"""
    fair_line: float = Field(..., description="Fair spread SIGNED for same pick team")


class ModelMoneyline(BaseModel):
    """Model fair value for moneyline"""
    win_prob: float = Field(..., description="Win probability for pick team (0-1)")


class ModelTotal(BaseModel):
    """Model fair value for total"""
    fair_total: float = Field(..., description="Fair total points projection")


class Probabilities(BaseModel):
    """Model vs market probabilities"""
    model_prob: float = Field(..., description="Model probability of pick outcome (0-1)")
    market_implied_prob: float = Field(..., description="Market implied probability (vig-aware)")


class Edge(BaseModel):
    """Edge quantification"""
    edge_points: Optional[float] = Field(None, description="Edge in points (spread/total)")
    edge_ev: Optional[float] = Field(None, description="Edge in EV % (moneyline)")
    edge_grade: Optional[Literal["S", "A", "B", "C", "D"]] = Field(None, description="Visual grade badge")


class Risk(BaseModel):
    """Risk assessment"""
    volatility_flag: Optional[str] = Field(None, description="HIGH/MODERATE/STABLE")
    injury_impact: Optional[float] = Field(None, description="Total injury impact score")
    clv_forecast: Optional[float] = Field(None, description="Expected closing line movement")
    blocked_reason: Optional[str] = Field(None, description="Why this was blocked (if applicable)")


class Debug(BaseModel):
    """Debug payload"""
    inputs_hash: str = Field(..., description="Hash of odds snapshot + sim run + config")
    odds_timestamp: str = Field(..., description="ISO timestamp of odds snapshot")
    sim_run_id: str = Field(..., description="Simulation run identifier")
    trace_id: str = Field(..., description="Trace ID for audit/debugging (UUID)")
    config_profile: Optional[str] = Field(None, description="Config used (balanced/high-vol/etc)")
    decision_version: int = Field(..., description="Monotonic version for freshness checking (ATOMIC across all markets)")
    computed_at: str = Field(..., description="ISO timestamp when decision was computed")


class MarketDecision(BaseModel):
    """
    CANONICAL MARKET DECISION
    
    This is the ONLY object that contains market-level decisions.
    ALL UI panels must render from this object.
    NO UI-side computation of direction/preference/status/reasons allowed.
    
    DETERMINISTIC MAPPING RULES (enforced by validator):
    - Spread: market.line = sportsbook line for pick.team_id with correct sign
    - Spread: model.fair_line = fair spread for SAME pick.team_id with correct sign
    - Total: pick.side determined by model.fair_total vs market.line comparison
    - ML: probabilities refer to SAME pick.team_id
    
    INTEGRITY INVARIANTS (validator fails if violated):
    - Spread: opponent cannot have same signed line in same snapshot
    - Classification coherence: MARKET_ALIGNED cannot claim misprice in reasons
    - Selection binding: selection_id maps to same team/side across entire payload
    - Competitor integrity: pick.team_id must be in game competitors
    
    ATOMIC CONSISTENCY:
    - decision_version MUST be identical across all markets in same response
    - trace_id MUST be identical across all markets in same response
    - inputs_hash MUST be identical across all markets in same response
    """
    
    # Identifiers
    league: str = Field(..., description="League (NBA/NFL/NCAAF/NHL/MLB/etc)")
    game_id: str = Field(..., description="Internal game identifier")
    odds_event_id: str = Field(..., description="Provider event ID (prevents cross-game bleed)")
    market_type: MarketType = Field(..., description="Market type")
    
    # CANONICAL FIELDS (required for audit + display)
    decision_id: str = Field(..., description="Unique UUID for this specific decision")
    selection_id: str = Field(..., description="Canonical selection identifier")
    preferred_selection_id: str = Field(..., description="The bettable leg anchor (selection_id for preferred side)")
    market_selections: list[dict] = Field(..., description="All available selections (both sides of market)")
    
    # Pick (team or side) - null if BLOCKED
    pick: Optional[Union[PickSpread, PickTotal]] = Field(None, description="Pick team or side")
    
    # Market data
    market: Union[MarketSpread, MarketMoneyline, MarketTotal] = Field(..., description="Market line/odds")
    
    # Model data - null if BLOCKED
    model: Optional[Union[ModelSpread, ModelMoneyline, ModelTotal]] = Field(None, description="Model fair value")
    
    # Fair selection (fair line for preferred selection) - null if BLOCKED
    fair_selection: Optional[dict] = Field(None, description="Fair line/total expressed for preferred selection")
    
    # Probabilities - null if BLOCKED
    probabilities: Optional[Probabilities] = Field(None, description="Model vs market probabilities")
    
    # Edge assessment - null if BLOCKED
    edge: Optional[Edge] = Field(None, description="Edge quantification")
    
    # Classification & status
    classification: Optional[Classification] = Field(None, description="Edge classification")
    release_status: ReleaseStatus = Field(..., description="Release eligibility")
    
    # Pre-computed UI text
    reasons: list[str] = Field(default_factory=list, description="Pre-written bullets for 'Why This Edge Exists'")
    
    # Risk assessment
    risk: Risk = Field(..., description="Risk factors")
    
    # Debug payload
    debug: Debug = Field(..., description="Debug/trace information")
    
    # Validator failures (empty if passed)
    validator_failures: list[str] = Field(default_factory=list, description="Integrity check failures")


class GameDecisions(BaseModel):
    """
    Complete decisions for a game - returned by unified endpoint
    
    GET /games/{league}/{game_id}/decisions
    """
    spread: Optional[MarketDecision] = None
    moneyline: Optional[MarketDecision] = None
    total: Optional[MarketDecision] = None
    
    # Game context
    home_team_name: str = Field(..., description="Home team display name")
    away_team_name: str = Field(..., description="Away team display name")
    
    # Meta
    inputs_hash: str = Field(..., description="Global inputs hash for this snapshot")
    decision_version: int = Field(..., description="Monotonic version number")
    computed_at: str = Field(..., description="ISO timestamp of computation")
