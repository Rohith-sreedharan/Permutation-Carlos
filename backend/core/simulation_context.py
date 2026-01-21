"""
Simulation Context - Immutable Snapshot System
==============================================
Ensures deterministic, reproducible simulation outputs.

Key Guarantees:
- Same context → same seed → same output
- Context changes auto-generate new seeds
- No rerun variance for identical inputs
"""

from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone
from enum import Enum
import hashlib
import json


class SimulationStatus(str, Enum):
    """Simulation execution status"""
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    CACHED = "CACHED"
    PRICE_MOVED = "PRICE_MOVED"  # Market moved past playable limit
    INVALIDATED = "INVALIDATED"  # Manually invalidated
    FAILED = "FAILED"


@dataclass(frozen=True)
class MarketSnapshot:
    """
    Immutable market snapshot at time of simulation.
    Captures line, odds, and de-vig probabilities.
    """
    market_type: str  # "SPREAD", "TOTAL", "MONEYLINE", "PROP"
    selection: str  # e.g. "away +7.5", "over 228.5", "LeBron points over 25.5"
    line: Optional[float]  # spread/total line (None for ML)
    american_odds: int  # e.g. -110, +150
    decimal_odds: float  # e.g. 1.909, 2.50
    implied_prob: float  # with vig, 0-1
    devig_prob: float  # no-vig probability, 0-1
    book_id: str  # sportsbook identifier
    timestamp_utc: datetime
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize for hashing"""
        return {
            "market_type": self.market_type,
            "selection": self.selection,
            "line": self.line,
            "american_odds": self.american_odds,
            "decimal_odds": round(self.decimal_odds, 4),
            "implied_prob": round(self.implied_prob, 6),
            "devig_prob": round(self.devig_prob, 6),
            "book_id": self.book_id,
            "timestamp_utc": self.timestamp_utc.isoformat(),
        }


@dataclass(frozen=True)
class InjurySnapshot:
    """Immutable injury status at time of simulation"""
    player_id: str
    player_name: str
    status: str  # OUT, DOUBTFUL, QUESTIONABLE, PROBABLE, AVAILABLE
    minutes_projection: Optional[float]
    confidence: float  # 0-1
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "player_id": self.player_id,
            "player_name": self.player_name,
            "status": self.status,
            "minutes_projection": self.minutes_projection,
            "confidence": round(self.confidence, 4),
        }


@dataclass(frozen=True)
class SimulationContext:
    """
    Immutable simulation context.
    
    All inputs frozen at time of simulation creation.
    Context hash determines deterministic seed.
    
    Rerun Rules:
    - Same context hash → return cached result
    - Changed context hash → run new simulation
    """
    # Game identifiers
    game_id: str
    sport: str
    league: str
    home_team: str
    away_team: str
    game_time_utc: datetime
    
    # Model versioning
    model_version: str
    engine_version: str
    data_feed_version: str
    
    # Market snapshot
    market: MarketSnapshot
    
    # Game state inputs (frozen)
    injuries: List[InjurySnapshot] = field(default_factory=list)
    pace_projection: Optional[float] = None
    fatigue_factors: Optional[Dict[str, float]] = None
    weather: Optional[Dict[str, Any]] = None
    
    # Simulation parameters
    n_simulations: int = 10000
    random_seed_base: Optional[int] = None  # Optional override
    
    # Metadata
    created_at_utc: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    created_by: Optional[str] = None
    
    @property
    def context_hash(self) -> str:
        """
        Generate deterministic hash from context.
        
        Same inputs → same hash → same seed → same output.
        """
        canonical = self._canonical_dict()
        json_str = json.dumps(canonical, separators=(",", ":"), sort_keys=True)
        return hashlib.sha256(json_str.encode("utf-8")).hexdigest()
    
    def _canonical_dict(self) -> Dict[str, Any]:
        """
        Canonical representation for hashing.
        Excludes metadata (created_at, created_by) to focus on inputs.
        """
        return {
            # Game identifiers
            "game_id": self.game_id,
            "sport": self.sport,
            "league": self.league,
            "home_team": self.home_team,
            "away_team": self.away_team,
            "game_time_utc": self.game_time_utc.isoformat(),
            
            # Model versioning
            "model_version": self.model_version,
            "engine_version": self.engine_version,
            "data_feed_version": self.data_feed_version,
            
            # Market snapshot
            "market": self.market.to_dict(),
            
            # Game state inputs
            "injuries": [inj.to_dict() for inj in sorted(self.injuries, key=lambda x: x.player_id)],
            "pace_projection": round(self.pace_projection, 4) if self.pace_projection else None,
            "fatigue_factors": {k: round(v, 4) for k, v in sorted(self.fatigue_factors.items())} if self.fatigue_factors else None,
            "weather": self.weather,
            
            # Simulation parameters
            "n_simulations": self.n_simulations,
            "random_seed_base": self.random_seed_base,
        }
    
    def deterministic_seed(self) -> int:
        """
        Generate deterministic seed from context hash.
        
        Formula: seed = hash(game_id + market_type + context_hash + model_version)
        
        This ensures:
        - Same context → same seed
        - Different context → different seed
        - Reproducible across reruns
        """
        if self.random_seed_base is not None:
            # Use override if provided (for testing)
            return self.random_seed_base
        
        seed_input = f"{self.game_id}:{self.market.market_type}:{self.context_hash}:{self.model_version}"
        seed_hash = hashlib.sha256(seed_input.encode("utf-8")).hexdigest()
        # Take first 8 bytes as integer
        return int(seed_hash[:16], 16) % (2**31)  # Keep within int32 range
    
    def is_eligible_for_rerun(self, new_context: SimulationContext) -> tuple[bool, str]:
        """
        Check if rerun is allowed based on context changes.
        
        Rerun allowed ONLY if:
        - Injury status changed
        - Lineup confirmed (minutes projection updated)
        - Market moved materially (>= 0.5 point for spreads/totals)
        - Model version updated
        
        Returns:
            (is_eligible, reason)
        """
        # Model version change
        if self.model_version != new_context.model_version:
            return (True, "model_version_updated")
        
        if self.engine_version != new_context.engine_version:
            return (True, "engine_version_updated")
        
        if self.data_feed_version != new_context.data_feed_version:
            return (True, "data_feed_version_updated")
        
        # Injury status change
        old_injuries = {inj.player_id: inj for inj in self.injuries}
        new_injuries = {inj.player_id: inj for inj in new_context.injuries}
        
        if old_injuries.keys() != new_injuries.keys():
            return (True, "injury_list_changed")
        
        for player_id, old_inj in old_injuries.items():
            new_inj = new_injuries[player_id]
            if old_inj.status != new_inj.status:
                return (True, f"injury_status_changed:{player_id}")
            
            # Minutes projection changed materially (>= 2.0 minutes)
            if old_inj.minutes_projection and new_inj.minutes_projection:
                if abs(old_inj.minutes_projection - new_inj.minutes_projection) >= 2.0:
                    return (True, f"minutes_projection_changed:{player_id}")
        
        # Market line moved materially
        old_line = self.market.line
        new_line = new_context.market.line
        
        if old_line is not None and new_line is not None:
            if abs(old_line - new_line) >= 0.5:
                return (True, f"market_line_moved:{old_line}→{new_line}")
        
        # Odds moved materially (>= 10 cents, e.g. -110 → -120)
        if abs(self.market.american_odds - new_context.market.american_odds) >= 10:
            return (True, f"market_odds_moved:{self.market.american_odds}→{new_context.market.american_odds}")
        
        # No material changes
        return (False, "no_material_changes")
    
    def to_dict(self) -> Dict[str, Any]:
        """Full serialization for storage"""
        return {
            "game_id": self.game_id,
            "sport": self.sport,
            "league": self.league,
            "home_team": self.home_team,
            "away_team": self.away_team,
            "game_time_utc": self.game_time_utc.isoformat(),
            "model_version": self.model_version,
            "engine_version": self.engine_version,
            "data_feed_version": self.data_feed_version,
            "market": self.market.to_dict(),
            "injuries": [inj.to_dict() for inj in self.injuries],
            "pace_projection": self.pace_projection,
            "fatigue_factors": self.fatigue_factors,
            "weather": self.weather,
            "n_simulations": self.n_simulations,
            "random_seed_base": self.random_seed_base,
            "created_at_utc": self.created_at_utc.isoformat(),
            "created_by": self.created_by,
            "context_hash": self.context_hash,
            "deterministic_seed": self.deterministic_seed(),
        }


@dataclass(frozen=True)
class ConfidenceInterval:
    """Confidence interval for probability estimate"""
    lower: float  # Lower bound, 0-1
    upper: float  # Upper bound, 0-1
    half_width: float  # (upper - lower) / 2
    confidence_level: float = 0.95  # Default 95% CI
    
    @property
    def converged(self, target_half_width: float = 0.01) -> bool:
        """Check if CI has converged to target precision"""
        return self.half_width <= target_half_width


@dataclass(frozen=True)
class SimulationResult:
    """
    Official simulation output.
    
    One result per (context_hash, market).
    Immutable once created.
    """
    # Context linkage
    context_hash: str
    game_id: str
    market_type: str
    selection: str
    
    # Model output
    model_probability: float  # 0-1
    confidence_interval: ConfidenceInterval
    
    # Edge calculation
    devig_market_probability: float  # 0-1
    raw_edge: float  # model_prob - devig_prob
    edge_percent: float  # raw_edge * 100
    
    # Validation gates
    meets_edge_threshold: bool  # edge >= 2.0%
    meets_uncertainty_gate: bool  # edge >= 2x CI half-width
    is_valid_play: bool  # Both gates passed
    
    # Execution guardrails
    playable_line_min: Optional[float] = None  # Worst acceptable line
    playable_line_max: Optional[float] = None  # Best acceptable line
    playable_odds_min: Optional[int] = None  # Worst acceptable odds
    
    # Simulation metadata
    n_simulations_run: int = 10000
    convergence_achieved: bool = False
    random_seed_used: int = 0
    
    # Timestamps
    created_at_utc: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    # Status
    status: SimulationStatus = SimulationStatus.COMPLETED
    
    def is_playable_at_line(self, current_line: Optional[float]) -> bool:
        """Check if current line is still playable"""
        if current_line is None:
            return True
        
        if self.playable_line_min is not None and current_line < self.playable_line_min:
            return False
        
        if self.playable_line_max is not None and current_line > self.playable_line_max:
            return False
        
        return True
    
    def is_playable_at_odds(self, current_odds: int) -> bool:
        """Check if current odds are still playable"""
        if self.playable_odds_min is not None and current_odds < self.playable_odds_min:
            return False
        
        return True
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize for storage"""
        return {
            "context_hash": self.context_hash,
            "game_id": self.game_id,
            "market_type": self.market_type,
            "selection": self.selection,
            "model_probability": round(self.model_probability, 6),
            "confidence_interval": {
                "lower": round(self.confidence_interval.lower, 6),
                "upper": round(self.confidence_interval.upper, 6),
                "half_width": round(self.confidence_interval.half_width, 6),
                "confidence_level": self.confidence_interval.confidence_level,
            },
            "devig_market_probability": round(self.devig_market_probability, 6),
            "raw_edge": round(self.raw_edge, 6),
            "edge_percent": round(self.edge_percent, 4),
            "meets_edge_threshold": self.meets_edge_threshold,
            "meets_uncertainty_gate": self.meets_uncertainty_gate,
            "is_valid_play": self.is_valid_play,
            "playable_line_min": self.playable_line_min,
            "playable_line_max": self.playable_line_max,
            "playable_odds_min": self.playable_odds_min,
            "n_simulations_run": self.n_simulations_run,
            "convergence_achieved": self.convergence_achieved,
            "random_seed_used": self.random_seed_used,
            "created_at_utc": self.created_at_utc.isoformat(),
            "status": self.status.value,
        }
