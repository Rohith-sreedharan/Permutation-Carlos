"""
PickIntegrityValidator — Hard-Block Enforcement
================================================

Centralized validator that enforces integrity constraints and fails closed
when violations detected. NO inference, NO partial output, NO warnings.

Hard Rules:
- Missing selection IDs → BLOCKED (no recommendation)
- Missing snapshot identity → BLOCKED
- Probability mismatch → BLOCKED
- Provider mapping drift → BLOCKED (freeze grading)
- Action payload incomplete → BLOCKED

All downstream systems (UI, Telegram, Parlay, Publisher) MUST call this
validator before rendering/publishing.

Author: System
Date: 2026-02-02
Version: v1.0.0 (Hard-Lock Patch)
"""

import hashlib
from enum import Enum
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from datetime import datetime


class RecommendedAction(str, Enum):
    """Canonical action enum - NO INFERENCE ALLOWED"""
    TAKE_THIS = "TAKE_THIS"          # Bet the recommended selection
    TAKE_OPPOSITE = "TAKE_OPPOSITE"  # Bet the opposite selection
    NO_PLAY = "NO_PLAY"              # No actionable edge


class RecommendedReasonCode(str, Enum):
    """Why this action was recommended"""
    EDGE_POSITIVE = "EDGE_POSITIVE"           # Positive EV detected
    EDGE_NEGATIVE = "EDGE_NEGATIVE"           # Negative EV - take opposite
    BELOW_THRESHOLD = "BELOW_THRESHOLD"       # Edge too small
    INTEGRITY_BLOCKED = "INTEGRITY_BLOCKED"   # Missing IDs/data
    PROBABILITY_MISMATCH = "PROBABILITY_MISMATCH"
    SNAPSHOT_MISSING = "SNAPSHOT_MISSING"
    DRIFT_DETECTED = "DRIFT_DETECTED"


class TierLevel(str, Enum):
    """Pick tier classification"""
    SHARP = "SHARP"
    ALPHA = "ALPHA"
    TACTICAL = "TACTICAL"
    STANDARD = "STANDARD"
    BLOCKED = "BLOCKED"  # Integrity violations


@dataclass
class CanonicalActionPayload:
    """
    Single source of truth for recommendation output.
    
    UI, Telegram, Parlay MUST render ONLY from this payload.
    NO inference from edge sign, probabilities, or labels allowed.
    """
    recommended_selection_id: str
    recommended_action: RecommendedAction
    recommended_reason_code: RecommendedReasonCode
    tier: TierLevel
    
    # Metadata for rendering
    market_type: str
    line: Optional[float]
    odds: Optional[float]
    book: str
    
    # Integrity references
    market_snapshot_id: str
    snapshot_timestamp: datetime
    
    # Optional context (informational only - not for action inference)
    edge_percentage: Optional[float] = None
    model_fair_line: Optional[float] = None
    model_fair_probability: Optional[float] = None


@dataclass
class IntegrityViolation:
    """Records what integrity check failed"""
    violation_type: str
    field_name: str
    expected: str
    actual: str
    severity: str  # CRITICAL, WARNING


class PickIntegrityValidator:
    """
    Central validator - enforces integrity constraints.
    
    Usage:
        validator = PickIntegrityValidator(db, epsilon=0.0001)
        
        # Block if integrity fails
        violations = validator.validate_pick_integrity(pick_data)
        if violations:
            return canonical_blocked_payload(violations)
        
        # Safe to proceed
        return build_recommendation(pick_data)
    """
    
    def __init__(self, db, epsilon: float = 0.0001, strict_mode: bool = True):
        self.db = db
        self.epsilon = epsilon  # Probability mismatch tolerance
        self.strict_mode = strict_mode  # If True, ANY violation blocks
        
    def validate_pick_integrity(
        self,
        pick_data: Dict[str, Any],
        event_data: Dict[str, Any],
        market_data: Dict[str, Any]
    ) -> List[IntegrityViolation]:
        """
        Central integrity check - returns violations or empty list.
        
        Hard Rules Enforced:
        1. Selection IDs required (home, away, model_preference, recommended)
        2. Snapshot identity required (market_snapshot_id or snapshot_hash)
        3. Probability consistency (display == model within epsilon)
        4. Provider mapping present (if using external IDs)
        5. Action payload complete
        
        Returns:
            List of IntegrityViolation objects. If non-empty, output MUST be blocked.
        """
        violations = []
        
        # Rule 1: Selection IDs are mandatory
        violations.extend(self._validate_selection_ids(pick_data, market_data))
        
        # Rule 2: Snapshot identity required
        violations.extend(self._validate_snapshot_identity(pick_data, market_data))
        
        # Rule 3: Probability consistency
        violations.extend(self._validate_probability_consistency(pick_data))
        
        # Rule 4: Provider mapping (if external grading)
        violations.extend(self._validate_provider_mapping(event_data))
        
        # Rule 5: Action payload complete
        violations.extend(self._validate_action_payload(pick_data))
        
        return violations
    
    def _validate_selection_ids(
        self,
        pick_data: Dict[str, Any],
        market_data: Dict[str, Any]
    ) -> List[IntegrityViolation]:
        """
        HARD RULE: All selection IDs must be present.
        
        Required:
        - home_selection_id
        - away_selection_id
        - model_preference_selection_id
        - recommended_selection_id (after pick creation)
        """
        violations = []
        
        required_ids = [
            "home_selection_id",
            "away_selection_id",
            "model_preference_selection_id"
        ]
        
        for field in required_ids:
            value = market_data.get(field) or pick_data.get(field)
            
            if not value or value == "MISSING":
                violations.append(IntegrityViolation(
                    violation_type="SELECTION_ID_MISSING",
                    field_name=field,
                    expected="Valid UUID",
                    actual=str(value) if value else "null",
                    severity="CRITICAL"
                ))
        
        # Recommended selection (required for published picks only)
        if pick_data.get("status") == "PUBLISHED":
            rec_id = pick_data.get("recommended_selection_id")
            if not rec_id or rec_id == "MISSING":
                violations.append(IntegrityViolation(
                    violation_type="RECOMMENDED_SELECTION_MISSING",
                    field_name="recommended_selection_id",
                    expected="Valid UUID",
                    actual=str(rec_id) if rec_id else "null",
                    severity="CRITICAL"
                ))
        
        return violations
    
    def _validate_snapshot_identity(
        self,
        pick_data: Dict[str, Any],
        market_data: Dict[str, Any]
    ) -> List[IntegrityViolation]:
        """
        HARD RULE: Snapshot identity required for determinism.
        
        Accept either:
        - market_snapshot_id (preferred)
        - snapshot_hash (maps to immutable snapshot)
        """
        violations = []
        
        snapshot_id = pick_data.get("market_snapshot_id") or market_data.get("market_snapshot_id")
        snapshot_hash = pick_data.get("snapshot_hash") or market_data.get("snapshot_hash")
        
        if not snapshot_id and not snapshot_hash:
            violations.append(IntegrityViolation(
                violation_type="SNAPSHOT_IDENTITY_MISSING",
                field_name="market_snapshot_id / snapshot_hash",
                expected="UUID or hash string",
                actual="null",
                severity="CRITICAL"
            ))
        
        # If hash exists, verify it references a real snapshot
        if snapshot_hash and snapshot_hash != "MISSING":
            snapshot = self.db["market_snapshots"].find_one({"snapshot_hash": snapshot_hash})
            if not snapshot:
                violations.append(IntegrityViolation(
                    violation_type="SNAPSHOT_HASH_INVALID",
                    field_name="snapshot_hash",
                    expected="Valid snapshot reference",
                    actual=snapshot_hash,
                    severity="CRITICAL"
                ))
        
        return violations
    
    def _validate_probability_consistency(
        self,
        pick_data: Dict[str, Any]
    ) -> List[IntegrityViolation]:
        """
        HARD RULE: Display probability MUST match model probability.
        
        Mismatch indicates:
        - Stale UI state
        - Wrong payload wiring
        - Cross-market contamination
        
        Tolerance: self.epsilon (default 0.0001)
        """
        violations = []
        
        # Extract probabilities
        tile_prob = pick_data.get("tile_probability") or pick_data.get("display_probability")
        model_prob = pick_data.get("model_probability")
        model_pref_prob = pick_data.get("model_preference_probability")
        
        # Check tile vs model
        if tile_prob is not None and model_prob is not None:
            if abs(float(tile_prob) - float(model_prob)) > self.epsilon:
                violations.append(IntegrityViolation(
                    violation_type="PROBABILITY_MISMATCH",
                    field_name="tile_probability vs model_probability",
                    expected=str(model_prob),
                    actual=str(tile_prob),
                    severity="CRITICAL"
                ))
        
        # Check model vs preference
        if model_prob is not None and model_pref_prob is not None:
            if abs(float(model_prob) - float(model_pref_prob)) > self.epsilon:
                violations.append(IntegrityViolation(
                    violation_type="PROBABILITY_MISMATCH",
                    field_name="model_probability vs model_preference_probability",
                    expected=str(model_pref_prob),
                    actual=str(model_prob),
                    severity="CRITICAL"
                ))
        
        return violations
    
    def _validate_provider_mapping(
        self,
        event_data: Dict[str, Any]
    ) -> List[IntegrityViolation]:
        """
        HARD RULE: Provider mapping must exist for external grading.
        
        If using OddsAPI for grading, event MUST have:
        - provider_event_map.oddsapi.event_id
        """
        violations = []
        
        # Check if external grading required
        uses_external_grading = event_data.get("grade_source") == "oddsapi"
        
        if uses_external_grading:
            provider_map = event_data.get("provider_event_map", {})
            oddsapi_map = provider_map.get("oddsapi", {})
            oddsapi_event_id = oddsapi_map.get("event_id")
            
            if not oddsapi_event_id:
                violations.append(IntegrityViolation(
                    violation_type="PROVIDER_ID_MISSING",
                    field_name="provider_event_map.oddsapi.event_id",
                    expected="OddsAPI event ID",
                    actual="null",
                    severity="CRITICAL"
                ))
        
        return violations
    
    def _validate_action_payload(
        self,
        pick_data: Dict[str, Any]
    ) -> List[IntegrityViolation]:
        """
        HARD RULE: Canonical action payload must be complete.
        
        Required for published picks:
        - recommended_selection_id
        - recommended_action
        - recommended_reason_code
        """
        violations = []
        
        if pick_data.get("status") != "PUBLISHED":
            return violations  # Not required for draft picks
        
        required_fields = {
            "recommended_selection_id": "UUID",
            "recommended_action": "RecommendedAction enum",
            "recommended_reason_code": "RecommendedReasonCode enum"
        }
        
        for field, expected_type in required_fields.items():
            value = pick_data.get(field)
            
            if not value or value == "MISSING":
                violations.append(IntegrityViolation(
                    violation_type="ACTION_PAYLOAD_INCOMPLETE",
                    field_name=field,
                    expected=expected_type,
                    actual=str(value) if value else "null",
                    severity="CRITICAL"
                ))
        
        return violations
    
    def create_blocked_payload(
        self,
        violations: List[IntegrityViolation],
        pick_data: Dict[str, Any]
    ) -> CanonicalActionPayload:
        """
        Create canonical BLOCKED payload when integrity fails.
        
        This is what UI/Telegram/Parlay MUST render when violations exist.
        """
        return CanonicalActionPayload(
            recommended_selection_id="BLOCKED",
            recommended_action=RecommendedAction.NO_PLAY,
            recommended_reason_code=RecommendedReasonCode.INTEGRITY_BLOCKED,
            tier=TierLevel.BLOCKED,
            
            # Minimal safe metadata
            market_type=pick_data.get("market_type", "UNKNOWN"),
            line=None,
            odds=None,
            book="BLOCKED",
            
            # No snapshot (missing)
            market_snapshot_id="BLOCKED",
            snapshot_timestamp=datetime.utcnow(),
            
            # No edge data (unsafe)
            edge_percentage=None,
            model_fair_line=None,
            model_fair_probability=None
        )
    
    def emit_integrity_alert(
        self,
        violations: List[IntegrityViolation],
        pick_id: str,
        event_id: str
    ):
        """
        Emit operational alert when integrity violations detected.
        
        Alert includes all violations for debugging.
        """
        violation_details = [
            {
                "type": v.violation_type,
                "field": v.field_name,
                "expected": v.expected,
                "actual": v.actual,
                "severity": v.severity
            }
            for v in violations
        ]
        
        self.db["ops_alerts"].insert_one({
            "alert_type": "INTEGRITY_VIOLATIONS_DETECTED",
            "severity": "CRITICAL",
            "pick_id": pick_id,
            "event_id": event_id,
            "violations": violation_details,
            "violation_count": len(violations),
            "created_at": datetime.utcnow(),
            "resolved": False
        })


class OppositeSelectionResolver:
    """
    Deterministic opposite selection resolver.
    
    NO string matching. NO inference. Only canonical selection pairs.
    """
    
    def __init__(self, db):
        self.db = db
    
    def get_opposite_selection_id(
        self,
        event_id: str,
        market_type: str,
        selection_id: str
    ) -> Optional[str]:
        """
        Resolve opposite selection deterministically.
        
        Rules:
        - SPREAD: HOME <-> AWAY
        - ML: HOME <-> AWAY
        - TOTAL: OVER <-> UNDER
        - PROP: explicit pairs (future)
        
        Returns:
            Opposite selection_id or None if cannot resolve
        """
        # Fetch market snapshot with both selections
        market = self.db["markets"].find_one({
            "event_id": event_id,
            "market_type": market_type
        })
        
        if not market:
            return None
        
        home_id = market.get("home_selection_id")
        away_id = market.get("away_selection_id")
        over_id = market.get("over_selection_id")
        under_id = market.get("under_selection_id")
        
        # Deterministic mapping by market type
        if market_type in ["SPREAD", "MONEYLINE"]:
            if selection_id == home_id:
                return away_id
            elif selection_id == away_id:
                return home_id
        
        elif market_type == "TOTAL":
            if selection_id == over_id:
                return under_id
            elif selection_id == under_id:
                return over_id
        
        # Cannot resolve
        return None
    
    def validate_opposite_is_invertible(
        self,
        event_id: str,
        market_type: str,
        selection_id: str
    ) -> bool:
        """
        Property test: opposite(opposite(x)) == x
        
        Returns:
            True if invertible, False otherwise
        """
        opposite_id = self.get_opposite_selection_id(event_id, market_type, selection_id)
        
        if not opposite_id:
            return False
        
        double_opposite_id = self.get_opposite_selection_id(event_id, market_type, opposite_id)
        
        return double_opposite_id == selection_id


class ActionCopyMapper:
    """
    Maps canonical action to exact copy strings.
    
    NO conditional logic. NO heuristics. Strict mapping only.
    """
    
    # Canonical copy mapping (approved strings only)
    ACTION_COPY_MAP = {
        RecommendedAction.TAKE_THIS: "Recommended Selection",
        RecommendedAction.TAKE_OPPOSITE: "Take Opposite Side",
        RecommendedAction.NO_PLAY: "No Actionable Edge"
    }
    
    REASON_COPY_MAP = {
        RecommendedReasonCode.EDGE_POSITIVE: "Positive expected value detected",
        RecommendedReasonCode.EDGE_NEGATIVE: "Negative EV — opposite side recommended",
        RecommendedReasonCode.BELOW_THRESHOLD: "Edge below actionable threshold",
        RecommendedReasonCode.INTEGRITY_BLOCKED: "Integrity violation — output blocked",
        RecommendedReasonCode.PROBABILITY_MISMATCH: "Probability mismatch detected",
        RecommendedReasonCode.SNAPSHOT_MISSING: "Market snapshot missing",
        RecommendedReasonCode.DRIFT_DETECTED: "Provider mapping drift detected"
    }
    
    @classmethod
    def get_action_copy(cls, action: RecommendedAction) -> str:
        """Get exact copy for action - NO variations allowed"""
        return cls.ACTION_COPY_MAP[action]
    
    @classmethod
    def get_reason_copy(cls, reason: RecommendedReasonCode) -> str:
        """Get exact copy for reason - NO variations allowed"""
        return cls.REASON_COPY_MAP[reason]
    
    @classmethod
    def validate_no_legacy_phrases(cls, copy_text: str) -> bool:
        """
        Ensure no legacy phrases exist in copy.
        
        Forbidden phrases:
        - "take dog" / "take the dog"
        - "lay points"
        - "fade"
        - Any conditional logic based on favorite/underdog
        """
        forbidden_phrases = [
            "take dog",
            "take the dog",
            "lay points",
            "lay the points",
            "fade",
            "underdog getting",
            "favorite laying"
        ]
        
        copy_lower = copy_text.lower()
        
        for phrase in forbidden_phrases:
            if phrase in copy_lower:
                return False
        
        return True
