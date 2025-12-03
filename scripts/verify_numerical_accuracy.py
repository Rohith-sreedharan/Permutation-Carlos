"""
Numerical Accuracy System - Verification Script

Tests all core components to ensure numerical accuracy is enforced.
Run this before deploying to production.

Usage:
    python scripts/verify_numerical_accuracy.py
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import numpy as np
from datetime import datetime, timezone

def test_simulation_output_validation():
    """Test that SimulationOutput enforces data integrity"""
    from backend.core.numerical_accuracy import SimulationOutput
    
    print("\n🧪 Testing SimulationOutput validation...")
    
    # Valid output
    try:
        valid_output = SimulationOutput(
            median_total=225.5,
            mean_total=226.1,
            variance_total=125.4,
            home_win_probability=0.58,
            away_win_probability=0.42,
            h1_median_total=110.2,
            h1_variance=42.3,
            sim_count=50000,
            timestamp=datetime.now(timezone.utc),
            source="test"
        )
        valid_output.validate()
        print("  ✅ Valid SimulationOutput accepted")
    except Exception as e:
        print(f"  ❌ FAIL: Valid output rejected: {e}")
        return False
    
    # Invalid: negative median
    try:
        invalid = SimulationOutput(
            median_total=-10.0,  # Invalid!
            mean_total=226.1,
            variance_total=125.4,
            home_win_probability=0.58,
            away_win_probability=0.42,
            h1_median_total=None,
            h1_variance=None,
            sim_count=50000,
            timestamp=datetime.now(timezone.utc),
            source="test"
        )
        invalid.validate()
        print("  ❌ FAIL: Negative median_total accepted (should raise error)")
        return False
    except ValueError as e:
        print(f"  ✅ Negative median correctly rejected: {e}")
    
    # Invalid: win probability > 1.0
    try:
        invalid = SimulationOutput(
            median_total=225.5,
            mean_total=226.1,
            variance_total=125.4,
            home_win_probability=1.5,  # Invalid!
            away_win_probability=0.42,
            h1_median_total=None,
            h1_variance=None,
            sim_count=50000,
            timestamp=datetime.now(timezone.utc),
            source="test"
        )
        invalid.validate()
        print("  ❌ FAIL: Win probability > 1.0 accepted (should raise error)")
        return False
    except ValueError as e:
        print(f"  ✅ Invalid win probability correctly rejected: {e}")
    
    # Invalid: wrong sim_count
    try:
        invalid = SimulationOutput(
            median_total=225.5,
            mean_total=226.1,
            variance_total=125.4,
            home_win_probability=0.58,
            away_win_probability=0.42,
            h1_median_total=None,
            h1_variance=None,
            sim_count=15000,  # Invalid! Must be 10K/25K/50K/100K
            timestamp=datetime.now(timezone.utc),
            source="test"
        )
        invalid.validate()
        print("  ❌ FAIL: Invalid sim_count accepted (should raise error)")
        return False
    except ValueError as e:
        print(f"  ✅ Invalid sim_count correctly rejected: {e}")
    
    return True


def test_over_under_analysis():
    """Test Over/Under probability calculations"""
    from backend.core.numerical_accuracy import OverUnderAnalysis
    
    print("\n🧪 Testing OverUnderAnalysis...")
    
    # Create sample simulation data
    totals = np.array([220, 222, 225, 228, 230, 232, 235, 238, 240])
    book_line = 230.0
    
    try:
        ou = OverUnderAnalysis.from_simulation(totals, book_line)
        
        # Verify counts
        expected_over = 3  # 232, 235, 238, 240 = 4, but 240 is last so 3?
        # Actually: 232, 235, 238, 240 = 4 values > 230
        actual_over = sum(1 for t in totals if t > book_line)
        
        if ou.sims_over == actual_over:
            print(f"  ✅ Over count correct: {ou.sims_over}/{len(totals)}")
        else:
            print(f"  ❌ FAIL: Over count wrong. Expected {actual_over}, got {ou.sims_over}")
            return False
        
        # Verify probabilities sum to ~1.0 (excluding pushes)
        prob_sum = ou.over_probability + ou.under_probability
        if abs(prob_sum - 1.0) < 0.01:
            print(f"  ✅ Probabilities sum to 1.0: {prob_sum:.4f}")
        else:
            print(f"  ❌ FAIL: Probabilities don't sum to 1.0: {prob_sum:.4f}")
            return False
        
        print(f"  ✅ Over: {ou.over_probability:.1%}, Under: {ou.under_probability:.1%}")
        
    except Exception as e:
        print(f"  ❌ FAIL: OverUnderAnalysis failed: {e}")
        return False
    
    return True


def test_expected_value():
    """Test EV calculations"""
    from backend.core.numerical_accuracy import ExpectedValue
    
    print("\n🧪 Testing ExpectedValue calculations...")
    
    # Test case 1: Positive American odds
    try:
        ev = ExpectedValue.calculate(model_prob=0.55, american_odds=150)
        
        # Implied prob for +150 should be 100/(150+100) = 0.4
        expected_implied = 0.4
        if abs(ev.implied_probability - expected_implied) < 0.01:
            print(f"  ✅ +150 odds → implied prob {ev.implied_probability:.2%}")
        else:
            print(f"  ❌ FAIL: Expected {expected_implied:.2%}, got {ev.implied_probability:.2%}")
            return False
        
        # Edge should be 0.55 - 0.4 = 0.15
        if abs(ev.edge_percentage - 0.15) < 0.01:
            print(f"  ✅ Edge: {ev.edge_percentage:.1%}")
        else:
            print(f"  ❌ FAIL: Expected 15% edge, got {ev.edge_percentage:.1%}")
            return False
        
    except Exception as e:
        print(f"  ❌ FAIL: Positive odds EV failed: {e}")
        return False
    
    # Test case 2: Negative American odds
    try:
        ev = ExpectedValue.calculate(model_prob=0.58, american_odds=-110)
        
        # Implied prob for -110 should be 110/(110+100) = 0.5238
        expected_implied = 0.5238
        if abs(ev.implied_probability - expected_implied) < 0.01:
            print(f"  ✅ -110 odds → implied prob {ev.implied_probability:.2%}")
        else:
            print(f"  ❌ FAIL: Expected {expected_implied:.2%}, got {ev.implied_probability:.2%}")
            return False
        
        # Should be EV+ (edge >= 3%, tier >= 25K)
        if ev.is_ev_plus(current_tier=50000):
            print(f"  ✅ Correctly classified as EV+ (edge {ev.edge_percentage:.1%})")
        else:
            print(f"  ❌ FAIL: Should be EV+ with {ev.edge_percentage:.1%} edge at 50K tier")
            return False
        
    except Exception as e:
        print(f"  ❌ FAIL: Negative odds EV failed: {e}")
        return False
    
    return True


def test_closing_line_value():
    """Test CLV tracking"""
    from backend.core.numerical_accuracy import ClosingLineValue
    
    print("\n🧪 Testing ClosingLineValue...")
    
    # Test case: Over lean, line moves up (favorable)
    try:
        clv = ClosingLineValue(
            event_id="test123",
            prediction_timestamp=datetime.now(timezone.utc),
            model_projection=227.5,
            book_line_open=225.5,
            book_line_close=None,
            lean="over"
        )
        
        # Line moves from 225.5 → 226.5 (in our favor)
        clv.calculate_clv(closing_line=226.5)
        
        if clv.clv_favorable:
            print("  ✅ Over lean + line up = favorable CLV")
        else:
            print("  ❌ FAIL: Should be favorable when line moves toward our projection")
            return False
        
    except Exception as e:
        print(f"  ❌ FAIL: CLV calculation failed: {e}")
        return False
    
    # Test case: Under lean, line moves down (favorable)
    try:
        clv = ClosingLineValue(
            event_id="test124",
            prediction_timestamp=datetime.now(timezone.utc),
            model_projection=223.0,
            book_line_open=225.5,
            book_line_close=None,
            lean="under"
        )
        
        # Line moves from 225.5 → 224.0 (in our favor)
        clv.calculate_clv(closing_line=224.0)
        
        if clv.clv_favorable:
            print("  ✅ Under lean + line down = favorable CLV")
        else:
            print("  ❌ FAIL: Should be favorable when line moves toward our projection")
            return False
        
    except Exception as e:
        print(f"  ❌ FAIL: CLV calculation failed: {e}")
        return False
    
    return True


def test_simulation_tier_config():
    """Test tier configurations"""
    from backend.core.numerical_accuracy import SimulationTierConfig
    
    print("\n🧪 Testing SimulationTierConfig...")
    
    try:
        # Test 10K tier
        tier_10k = SimulationTierConfig.get_tier_config(10000)
        if tier_10k['label'] == 'Starter' and tier_10k['stability_band'] == 0.15:
            print(f"  ✅ 10K tier: {tier_10k['label']}, ±{tier_10k['stability_band']*100:.0f}% band")
        else:
            print(f"  ❌ FAIL: 10K tier config wrong")
            return False
        
        # Test 50K tier
        tier_50k = SimulationTierConfig.get_tier_config(50000)
        if tier_50k['label'] == 'Pro' and tier_50k['stability_band'] == 0.06:
            print(f"  ✅ 50K tier: {tier_50k['label']}, ±{tier_50k['stability_band']*100:.0f}% band")
        else:
            print(f"  ❌ FAIL: 50K tier config wrong")
            return False
        
        # Test 100K tier
        tier_100k = SimulationTierConfig.get_tier_config(100000)
        if tier_100k['label'] == 'Elite' and tier_100k['stability_band'] == 0.035:
            print(f"  ✅ 100K tier: {tier_100k['label']}, ±{tier_100k['stability_band']*100:.1f}% band")
        else:
            print(f"  ❌ FAIL: 100K tier config wrong")
            return False
        
        # Test invalid tier
        try:
            SimulationTierConfig.get_tier_config(15000)
            print("  ❌ FAIL: Invalid tier accepted (should raise error)")
            return False
        except ValueError:
            print("  ✅ Invalid tier correctly rejected")
        
    except Exception as e:
        print(f"  ❌ FAIL: Tier config test failed: {e}")
        return False
    
    return True


def test_confidence_calculator():
    """Test confidence score calculations"""
    from backend.core.numerical_accuracy import ConfidenceCalculator
    
    print("\n🧪 Testing ConfidenceCalculator...")
    
    try:
        # Low variance, high sims = high confidence
        conf_high = ConfidenceCalculator.calculate(
            variance=50.0,
            sim_count=100000,
            volatility="LOW",
            median_value=225.0
        )
        
        if conf_high >= 70:
            print(f"  ✅ Low variance + 100K sims = high confidence ({conf_high}/100)")
        else:
            print(f"  ❌ FAIL: Expected high confidence, got {conf_high}/100")
            return False
        
        # High variance, low sims = low confidence
        conf_low = ConfidenceCalculator.calculate(
            variance=300.0,
            sim_count=10000,
            volatility="HIGH",
            median_value=225.0
        )
        
        if conf_low <= 50:
            print(f"  ✅ High variance + 10K sims = low confidence ({conf_low}/100)")
        else:
            print(f"  ❌ FAIL: Expected low confidence, got {conf_low}/100")
            return False
        
        # Confidence should increase with tier
        conf_25k = ConfidenceCalculator.calculate(
            variance=125.0,
            sim_count=25000,
            volatility="MEDIUM",
            median_value=225.0
        )
        
        conf_100k = ConfidenceCalculator.calculate(
            variance=125.0,
            sim_count=100000,
            volatility="MEDIUM",
            median_value=225.0
        )
        
        if conf_100k > conf_25k:
            print(f"  ✅ Confidence increases with tier: 25K={conf_25k}, 100K={conf_100k}")
        else:
            print(f"  ❌ FAIL: 100K tier should have higher confidence than 25K")
            return False
        
    except Exception as e:
        print(f"  ❌ FAIL: Confidence calculation failed: {e}")
        return False
    
    return True


def test_edge_validator():
    """Test edge classification"""
    from backend.core.numerical_accuracy import EdgeValidator
    
    print("\n🧪 Testing EdgeValidator...")
    
    try:
        # EDGE: All conditions met
        edge = EdgeValidator.classify_edge(
            model_prob=0.58,
            implied_prob=0.52,
            confidence=72,
            volatility="MEDIUM",
            sim_count=50000,
            injury_impact=0.8
        )
        
        if edge == "EDGE":
            print("  ✅ Strong conditions → EDGE classification")
        else:
            print(f"  ❌ FAIL: Expected EDGE, got {edge}")
            return False
        
        # LEAN: Edge but low confidence
        lean = EdgeValidator.classify_edge(
            model_prob=0.58,
            implied_prob=0.52,
            confidence=50,  # Below 60 threshold
            volatility="MEDIUM",
            sim_count=50000,
            injury_impact=0.8
        )
        
        if lean == "LEAN":
            print("  ✅ Edge but low confidence → LEAN classification")
        else:
            print(f"  ❌ FAIL: Expected LEAN, got {lean}")
            return False
        
        # NEUTRAL: Small edge
        neutral = EdgeValidator.classify_edge(
            model_prob=0.52,
            implied_prob=0.51,
            confidence=72,
            volatility="MEDIUM",
            sim_count=50000,
            injury_impact=0.8
        )
        
        if neutral == "NEUTRAL":
            print("  ✅ Small edge → NEUTRAL classification")
        else:
            print(f"  ❌ FAIL: Expected NEUTRAL, got {neutral}")
            return False
        
    except Exception as e:
        print(f"  ❌ FAIL: Edge validation failed: {e}")
        return False
    
    return True


def main():
    """Run all verification tests"""
    print("=" * 60)
    print("NUMERICAL ACCURACY SYSTEM - VERIFICATION")
    print("=" * 60)
    
    tests = [
        ("SimulationOutput Validation", test_simulation_output_validation),
        ("OverUnderAnalysis", test_over_under_analysis),
        ("ExpectedValue", test_expected_value),
        ("ClosingLineValue", test_closing_line_value),
        ("SimulationTierConfig", test_simulation_tier_config),
        ("ConfidenceCalculator", test_confidence_calculator),
        ("EdgeValidator", test_edge_validator),
    ]
    
    results = []
    for name, test_func in tests:
        try:
            passed = test_func()
            results.append((name, passed))
        except Exception as e:
            print(f"\n❌ FATAL ERROR in {name}: {e}")
            results.append((name, False))
    
    print("\n" + "=" * 60)
    print("VERIFICATION SUMMARY")
    print("=" * 60)
    
    for name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status} - {name}")
    
    all_passed = all(passed for _, passed in results)
    
    print("\n" + "=" * 60)
    if all_passed:
        print("✅ ALL TESTS PASSED - System ready for deployment")
        print("=" * 60)
        return 0
    else:
        failed_count = sum(1 for _, passed in results if not passed)
        print(f"❌ {failed_count}/{len(tests)} TESTS FAILED - Fix issues before deploying")
        print("=" * 60)
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
