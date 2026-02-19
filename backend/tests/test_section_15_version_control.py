"""
Section 15 - Version Control Unit Tests
ENGINE LOCK Specification Compliance

Tests:
1. SEMVER format validation
2. Identical inputs => identical outputs + identical decision_version
3. Version stability across multiple calls
4. Deterministic replay cache functionality
5. Version bump rules (MAJOR/MINOR/PATCH)
6. Git commit SHA traceability
"""

import pytest
import hashlib
from datetime import datetime
from core.version_manager import (
    DecisionVersionManager, 
    get_version_manager,
    get_current_decision_version
)
from core.deterministic_replay_cache import DeterministicReplayCache


class TestVersionManager:
    """Test DecisionVersionManager SEMVER functionality"""
    
    def test_version_format_validation(self):
        """Test SEMVER format validation"""
        manager = DecisionVersionManager()
        
        # Valid SEMVER
        assert manager.validate_version_format("2.0.0") == True
        assert manager.validate_version_format("1.2.3") == True
        assert manager.validate_version_format("10.20.30") == True
        
        # Invalid formats
        assert manager.validate_version_format("2.0") == False
        assert manager.validate_version_format("2") == False
        assert manager.validate_version_format("2.0.0.1") == False
        assert manager.validate_version_format("v2.0.0") == False
        assert manager.validate_version_format("2.0.x") == False
        assert manager.validate_version_format("abc") == False
    
    def test_get_current_version_returns_semver(self):
        """Test that current version is valid SEMVER"""
        version = get_current_decision_version()
        
        # Must be string
        assert isinstance(version, str)
        
        # Must be valid SEMVER
        assert DecisionVersionManager().validate_version_format(version)
        
        # Must have 3 parts
        parts = version.split('.')
        assert len(parts) == 3
        
        # All parts must be numeric
        for part in parts:
            assert part.isdigit()
    
    def test_version_metadata_includes_git_sha(self):
        """Test that version metadata includes git commit SHA"""
        metadata = get_version_manager().get_version_metadata()
        
        # Required fields
        assert "decision_version" in metadata
        assert "git_commit_sha" in metadata
        assert "engine_version" in metadata
        
        # decision_version must be SEMVER
        assert DecisionVersionManager().validate_version_format(metadata["decision_version"])
        
        # git_commit_sha must be string (could be "unknown" if not in git repo)
        assert isinstance(metadata["git_commit_sha"], str)
    
    def test_version_bump_major(self):
        """Test MAJOR version bump (breaking changes)"""
        manager = DecisionVersionManager()
        initial_version = manager.get_current_version()
        parts = initial_version.split('.')
        initial_major = int(parts[0])
        
        new_version = manager.bump_version(
            bump_type="major",
            updated_by="test_user",
            change_description="Breaking change: new threshold formula"
        )
        
        new_parts = new_version.split('.')
        new_major = int(new_parts[0])
        new_minor = int(new_parts[1])
        new_patch = int(new_parts[2])
        
        # MAJOR incremented, MINOR and PATCH reset to 0
        assert new_major == initial_major + 1
        assert new_minor == 0
        assert new_patch == 0
    
    def test_version_bump_minor(self):
        """Test MINOR version bump (additive changes)"""
        manager = DecisionVersionManager()
        initial_version = manager.get_current_version()
        parts = initial_version.split('.')
        initial_major = int(parts[0])
        initial_minor = int(parts[1])
        
        new_version = manager.bump_version(
            bump_type="minor",
            updated_by="test_user",
            change_description="Additive change: new rule added"
        )
        
        new_parts = new_version.split('.')
        new_major = int(new_parts[0])
        new_minor = int(new_parts[1])
        new_patch = int(new_parts[2])
        
        # MAJOR unchanged, MINOR incremented, PATCH reset to 0
        assert new_major == initial_major
        assert new_minor == initial_minor + 1
        assert new_patch == 0
    
    def test_version_bump_patch(self):
        """Test PATCH version bump (bug fixes)"""
        manager = DecisionVersionManager()
        initial_version = manager.get_current_version()
        parts = initial_version.split('.')
        initial_major = int(parts[0])
        initial_minor = int(parts[1])
        initial_patch = int(parts[2])
        
        new_version = manager.bump_version(
            bump_type="patch",
            updated_by="test_user",
            change_description="Bug fix: edge calculation rounding"
        )
        
        new_parts = new_version.split('.')
        new_major = int(new_parts[0])
        new_minor = int(new_parts[1])
        new_patch = int(new_parts[2])
        
        # MAJOR and MINOR unchanged, PATCH incremented
        assert new_major == initial_major
        assert new_minor == initial_minor
        assert new_patch == initial_patch + 1
    
    def test_version_bump_invalid_type(self):
        """Test that invalid bump type raises ValueError"""
        manager = DecisionVersionManager()
        
        with pytest.raises(ValueError):
            manager.bump_version(
                bump_type="invalid",
                updated_by="test_user",
                change_description="Invalid bump"
            )


class TestDeterministicReplayCache:
    """Test deterministic replay cache functionality"""
    
    def test_cache_miss_returns_none(self):
        """Test that cache miss returns None"""
        cache = DeterministicReplayCache()
        
        result = cache.get_cached_decision(
            event_id="test_event_1",
            inputs_hash="abc123",
            market_type="spread",
            decision_version="2.0.0"
        )
        
        assert result is None
    
    def test_cache_hit_returns_decision(self):
        """Test that cached decision is retrieved"""
        cache = DeterministicReplayCache()
        
        # Cache a decision
        test_decision = {
            "event_id": "test_event_2",
            "classification": "EDGE",
            "edge_points": 2.5,
            "model_prob": 0.65
        }
        
        success = cache.cache_decision(
            event_id="test_event_2",
            inputs_hash="def456",
            market_type="spread",
            decision_version="2.0.0",
            decision_payload=test_decision
        )
        
        assert success == True
        
        # Retrieve from cache
        cached = cache.get_cached_decision(
            event_id="test_event_2",
            inputs_hash="def456",
            market_type="spread",
            decision_version="2.0.0"
        )
        
        assert cached is not None
        assert cached["event_id"] == "test_event_2"
        assert cached["classification"] == "EDGE"
        assert cached["edge_points"] == 2.5
    
    def test_identical_inputs_return_identical_outputs(self):
        """
        CRITICAL: Identical inputs MUST return identical decisions.
        This is the core determinism requirement.
        """
        cache = DeterministicReplayCache()
        
        # First call: cache miss, compute decision
        decision_1 = {
            "event_id": "test_determinism",
            "classification": "LEAN",
            "edge_points": 1.2,
            "model_prob": 0.58,
            "decision_version": "2.0.0"
        }
        
        cache.cache_decision(
            event_id="test_determinism",
            inputs_hash="same_inputs_hash",
            market_type="spread",
            decision_version="2.0.0",
            decision_payload=decision_1
        )
        
        # Second call: cache hit, return cached decision
        decision_2 = cache.get_cached_decision(
            event_id="test_determinism",
            inputs_hash="same_inputs_hash",
            market_type="spread",
            decision_version="2.0.0"
        )
        
        # Decisions must be byte-identical (excluding timestamp fields)
        assert decision_2["event_id"] == decision_1["event_id"]
        assert decision_2["classification"] == decision_1["classification"]
        assert decision_2["edge_points"] == decision_1["edge_points"]
        assert decision_2["model_prob"] == decision_1["model_prob"]
        assert decision_2["decision_version"] == decision_1["decision_version"]
    
    def test_different_version_cache_miss(self):
        """Test that different decision_version results in cache miss"""
        cache = DeterministicReplayCache()
        
        # Cache with version 2.0.0
        cache.cache_decision(
            event_id="test_version_cache",
            inputs_hash="inputs_v1",
            market_type="spread",
            decision_version="2.0.0",
            decision_payload={"data": "version_2.0.0"}
        )
        
        # Try to retrieve with version 2.0.1 (should be cache miss)
        cached = cache.get_cached_decision(
            event_id="test_version_cache",
            inputs_hash="inputs_v1",
            market_type="spread",
            decision_version="2.0.1"
        )
        
        assert cached is None
    
    def test_verify_determinism_success(self):
        """Test determinism verification when decisions match"""
        cache = DeterministicReplayCache()
        
        # Original decision
        original = {
            "classification": "EDGE",
            "edge_points": 3.0,
            "model_prob": 0.70,
            "timestamp": "2026-02-19T12:00:00Z"
        }
        
        cache.cache_decision(
            event_id="test_verify_1",
            inputs_hash="verify_hash_1",
            market_type="spread",
            decision_version="2.0.0",
            decision_payload=original
        )
        
        # Current decision (same except timestamp)
        current = {
            "classification": "EDGE",
            "edge_points": 3.0,
            "model_prob": 0.70,
            "timestamp": "2026-02-19T12:05:00Z"  # Different timestamp OK
        }
        
        is_deterministic, differences = cache.verify_determinism(
            event_id="test_verify_1",
            inputs_hash="verify_hash_1",
            market_type="spread",
            decision_version="2.0.0",
            current_decision=current,
            exclude_fields=["timestamp", "trace_id"]
        )
        
        assert is_deterministic == True
        assert len(differences) == 0
    
    def test_verify_determinism_failure(self):
        """Test determinism verification when decisions differ"""
        cache = DeterministicReplayCache()
        
        # Original decision
        original = {
            "classification": "EDGE",
            "edge_points": 3.0,
            "model_prob": 0.70
        }
        
        cache.cache_decision(
            event_id="test_verify_2",
            inputs_hash="verify_hash_2",
            market_type="spread",
            decision_version="2.0.0",
            decision_payload=original
        )
        
        # Current decision (DIFFERENT edge_points - non-deterministic!)
        current = {
            "classification": "EDGE",
            "edge_points": 2.5,  # Changed!
            "model_prob": 0.70
        }
        
        is_deterministic, differences = cache.verify_determinism(
            event_id="test_verify_2",
            inputs_hash="verify_hash_2",
            market_type="spread",
            decision_version="2.0.0",
            current_decision=current
        )
        
        assert is_deterministic == False
        assert len(differences) > 0
        assert any("edge_points" in diff for diff in differences)
    
    def test_cache_statistics(self):
        """Test cache statistics reporting"""
        cache = DeterministicReplayCache()
        
        stats = cache.get_cache_statistics()
        
        # Required fields
        assert "total_entries" in stats
        assert "spread_decisions" in stats
        assert "total_decisions" in stats
        assert "cache_ttl_policy" in stats
        
        # TTL policy must be no_expiration (determinism records persist)
        assert stats["cache_ttl_policy"] == "no_expiration"


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v", "-s"])
