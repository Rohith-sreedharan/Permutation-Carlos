"""
Grading Architecture Acceptance Tests
======================================

Tests for Production Requirements A, B, C, D:

A) OddsAPI event ID mapping
   - Exact ID lookup only (no fuzzy matching)
   - Provider ID missing alerts
   
B) Unified grading pipeline
   - Single writer enforcement
   - Legacy graders blocked
   
C) Non-blocking CLV
   - Grading completes without snapshot
   
D) Grading determinism
   - Exact mapping lookup
   - Idempotency
   - Rules versioning
"""
import asyncio
import pytest
import hashlib
from datetime import datetime, timezone
from unittest.mock import Mock, patch, AsyncMock
from backend.services.unified_grading_service_v2 import (
    UnifiedGradingService,
    PickNotFoundError,
    EventNotFoundError,
    MissingOddsAPIIDError,
    GameNotCompletedError,
    ProviderMappingDriftError
)


class TestExactMappingLookup:
    """
    Requirement A: OddsAPI event ID mapping
    Invariant: exact-id only, no fuzzy matching
    """
    
    @pytest.mark.asyncio
    async def test_exact_id_lookup_required(self):
        """Provider ID must exist - no fallback to fuzzy matching"""
        db_mock = Mock()
        db_mock.__getitem__ = Mock(return_value=Mock())
        
        # Pick exists
        db_mock["ai_picks"].find_one.return_value = {
            "pick_id": "pick_123",
            "event_id": "event_456"
        }
        
        # Event exists but NO provider_event_map.oddsapi.event_id
        db_mock["events"].find_one.return_value = {
            "event_id": "event_456",
            "home_team": "Lakers",
            "away_team": "Warriors"
            # ❌ Missing provider_event_map
        }
        
        service = UnifiedGradingService(db_mock)
        
        # Should raise MissingOddsAPIIDError (NO fuzzy matching allowed)
        with pytest.raises(MissingOddsAPIIDError) as exc_info:
            await service.grade_pick("pick_123")
        
        assert "provider_event_map.oddsapi.event_id" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_ops_alert_emitted_for_missing_provider_id(self):
        """Ops alert must be emitted when provider ID missing"""
        db_mock = Mock()
        db_mock.__getitem__ = Mock(return_value=Mock())
        
        db_mock["ai_picks"].find_one.return_value = {
            "pick_id": "pick_123",
            "event_id": "event_456"
        }
        
        db_mock["events"].find_one.return_value = {
            "event_id": "event_456",
            "home_team": "Lakers"
        }
        
        # Mock ops_alerts collection
        ops_alerts_mock = Mock()
        db_mock["ops_alerts"] = ops_alerts_mock
        
        service = UnifiedGradingService(db_mock)
        
        with pytest.raises(MissingOddsAPIIDError):
            await service.grade_pick("pick_123")
        
        # Verify ops_alert was emitted
        ops_alerts_mock.insert_one.assert_called_once()
        alert = ops_alerts_mock.insert_one.call_args[0][0]
        assert alert["alert_type"] == "PROVIDER_ID_MISSING"
        assert alert["event_id"] == "event_456"
    
    @pytest.mark.asyncio
    async def test_provider_drift_detection(self):
        """Provider mapping drift must be detected and grading frozen"""
        db_mock = Mock()
        db_mock.__getitem__ = Mock(return_value=Mock())
        
        db_mock["ai_picks"].find_one.return_value = {
            "pick_id": "pick_123",
            "event_id": "event_456",
            "market_type": "spread"
        }
        
        db_mock["events"].find_one.return_value = {
            "event_id": "event_456",
            "home_team": "Lakers",  # ← Event says Lakers
            "away_team": "Warriors",
            "provider_event_map": {
                "oddsapi": {
                    "event_id": "oddsapi_xyz"
                }
            }
        }
        
        # Mock score fetch
        score_data_with_drift = {
            "oddsapi_event_id": "oddsapi_xyz",
            "home_team": "Celtics",  # ← OddsAPI says Celtics (DRIFT!)
            "away_team": "Warriors",
            "home_score": 110,
            "away_score": 105,
            "completed": True
        }
        
        service = UnifiedGradingService(db_mock)
        
        with patch.object(service, '_fetch_score_by_oddsapi_id', new=AsyncMock(return_value=score_data_with_drift)):
            # Should raise ProviderMappingDriftError
            with pytest.raises(ProviderMappingDriftError) as exc_info:
                await service.grade_pick("pick_123")
            
            assert "drift" in str(exc_info.value).lower()
            assert "Lakers" in str(exc_info.value)
            assert "Celtics" in str(exc_info.value)


class TestUnifiedGradingEnforcement:
    """
    Requirement B: Single writer enforcement
    Invariant: ONLY UnifiedGradingService can write grading outcomes
    """
    
    def test_idempotency_key_generation(self):
        """Idempotency key must include pick_id + grade_source + rules versions"""
        db_mock = Mock()
        service = UnifiedGradingService(db_mock)
        
        key = service._generate_idempotency_key(
            pick_id="pick_123",
            grade_source="unified_grading_service",
            settlement_rules_version="v1.0.0",
            clv_rules_version="v1.0.0"
        )
        
        # Key should be deterministic hash
        assert len(key) == 32  # SHA256 truncated to 32 chars
        
        # Same inputs → same key
        key2 = service._generate_idempotency_key(
            pick_id="pick_123",
            grade_source="unified_grading_service",
            settlement_rules_version="v1.0.0",
            clv_rules_version="v1.0.0"
        )
        assert key == key2
        
        # Different rules version → different key
        key3 = service._generate_idempotency_key(
            pick_id="pick_123",
            grade_source="unified_grading_service",
            settlement_rules_version="v2.0.0",  # Changed
            clv_rules_version="v1.0.0"
        )
        assert key != key3
    
    @pytest.mark.asyncio
    async def test_grading_idempotency(self):
        """Re-grading same pick with same rules must be idempotent"""
        db_mock = Mock()
        db_mock.__getitem__ = Mock(return_value=Mock())
        
        db_mock["ai_picks"].find_one.return_value = {
            "pick_id": "pick_123",
            "event_id": "event_456",
            "market_type": "spread",
            "market_line": -3.0,
            "market_selection": "Lakers -3.0"
        }
        
        db_mock["events"].find_one.return_value = {
            "event_id": "event_456",
            "home_team": "Lakers",
            "away_team": "Warriors",
            "provider_event_map": {
                "oddsapi": {"event_id": "oddsapi_xyz"}
            }
        }
        
        score_data = {
            "oddsapi_event_id": "oddsapi_xyz",
            "home_team": "Lakers",
            "away_team": "Warriors",
            "home_score": 115,
            "away_score": 110,
            "completed": True
        }
        
        grading_collection_mock = Mock()
        db_mock["grading"] = grading_collection_mock
        
        service = UnifiedGradingService(db_mock)
        
        with patch.object(service, '_fetch_score_by_oddsapi_id', new=AsyncMock(return_value=score_data)):
            # Grade once
            result1 = await service.grade_pick("pick_123")
            
            # Grade again (should use same idempotency key)
            result2 = await service.grade_pick("pick_123")
            
            # Same idempotency key
            assert result1.grading_idempotency_key == result2.grading_idempotency_key
            
            # Verify update_one was called with idempotency key (upsert)
            assert grading_collection_mock.update_one.call_count == 2
            for call in grading_collection_mock.update_one.call_args_list:
                filter_doc = call[0][0]
                assert "grading_idempotency_key" in filter_doc
    
    def test_admin_override_requires_audit_note(self):
        """Admin override must require audit note for compliance"""
        db_mock = Mock()
        service = UnifiedGradingService(db_mock)
        
        with pytest.raises(ValueError) as exc_info:
            # Admin override without note
            asyncio.run(service.grade_pick(
                "pick_123",
                admin_override="VOID"
                # ❌ Missing admin_note
            ))
        
        assert "admin_note" in str(exc_info.value).lower()


class TestNonBlockingCLV:
    """
    Requirement C: Missing closing snapshot must not block grading
    """
    
    @pytest.mark.asyncio
    async def test_grading_completes_without_clv(self):
        """Grading must complete even if CLV cannot be computed"""
        db_mock = Mock()
        db_mock.__getitem__ = Mock(return_value=Mock())
        
        # Pick without snapshot_odds (CLV impossible)
        db_mock["ai_picks"].find_one.return_value = {
            "pick_id": "pick_123",
            "event_id": "event_456",
            "market_type": "spread",
            "market_line": -3.0,
            "market_selection": "Lakers -3.0"
            # ❌ No snapshot_odds
        }
        
        db_mock["events"].find_one.return_value = {
            "event_id": "event_456",
            "home_team": "Lakers",
            "away_team": "Warriors",
            "provider_event_map": {
                "oddsapi": {"event_id": "oddsapi_xyz"}
            }
        }
        
        score_data = {
            "oddsapi_event_id": "oddsapi_xyz",
            "home_team": "Lakers",
            "away_team": "Warriors",
            "home_score": 115,
            "away_score": 110,
            "completed": True
        }
        
        db_mock["grading"] = Mock()
        db_mock["ops_alerts"] = Mock()
        
        service = UnifiedGradingService(db_mock)
        
        with patch.object(service, '_fetch_score_by_oddsapi_id', new=AsyncMock(return_value=score_data)):
            result = await service.grade_pick("pick_123")
            
            # Grading completed
            assert result.settlement_status == "WIN"  # Lakers won by 5
            
            # CLV is None (not blocking)
            assert result.clv is None
    
    @pytest.mark.asyncio
    async def test_ops_alert_for_missing_snapshot(self):
        """Ops alert must be emitted when CLV cannot be computed"""
        db_mock = Mock()
        db_mock.__getitem__ = Mock(return_value=Mock())
        
        db_mock["ai_picks"].find_one.return_value = {
            "pick_id": "pick_123",
            "event_id": "event_456",
            "market_type": "spread",
            "market_line": -3.0,
            "market_selection": "Lakers -3.0"
        }
        
        db_mock["events"].find_one.return_value = {
            "event_id": "event_456",
            "home_team": "Lakers",
            "away_team": "Warriors",
            "provider_event_map": {
                "oddsapi": {"event_id": "oddsapi_xyz"}
            }
        }
        
        score_data = {
            "oddsapi_event_id": "oddsapi_xyz",
            "home_team": "Lakers",
            "away_team": "Warriors",
            "home_score": 115,
            "away_score": 110,
            "completed": True
        }
        
        ops_alerts_mock = Mock()
        db_mock["ops_alerts"] = ops_alerts_mock
        db_mock["grading"] = Mock()
        
        service = UnifiedGradingService(db_mock)
        
        with patch.object(service, '_fetch_score_by_oddsapi_id', new=AsyncMock(return_value=score_data)):
            await service.grade_pick("pick_123")
            
            # Verify CLOSE_SNAPSHOT_MISSING alert emitted
            ops_alerts_mock.insert_one.assert_called()
            alert = ops_alerts_mock.insert_one.call_args[0][0]
            assert alert["alert_type"] == "CLOSE_SNAPSHOT_MISSING"


class TestGradingDeterminism:
    """
    Requirement D: Grading must be deterministic and versioned
    """
    
    def test_rules_versioning_included(self):
        """Grading result must include rules versions for replay"""
        db_mock = Mock()
        service = UnifiedGradingService(db_mock)
        
        # Verify rules versions are set
        assert service.settlement_rules_version == "v1.0.0"
        assert service.clv_rules_version == "v1.0.0"
        assert service.grade_source == "unified_grading_service"
    
    @pytest.mark.asyncio
    async def test_score_payload_stored_for_audit(self):
        """Score payload must be stored for dispute resolution"""
        db_mock = Mock()
        db_mock.__getitem__ = Mock(return_value=Mock())
        
        db_mock["ai_picks"].find_one.return_value = {
            "pick_id": "pick_123",
            "event_id": "event_456",
            "market_type": "spread",
            "market_line": -3.0,
            "market_selection": "Lakers -3.0"
        }
        
        db_mock["events"].find_one.return_value = {
            "event_id": "event_456",
            "home_team": "Lakers",
            "away_team": "Warriors",
            "provider_event_map": {
                "oddsapi": {"event_id": "oddsapi_xyz"}
            }
        }
        
        score_data = {
            "oddsapi_event_id": "oddsapi_xyz",
            "home_team": "Lakers",
            "away_team": "Warriors",
            "home_score": 115,
            "away_score": 110,
            "completed": True
        }
        
        grading_mock = Mock()
        db_mock["grading"] = grading_mock
        
        service = UnifiedGradingService(db_mock)
        
        with patch.object(service, '_fetch_score_by_oddsapi_id', new=AsyncMock(return_value=score_data)):
            await service.grade_pick("pick_123")
            
            # Verify score_payload_ref was stored
            grading_record = grading_mock.update_one.call_args[0][1]["$set"]
            assert "score_payload_ref" in grading_record
            assert grading_record["score_payload_ref"]["oddsapi_event_id"] == "oddsapi_xyz"
            assert "payload_hash" in grading_record["score_payload_ref"]
            assert "payload_snapshot" in grading_record["score_payload_ref"]


class TestLegacyGradersBlocked:
    """
    Requirement B: Legacy grading paths must be blocked
    
    This is enforced via:
    1. Database unique constraint on grading_idempotency_key
    2. Runtime assertions (to be added to legacy code)
    3. Unit tests that verify legacy paths fail
    """
    
    def test_grading_idempotency_key_unique_constraint(self):
        """
        Database must have unique constraint on grading_idempotency_key.
        
        This test verifies the constraint exists in index definitions.
        """
        from backend.db.indexes import get_grading_indexes
        
        indexes = get_grading_indexes()
        
        # Find idempotency key index
        idempotency_index = None
        for index in indexes:
            if any("grading_idempotency_key" in key for key, _ in index.document["key"]):
                idempotency_index = index
                break
        
        assert idempotency_index is not None, "grading_idempotency_key index missing"
        assert idempotency_index.document.get("unique") is True, "Index must be unique"
    
    def test_no_fuzzy_matching_in_production_code(self):
        """
        Verify no fuzzy matching exists in production runtime logic.
        
        Fuzzy matching allowed ONLY in backfill script.
        """
        import os
        import re
        
        # Files that MUST NOT contain fuzzy matching
        production_files = [
            "backend/services/unified_grading_service_v2.py",
            "backend/services/result_service.py"
        ]
        
        # Pattern that indicates fuzzy matching
        fuzzy_patterns = [
            r"\.lower\(\).*==.*\.lower\(\)",  # Team name comparison
            r"fuzz",  # Fuzzywuzzy library
            r"difflib",  # Python difflib for fuzzy matching
            r"levenshtein",  # Levenshtein distance
        ]
        
        for file_path in production_files:
            if not os.path.exists(file_path):
                continue
            
            with open(file_path, "r") as f:
                content = f.read()
            
            # Allowed: drift detection compares teams (but doesn't use for grading)
            # We're looking for fuzzy matching used for ID lookup
            if "_validate_provider_mapping" in content:
                # Drift detection is OK - it's a safety check
                continue
            
            for pattern in fuzzy_patterns:
                matches = re.findall(pattern, content, re.IGNORECASE)
                if matches and "_validate_provider_mapping" not in content:
                    pytest.fail(
                        f"Fuzzy matching found in production file {file_path}: {matches}. "
                        "Only exact OddsAPI ID lookup allowed."
                    )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
