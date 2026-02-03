"""
Unified Grading Service — SINGLE SOURCE OF TRUTH (v2.0)
=======================================================

This is the ONLY service allowed to grade picks and write settlement results.

Version: 2.0
Generated: February 2, 2026

NEW IN V2.0:
- Rules versioning (settlement + CLV)
- Idempotency key (pick_id + grade_source + rules_versions)
- Score payload reference (audit trail)
- Provider mapping drift detection
- Ops alerts for missing data/drift
- Hard blocking of fuzzy matching

CANONICAL GRADING PIPELINE:
1. Read pick from ai_picks
2. Load event with provider_event_map.oddsapi.event_id
3. Fetch score by EXACT OddsAPI ID (no fuzzy matching allowed)
4. Validate provider mapping (detect drift)
5. Determine settlement (WIN/LOSS/PUSH/VOID) using versioned rules
6. Compute CLV using closing snapshot (non-blocking)
7. Generate idempotency key
8. Write to grading collection with score payload reference
9. Optionally mirror to ai_picks (denormalized)

🔒 LOCKED: All other grading paths must be disabled/retired
"""

from typing import Optional, Dict, Any
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
import logging
import hashlib
import json

logger = logging.getLogger(__name__)

# Rules Versioning Constants
SETTLEMENT_RULES_VERSION = "v1.0.0"  # Spread/ML/Total settlement logic
CLV_RULES_VERSION = "v1.0.0"         # CLV calculation methodology
GRADE_SOURCE = "unified_grading_service"


class BetStatus(str, Enum):
    """Bet status for grading"""
    PENDING = "PENDING"
    SETTLED = "SETTLED"
    VOID = "VOID"
    NO_ACTION = "NO_ACTION"


class ResultCode(str, Enum):
    """Settlement result codes"""
    WIN = "WIN"
    LOSS = "LOSS"
    PUSH = "PUSH"
    VOID = "VOID"


# Custom Exceptions
class PickNotFoundError(Exception):
    pass


class EventNotFoundError(Exception):
    pass


class MissingOddsAPIIDError(Exception):
    pass


class GameNotCompletedError(Exception):
    pass


class ProviderMappingDriftError(Exception):
    """Raised when provider event mapping changes unexpectedly"""
    pass


@dataclass
class ScoreData:
    """OddsAPI score structure"""
    oddsapi_event_id: str
    home_team: str
    away_team: str
    home_score: int
    away_score: int
    completed: bool
    last_update: str


@dataclass
class GradingResult:
    """Result of grading a pick"""
    pick_id: str
    settlement_status: str  # WIN | LOSS | PUSH | VOID
    clv: Optional[Dict[str, Any]]
    graded_at: str
    grading_idempotency_key: str  # Unique key for deduplication
    settlement_rules_version: str
    clv_rules_version: str


class UnifiedGradingService:
    """
    Single source of truth for ALL pick grading.
    
    Hard Rules (v2.0):
    1. ONLY this service writes to grading collection
    2. Exact OddsAPI ID lookup (no fuzzy matching allowed)
    3. Missing CLV doesn't block settlement
    4. Idempotent (unique key: pick_id + grade_source + rules_versions)
    5. Admin overrides require audit note
    6. Rules versioning for historical replay
    7. Provider drift detection (event mapping validation)
    8. Score payload stored for dispute resolution
    9. Ops alerts for missing data/drift
    """
    
    def __init__(self, db, mirror_to_ai_picks: bool = False):
        self.db = db
        self.logger = logging.getLogger(__name__)
        self.mirror_to_ai_picks = mirror_to_ai_picks
        self.settlement_rules_version = SETTLEMENT_RULES_VERSION
        self.clv_rules_version = CLV_RULES_VERSION
        self.grade_source = GRADE_SOURCE
    
    async def grade_pick(
        self,
        pick_id: str,
        admin_override: Optional[str] = None,
        admin_note: Optional[str] = None
    ) -> GradingResult:
        """
        Grade a single pick using canonical grading pipeline.
        
        This is the ONLY way to grade picks. All other systems must call this.
        
        Args:
            pick_id: Unique pick identifier
            admin_override: Optional admin settlement override (WIN|LOSS|PUSH|VOID)
            admin_note: Required if admin_override is provided
            
        Returns:
            GradingResult with settlement status, CLV, idempotency key, rules versions
            
        Raises:
            PickNotFoundError: pick_id doesn't exist
            EventNotFoundError: event_id doesn't exist
            MissingOddsAPIIDError: event missing provider_event_map.oddsapi.event_id
            GameNotCompletedError: game not finished yet
            ProviderMappingDriftError: provider event mapping changed unexpectedly
            ValueError: admin_override without admin_note
        """
        # Validate admin override
        if admin_override and not admin_note:
            raise ValueError("admin_override requires admin_note for audit trail")
        
        self.logger.info(f"Grading pick: {pick_id}")
        
        # Fetch pick
        pick = self.db["ai_picks"].find_one({"pick_id": pick_id})
        if not pick:
            raise PickNotFoundError(f"Pick {pick_id} not found")
        
        # Fetch event
        event_id = pick.get("event_id")
        event = self.db["events"].find_one({"event_id": event_id})
        if not event:
            raise EventNotFoundError(f"Event {event_id} not found")
        
        # Get OddsAPI event ID (REQUIRED)
        oddsapi_event_id = self._get_oddsapi_event_id(event)
        if not oddsapi_event_id:
            self._emit_ops_alert(
                alert_type="PROVIDER_ID_MISSING",
                event_id=event_id,
                details=f"Event missing provider_event_map.oddsapi.event_id"
            )
            raise MissingOddsAPIIDError(
                f"Event {event_id} missing provider_event_map.oddsapi.event_id. "
                "Run backfill script to add OddsAPI ID."
            )
        
        # Fetch score (exact ID lookup only)
        score_data = await self._fetch_score_by_oddsapi_id(oddsapi_event_id)
        if not score_data:
            raise GameNotCompletedError(f"Game {event_id} not completed yet")
        
        # Provider drift detection
        self._validate_provider_mapping(event, score_data, oddsapi_event_id)
        
        # Determine settlement
        if admin_override:
            settlement_status = admin_override
            self.logger.info(f"Using admin override: {settlement_status}")
        else:
            settlement_status = self._determine_settlement(pick, score_data)
        
        # Compute CLV (non-blocking)
        clv = self._compute_clv(pick)
        if clv is None:
            self.logger.warning(f"CLV unavailable for {pick_id} (missing snapshot)")
            self._emit_ops_alert(
                alert_type="CLOSE_SNAPSHOT_MISSING",
                pick_id=pick_id,
                event_id=event_id,
                details="Cannot compute CLV - closing snapshot not found"
            )
        
        # Generate idempotency key
        idempotency_key = self._generate_idempotency_key(
            pick_id=pick_id,
            grade_source=self.grade_source,
            settlement_rules_version=self.settlement_rules_version,
            clv_rules_version=self.clv_rules_version
        )
        
        # Write grading record (canonical storage)
        graded_at = datetime.now(timezone.utc).isoformat()
        await self._write_grading_record(
            pick_id=pick_id,
            event_id=event_id,
            settlement_status=settlement_status,
            score_data=score_data,
            clv=clv,
            graded_at=graded_at,
            admin_override=admin_override,
            admin_note=admin_note,
            idempotency_key=idempotency_key,
            oddsapi_event_id=oddsapi_event_id
        )
        
        # Optional: Mirror to ai_picks (denormalized convenience)
        if self.mirror_to_ai_picks:
            await self._mirror_to_ai_picks(pick_id, settlement_status, clv, graded_at)
        
        return GradingResult(
            pick_id=pick_id,
            settlement_status=settlement_status,
            clv=clv,
            graded_at=graded_at,
            grading_idempotency_key=idempotency_key,
            settlement_rules_version=self.settlement_rules_version,
            clv_rules_version=self.clv_rules_version
        )
    
    def _generate_idempotency_key(
        self,
        pick_id: str,
        grade_source: str,
        settlement_rules_version: str,
        clv_rules_version: str
    ) -> str:
        """
        Generate unique idempotency key for grading.
        
        This prevents duplicate grading records even if rules change.
        Key includes pick_id + source + rules versions.
        
        Format: SHA256(pick_id|source|settlement_version|clv_version)[:32]
        """
        key_components = "|".join([
            pick_id,
            grade_source,
            settlement_rules_version,
            clv_rules_version
        ])
        
        return hashlib.sha256(key_components.encode()).hexdigest()[:32]
    
    def _get_oddsapi_event_id(self, event: Dict[str, Any]) -> Optional[str]:
        """Extract OddsAPI event ID from event"""
        # Try preferred location
        provider_map = event.get("provider_event_map", {})
        oddsapi_map = provider_map.get("oddsapi", {})
        oddsapi_event_id = oddsapi_map.get("event_id")
        
        # Fallback to legacy field (if exists)
        if not oddsapi_event_id:
            oddsapi_event_id = event.get("oddsapi_event_id")
        
        return oddsapi_event_id
    
    def _validate_provider_mapping(
        self,
        event: Dict[str, Any],
        score_data: Dict[str, Any],
        oddsapi_event_id: str
    ):
        """
        Detect provider mapping drift.
        
        Validates that OddsAPI event ID still maps to expected teams.
        Prevents grading wrong game if OddsAPI changes event IDs.
        
        Raises:
            ProviderMappingDriftError: If team mismatch detected
        """
        event_home = event.get("home_team", "").strip().lower()
        event_away = event.get("away_team", "").strip().lower()
        
        score_home = score_data.get("home_team", "").strip().lower()
        score_away = score_data.get("away_team", "").strip().lower()
        
        # Check for team mismatch (drift)
        if event_home != score_home or event_away != score_away:
            self._emit_ops_alert(
                alert_type="MAPPING_DRIFT",
                event_id=event["event_id"],
                oddsapi_event_id=oddsapi_event_id,
                details=(
                    f"Team mismatch detected. "
                    f"Event: {event_home} vs {event_away}. "
                    f"Score: {score_home} vs {score_away}. "
                    f"FREEZING grading for this event."
                )
            )
            raise ProviderMappingDriftError(
                f"Provider mapping drift detected for event {event['event_id']}. "
                f"Expected {event_home} vs {event_away}, "
                f"but OddsAPI returned {score_home} vs {score_away}. "
                f"Grading frozen until resolved."
            )
    
    def _emit_ops_alert(
        self,
        alert_type: str,
        **kwargs
    ):
        """
        Emit operational alert for monitoring.
        
        Alert types:
        - PROVIDER_ID_MISSING: Event missing OddsAPI ID
        - CLOSE_SNAPSHOT_MISSING: Cannot compute CLV
        - MAPPING_DRIFT: Provider mapping changed unexpectedly
        """
        alert = {
            "alert_type": alert_type,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "source": "unified_grading_service",
            **kwargs
        }
        
        # Write to ops_alerts collection
        try:
            self.db["ops_alerts"].insert_one(alert)
            self.logger.warning(f"OPS_ALERT: {alert_type} - {kwargs}")
        except Exception as e:
            self.logger.error(f"Failed to emit ops_alert: {e}")
    
    async def _fetch_score_by_oddsapi_id(
        self,
        oddsapi_event_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Fetch final score using exact OddsAPI event ID.
        
        ⚠️ CRITICAL: No fuzzy matching allowed. Exact ID lookup only.
        
        Args:
            oddsapi_event_id: Exact OddsAPI event ID
            
        Returns:
            Score data dict or None if not completed
        """
        # Import here to avoid circular dependency
        from services.result_service import ResultService
        
        result_service = ResultService()
        score = await result_service.fetch_scores_by_oddsapi_id(oddsapi_event_id)
        
        return score
    
    def _determine_settlement(
        self,
        pick: Dict[str, Any],
        score_data: Dict[str, Any]
    ) -> str:
        """
        Determine settlement using canonical rules (versioned).
        
        Settlement Rules Version: v1.0.0
        
        Returns:
            "WIN" | "LOSS" | "PUSH" | "VOID"
        """
        market_type = pick.get("market_type", "").lower()
        
        if market_type == "spread":
            return self._grade_spread(pick, score_data)
        elif market_type in ["h2h", "moneyline", "ml"]:
            return self._grade_moneyline(pick, score_data)
        elif market_type in ["totals", "total"]:
            return self._grade_total(pick, score_data)
        else:
            self.logger.error(f"Unknown market type: {market_type}")
            return "VOID"
    
    def _grade_spread(
        self,
        pick: Dict[str, Any],
        score_data: Dict[str, Any]
    ) -> str:
        """Grade spread pick"""
        home_score = score_data["home_score"]
        away_score = score_data["away_score"]
        actual_margin = home_score - away_score
        
        # Extract market line and team
        market_line = pick.get("market_line")
        market_selection = pick.get("market_selection", "")
        
        # Determine if pick was on home or away
        is_home_pick = "home" in market_selection.lower() or score_data["home_team"].lower() in market_selection.lower()
        
        if is_home_pick:
            # Picked home team
            cover_margin = actual_margin - market_line
        else:
            # Picked away team
            cover_margin = -actual_margin - market_line
        
        if cover_margin > 0:
            return "WIN"
        elif cover_margin < 0:
            return "LOSS"
        else:
            return "PUSH"
    
    def _grade_moneyline(
        self,
        pick: Dict[str, Any],
        score_data: Dict[str, Any]
    ) -> str:
        """Grade moneyline pick"""
        home_score = score_data["home_score"]
        away_score = score_data["away_score"]
        
        market_selection = pick.get("market_selection", "")
        is_home_pick = "home" in market_selection.lower() or score_data["home_team"].lower() in market_selection.lower()
        
        if home_score > away_score:
            return "WIN" if is_home_pick else "LOSS"
        elif home_score < away_score:
            return "LOSS" if is_home_pick else "WIN"
        else:
            return "PUSH"
    
    def _grade_total(
        self,
        pick: Dict[str, Any],
        score_data: Dict[str, Any]
    ) -> str:
        """Grade total (over/under) pick"""
        home_score = score_data["home_score"]
        away_score = score_data["away_score"]
        actual_total = home_score + away_score
        
        market_line = pick.get("market_line")
        market_selection = pick.get("market_selection", "").lower()
        
        is_over = "over" in market_selection
        
        if actual_total > market_line:
            return "WIN" if is_over else "LOSS"
        elif actual_total < market_line:
            return "LOSS" if is_over else "WIN"
        else:
            return "PUSH"
    
    def _compute_clv(self, pick: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Compute Closing Line Value (CLV) using snapshot.
        
        CLV Rules Version: v1.0.0
        
        Non-blocking: Returns None if snapshot missing.
        """
        snapshot_odds = pick.get("snapshot_odds")
        closing_odds = pick.get("closing_line_decimal")
        
        if not snapshot_odds or not closing_odds:
            return None
        
        # CLV calculation
        clv_points = closing_odds - snapshot_odds
        clv_percentage = (clv_points / snapshot_odds) * 100
        
        return {
            "snapshot_line": snapshot_odds,
            "closing_line": closing_odds,
            "clv_points": round(clv_points, 3),
            "clv_percentage": round(clv_percentage, 2)
        }
    
    async def _write_grading_record(
        self,
        pick_id: str,
        event_id: str,
        settlement_status: str,
        score_data: Dict[str, Any],
        clv: Optional[Dict[str, Any]],
        graded_at: str,
        idempotency_key: str,
        oddsapi_event_id: str,
        admin_override: Optional[str] = None,
        admin_note: Optional[str] = None
    ):
        """
        Write grading record to canonical grading collection.
        
        Idempotent via grading_idempotency_key unique constraint.
        """
        # Store score payload reference (for audit/replay)
        score_payload_hash = hashlib.sha256(
            json.dumps(score_data, sort_keys=True).encode()
        ).hexdigest()
        
        grading_record = {
            "pick_id": pick_id,
            "event_id": event_id,
            "settlement_status": settlement_status,
            
            # Actual score used for grading
            "actual_score": {
                "home": score_data["home_score"],
                "away": score_data["away_score"]
            },
            
            # Score payload reference (for dispute resolution)
            "score_payload_ref": {
                "oddsapi_event_id": oddsapi_event_id,
                "payload_hash": score_payload_hash,
                "payload_snapshot": score_data  # Full payload for audit
            },
            
            # CLV
            "clv": clv,
            
            # Grading metadata
            "graded_at": graded_at,
            "grade_source": self.grade_source,
            "grading_idempotency_key": idempotency_key,
            
            # Rules versioning (for historical replay)
            "settlement_rules_version": self.settlement_rules_version,
            "clv_rules_version": self.clv_rules_version,
            
            # Admin override audit
            "admin_override": admin_override,
            "admin_note": admin_note if admin_override else None
        }
        
        # Write to grading collection (idempotent via grading_idempotency_key)
        try:
            self.db["grading"].update_one(
                {"grading_idempotency_key": idempotency_key},
                {"$set": grading_record},
                upsert=True
            )
            self.logger.info(
                f"Grading record written for {pick_id} "
                f"(idempotency_key: {idempotency_key})"
            )
        except Exception as e:
            self.logger.error(f"Failed to write grading record: {e}")
            raise
    
    async def _mirror_to_ai_picks(
        self,
        pick_id: str,
        settlement_status: str,
        clv: Optional[Dict[str, Any]],
        graded_at: str
    ):
        """
        Optional: Mirror grading result to ai_picks collection.
        
        This is a denormalized convenience field only.
        Canonical source is always grading collection.
        """
        try:
            self.db["ai_picks"].update_one(
                {"pick_id": pick_id},
                {
                    "$set": {
                        "outcome": settlement_status.lower(),
                        "clv_pct": clv["clv_percentage"] if clv else None,
                        "settled_at": graded_at
                    }
                }
            )
            self.logger.info(f"Mirrored grading to ai_picks for {pick_id}")
        except Exception as e:
            self.logger.error(f"Failed to mirror to ai_picks: {e}")
            # Don't raise - mirror is optional
