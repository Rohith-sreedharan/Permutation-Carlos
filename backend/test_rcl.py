"""
Test suite for Reality Check Layer (RCL)
Tests all three guardrail layers and edge blocking logic
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from datetime import datetime, timezone
from core.reality_check_layer import (
    apply_historical_rcl,
    apply_live_pace_guardrail,
    apply_per_team_pace_guardrail,
    get_public_total_projection,
    update_league_total_stats,
    MAX_SIGMA,
    PER_TEAM_PACE_THRESHOLD
)
from db.mongo import db


# ===== TEST FIXTURES =====

@pytest.fixture(autouse=True)
def setup_test_db():
    """Setup test database with league stats"""
    # Clean test collections
    db["sim_audit"].delete_many({"sim_audit_id": {"$regex": "^test_"}})
    db["league_total_stats"].delete_many({"league_code": "TEST_NCAAB"})
    
    # Insert test league stats
    update_league_total_stats("TEST_NCAAB", [
        140, 142, 143, 145, 145, 147, 148, 150  # mean=145, std≈3
    ])
    
    yield
    
    # Cleanup
    db["sim_audit"].delete_many({"sim_audit_id": {"$regex": "^test_"}})
    db["league_total_stats"].delete_many({"league_code": "TEST_NCAAB"})


# ===== LAYER 1: HISTORICAL RCL TESTS =====

def test_historical_rcl_passes_normal_projection():
    """Test that a normal projection passes historical RCL"""
    sim_audit_id = "test_hist_pass"
    
    # 145.0 is within ±2σ of mean (145 ± 6)
    result_total, passed, details = apply_historical_rcl(
        model_total=145.0,
        league_code="TEST_NCAAB",
        sim_audit_id=sim_audit_id
    )
    
    assert passed is True
    assert result_total == 145.0
    assert details["rcl_reason"] == "RCL_OK"
    assert details["rcl_passed"] is True
    assert abs(details["historical_z_score"]) <= MAX_SIGMA


def test_historical_rcl_fails_inflated_projection():
    """Test that inflated projection (153 vs 145.5) gets clamped"""
    sim_audit_id = "test_hist_fail_high"
    
    # 153.0 is > 2σ above mean (145 + 6 = 151)
    result_total, passed, details = apply_historical_rcl(
        model_total=153.0,
        league_code="TEST_NCAAB",
        sim_audit_id=sim_audit_id
    )
    
    assert passed is False
    assert result_total < 153.0  # Should be clamped
    assert "HISTORICAL_OUTLIER" in details["rcl_reason"]
    assert details["rcl_passed"] is False
    assert details["historical_z_score"] > MAX_SIGMA


def test_historical_rcl_fails_deflated_projection():
    """Test that deflated projection gets clamped"""
    sim_audit_id = "test_hist_fail_low"
    
    # 135.0 is > 2σ below mean (145 - 6 = 139)
    result_total, passed, details = apply_historical_rcl(
        model_total=135.0,
        league_code="TEST_NCAAB",
        sim_audit_id=sim_audit_id
    )
    
    assert passed is False
    assert result_total > 135.0  # Should be clamped up
    assert "HISTORICAL_OUTLIER" in details["rcl_reason"]
    assert details["historical_z_score"] < -MAX_SIGMA


def test_historical_rcl_no_data():
    """Test behavior when no historical data available"""
    sim_audit_id = "test_hist_no_data"
    
    result_total, passed, details = apply_historical_rcl(
        model_total=200.0,
        league_code="UNKNOWN_LEAGUE",
        sim_audit_id=sim_audit_id
    )
    
    assert passed is True  # Should allow through
    assert result_total == 200.0  # Unchanged
    assert details["rcl_reason"] == "NO_HISTORICAL_DATA"


# ===== LAYER 2: LIVE PACE GUARDRAIL TESTS =====

def test_live_pace_passes_realistic():
    """Test that realistic pace passes guardrail"""
    sim_audit_id = "test_pace_pass"
    
    # Current: 44 pts in 10 min → 4.4 PPM → projects to 176 pts
    # Model: 180 → within MAX_DELTA (15)
    result_total, passed, details = apply_live_pace_guardrail(
        model_total=180.0,
        current_total_points=44.0,
        elapsed_minutes=10.0,
        regulation_minutes=40.0,
        sim_audit_id=sim_audit_id
    )
    
    assert passed is True
    assert result_total == 180.0
    assert details["live_pace_ppm"] >= 2.0


def test_live_pace_fails_slow_pace():
    """Test Florida vs UConn scenario: 22 pts at 11:27 → way too slow for 153"""
    sim_audit_id = "test_pace_fail"
    
    # Current: 22 pts in 8.55 min (11:27 = 20 - 11:27) → 2.57 PPM → projects to ~103 pts
    # Model: 153 → fails because pace too slow AND delta > 15
    elapsed = 20.0 - 11.45  # 8.55 minutes elapsed
    result_total, passed, details = apply_live_pace_guardrail(
        model_total=153.0,
        current_total_points=22.0,
        elapsed_minutes=elapsed,
        regulation_minutes=40.0,
        sim_audit_id=sim_audit_id
    )
    
    # Should fail because:
    # 1. PPM = 22/8.55 ≈ 2.57 < MIN_PPM_FOR_MODEL (2.0) - marginal
    # 2. Live projection ≈ 103, model = 153, delta = 50 > MAX_DELTA (15)
    assert passed is False
    assert result_total < 153.0
    assert "LIVE_PACE_TOO_SLOW" in details["rcl_reason"]


def test_live_pace_pre_game():
    """Test that pre-game gets no pace check"""
    sim_audit_id = "test_pace_pregame"
    
    result_total, passed, details = apply_live_pace_guardrail(
        model_total=153.0,
        current_total_points=None,
        elapsed_minutes=None,
        regulation_minutes=40.0,
        sim_audit_id=sim_audit_id
    )
    
    assert passed is True
    assert result_total == 153.0
    assert details["live_pace_ppm"] is None


def test_live_pace_too_early():
    """Test that first 5 minutes are skipped"""
    sim_audit_id = "test_pace_early"
    
    result_total, passed, details = apply_live_pace_guardrail(
        model_total=153.0,
        current_total_points=10.0,
        elapsed_minutes=3.0,  # Too early
        regulation_minutes=40.0,
        sim_audit_id=sim_audit_id
    )
    
    assert passed is True
    assert result_total == 153.0


# ===== LAYER 3: PER-TEAM PACE GUARDRAIL TESTS =====

def test_per_team_pace_passes():
    """Test that realistic per-team pace passes"""
    sim_audit_id = "test_perteam_pass"
    
    # Current: 60 pts, 20 min left, model = 100
    # Needs 40 more pts in 20 min = 2.0 PPM total = 1.0 PPM per team
    # 1.0 < THRESHOLD (3.5) → PASS
    result_total, passed, details = apply_per_team_pace_guardrail(
        model_total=100.0,
        current_total_points=60.0,
        elapsed_minutes=20.0,
        regulation_minutes=40.0,
        sim_audit_id=sim_audit_id
    )
    
    assert passed is True
    assert result_total == 100.0
    assert details["per_team_pace_needed"] < PER_TEAM_PACE_THRESHOLD
    assert details["pace_guardrail_status"] == "passed"


def test_per_team_pace_fails_unrealistic():
    """Test that unrealistic per-team pace fails"""
    sim_audit_id = "test_perteam_fail"
    
    # Current: 50 pts, 10 min left, model = 150
    # Needs 100 more pts in 10 min = 10.0 PPM total = 5.0 PPM per team
    # 5.0 > THRESHOLD (3.5) → FAIL
    result_total, passed, details = apply_per_team_pace_guardrail(
        model_total=150.0,
        current_total_points=50.0,
        elapsed_minutes=30.0,
        regulation_minutes=40.0,
        sim_audit_id=sim_audit_id
    )
    
    assert passed is False
    assert details["per_team_pace_needed"] > PER_TEAM_PACE_THRESHOLD
    assert details["pace_guardrail_status"] == "failed_unrealistic"
    assert "PER_TEAM_PACE_UNREALISTIC" in details["rcl_reason"]


def test_per_team_pace_ahead_of_projection():
    """Test when already ahead of projection"""
    sim_audit_id = "test_perteam_ahead"
    
    # Current: 80 pts, model = 100, but only 5 min left
    # Already on pace, no issue
    result_total, passed, details = apply_per_team_pace_guardrail(
        model_total=100.0,
        current_total_points=80.0,
        elapsed_minutes=35.0,
        regulation_minutes=40.0,
        sim_audit_id=sim_audit_id
    )
    
    assert passed is True
    assert details["per_team_pace_needed"] == 0.0
    assert details["pace_guardrail_status"] == "passed"


# ===== MASTER FLOW TESTS =====

def test_full_rcl_flow_pass():
    """Test full RCL flow with all checks passing"""
    result = get_public_total_projection(
        sim_stats={
            "median_total": 145.0,
            "mean_total": 145.5,
            "total_line": 145.5
        },
        league_code="TEST_NCAAB",
        live_context=None,  # Pre-game
        simulation_id="test_sim_123",
        event_id="test_event_123",
        regulation_minutes=40.0
    )
    
    assert result["rcl_ok"] is True
    assert result["model_total"] == 145.0
    assert result["rcl_reason"] == "RCL_OK"
    assert result["edge_eligible"] is True


def test_full_rcl_flow_historical_fail():
    """Test full RCL flow with historical outlier"""
    result = get_public_total_projection(
        sim_stats={
            "median_total": 160.0,  # Way above mean (145)
            "mean_total": 160.5,
            "total_line": 145.5
        },
        league_code="TEST_NCAAB",
        live_context=None,
        simulation_id="test_sim_456",
        event_id="test_event_456",
        regulation_minutes=40.0
    )
    
    assert result["rcl_ok"] is False
    assert result["model_total"] < 160.0  # Should be clamped
    assert "HISTORICAL_OUTLIER" in result["rcl_reason"]
    assert result["edge_eligible"] is False
    assert result["confidence_adjustment"] == "DOWNGRADE_2_TIERS"


def test_full_rcl_flow_live_pace_fail():
    """Test full RCL flow with live pace failure (Florida scenario)"""
    result = get_public_total_projection(
        sim_stats={
            "median_total": 153.0,
            "mean_total": 153.5,
            "total_line": 145.5
        },
        league_code="TEST_NCAAB",
        live_context={
            "current_total_points": 22.0,
            "elapsed_minutes": 8.55
        },
        simulation_id="test_sim_789",
        event_id="test_event_789",
        regulation_minutes=40.0
    )
    
    # Should fail on live pace OR historical (153 > 151)
    assert result["rcl_ok"] is False
    assert result["edge_eligible"] is False


def test_full_rcl_flow_per_team_pace_fail():
    """Test full RCL flow with per-team pace failure"""
    result = get_public_total_projection(
        sim_stats={
            "median_total": 145.0,  # Passes historical
            "mean_total": 145.5,
            "total_line": 145.5
        },
        league_code="TEST_NCAAB",
        live_context={
            "current_total_points": 50.0,
            "elapsed_minutes": 30.0  # 10 min left, needs 95 more (4.75 per team)
        },
        simulation_id="test_sim_perteam",
        event_id="test_event_perteam",
        regulation_minutes=40.0
    )
    
    # Should fail on per-team pace
    assert result["rcl_ok"] is False
    assert result["edge_eligible"] is False
    assert result.get("per_team_pace_needed", 0) > PER_TEAM_PACE_THRESHOLD


# ===== EDGE BLOCKING TESTS =====

def test_edge_blocked_when_rcl_fails():
    """Verify that edges are blocked when RCL fails"""
    # This would be tested in monte_carlo_engine integration
    # Here we just verify the RCL result structure
    result = get_public_total_projection(
        sim_stats={"median_total": 160.0, "mean_total": 160.5, "total_line": 145.5},
        league_code="TEST_NCAAB",
        live_context=None,
        simulation_id="test_edge_block",
        event_id="test_edge_block",
        regulation_minutes=40.0
    )
    
    assert result["edge_eligible"] is False
    assert result["confidence_adjustment"] == "DOWNGRADE_2_TIERS"


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v", "--tb=short"])
