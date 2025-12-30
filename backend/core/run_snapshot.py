"""
Run Snapshot System v1.0
========================

Implements run snapshots and change detection to prevent edge flicker.

RULES:
1. Every simulation creates a run_id
2. Store: market line used, timestamp, odds source, injuries/minutes used, sim count, seed, outputs
3. Page refresh loads latest run_id (no auto re-sim)
4. New simulation requires explicit action
5. Detect & explain changes between runs

This prevents the "edge disappearing on refresh" problem.
"""

import hashlib
import json
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field, asdict
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class ChangeType(Enum):
    """Types of changes between runs"""
    LINE_MOVED = "line_moved"
    INJURY_UPDATE = "injury_update"
    LINEUP_CHANGE = "lineup_change"
    NEW_SIMULATION = "new_simulation"
    ODDS_SOURCE_CHANGE = "odds_source_change"
    MINUTES_PROJECTION_CHANGE = "minutes_projection_change"
    RNG_VARIANCE = "rng_variance"  # Monte Carlo variance
    NO_CHANGE = "no_change"


@dataclass
class RunSnapshot:
    """
    Immutable snapshot of a simulation run
    
    CRITICAL: Once created, these values should never change.
    New simulation = new run_id
    """
    run_id: str
    event_id: str
    created_at: str
    
    # Market context
    market_line_spread: Optional[float] = None
    market_line_total: Optional[float] = None
    odds_source: str = "unknown"
    odds_timestamp: Optional[str] = None
    
    # Inputs hash (for change detection)
    inputs_hash: str = ""
    
    # Key inputs (for display)
    injuries_used: List[Dict[str, Any]] = field(default_factory=list)
    minutes_projections: Dict[str, float] = field(default_factory=dict)
    
    # Simulation config
    sim_count: int = 10000
    random_seed: Optional[int] = None
    
    # Outputs
    model_spread: Optional[float] = None
    model_total: Optional[float] = None
    spread_edge_pts: Optional[float] = None
    total_edge_pts: Optional[float] = None
    home_win_prob: Optional[float] = None
    over_prob: Optional[float] = None
    confidence_score: Optional[int] = None
    edge_state: str = "no_action"
    
    # State reasons
    state_reasons: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'RunSnapshot':
        return cls(**data)


@dataclass
class ChangeDetectionResult:
    """Result of comparing two run snapshots"""
    has_changes: bool
    change_types: List[ChangeType]
    changes: List[Dict[str, Any]]
    explanation: str
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "has_changes": self.has_changes,
            "change_types": [ct.value for ct in self.change_types],
            "changes": self.changes,
            "explanation": self.explanation
        }


class RunSnapshotManager:
    """
    Manages run snapshots for simulation runs
    
    USAGE:
    1. Before running simulation: create_snapshot() with inputs
    2. After simulation: update_snapshot() with outputs
    3. On page refresh: get_latest_snapshot() - NO re-simulation
    4. On explicit re-run: detect_changes() then create new snapshot
    """
    
    def __init__(self, db=None):
        self.db = db
        self._cache: Dict[str, RunSnapshot] = {}
    
    def generate_run_id(self, event_id: str, timestamp: datetime) -> str:
        """Generate unique run_id"""
        seed = f"{event_id}_{timestamp.isoformat()}_{id(self)}"
        return f"run_{hashlib.sha256(seed.encode()).hexdigest()[:16]}"
    
    def generate_inputs_hash(
        self,
        market_line_spread: Optional[float],
        market_line_total: Optional[float],
        injuries: List[Dict[str, Any]],
        minutes: Dict[str, float]
    ) -> str:
        """Generate hash of inputs for change detection"""
        data = {
            "spread": market_line_spread,
            "total": market_line_total,
            "injuries": sorted([str(i) for i in injuries]),
            "minutes": dict(sorted(minutes.items()))
        }
        return hashlib.md5(json.dumps(data, sort_keys=True).encode()).hexdigest()
    
    def create_snapshot(
        self,
        event_id: str,
        market_line_spread: Optional[float] = None,
        market_line_total: Optional[float] = None,
        odds_source: str = "unknown",
        injuries: Optional[List[Dict[str, Any]]] = None,
        minutes_projections: Optional[Dict[str, float]] = None,
        sim_count: int = 10000,
        random_seed: Optional[int] = None
    ) -> RunSnapshot:
        """
        Create a new run snapshot before simulation
        
        This captures the inputs so we can detect changes later.
        """
        now = datetime.now(timezone.utc)
        run_id = self.generate_run_id(event_id, now)
        
        injuries = injuries or []
        minutes_projections = minutes_projections or {}
        
        inputs_hash = self.generate_inputs_hash(
            market_line_spread,
            market_line_total,
            injuries,
            minutes_projections
        )
        
        snapshot = RunSnapshot(
            run_id=run_id,
            event_id=event_id,
            created_at=now.isoformat(),
            market_line_spread=market_line_spread,
            market_line_total=market_line_total,
            odds_source=odds_source,
            odds_timestamp=now.isoformat(),
            inputs_hash=inputs_hash,
            injuries_used=injuries,
            minutes_projections=minutes_projections,
            sim_count=sim_count,
            random_seed=random_seed
        )
        
        self._cache[run_id] = snapshot
        
        logger.info(f"Created run snapshot {run_id} for event {event_id}")
        return snapshot
    
    def update_snapshot_outputs(
        self,
        run_id: str,
        model_spread: Optional[float] = None,
        model_total: Optional[float] = None,
        spread_edge_pts: Optional[float] = None,
        total_edge_pts: Optional[float] = None,
        home_win_prob: Optional[float] = None,
        over_prob: Optional[float] = None,
        confidence_score: Optional[int] = None,
        edge_state: str = "no_action",
        state_reasons: Optional[List[str]] = None
    ) -> Optional[RunSnapshot]:
        """
        Update snapshot with simulation outputs
        
        Call this after simulation completes.
        """
        snapshot = self._cache.get(run_id)
        if not snapshot:
            logger.warning(f"Snapshot {run_id} not found in cache")
            return None
        
        snapshot.model_spread = model_spread
        snapshot.model_total = model_total
        snapshot.spread_edge_pts = spread_edge_pts
        snapshot.total_edge_pts = total_edge_pts
        snapshot.home_win_prob = home_win_prob
        snapshot.over_prob = over_prob
        snapshot.confidence_score = confidence_score
        snapshot.edge_state = edge_state
        snapshot.state_reasons = state_reasons or []
        
        # Persist to database if available
        if self.db:
            try:
                self.db["run_snapshots"].update_one(
                    {"run_id": run_id},
                    {"$set": snapshot.to_dict()},
                    upsert=True
                )
            except Exception as e:
                logger.error(f"Failed to persist snapshot {run_id}: {e}")
        
        return snapshot
    
    def get_latest_snapshot(self, event_id: str) -> Optional[RunSnapshot]:
        """
        Get the latest snapshot for an event
        
        This is what page refresh should use - NO re-simulation.
        """
        # Check database first
        if self.db:
            try:
                doc = self.db["run_snapshots"].find_one(
                    {"event_id": event_id},
                    sort=[("created_at", -1)]
                )
                if doc:
                    doc.pop("_id", None)
                    return RunSnapshot.from_dict(doc)
            except Exception as e:
                logger.error(f"Failed to fetch snapshot for {event_id}: {e}")
        
        # Fall back to cache
        event_snapshots = [
            s for s in self._cache.values() 
            if s.event_id == event_id
        ]
        if event_snapshots:
            return max(event_snapshots, key=lambda s: s.created_at)
        
        return None
    
    def detect_changes(
        self,
        old_snapshot: RunSnapshot,
        new_market_spread: Optional[float] = None,
        new_market_total: Optional[float] = None,
        new_injuries: Optional[List[Dict[str, Any]]] = None,
        new_minutes: Optional[Dict[str, float]] = None
    ) -> ChangeDetectionResult:
        """
        Detect what changed between old snapshot and new inputs
        
        Use this before running a new simulation to explain changes to user.
        """
        change_types = []
        changes = []
        explanations = []
        
        # Check market line changes
        if new_market_spread is not None and old_snapshot.market_line_spread is not None:
            spread_diff = new_market_spread - old_snapshot.market_line_spread
            if abs(spread_diff) >= 0.5:
                change_types.append(ChangeType.LINE_MOVED)
                changes.append({
                    "type": "spread_line",
                    "old": old_snapshot.market_line_spread,
                    "new": new_market_spread,
                    "diff": spread_diff
                })
                direction = "up" if spread_diff > 0 else "down"
                explanations.append(f"Spread line moved {direction} {abs(spread_diff):.1f} pts")
        
        if new_market_total is not None and old_snapshot.market_line_total is not None:
            total_diff = new_market_total - old_snapshot.market_line_total
            if abs(total_diff) >= 0.5:
                change_types.append(ChangeType.LINE_MOVED)
                changes.append({
                    "type": "total_line",
                    "old": old_snapshot.market_line_total,
                    "new": new_market_total,
                    "diff": total_diff
                })
                direction = "up" if total_diff > 0 else "down"
                explanations.append(f"Total line moved {direction} {abs(total_diff):.1f} pts")
        
        # Check injury changes
        if new_injuries is not None:
            old_injury_set = {str(i) for i in old_snapshot.injuries_used}
            new_injury_set = {str(i) for i in new_injuries}
            
            if old_injury_set != new_injury_set:
                change_types.append(ChangeType.INJURY_UPDATE)
                added = new_injury_set - old_injury_set
                removed = old_injury_set - new_injury_set
                changes.append({
                    "type": "injuries",
                    "added": list(added),
                    "removed": list(removed)
                })
                if added:
                    explanations.append(f"New injury updates detected")
                if removed:
                    explanations.append(f"Injury status cleared")
        
        # Check minutes projection changes
        if new_minutes is not None:
            significant_changes = []
            for player, new_mins in new_minutes.items():
                old_mins = old_snapshot.minutes_projections.get(player)
                if old_mins is not None and abs(new_mins - old_mins) >= 3.0:
                    significant_changes.append({
                        "player": player,
                        "old": old_mins,
                        "new": new_mins
                    })
            
            if significant_changes:
                change_types.append(ChangeType.MINUTES_PROJECTION_CHANGE)
                changes.append({
                    "type": "minutes",
                    "players": significant_changes
                })
                explanations.append(f"Minutes projections updated for {len(significant_changes)} players")
        
        # Check inputs hash for any other changes
        new_hash = self.generate_inputs_hash(
            new_market_spread,
            new_market_total,
            new_injuries or [],
            new_minutes or {}
        )
        
        if new_hash != old_snapshot.inputs_hash and not change_types:
            change_types.append(ChangeType.NEW_SIMULATION)
            explanations.append("New simulation requested")
        
        has_changes = len(change_types) > 0
        
        if not has_changes:
            change_types.append(ChangeType.NO_CHANGE)
            explanations.append("No changes detected - using cached results")
        
        return ChangeDetectionResult(
            has_changes=has_changes,
            change_types=change_types,
            changes=changes,
            explanation=" | ".join(explanations) if explanations else "No changes"
        )


# Global instance
_snapshot_manager: Optional[RunSnapshotManager] = None


def get_snapshot_manager(db=None) -> RunSnapshotManager:
    """Get or create the global snapshot manager"""
    global _snapshot_manager
    if _snapshot_manager is None:
        _snapshot_manager = RunSnapshotManager(db)
    elif db is not None and _snapshot_manager.db is None:
        _snapshot_manager.db = db
    return _snapshot_manager
