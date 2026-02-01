"""
Test Safety Engine Suppression Behavior
Verifies that divergence-based suppression is explicit and visible
"""
import unittest
import sys
from pathlib import Path

# Add backend directory to Python path
backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from core.safety_engine import SafetyEngine, EnvironmentType


class TestSafetySuppressionTransparency(unittest.TestCase):
    """Test that suppression is loud, not hidden"""
    
    def test_divergence_suppression_is_explicit(self):
        """
        REQUIREMENT 4: Test that forces divergence 10.8 with limit 10
        and asserts response contains explicit suppression metadata
        """
        engine = SafetyEngine()
        
        # Setup: model total diverges 10.8 points from market (exceeds free tier limit of 10)
        model_total = 230.8
        market_total = 220.0
        expected_divergence = 10.8
        
        result = engine.evaluate_simulation(
            sport_key="basketball_ncaab",
            model_total=model_total,
            market_total=market_total,
            market_id="test_market",
            is_postseason=False,
            is_championship=False,
            weather_data=None,
            variance=100,
            confidence=0.7,
            market_type="total",
            user_tier="free"  # Free tier has strict limit of 10
        )
        
        # ASSERTION 1: safety.is_suppressed = true
        self.assertTrue(
            result["is_suppressed"],
            "Expected is_suppressed=True when divergence exceeds limit"
        )
        
        # ASSERTION 2: suppression_reason is explicit
        self.assertEqual(
            result["suppression_reason"],
            "DIVERGENCE_EXCEEDED",
            "Expected suppression_reason='DIVERGENCE_EXCEEDED'"
        )
        
        # ASSERTION 3: divergence values are present
        self.assertAlmostEqual(
            result["divergence_score"],
            expected_divergence,
            places=1,
            msg="Divergence score should be 10.8"
        )
        
        self.assertEqual(
            result["divergence_limit"],
            10,
            "Free tier divergence limit should be 10"
        )
        
        # ASSERTION 4: output_mode reflects suppression
        self.assertEqual(
            result["output_mode"],
            "exploration_only",
            "Suppressed simulations should be exploration_only"
        )
        
        # ASSERTION 5: not eligible for official pick
        self.assertFalse(
            result["eligible_for_official_pick"],
            "Suppressed simulations should not be eligible for official picks"
        )
        
        print("✅ Suppression transparency test passed:")
        print(f"   - is_suppressed: {result['is_suppressed']}")
        print(f"   - suppression_reason: {result['suppression_reason']}")
        print(f"   - divergence: {result['divergence_score']:.1f} > {result['divergence_limit']}")
    
    def test_paid_tier_relaxed_limit(self):
        """Test that paid tiers get relaxed divergence limits"""
        engine = SafetyEngine()
        
        # Same scenario but with Pro tier (limit should be 14 instead of 10)
        model_total = 230.8
        market_total = 220.0
        
        result = engine.evaluate_simulation(
            sport_key="basketball_ncaab",
            model_total=model_total,
            market_total=market_total,
            market_id="test_market",
            is_postseason=False,
            is_championship=False,
            weather_data=None,
            variance=100,
            confidence=0.7,
            market_type="total",
            user_tier="pro"  # Pro tier has relaxed limit
        )
        
        # Pro tier should NOT be suppressed (divergence 10.8 < limit 14)
        self.assertFalse(
            result["is_suppressed"],
            "Pro tier with divergence 10.8 should not be suppressed (limit 14)"
        )
        
        self.assertGreater(
            result["divergence_limit"],
            10,
            "Pro tier should have higher divergence limit than free tier"
        )
        
        print("✅ Tier-aware limits test passed:")
        print(f"   - Pro tier limit: {result['divergence_limit']}")
        print(f"   - is_suppressed: {result['is_suppressed']}")
    
    def test_suppression_includes_all_required_fields(self):
        """Test that suppressed response includes all required fields for frontend"""
        engine = SafetyEngine()
        
        result = engine.evaluate_simulation(
            sport_key="basketball_nba",
            model_total=235.0,
            market_total=220.0,  # 15 point divergence
            market_id="test_market",
            is_postseason=False,
            is_championship=False,
            weather_data=None,
            variance=100,
            confidence=0.7,
            market_type="total",
            user_tier="free"
        )
        
        # Required fields for frontend display
        required_fields = [
            "is_suppressed",
            "suppression_reason",
            "divergence_score",
            "divergence_limit",
            "output_mode",
            "risk_score",
            "eligible_for_official_pick"
        ]
        
        for field in required_fields:
            self.assertIn(
                field,
                result,
                f"Safety result must include '{field}' for frontend transparency"
            )
        
        print("✅ All required fields present in suppressed response")


if __name__ == "__main__":
    unittest.main()
