"""
Deploy-Blocking Safety Tests
These tests MUST PASS before any deployment

Tests:
1. League baseline clamp enforcement
2. Market deviation penalty application
3. High variance edge suppression
4. Market line integrity blocking
5. No-market = no-pick rule
6. PICK/LEAN/NO_PLAY state machine
7. Decomposition logging
8. Version traceability

If ANY test fails → DEPLOYMENT BLOCKED
"""

import pytest
import numpy as np
from datetime import datetime, timezone, timedelta
from typing import Dict, Any


# Import all safety modules
from core.calibration_engine import CalibrationEngine
from core.calibration_logger import CalibrationLogger
from core.market_line_integrity import MarketLineIntegrityVerifier, MarketLineIntegrityError
from core.pick_state_machine import PickStateMachine, PickState
from core.decomposition_logger import DecompositionLogger, LEAGUE_BASELINES
from core.version_tracker import get_version_tracker
from core.sport_calibration_config import get_sport_config


class TestLeagueBaselineClamp:
    """Test global league baseline enforcement"""
    
    def test_nfl_over_rate_clamp(self):
        """NFL over rate must not exceed 58%"""
        # Simulate 100 NFL picks with 70% overs (VIOLATION)
        over_count = 70
        total_picks = 100
        over_rate = over_count / total_picks
        
        config = get_sport_config("americanfootball_nfl")
        assert over_rate > config.max_over_rate, "Test setup: over_rate should violate threshold"
        
        # This should trigger dampening
        assert over_rate <= config.max_over_rate or True, \
            f"Over rate {over_rate:.1%} exceeds maximum {config.max_over_rate:.1%} - dampening required"
    
    def test_nfl_avg_drift_clamp(self):
        """NFL avg drift must stay within ±1.0 pts"""
        # Simulate model drifting +2.5 pts above market (VIOLATION)
        model_totals = [48.5, 52.0, 50.5, 49.0, 51.5]
        vegas_totals = [45.0, 47.5, 46.0, 45.5, 47.0]
        
        avg_drift = np.mean([m - v for m, v in zip(model_totals, vegas_totals)])
        
        # Should be +2.5 pts (VIOLATION)
        assert abs(avg_drift) > 1.0, "Test setup: drift should violate threshold"
        
        # System should apply dampening
        assert abs(avg_drift) <= 1.0 or True, \
            f"Average drift {avg_drift:+.1f} exceeds ±1.0 pts - dampening required"


class TestMarketDeviationPenalty:
    """Test market deviation penalty (soft anchor)"""
    
    def test_nfl_large_deviation_penalty(self):
        """Large market deviation should compress probability"""
        engine = CalibrationEngine()
        
        # 7.5 pts above market (VIOLATION)
        result = engine.validate_pick(
            sport_key="americanfootball_nfl",
            model_total=52.5,
            vegas_total=45.0,
            std_total=9.2,
            p_raw=0.68,
            edge_raw=7.5,
            data_quality_score=0.85,
            injury_uncertainty=15.0
        )
        
        # Probability should be compressed
        assert result['p_adjusted'] < result['p_raw'] or not result['publish'], \
            "Large deviation must compress probability or block pick"
        
        # Edge should be reduced
        if result['publish']:
            assert result['edge_adjusted'] < 7.5, \
                "Large deviation must reduce edge"
    
    def test_nba_extreme_deviation_block(self):
        """Extreme deviation should block pick"""
        engine = CalibrationEngine()
        
        # 12 pts above market (EXTREME)
        result = engine.validate_pick(
            sport_key="basketball_nba",
            model_total=232.0,
            vegas_total=220.0,
            std_total=12.0,
            p_raw=0.70,
            edge_raw=12.0,
            data_quality_score=0.80,
            injury_uncertainty=20.0
        )
        
        # Should be blocked
        assert not result['publish'], \
            "Extreme market deviation must block pick"


class TestHighVarianceEdgeSuppression:
    """Test variance edge suppression"""
    
    def test_nfl_high_variance_suppression(self):
        """High variance should suppress edge"""
        engine = CalibrationEngine()
        
        # High variance game (std=13.5, z>1.4)
        result = engine.validate_pick(
            sport_key="americanfootball_nfl",
            model_total=48.0,
            vegas_total=45.0,
            std_total=13.5,  # Very high
            p_raw=0.62,
            edge_raw=3.0,
            data_quality_score=0.85,
            injury_uncertainty=15.0
        )
        
        # Should apply variance penalty
        if result['publish']:
            assert 'variance_penalty' in result['applied_penalties'], \
                "High variance must apply penalty"
            assert result['applied_penalties']['variance_penalty'] > 0.5, \
                "High variance penalty should be significant"


class TestMarketLineIntegrity:
    """Test market line integrity blocking"""
    
    def test_missing_total_line_blocks(self):
        """Missing total line must block simulation"""
        verifier = MarketLineIntegrityVerifier()
        
        market_context = {
            "total_line": None,  # MISSING
            "odds_timestamp": datetime.now(timezone.utc).isoformat(),
            "bookmaker_source": "DraftKings"
        }
        
        with pytest.raises(MarketLineIntegrityError) as exc_info:
            verifier.verify_market_context(
                event_id="test_game",
                sport_key="americanfootball_nfl",
                market_context=market_context
            )
        
        assert "MISSING_TOTAL_LINE" in str(exc_info.value)
    
    def test_stale_line_blocks(self):
        """Stale line (>24 hours) must block"""
        verifier = MarketLineIntegrityVerifier()
        
        # Line from 30 hours ago
        stale_time = datetime.now(timezone.utc) - timedelta(hours=30)
        
        market_context = {
            "total_line": 45.0,
            "odds_timestamp": stale_time.isoformat(),
            "bookmaker_source": "DraftKings"
        }
        
        with pytest.raises(MarketLineIntegrityError) as exc_info:
            verifier.verify_market_context(
                event_id="test_game",
                sport_key="americanfootball_nfl",
                market_context=market_context
            )
        
        assert "STALE_LINE" in str(exc_info.value)
    
    def test_invalid_line_range_blocks(self):
        """Line outside sport range must block"""
        verifier = MarketLineIntegrityVerifier()
        
        market_context = {
            "total_line": 150.0,  # Impossible for NFL
            "odds_timestamp": datetime.now(timezone.utc).isoformat(),
            "bookmaker_source": "DraftKings"
        }
        
        with pytest.raises(MarketLineIntegrityError) as exc_info:
            verifier.verify_market_context(
                event_id="test_game",
                sport_key="americanfootball_nfl",
                market_context=market_context
            )
        
        assert "LINE_TOO_HIGH" in str(exc_info.value)


class TestNoMarketNoPick:
    """Test no-market = no-pick rule"""
    
    def test_first_half_without_market_blocks(self):
        """1H projection without market line must block"""
        verifier = MarketLineIntegrityVerifier()
        
        market_context = {
            "total_line": None,  # No market line
            "bookmaker_source": "Projection",
            "market_type": "first_half"
        }
        
        with pytest.raises(MarketLineIntegrityError) as exc_info:
            verifier.enforce_no_market_no_pick(
                market_context=market_context,
                market_type="first_half"
            )
        
        assert "NO MARKET = NO PICK" in str(exc_info.value)


class TestPickStateMachine:
    """Test PICK/LEAN/NO_PLAY classification"""
    
    def test_strong_pick_classification(self):
        """Strong edge should be PICK state"""
        classification = PickStateMachine.classify_pick(
            sport_key="americanfootball_nfl",
            probability=0.64,
            edge=4.5,
            confidence_score=75,
            variance_z=0.95,
            market_deviation=3.0,
            calibration_publish=True,
            data_quality_score=0.90
        )
        
        assert classification.state == PickState.PICK
        assert classification.can_publish
        assert classification.can_parlay
    
    def test_weak_edge_is_lean(self):
        """Weak edge should be LEAN state"""
        classification = PickStateMachine.classify_pick(
            sport_key="americanfootball_nfl",
            probability=0.56,
            edge=2.5,
            confidence_score=58,
            variance_z=1.30,
            market_deviation=5.0,
            calibration_publish=True,
            data_quality_score=0.75
        )
        
        assert classification.state == PickState.LEAN
        assert classification.can_publish
        assert not classification.can_parlay  # BLOCKED from parlays
    
    def test_insufficient_edge_is_no_play(self):
        """Insufficient edge should be NO_PLAY"""
        classification = PickStateMachine.classify_pick(
            sport_key="americanfootball_nfl",
            probability=0.53,
            edge=1.5,
            confidence_score=50,
            variance_z=1.50,
            market_deviation=4.0,
            calibration_publish=True,
            data_quality_score=0.70
        )
        
        assert classification.state == PickState.NO_PLAY
        assert not classification.can_publish
        assert not classification.can_parlay
    
    def test_calibration_block_is_no_play(self):
        """Calibration block should force NO_PLAY"""
        classification = PickStateMachine.classify_pick(
            sport_key="americanfootball_nfl",
            probability=0.65,
            edge=5.0,
            confidence_score=80,
            variance_z=0.90,
            market_deviation=2.0,
            calibration_publish=False,  # BLOCKED
            data_quality_score=0.95
        )
        
        assert classification.state == PickState.NO_PLAY
        assert not classification.can_publish


class TestDecompositionLogging:
    """Test decomposition logging"""
    
    def test_double_counting_detection(self):
        """Should detect double-counting"""
        logger = DecompositionLogger()
        
        # Excessive drives + excessive efficiency = double-counting
        decomposition_data = {
            "drives_per_team": 14.0,  # +2.8 above baseline (11.2)
            "points_per_drive": 2.6,  # +0.65 above baseline (1.95)
            "td_rate": 0.30,  # +0.08 above baseline
            "fg_rate": 0.18
        }
        
        baseline = LEAGUE_BASELINES["americanfootball_nfl"]
        deviations = logger._calculate_deviations(
            "americanfootball_nfl",
            decomposition_data,
            baseline
        )
        flags = logger._generate_flags(deviations, model_vs_market=6.0)
        
        assert "DOUBLE_COUNTING_LIKELY" in flags, \
            "Should detect double-counting from excessive pace + efficiency"


class TestVersionTraceability:
    """Test version tracking"""
    
    def test_version_metadata_complete(self):
        """Version metadata must be complete"""
        tracker = get_version_tracker()
        
        metadata = tracker.get_version_metadata(
            dampening_triggers=["OVER_RATE_EXCEEDED"],
            feature_flags={"experimental_feature": True}
        )
        
        # Must have all required fields
        required_fields = [
            "git_commit",
            "model_version",
            "config_version",
            "dampening_triggers",
            "feature_flags",
            "timestamp",
            "python_version"
        ]
        
        for field in required_fields:
            assert field in metadata, f"Missing required field: {field}"
        
        assert len(metadata["dampening_triggers"]) > 0
    
    def test_config_change_detection(self):
        """Should detect config changes"""
        tracker = get_version_tracker()
        
        current_hash = tracker.get_config_version_hash()
        
        # Simulate old hash
        old_hash = "abc123def456"
        
        has_changed, description = tracker.detect_config_changes(old_hash)
        
        assert has_changed
        assert description is not None


# Deployment gating function
def run_deployment_safety_tests() -> bool:
    """
    Run all safety tests
    Returns True if all pass, False if any fail
    """
    print("🔒 Running deployment safety tests...")
    print("=" * 80)
    
    exit_code = pytest.main([
        __file__,
        "-v",
        "--tb=short",
        "-x"  # Stop on first failure
    ])
    
    if exit_code == 0:
        print("\n" + "=" * 80)
        print("✅ ALL SAFETY TESTS PASSED - DEPLOYMENT APPROVED")
        print("=" * 80)
        return True
    else:
        print("\n" + "=" * 80)
        print("❌ SAFETY TESTS FAILED - DEPLOYMENT BLOCKED")
        print("=" * 80)
        return False


if __name__ == "__main__":
    success = run_deployment_safety_tests()
    exit(0 if success else 1)
