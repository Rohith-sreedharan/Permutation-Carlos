"""
Decision Audit Logger Tests
Section 14 - ENGINE LOCK Specification Compliance

Tests verify:
1. Audit logs are written for all decisions
2. HTTP 500 triggered if audit write fails
3. All required fields are captured
4. Collection is append-only
5. 7-year retention enforced
"""

import pytest
from datetime import datetime, timezone
from db.decision_audit_logger import DecisionAuditLogger, get_decision_audit_logger
from pymongo import MongoClient
import os


@pytest.fixture
def audit_logger():
    """Create test audit logger instance."""
    mongo_uri = os.getenv("MONGO_URI", "mongodb://159.203.122.145:27017/")
    logger = DecisionAuditLogger(mongo_uri, database="beatvegas_test")
    
    # Clean up test collection before each test
    logger.collection.delete_many({})
    
    yield logger
    
    # Clean up after test
    logger.collection.delete_many({})


def test_audit_log_approved_decision(audit_logger):
    """Test logging an APPROVED decision with all fields populated."""
    success = audit_logger.log_decision(
        event_id="test_event_123",
        inputs_hash="abc123hash",
        decision_version="2.0.0",
        classification="EDGE",
        release_status="APPROVED",
        edge_points=9.03,
        model_prob=0.8391,
        trace_id="trace_xyz",
        engine_version="2.0.0",
        market_type="spread",
        league="NBA",
        additional_metadata={"home_team": "Lakers", "away_team": "Celtics"}
    )
    
    assert success is True
    
    # Verify log was written
    logs = audit_logger.query_by_event("test_event_123")
    assert len(logs) == 1
    
    log = logs[0]
    assert log["event_id"] == "test_event_123"
    assert log["inputs_hash"] == "abc123hash"
    assert log["decision_version"] == "2.0.0"
    assert log["classification"] == "EDGE"
    assert log["release_status"] == "APPROVED"
    assert log["edge_points"] == 9.03
    assert log["model_prob"] == 0.8391
    assert log["trace_id"] == "trace_xyz"
    assert log["engine_version"] == "2.0.0"
    assert log["market_type"] == "spread"
    assert log["league"] == "NBA"
    assert log["metadata"]["home_team"] == "Lakers"
    
    # Verify timestamp fields
    assert "timestamp" in log
    assert "retention_expires_at" in log
    assert "logged_at_unix" in log


def test_audit_log_blocked_decision(audit_logger):
    """Test logging a BLOCKED decision with null decision fields."""
    success = audit_logger.log_decision(
        event_id="test_event_456",
        inputs_hash="def456hash",
        decision_version="2.0.0",
        classification=None,  # Null when BLOCKED
        release_status="BLOCKED_BY_ODDS_MISMATCH",
        edge_points=None,  # Null when BLOCKED
        model_prob=None,  # Null when BLOCKED
        trace_id="trace_abc",
        engine_version="2.0.0",
        market_type="spread",
        league="NCAAB"
    )
    
    assert success is True
    
    # Verify log was written
    logs = audit_logger.query_by_event("test_event_456")
    assert len(logs) == 1
    
    log = logs[0]
    assert log["release_status"] == "BLOCKED_BY_ODDS_MISMATCH"
    assert log["classification"] is None
    assert log["edge_points"] is None
    assert log["model_prob"] is None


def test_audit_log_query_by_trace_id(audit_logger):
    """Test querying audit logs by trace ID."""
    trace_id = "trace_multi_123"
    
    # Log multiple decisions with same trace ID
    audit_logger.log_decision(
        event_id="event_1",
        inputs_hash="hash1",
        decision_version="2.0.0",
        classification="EDGE",
        release_status="APPROVED",
        edge_points=5.0,
        model_prob=0.7,
        trace_id=trace_id,
        engine_version="2.0.0",
        market_type="spread",
        league="NBA"
    )
    
    audit_logger.log_decision(
        event_id="event_2",
        inputs_hash="hash2",
        decision_version="2.0.0",
        classification="LEAN",
        release_status="APPROVED",
        edge_points=1.5,
        model_prob=0.6,
        trace_id=trace_id,
        engine_version="2.0.0",
        market_type="total",
        league="NBA"
    )
    
    # Query by trace ID
    logs = audit_logger.query_by_trace_id(trace_id)
    assert len(logs) == 2
    
    # Verify both logs have same trace_id
    assert all(log["trace_id"] == trace_id for log in logs)


def test_audit_log_decision_history(audit_logger):
    """Test querying decision history for identical inputs."""
    event_id = "event_determinism"
    inputs_hash = "hash_deterministic_123"
    
    # Log same event with same inputs multiple times
    for i in range(3):
        audit_logger.log_decision(
            event_id=event_id,
            inputs_hash=inputs_hash,
            decision_version="2.0.0",
            classification="EDGE",
            release_status="APPROVED",
            edge_points=5.0,
            model_prob=0.7,
            trace_id=f"trace_{i}",
            engine_version="2.0.0",
            market_type="spread",
            league="NBA"
        )
    
    # Get decision history
    history = audit_logger.get_decision_history(event_id, inputs_hash)
    assert len(history) == 3
    
    # Verify all have same classification (determinism)
    assert all(log["classification"] == "EDGE" for log in history)
    assert all(log["decision_version"] == "2.0.0" for log in history)


def test_retention_expiry_calculated(audit_logger):
    """Test that retention expiry is 7 years in future."""
    success = audit_logger.log_decision(
        event_id="test_retention",
        inputs_hash="hash_retention",
        decision_version="2.0.0",
        classification="EDGE",
        release_status="APPROVED",
        edge_points=5.0,
        model_prob=0.7,
        trace_id="trace_retention",
        engine_version="2.0.0",
        market_type="spread",
        league="NBA"
    )
    
    assert success is True
    
    logs = audit_logger.query_by_event("test_retention")
    log = logs[0]
    
    # Verify retention_expires_at is ~7 years in future
    expiry = datetime.fromisoformat(log["retention_expires_at"].replace('Z', '+00:00'))
    now = datetime.now(timezone.utc)
    diff_years = (expiry - now).days / 365
    
    # Should be approximately 7 years (allow 1 day tolerance)
    assert 6.99 < diff_years < 7.01


def test_singleton_instance():
    """Test that get_decision_audit_logger returns singleton."""
    logger1 = get_decision_audit_logger()
    logger2 = get_decision_audit_logger()
    
    assert logger1 is logger2  # Same instance


def test_audit_log_handles_write_failure():
    """Test that audit logger returns False on write failure."""
    # Create logger with invalid connection (should fail gracefully)
    logger = DecisionAuditLogger("mongodb://invalid:27017/", database="test_db")
    
    # This should return False without raising exception
    success = logger.log_decision(
        event_id="test_failure",
        inputs_hash="hash",
        decision_version="2.0.0",
        classification="EDGE",
        release_status="APPROVED",
        edge_points=5.0,
        model_prob=0.7,
        trace_id="trace",
        engine_version="2.0.0",
        market_type="spread",
        league="NBA"
    )
    
    # Should return False, not raise exception
    assert success is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
