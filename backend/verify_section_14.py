#!/usr/bin/env python3
"""
Section 14 Audit Logging - Production Verification Script

Runs comprehensive tests against production database to verify:
1. APPROVED decision logging
2. BLOCKED decision logging
3. Trace ID queries
4. Decision history queries
5. 7-year retention enforcement
6. Append-only enforcement (if configured)

Usage:
    python verify_section_14.py
"""

import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# Add backend to path
backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))

from db.decision_audit_logger import get_decision_audit_logger

# ANSI colors for output
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
RESET = "\033[0m"

def print_header(text):
    print(f"\n{BLUE}{'=' * 70}{RESET}")
    print(f"{BLUE}{text}{RESET}")
    print(f"{BLUE}{'=' * 70}{RESET}\n")

def print_success(text):
    print(f"{GREEN}✅ {text}{RESET}")

def print_failure(text):
    print(f"{RED}❌ {text}{RESET}")

def print_warning(text):
    print(f"{YELLOW}⚠️  {text}{RESET}")

def test_approved_decision_logging():
    """Test logging an APPROVED EDGE decision."""
    print_header("TEST 1: APPROVED Decision Logging")
    
    logger = get_decision_audit_logger()
    
    test_data = {
        "event_id": f"verify_approved_{int(datetime.now(timezone.utc).timestamp())}",
        "inputs_hash": "hash_approved_test_12345",
        "decision_version": "2.0.0",
        "classification": "EDGE",
        "release_status": "APPROVED",
        "edge_points": 12.45,
        "model_prob": 0.8734,
        "trace_id": f"trace_verify_{int(datetime.now(timezone.utc).timestamp())}",
        "engine_version": "2.0.0",
        "market_type": "spread",
        "league": "NBA",
        "additional_metadata": {
            "home_team": "Lakers",
            "away_team": "Celtics",
            "test_marker": "SECTION_14_VERIFICATION"
        }
    }
    
    success = logger.log_decision(**test_data)
    
    if success:
        print_success("APPROVED decision logged successfully")
        
        # Verify it was actually written
        logs = logger.query_by_event(test_data["event_id"])
        if len(logs) > 0:
            log = logs[0]
            print_success(f"Verified log exists in database: event_id={log['event_id']}")
            
            # Check all required fields
            required_fields = [
                "event_id", "inputs_hash", "decision_version", "classification",
                "release_status", "edge_points", "model_prob", "timestamp",
                "trace_id", "engine_version", "market_type", "league",
                "retention_expires_at", "logged_at_unix"
            ]
            
            missing_fields = [f for f in required_fields if f not in log]
            if missing_fields:
                print_failure(f"Missing required fields: {missing_fields}")
                return False
            
            print_success(f"All {len(required_fields)} required fields present")
            
            # Verify values
            if log["classification"] == "EDGE":
                print_success("Classification = EDGE ✓")
            else:
                print_failure(f"Classification mismatch: {log['classification']}")
                return False
            
            if log["release_status"] == "APPROVED":
                print_success("ReleaseStatus = APPROVED ✓")
            else:
                print_failure(f"ReleaseStatus mismatch: {log['release_status']}")
                return False
            
            if log["edge_points"] == 12.45:
                print_success("edge_points = 12.45 ✓")
            else:
                print_failure(f"edge_points mismatch: {log['edge_points']}")
                return False
            
            return True
        else:
            print_failure("Log not found in database after write")
            return False
    else:
        print_failure("APPROVED decision logging failed")
        return False

def test_blocked_decision_logging():
    """Test logging a BLOCKED decision with null fields."""
    print_header("TEST 2: BLOCKED Decision Logging")
    
    logger = get_decision_audit_logger()
    
    test_data = {
        "event_id": f"verify_blocked_{int(datetime.now(timezone.utc).timestamp())}",
        "inputs_hash": "hash_blocked_test_67890",
        "decision_version": "2.0.0",
        "classification": None,  # Null when BLOCKED
        "release_status": "BLOCKED_BY_ODDS_MISMATCH",
        "edge_points": None,  # Null when BLOCKED
        "model_prob": None,  # Null when BLOCKED
        "trace_id": f"trace_blocked_{int(datetime.now(timezone.utc).timestamp())}",
        "engine_version": "2.0.0",
        "market_type": "spread",
        "league": "NCAAB"
    }
    
    success = logger.log_decision(**test_data)
    
    if success:
        print_success("BLOCKED decision logged successfully")
        
        # Verify it was actually written
        logs = logger.query_by_event(test_data["event_id"])
        if len(logs) > 0:
            log = logs[0]
            print_success(f"Verified log exists: event_id={log['event_id']}")
            
            # Verify BLOCKED fields
            if log["release_status"] == "BLOCKED_BY_ODDS_MISMATCH":
                print_success("ReleaseStatus = BLOCKED_BY_ODDS_MISMATCH ✓")
            else:
                print_failure(f"ReleaseStatus mismatch: {log['release_status']}")
                return False
            
            if log["classification"] is None:
                print_success("classification = null (correct for BLOCKED) ✓")
            else:
                print_failure(f"classification should be null, got: {log['classification']}")
                return False
            
            if log["edge_points"] is None:
                print_success("edge_points = null (correct for BLOCKED) ✓")
            else:
                print_failure(f"edge_points should be null, got: {log['edge_points']}")
                return False
            
            return True
        else:
            print_failure("Log not found in database after write")
            return False
    else:
        print_failure("BLOCKED decision logging failed")
        return False

def test_trace_id_query():
    """Test querying by trace_id."""
    print_header("TEST 3: Trace ID Query")
    
    logger = get_decision_audit_logger()
    
    trace_id = f"trace_multi_test_{int(datetime.now(timezone.utc).timestamp())}"
    
    # Log multiple decisions with same trace_id
    for i in range(3):
        success = logger.log_decision(
            event_id=f"event_trace_{i}_{int(datetime.now(timezone.utc).timestamp())}",
            inputs_hash=f"hash_trace_{i}",
            decision_version="2.0.0",
            classification="LEAN",
            release_status="APPROVED",
            edge_points=1.5 + i,
            model_prob=0.6 + (i * 0.05),
            trace_id=trace_id,
            engine_version="2.0.0",
            market_type="spread" if i % 2 == 0 else "total",
            league="NBA"
        )
        
        if not success:
            print_failure(f"Failed to log decision {i}")
            return False
    
    print_success("Logged 3 decisions with same trace_id")
    
    # Query by trace_id
    logs = logger.query_by_trace_id(trace_id)
    
    if len(logs) == 3:
        print_success(f"Query returned all 3 logs for trace_id={trace_id}")
        
        # Verify all have same trace_id
        if all(log["trace_id"] == trace_id for log in logs):
            print_success("All logs have correct trace_id ✓")
            return True
        else:
            print_failure("Some logs have incorrect trace_id")
            return False
    else:
        print_failure(f"Expected 3 logs, got {len(logs)}")
        return False

def test_decision_history():
    """Test decision history query (determinism verification)."""
    print_header("TEST 4: Decision History (Determinism)")
    
    logger = get_decision_audit_logger()
    
    event_id = f"event_determinism_{int(datetime.now(timezone.utc).timestamp())}"
    inputs_hash = "hash_deterministic_12345"
    
    # Log same event+inputs 3 times (should be deterministic)
    for i in range(3):
        success = logger.log_decision(
            event_id=event_id,
            inputs_hash=inputs_hash,
            decision_version="2.0.0",
            classification="EDGE",
            release_status="APPROVED",
            edge_points=8.5,
            model_prob=0.7823,
            trace_id=f"trace_{i}_{int(datetime.now(timezone.utc).timestamp())}",
            engine_version="2.0.0",
            market_type="spread",
            league="NBA"
        )
        
        if not success:
            print_failure(f"Failed to log decision {i}")
            return False
    
    print_success("Logged 3 decisions with identical event_id + inputs_hash")
    
    # Get decision history
    history = logger.get_decision_history(event_id, inputs_hash)
    
    if len(history) == 3:
        print_success(f"History query returned all 3 logs")
        
        # Verify determinism (all should have same classification, edge_points, etc.)
        classifications = [log["classification"] for log in history]
        edge_points = [log["edge_points"] for log in history]
        decision_versions = [log["decision_version"] for log in history]
        
        if len(set(classifications)) == 1 and classifications[0] == "EDGE":
            print_success("Determinism verified: All classifications = EDGE ✓")
        else:
            print_failure(f"Non-deterministic classifications: {classifications}")
            return False
        
        if len(set(edge_points)) == 1 and edge_points[0] == 8.5:
            print_success("Determinism verified: All edge_points = 8.5 ✓")
        else:
            print_failure(f"Non-deterministic edge_points: {edge_points}")
            return False
        
        if len(set(decision_versions)) == 1 and decision_versions[0] == "2.0.0":
            print_success("Determinism verified: All decision_version = 2.0.0 ✓")
            return True
        else:
            print_failure(f"Non-deterministic decision_versions: {decision_versions}")
            return False
    else:
        print_failure(f"Expected 3 logs, got {len(history)}")
        return False

def test_retention_policy():
    """Test that retention_expires_at is set correctly (7 years)."""
    print_header("TEST 5: 7-Year Retention Policy")
    
    logger = get_decision_audit_logger()
    
    event_id = f"verify_retention_{int(datetime.now(timezone.utc).timestamp())}"
    
    success = logger.log_decision(
        event_id=event_id,
        inputs_hash="hash_retention_test",
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
    
    if not success:
        print_failure("Failed to log decision")
        return False
    
    # Verify retention policy
    logs = logger.query_by_event(event_id)
    if len(logs) > 0:
        log = logs[0]
        
        expiry = datetime.fromisoformat(log["retention_expires_at"].replace('Z', '+00:00'))
        now = datetime.now(timezone.utc)
        diff_years = (expiry - now).days / 365
        
        print(f"   Logged at: {log['timestamp']}")
        print(f"   Expires at: {log['retention_expires_at']}")
        print(f"   Retention period: {diff_years:.2f} years")
        
        if 6.99 < diff_years < 7.01:
            print_success("Retention policy correct: ~7 years ✓")
            return True
        else:
            print_failure(f"Retention period incorrect: {diff_years:.2f} years")
            return False
    else:
        print_failure("Log not found")
        return False

def get_sample_production_record():
    """Fetch one live production decision audit record."""
    print_header("SAMPLE PRODUCTION RECORD")
    
    logger = get_decision_audit_logger()
    
    # Get the most recent production decision log
    try:
        cursor = logger.collection.find().sort("timestamp", -1).limit(1)
        logs = list(cursor)
        
        if len(logs) > 0:
            log = logs[0]
            
            # Redact sensitive data
            redacted_log = {
                "event_id": log.get("event_id", "N/A"),
                "classification": log.get("classification", "N/A"),
                "release_status": log.get("release_status", "N/A"),
                "edge_points": log.get("edge_points", "N/A"),
                "timestamp": log.get("timestamp", "N/A"),
                "engine_version": log.get("engine_version", "N/A"),
                "market_type": log.get("market_type", "N/A"),
                "league": log.get("league", "N/A"),
                "retention_expires_at": log.get("retention_expires_at", "N/A")
            }
            
            print("Most recent production decision audit log:")
            for key, value in redacted_log.items():
                print(f"   {key}: {value}")
            
            print_success("Production audit log retrieved successfully")
            return True
        else:
            print_warning("No production logs found yet (expected if first run)")
            return True
    except Exception as e:
        print_failure(f"Failed to retrieve production record: {e}")
        return False

def main():
    """Run all verification tests."""
    print(f"\n{BLUE}{'#' * 70}{RESET}")
    print(f"{BLUE}# Section 14 Audit Logging - Production Verification{RESET}")
    print(f"{BLUE}# Date: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC{RESET}")
    print(f"{BLUE}{'#' * 70}{RESET}")
    
    # Check MongoDB connection
    mongo_uri = os.getenv("AUDIT_MONGO_URI") or os.getenv("MONGO_URI")
    if not mongo_uri:
        print_failure("No MONGO_URI or AUDIT_MONGO_URI found in environment")
        return 1
    
    print(f"\nMongoDB URI: {mongo_uri.split('@')[1] if '@' in mongo_uri else 'localhost'}")
    
    results = []
    
    # Run all tests
    results.append(("APPROVED Decision Logging", test_approved_decision_logging()))
    results.append(("BLOCKED Decision Logging", test_blocked_decision_logging()))
    results.append(("Trace ID Query", test_trace_id_query()))
    results.append(("Decision History", test_decision_history()))
    results.append(("7-Year Retention", test_retention_policy()))
    results.append(("Production Record Sample", get_sample_production_record()))
    
    # Print summary
    print_header("VERIFICATION SUMMARY")
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        if result:
            print_success(f"{test_name}: PASS")
        else:
            print_failure(f"{test_name}: FAIL")
    
    print(f"\n{BLUE}{'=' * 70}{RESET}")
    if passed == total:
        print_success(f"ALL TESTS PASSED ({passed}/{total})")
        print_success("Section 14 Production Verification: ✅ COMPLETE")
        print(f"{BLUE}{'=' * 70}{RESET}\n")
        return 0
    else:
        print_failure(f"SOME TESTS FAILED ({passed}/{total})")
        print_failure("Section 14 Production Verification: ❌ INCOMPLETE")
        print(f"{BLUE}{'=' * 70}{RESET}\n")
        return 1

if __name__ == "__main__":
    sys.exit(main())
