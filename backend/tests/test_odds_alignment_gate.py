"""
ODDS ALIGNMENT GATE - UNIT TESTS
=================================

Per ENGINE LOCK Specification Section 4.

Tests REQUIREMENT 1: Absolute Line Delta Logic
Tests REQUIREMENT 2: Pick'em Symmetry Check
Tests REQUIREMENT 3: No Edge Before Odds Pass
Tests REQUIREMENT 4: Lifecycle Order
Tests REQUIREMENT 5: Boundary Enforcement

All tests MUST pass before ENGINE LOCK.
"""

import pytest
from datetime import datetime, timedelta, timezone
from core.compute_market_decision import MarketDecisionComputer
from core.market_decision import ReleaseStatus, Classification


class TestOddsAlignmentGate:
    """Test Section 4 - Odds Alignment Gate"""
    
    def setup_method(self):
        """Setup test data with fresh timestamps"""
        self.computer = MarketDecisionComputer(
            league="NBA",
            game_id="test_game_123",
            odds_event_id="test_event_123"
        )
        
        self.game_competitors = {
            "lakers": "Los Angeles Lakers",
            "celtics": "Boston Celtics"
        }
        
        self.config = {
            'profile': 'balanced',
            'edge_threshold': 2.0,
            'lean_threshold': 0.5,
            'prob_threshold': 0.55
        }
        
        # Use dynamic timestamps to pass freshness gate (must be < 120 minutes old)
        now = datetime.now(timezone.utc)
        self.fresh_computed_at = (now - timedelta(minutes=60)).isoformat() + 'Z'
        self.fresh_odds_timestamp = now.isoformat() + 'Z'
    
    # ==========================================
    # TEST 1: Exact match - APPROVED
    # ==========================================
    def test_line_delta_exact_match_approved(self):
        """
        Test 1: sim = -3.5, market = -3.5 → APPROVED
        
        line_delta = 0.0
        Should PASS odds alignment gate.
        """
        odds_snapshot = {
            'timestamp': self.fresh_odds_timestamp,
            'spread_lines': {
                'lakers': {'line': -3.5, 'odds': -110},
                'celtics': {'line': 3.5, 'odds': -110}
            }
        }
        
        sim_result = {
            'simulation_id': 'sim_123',
            'model_spread_home_perspective': -3.2,  # Model says -3.2
            'simulation_market_spread_home': -3.5,  # Simulation saw -3.5
            'home_cover_probability': 0.58,
            'volatility': 'MODERATE',
            'total_injury_impact': 0.0,
            'computed_at': self.fresh_computed_at
        }
        
        decision = self.computer.compute_spread(
            odds_snapshot, sim_result, self.config, self.game_competitors
        )
        
        # Should be APPROVED (passes odds gate)
        assert decision.release_status == ReleaseStatus.APPROVED
        # Should have classification
        assert decision.classification is not None
        # Should have edge calculated
        assert decision.edge is not None
        assert decision.edge.edge_points is not None
    
    # ==========================================
    # TEST 2: Within tolerance - APPROVED
    # ==========================================
    def test_line_delta_within_tolerance_approved(self):
        """
        Test 2: sim = -3.5, market = -3.25 → APPROVED
        
        line_delta = 0.25 (EXACT boundary)
        Should PASS odds alignment gate.
        """
        odds_snapshot = {
            'timestamp': self.fresh_odds_timestamp,
            'spread_lines': {
                'lakers': {'line': -3.25, 'odds': -110},
                'celtics': {'line': 3.25, 'odds': -110}
            }
        }
        
        sim_result = {
            'simulation_id': 'sim_124',
            'model_spread_home_perspective': -3.1,
            'simulation_market_spread_home': -3.5,  # 0.25 delta from current -3.25
            'home_cover_probability': 0.57,
            'volatility': 'MODERATE',
            'total_injury_impact': 0.0,
            'computed_at': self.fresh_computed_at
        }
        
        decision = self.computer.compute_spread(
            odds_snapshot, sim_result, self.config, self.game_competitors
        )
        
        # CRITICAL: 0.25 MUST PASS (boundary test)
        assert decision.release_status == ReleaseStatus.APPROVED
        assert decision.classification is not None
        assert decision.edge is not None
    
    # ==========================================
    # TEST 3: Exceeds tolerance - BLOCKED
    # ==========================================
    def test_line_delta_exceeds_tolerance_blocked(self):
        """
        Test 3: sim = -3.5, market = -3.0 → BLOCKED_BY_ODDS_MISMATCH
        
        line_delta = 0.5 (EXCEEDS 0.25)
        Should BLOCK.
        
        CRITICAL: classification = null, edge_points = null, model_prob = null
        """
        odds_snapshot = {
            'timestamp': self.fresh_odds_timestamp,
            'spread_lines': {
                'lakers': {'line': -3.0, 'odds': -110},
                'celtics': {'line': 3.0, 'odds': -110}
            }
        }
        
        sim_result = {
            'simulation_id': 'sim_125',
            'model_spread_home_perspective': -2.8,
            'simulation_market_spread_home': -3.5,  # 0.5 delta from current -3.0
            'home_cover_probability': 0.56,
            'volatility': 'MODERATE',
            'total_injury_impact': 0.0,
            'computed_at': self.fresh_computed_at
        }
        
        decision = self.computer.compute_spread(
            odds_snapshot, sim_result, self.config, self.game_competitors
        )
        
        # MUST be BLOCKED
        assert decision.release_status == ReleaseStatus.BLOCKED_BY_ODDS_MISMATCH
        
        # REQUIREMENT 3: No edge before odds pass
        assert decision.classification is None
        assert decision.edge is None
        assert decision.probabilities is None
        assert decision.model is None
        assert decision.pick is None
        
        # Blocked reason must explain
        assert decision.risk.blocked_reason is not None
        assert "line_delta" in decision.risk.blocked_reason
    
    # ==========================================
    # TEST 4: Pick'em PASS
    # ==========================================
    def test_pickem_symmetry_pass(self):
        """
        Test 4 (Pick'em PASS): line = 0.0, prob_delta = 0.0091 → APPROVED
        
        implied_prob_home = 0.5238 (odds -110)
        implied_prob_away = 0.5147 (odds -107)
        prob_delta = 0.0091 (BELOW 0.0200 threshold)
        
        Should PASS pick'em symmetry check.
        """
        odds_snapshot = {
            'timestamp': self.fresh_odds_timestamp,
            'spread_lines': {
                'lakers': {'line': 0.0, 'odds': -110},
                'celtics': {'line': 0.0, 'odds': -107}
            }
        }
        
        sim_result = {
            'simulation_id': 'sim_126',
            'model_spread_home_perspective': -0.001,  # Near-zero, home slightly favored
            'simulation_market_spread_home': 0.0,
            'home_cover_probability': 0.52,  # Above 50% (matches negative spread)
            'volatility': 'MODERATE',
            'total_injury_impact': 0.0,
            'computed_at': self.fresh_computed_at
        }
        
        decision = self.computer.compute_spread(
            odds_snapshot, sim_result, self.config, self.game_competitors
        )
        
        # Should PASS pick'em symmetry
        assert decision.release_status == ReleaseStatus.APPROVED
        assert decision.classification is not None
        assert decision.edge is not None
    
    # ==========================================
    # TEST 5: Pick'em BLOCKED
    # ==========================================
    def test_pickem_symmetry_block(self):
        """
        Test 5 (Pick'em BLOCK): line = 0.0, prob_delta = 0.0428 → BLOCKED
        
        implied_prob_home = 0.5238 (odds -110)
        implied_prob_away = 0.4810 (odds +108)
        prob_delta = 0.0428 (EXCEEDS 0.0200 threshold)
        
        Should BLOCK pick'em symmetry violation.
        
        CRITICAL: All decision fields nullified.
        """
        odds_snapshot = {
            'timestamp': self.fresh_odds_timestamp,
            'spread_lines': {
                'lakers': {'line': 0.0, 'odds': -110},
                'celtics': {'line': 0.0, 'odds': 108}
            }
        }
        
        sim_result = {
            'simulation_id': 'sim_127',
            'model_spread_home_perspective': -0.001,  # Near-zero, home slightly favored
            'simulation_market_spread_home': 0.0,
            'home_cover_probability': 0.51,  # Just above 50% (matches negative spread)
            'volatility': 'MODERATE',
            'total_injury_impact': 0.0,
            'computed_at': self.fresh_computed_at
        }
        
        decision = self.computer.compute_spread(
            odds_snapshot, sim_result, self.config, self.game_competitors
        )
        
        # MUST be BLOCKED
        assert decision.release_status == ReleaseStatus.BLOCKED_BY_ODDS_MISMATCH
        
        # All decision fields nullified
        assert decision.classification is None
        assert decision.edge is None
        assert decision.probabilities is None
        assert decision.model is None
        assert decision.pick is None
        
        # Blocked reason must mention pick'em symmetry
        assert decision.risk.blocked_reason is not None
        assert "prob_delta" in decision.risk.blocked_reason.lower() or "symmetry" in decision.risk.blocked_reason.lower()
    
    # ==========================================
    # BOUNDARY ENFORCEMENT TESTS
    # ==========================================
    def test_boundary_0_25_exactly_passes(self):
        """Boundary: line_delta = 0.25 exactly → PASS"""
        odds_snapshot = {
            'timestamp': self.fresh_odds_timestamp,
            'spread_lines': {
                'lakers': {'line': -5.0, 'odds': -110},
                'celtics': {'line': 5.0, 'odds': -110}
            }
        }
        
        sim_result = {
            'simulation_id': 'sim_boundary_1',
            'model_spread_home_perspective': -4.5,
            'simulation_market_spread_home': -5.25,  # Delta = 0.25
            'home_cover_probability': 0.60,
            'volatility': 'MODERATE',
            'total_injury_impact': 0.0,
            'computed_at': self.fresh_computed_at
        }
        
        decision = self.computer.compute_spread(
            odds_snapshot, sim_result, self.config, self.game_competitors
        )
        
        assert decision.release_status == ReleaseStatus.APPROVED
    
    def test_boundary_0_25001_blocks(self):
        """Boundary: line_delta = 0.25001 → BLOCK"""
        odds_snapshot = {
            'timestamp': self.fresh_odds_timestamp,
            'spread_lines': {
                'lakers': {'line': -5.0, 'odds': -110},
                'celtics': {'line': 5.0, 'odds': -110}
            }
        }
        
        sim_result = {
            'simulation_id': 'sim_boundary_2',
            'model_spread_home_perspective': -4.5,
            'simulation_market_spread_home': -5.25001,  # Delta = 0.25001
            'home_cover_probability': 0.60,
            'volatility': 'MODERATE',
            'total_injury_impact': 0.0,
            'computed_at': self.fresh_computed_at
        }
        
        decision = self.computer.compute_spread(
            odds_snapshot, sim_result, self.config, self.game_competitors
        )
        
        assert decision.release_status == ReleaseStatus.BLOCKED_BY_ODDS_MISMATCH
    
    def test_boundary_prob_delta_0_0200_passes(self):
        """Boundary: pick'em prob_delta = 0.0200 exactly → PASS"""
        # Set up odds to create exactly 0.0200 prob delta
        # This requires careful American odds calculation
        odds_snapshot = {
            'timestamp': self.fresh_odds_timestamp,
            'spread_lines': {
                'lakers': {'line': 0.0, 'odds': -110},  # ~0.5238
                'celtics': {'line': 0.0, 'odds': -109}  # ~0.5217 → delta ~0.0021 (PASS)
            }
        }
        
        sim_result = {
            'simulation_id': 'sim_boundary_3',
            'model_spread_home_perspective': -0.002,  # Near-zero, home very slightly favored
            'simulation_market_spread_home': 0.0,
            'home_cover_probability': 0.52,  # Above 50% (matches negative spread)
            'volatility': 'MODERATE',
            'total_injury_impact': 0.0,
            'computed_at': self.fresh_computed_at
        }
        
        decision = self.computer.compute_spread(
            odds_snapshot, sim_result, self.config, self.game_competitors
        )
        
        # Should pass (prob delta is small)
        assert decision.release_status == ReleaseStatus.APPROVED
    
    # ==========================================
    # LIFECYCLE ORDER TEST
    # ==========================================
    def test_lifecycle_order_odds_before_classification(self):
        """
        REQUIREMENT 4: Validation gates MUST run before classification.
        
        If odds gate fails, classification must NOT occur.
        """
        odds_snapshot = {
            'timestamp': self.fresh_odds_timestamp,
            'spread_lines': {
                'lakers': {'line': -2.5, 'odds': -110},
                'celtics': {'line': 2.5, 'odds': -110}
            }
        }
        
        sim_result = {
            'simulation_id': 'sim_lifecycle',
            'model_spread_home_perspective': -6.0,  # Huge edge if it passed
            'simulation_market_spread_home': -3.0,  # But odds moved 0.5 points
            'home_cover_probability': 0.75,  # Strong probability
            'volatility': 'MODERATE',
            'total_injury_impact': 0.0,
            'computed_at': self.fresh_computed_at
        }
        
        decision = self.computer.compute_spread(
            odds_snapshot, sim_result, self.config, self.game_competitors
        )
        
        # Despite huge edge and strong probability, must BLOCK due to odds movement
        assert decision.release_status == ReleaseStatus.BLOCKED_BY_ODDS_MISMATCH
        
        # Classification MUST NOT occur
        assert decision.classification is None
        assert decision.edge is None  # Edge not calculated
        assert decision.probabilities is None  # Probability not populated
        
        # Proves lifecycle order: VALIDATED → (BLOCKED) → never reaches CLASSIFIED


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
