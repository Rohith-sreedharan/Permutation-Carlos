"""
Integration Tests — Integrity Gates Hard-Lock Patch
====================================================

Comprehensive test suite for all integrity enforcement rules.

Tests:
1. Missing selection IDs block output
2. Missing snapshot identity blocks output
3. Probability mismatch blocks output  
4. Provider mapping drift blocks grading
5. Opposite selection invertibility
6. Canonical action payload enforcement
7. Parlay eligibility gates
8. Writer matrix enforcement

Author: System
Date: 2026-02-02
Version: v1.0.0 (Hard-Lock Patch)
"""

import pytest
from datetime import datetime
from unittest.mock import MagicMock, patch

from backend.services.pick_integrity_validator import (
    PickIntegrityValidator,
    OppositeSelectionResolver,
    ActionCopyMapper,
    CanonicalActionPayload,
    RecommendedAction,
    RecommendedReasonCode,
    TierLevel,
    IntegrityViolation
)
from backend.services.parlay_eligibility_gate import ParlayEligibilityGate
from backend.services.writer_matrix_enforcement import (
    WriterMatrixGuard,
    UnauthorizedWriteError,
    enforce_writer_matrix
)


# ============================================================================
# TEST 1: Missing Selection IDs Block Output
# ============================================================================

class TestMissingSelectionIDsBlock:
    """Requirement: Selection IDs are mandatory - NO recommendation without IDs"""
    
    def test_missing_home_selection_id_blocks(self):
        """Missing home_selection_id triggers CRITICAL violation"""
        db = MagicMock()
        validator = PickIntegrityValidator(db)
        
        pick_data = {
            "pick_id": "pick_123",
            "status": "PUBLISHED"
        }
        
        event_data = {}
        
        market_data = {
            "home_selection_id": None,  # ❌ MISSING
            "away_selection_id": "sel_away_456",
            "model_preference_selection_id": "sel_pref_789"
        }
        
        violations = validator.validate_pick_integrity(pick_data, event_data, market_data)
        
        # Assert violation detected
        assert len(violations) > 0
        assert any(v.violation_type == "SELECTION_ID_MISSING" for v in violations)
        assert any(v.field_name == "home_selection_id" for v in violations)
        assert any(v.severity == "CRITICAL" for v in violations)
    
    def test_missing_away_selection_id_blocks(self):
        """Missing away_selection_id triggers CRITICAL violation"""
        db = MagicMock()
        validator = PickIntegrityValidator(db)
        
        pick_data = {"pick_id": "pick_123", "status": "PUBLISHED"}
        event_data = {}
        market_data = {
            "home_selection_id": "sel_home_123",
            "away_selection_id": None,  # ❌ MISSING
            "model_preference_selection_id": "sel_pref_789"
        }
        
        violations = validator.validate_pick_integrity(pick_data, event_data, market_data)
        
        assert len(violations) > 0
        assert any(v.field_name == "away_selection_id" for v in violations)
    
    def test_missing_model_preference_id_blocks(self):
        """Missing model_preference_selection_id triggers CRITICAL violation"""
        db = MagicMock()
        validator = PickIntegrityValidator(db)
        
        pick_data = {"pick_id": "pick_123", "status": "PUBLISHED"}
        event_data = {}
        market_data = {
            "home_selection_id": "sel_home_123",
            "away_selection_id": "sel_away_456",
            "model_preference_selection_id": None  # ❌ MISSING
        }
        
        violations = validator.validate_pick_integrity(pick_data, event_data, market_data)
        
        assert len(violations) > 0
        assert any(v.field_name == "model_preference_selection_id" for v in violations)
    
    def test_blocked_payload_returned_when_ids_missing(self):
        """Blocked payload returned when IDs missing"""
        db = MagicMock()
        validator = PickIntegrityValidator(db)
        
        pick_data = {"pick_id": "pick_123", "market_type": "SPREAD"}
        violations = [
            IntegrityViolation(
                violation_type="SELECTION_ID_MISSING",
                field_name="home_selection_id",
                expected="Valid UUID",
                actual="null",
                severity="CRITICAL"
            )
        ]
        
        blocked_payload = validator.create_blocked_payload(violations, pick_data)
        
        # Assert blocked payload structure
        assert blocked_payload.recommended_action == RecommendedAction.NO_PLAY
        assert blocked_payload.recommended_reason_code == RecommendedReasonCode.INTEGRITY_BLOCKED
        assert blocked_payload.tier == TierLevel.BLOCKED
        assert blocked_payload.recommended_selection_id == "BLOCKED"


# ============================================================================
# TEST 2: Missing Snapshot Identity Blocks Output
# ============================================================================

class TestMissingSnapshotBlocks:
    """Requirement: Snapshot identity required for determinism"""
    
    def test_missing_snapshot_id_and_hash_blocks(self):
        """Missing both market_snapshot_id and snapshot_hash triggers violation"""
        db = MagicMock()
        db["market_snapshots"].find_one.return_value = None
        
        validator = PickIntegrityValidator(db)
        
        pick_data = {
            "pick_id": "pick_123",
            "market_snapshot_id": None,  # ❌ MISSING
            "snapshot_hash": None  # ❌ MISSING
        }
        
        event_data = {}
        market_data = {
            "home_selection_id": "sel_123",
            "away_selection_id": "sel_456",
            "model_preference_selection_id": "sel_789"
        }
        
        violations = validator.validate_pick_integrity(pick_data, event_data, market_data)
        
        assert len(violations) > 0
        assert any(v.violation_type == "SNAPSHOT_IDENTITY_MISSING" for v in violations)
    
    def test_invalid_snapshot_hash_blocks(self):
        """Snapshot hash that doesn't reference real snapshot triggers violation"""
        db = MagicMock()
        db["market_snapshots"].find_one.return_value = None  # No snapshot found
        
        validator = PickIntegrityValidator(db)
        
        pick_data = {
            "pick_id": "pick_123",
            "snapshot_hash": "invalid_hash_xyz"  # ❌ No matching snapshot
        }
        
        event_data = {}
        market_data = {
            "home_selection_id": "sel_123",
            "away_selection_id": "sel_456",
            "model_preference_selection_id": "sel_789"
        }
        
        violations = validator.validate_pick_integrity(pick_data, event_data, market_data)
        
        assert len(violations) > 0
        assert any(v.violation_type == "SNAPSHOT_HASH_INVALID" for v in violations)


# ============================================================================
# TEST 3: Probability Mismatch Blocks Output
# ============================================================================

class TestProbabilityMismatchBlocks:
    """Requirement: Display probability MUST match model probability"""
    
    def test_tile_vs_model_probability_mismatch_blocks(self):
        """Mismatch between tile_probability and model_probability blocks"""
        db = MagicMock()
        validator = PickIntegrityValidator(db, epsilon=0.0001)
        
        pick_data = {
            "pick_id": "pick_123",
            "tile_probability": 0.6000,  # Display says 60%
            "model_probability": 0.5411,  # Model says 54.11%
            # ❌ Mismatch > epsilon
            "market_snapshot_id": "snap_123"
        }
        
        event_data = {}
        market_data = {
            "home_selection_id": "sel_123",
            "away_selection_id": "sel_456",
            "model_preference_selection_id": "sel_789"
        }
        
        violations = validator.validate_pick_integrity(pick_data, event_data, market_data)
        
        assert len(violations) > 0
        assert any(v.violation_type == "PROBABILITY_MISMATCH" for v in violations)
        assert any("tile_probability" in v.field_name for v in violations)
    
    def test_model_vs_preference_probability_mismatch_blocks(self):
        """Mismatch between model and preference probabilities blocks"""
        db = MagicMock()
        validator = PickIntegrityValidator(db, epsilon=0.0001)
        
        pick_data = {
            "pick_id": "pick_123",
            "model_probability": 0.6000,
            "model_preference_probability": 0.4589,
            # ❌ Mismatch
            "market_snapshot_id": "snap_123"
        }
        
        event_data = {}
        market_data = {
            "home_selection_id": "sel_123",
            "away_selection_id": "sel_456",
            "model_preference_selection_id": "sel_789"
        }
        
        violations = validator.validate_pick_integrity(pick_data, event_data, market_data)
        
        assert len(violations) > 0
        assert any("model_preference_probability" in v.field_name for v in violations)
    
    def test_probability_within_epsilon_passes(self):
        """Probability difference within epsilon passes validation"""
        db = MagicMock()
        validator = PickIntegrityValidator(db, epsilon=0.001)
        
        pick_data = {
            "pick_id": "pick_123",
            "tile_probability": 0.5411,
            "model_probability": 0.5410,  # ✅ Within epsilon
            "market_snapshot_id": "snap_123"
        }
        
        event_data = {}
        market_data = {
            "home_selection_id": "sel_123",
            "away_selection_id": "sel_456",
            "model_preference_selection_id": "sel_789"
        }
        
        violations = validator.validate_pick_integrity(pick_data, event_data, market_data)
        
        # Should have no probability mismatch violations
        prob_violations = [v for v in violations if v.violation_type == "PROBABILITY_MISMATCH"]
        assert len(prob_violations) == 0


# ============================================================================
# TEST 4: Provider Mapping Drift Blocks Grading
# ============================================================================

class TestProviderMappingDrift:
    """Requirement: Provider drift detection freezes grading"""
    
    def test_missing_provider_id_blocks_when_external_grading(self):
        """Missing provider_event_map.oddsapi.event_id blocks external grading"""
        db = MagicMock()
        validator = PickIntegrityValidator(db)
        
        pick_data = {"pick_id": "pick_123", "market_snapshot_id": "snap_123"}
        
        event_data = {
            "event_id": "nba_lakers_warriors",
            "grade_source": "oddsapi",  # ✅ External grading required
            "provider_event_map": {
                "oddsapi": {
                    "event_id": None  # ❌ MISSING
                }
            }
        }
        
        market_data = {
            "home_selection_id": "sel_123",
            "away_selection_id": "sel_456",
            "model_preference_selection_id": "sel_789"
        }
        
        violations = validator.validate_pick_integrity(pick_data, event_data, market_data)
        
        assert len(violations) > 0
        assert any(v.violation_type == "PROVIDER_ID_MISSING" for v in violations)


# ============================================================================
# TEST 5: Opposite Selection Invertibility
# ============================================================================

class TestOppositeSelectionInvertibility:
    """Requirement: opposite(opposite(x)) == x"""
    
    def test_spread_opposite_is_invertible(self):
        """Spread: opposite(home) == away AND opposite(away) == home"""
        db = MagicMock()
        db["markets"].find_one.return_value = {
            "event_id": "event_123",
            "market_type": "SPREAD",
            "home_selection_id": "sel_home",
            "away_selection_id": "sel_away"
        }
        
        resolver = OppositeSelectionResolver(db)
        
        # Test home -> away -> home
        opposite_of_home = resolver.get_opposite_selection_id("event_123", "SPREAD", "sel_home")
        assert opposite_of_home == "sel_away"
        
        opposite_of_away = resolver.get_opposite_selection_id("event_123", "SPREAD", "sel_away")
        assert opposite_of_away == "sel_home"
        
        # Test invertibility
        assert resolver.validate_opposite_is_invertible("event_123", "SPREAD", "sel_home")
        assert resolver.validate_opposite_is_invertible("event_123", "SPREAD", "sel_away")
    
    def test_total_opposite_is_invertible(self):
        """Total: opposite(over) == under AND opposite(under) == over"""
        db = MagicMock()
        db["markets"].find_one.return_value = {
            "event_id": "event_123",
            "market_type": "TOTAL",
            "over_selection_id": "sel_over",
            "under_selection_id": "sel_under"
        }
        
        resolver = OppositeSelectionResolver(db)
        
        # Test over -> under -> over
        opposite_of_over = resolver.get_opposite_selection_id("event_123", "TOTAL", "sel_over")
        assert opposite_of_over == "sel_under"
        
        opposite_of_under = resolver.get_opposite_selection_id("event_123", "TOTAL", "sel_under")
        assert opposite_of_under == "sel_over"
        
        # Test invertibility
        assert resolver.validate_opposite_is_invertible("event_123", "TOTAL", "sel_over")


# ============================================================================
# TEST 6: Canonical Action Payload Enforcement
# ============================================================================

class TestCanonicalActionPayload:
    """Requirement: Canonical action payload must be complete"""
    
    def test_missing_recommended_action_blocks_published_pick(self):
        """Published pick missing recommended_action triggers violation"""
        db = MagicMock()
        validator = PickIntegrityValidator(db)
        
        pick_data = {
            "pick_id": "pick_123",
            "status": "PUBLISHED",  # ✅ Published
            "recommended_selection_id": "sel_123",
            "recommended_action": None,  # ❌ MISSING
            "recommended_reason_code": "EDGE_POSITIVE",
            "market_snapshot_id": "snap_123"
        }
        
        event_data = {}
        market_data = {
            "home_selection_id": "sel_123",
            "away_selection_id": "sel_456",
            "model_preference_selection_id": "sel_789"
        }
        
        violations = validator.validate_pick_integrity(pick_data, event_data, market_data)
        
        assert len(violations) > 0
        assert any(v.violation_type == "ACTION_PAYLOAD_INCOMPLETE" for v in violations)
        assert any(v.field_name == "recommended_action" for v in violations)
    
    def test_action_copy_mapper_no_legacy_phrases(self):
        """Action copy mapper rejects legacy phrases"""
        # Forbidden phrases
        assert not ActionCopyMapper.validate_no_legacy_phrases("Take dog")
        assert not ActionCopyMapper.validate_no_legacy_phrases("Lay points")
        assert not ActionCopyMapper.validate_no_legacy_phrases("Fade the public")
        
        # Approved phrases
        assert ActionCopyMapper.validate_no_legacy_phrases("Recommended Selection")
        assert ActionCopyMapper.validate_no_legacy_phrases("Take Opposite Side")


# ============================================================================
# TEST 7: Parlay Eligibility Gates
# ============================================================================

class TestParlayEligibilityGates:
    """Requirement: Blocked picks never eligible for parlay legs"""
    
    def test_blocked_pick_rejected_as_parlay_leg(self):
        """Pick with tier=BLOCKED rejected from parlay"""
        db = MagicMock()
        validator = PickIntegrityValidator(db)
        gate = ParlayEligibilityGate(db, validator)
        
        db["events"].find_one.return_value = {}
        db["market_snapshots"].find_one.return_value = {}
        
        candidates = [
            {
                "pick_id": "pick_blocked",
                "tier": "BLOCKED",  # ❌ BLOCKED
                "event_id": "event_1",
                "market_snapshot_id": "snap_1"
            }
        ]
        
        # Patch validator to return violations for blocked pick
        with patch.object(validator, 'validate_pick_integrity') as mock_validate:
            mock_validate.return_value = [
                IntegrityViolation("SELECTION_ID_MISSING", "home_selection_id", "UUID", "null", "CRITICAL")
            ]
            
            result = gate.filter_eligible_legs(candidates, min_required=1)
            
            assert result["eligible_count"] == 0
            assert result["blocked_count"] == 1
            assert not result["has_minimum"]
    
    def test_no_play_action_rejected_as_parlay_leg(self):
        """Pick with recommended_action=NO_PLAY rejected from parlay"""
        db = MagicMock()
        validator = PickIntegrityValidator(db)
        gate = ParlayEligibilityGate(db, validator)
        
        db["events"].find_one.return_value = {}
        db["market_snapshots"].find_one.return_value = {}
        
        candidates = [
            {
                "pick_id": "pick_no_play",
                "recommended_action": "NO_PLAY",  # ❌ NO_PLAY
                "tier": "STANDARD",
                "event_id": "event_1",
                "market_snapshot_id": "snap_1"
            }
        ]
        
        with patch.object(validator, 'validate_pick_integrity') as mock_validate:
            mock_validate.return_value = []  # No violations
            
            result = gate.filter_eligible_legs(candidates, min_required=1)
            
            # Should still be blocked due to NO_PLAY action
            assert result["eligible_count"] == 0
            assert result["blocked_count"] == 1


# ============================================================================
# TEST 8: Writer Matrix Enforcement
# ============================================================================

class TestWriterMatrixEnforcement:
    """Requirement: Unauthorized writes blocked at runtime"""
    
    def test_unauthorized_grading_write_blocked(self):
        """Unauthorized module writing to grading collection raises error"""
        guard = WriterMatrixGuard()
        
        with pytest.raises(UnauthorizedWriteError) as exc_info:
            guard.validate_write_permission(
                collection="grading",
                operation="update",
                caller_module="backend.core.omni_edge_ai"  # ❌ NOT ALLOWED
            )
        
        assert "not allowed to write" in str(exc_info.value)
    
    def test_authorized_grading_write_allowed(self):
        """Authorized module (UnifiedGradingService) can write to grading"""
        guard = WriterMatrixGuard()
        
        # Should NOT raise
        guard.validate_write_permission(
            collection="grading",
            operation="update",
            caller_module="backend.services.unified_grading_service_v2"  # ✅ ALLOWED
        )
    
    def test_admin_override_requires_audit_note(self):
        """Admin override without audit_note raises error"""
        guard = WriterMatrixGuard()
        
        with pytest.raises(UnauthorizedWriteError) as exc_info:
            guard.validate_write_permission(
                collection="grading",
                operation="update",
                caller_module="backend.admin_tools",
                admin_override=True,
                audit_note=None  # ❌ MISSING
            )
        
        assert "requires audit_note" in str(exc_info.value)
    
    def test_immutable_collection_insert_only(self):
        """Immutable collection (market_snapshots) allows insert only"""
        guard = WriterMatrixGuard()
        
        # Insert allowed
        guard.validate_write_permission(
            collection="market_snapshots",
            operation="insert",
            caller_module="backend.services.market_ingest_service"
        )
        
        # Update blocked
        with pytest.raises(UnauthorizedWriteError):
            guard.validate_write_permission(
                collection="market_snapshots",
                operation="update",
                caller_module="backend.services.market_ingest_service"
            )


# ============================================================================
# RUN TESTS
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
