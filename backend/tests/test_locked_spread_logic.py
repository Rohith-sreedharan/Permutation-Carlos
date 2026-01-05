"""
Test Sharp Side Selection — LOCKED DEFINITION

Validates that the locked model spread logic works correctly.
"""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from backend.core.sharp_side_selection import select_sharp_side_spread
from backend.core.sport_configs import VolatilityLevel


def test_positive_model_spread():
    """
    Example 1 — Positive Model Spread (Sharp = FAVORITE)
    
    Market: Hawks +5.5, Knicks -5.5
    Model Spread: +12.3
    
    Expected: Sharp side = FAVORITE (Knicks -5.5)
    """
    print("\n" + "="*80)
    print("TEST 1: Positive Model Spread (+12.3)")
    print("="*80)
    
    selection = select_sharp_side_spread(
        home_team="New York Knicks",
        away_team="Atlanta Hawks",
        market_spread_home=-5.5,  # Knicks are favorite
        model_spread=12.3,  # Positive = underdog (Hawks)
        volatility=VolatilityLevel.MEDIUM
    )
    
    print(f"Market Spread Display: {selection.market_spread_display}")
    print(f"Model Spread Display:  {selection.model_spread_display}")
    print(f"Sharp Side Display:    {selection.sharp_side_display}")
    print(f"\nSharp Action:          {selection.sharp_action}")
    print(f"Edge Magnitude:        {selection.edge_magnitude:.1f} pts")
    print(f"Reasoning:             {selection.reasoning}")
    
    # Assertions
    assert selection.market_spread_display == "Atlanta Hawks +5.5"
    assert "Atlanta Hawks +12.3" in selection.model_spread_display
    assert "New York Knicks" in selection.sharp_side_display
    assert selection.sharp_action == "LAY_POINTS"
    assert abs(selection.edge_magnitude - 6.8) < 0.1  # 12.3 - 5.5 = 6.8
    
    print("\n✅ TEST 1 PASSED")
    return selection


def test_negative_model_spread():
    """
    Example 2 — Negative Model Spread (Sharp = UNDERDOG)
    
    Market: Hawks +5.5, Knicks -5.5
    Model Spread: −3.2
    
    Expected: Sharp side = UNDERDOG (Hawks +5.5)
    """
    print("\n" + "="*80)
    print("TEST 2: Negative Model Spread (-3.2)")
    print("="*80)
    
    selection = select_sharp_side_spread(
        home_team="New York Knicks",
        away_team="Atlanta Hawks",
        market_spread_home=-5.5,  # Knicks are favorite
        model_spread=-3.2,  # Negative = favorite (Knicks)
        volatility=VolatilityLevel.LOW
    )
    
    print(f"Market Spread Display: {selection.market_spread_display}")
    print(f"Model Spread Display:  {selection.model_spread_display}")
    print(f"Sharp Side Display:    {selection.sharp_side_display}")
    print(f"\nSharp Action:          {selection.sharp_action}")
    print(f"Edge Magnitude:        {selection.edge_magnitude:.1f} pts")
    print(f"Reasoning:             {selection.reasoning}")
    
    # Assertions
    assert selection.market_spread_display == "Atlanta Hawks +5.5"
    assert "Atlanta Hawks -3.2" in selection.model_spread_display
    assert "Atlanta Hawks" in selection.sharp_side_display
    assert selection.sharp_action == "TAKE_POINTS"
    assert abs(selection.edge_magnitude - 2.3) < 0.1  # abs(-3.2) - 5.5 = 2.3
    
    print("\n✅ TEST 2 PASSED")
    return selection


def test_close_spreads():
    """
    Test when model and market are close
    
    Market: Lakers +3.0, Warriors -3.0
    Model Spread: +3.1
    
    Expected: Small edge to FAVORITE
    """
    print("\n" + "="*80)
    print("TEST 3: Close Spreads (model +3.1 vs market +3.0)")
    print("="*80)
    
    selection = select_sharp_side_spread(
        home_team="Golden State Warriors",
        away_team="Los Angeles Lakers",
        market_spread_home=-3.0,  # Warriors are favorite
        model_spread=3.1,  # Positive = underdog (Lakers)
        volatility=VolatilityLevel.LOW
    )
    
    print(f"Market Spread Display: {selection.market_spread_display}")
    print(f"Model Spread Display:  {selection.model_spread_display}")
    print(f"Sharp Side Display:    {selection.sharp_side_display}")
    print(f"\nSharp Action:          {selection.sharp_action}")
    print(f"Edge Magnitude:        {selection.edge_magnitude:.1f} pts")
    
    # Assertions
    assert selection.edge_magnitude < 1.0  # Very small edge
    assert selection.sharp_action == "LAY_POINTS"  # Model > market → FAVORITE
    
    print("\n✅ TEST 3 PASSED")
    return selection


def test_large_underdog_spread():
    """
    Test large underdog spread
    
    Market: Duke +18.5, UNC -18.5
    Model Spread: +22.0
    
    Expected: Sharp = FAVORITE (UNC), but with volatility penalty
    """
    print("\n" + "="*80)
    print("TEST 4: Large Underdog Spread (+22.0)")
    print("="*80)
    
    selection = select_sharp_side_spread(
        home_team="North Carolina",
        away_team="Duke",
        market_spread_home=-18.5,  # UNC are favorite
        model_spread=22.0,  # Positive = underdog (Duke)
        volatility=VolatilityLevel.HIGH
    )
    
    print(f"Market Spread Display: {selection.market_spread_display}")
    print(f"Model Spread Display:  {selection.model_spread_display}")
    print(f"Sharp Side Display:    {selection.sharp_side_display}")
    print(f"\nSharp Action:          {selection.sharp_action}")
    print(f"Edge Magnitude:        {selection.edge_magnitude:.1f} pts")
    print(f"Volatility Penalty:    {selection.volatility_penalty:.1f} pts")
    print(f"Edge After Penalty:    {selection.edge_after_penalty:.1f} pts")
    
    # Assertions
    assert abs(selection.edge_magnitude - 3.5) < 0.1  # 22.0 - 18.5 = 3.5
    assert selection.volatility_penalty > 0  # Should have penalty for laying big number
    assert selection.sharp_action in ["LAY_POINTS", "NO_SHARP_PLAY"]
    
    print("\n✅ TEST 4 PASSED")
    return selection


def test_pick_em():
    """
    Test pick'em game
    
    Market: Celtics +0, Lakers +0 (pick'em)
    Model Spread: +2.5
    
    Expected: Sharp = FAVORITE (Lakers)
    """
    print("\n" + "="*80)
    print("TEST 5: Pick'em Game")
    print("="*80)
    
    selection = select_sharp_side_spread(
        home_team="Los Angeles Lakers",
        away_team="Boston Celtics",
        market_spread_home=0.0,  # Pick'em
        model_spread=2.5,  # Model thinks Celtics lose by 2.5
        volatility=VolatilityLevel.MEDIUM
    )
    
    print(f"Market Spread Display: {selection.market_spread_display}")
    print(f"Model Spread Display:  {selection.model_spread_display}")
    print(f"Sharp Side Display:    {selection.sharp_side_display}")
    print(f"\nSharp Action:          {selection.sharp_action}")
    
    # In pick'em, if model_spread > 0, sharp side should be the home team (Lakers)
    assert selection.sharp_action == "LAY_POINTS"
    
    print("\n✅ TEST 5 PASSED")
    return selection


def run_all_tests():
    """Run all test cases"""
    print("\n" + "🔒"*40)
    print("LOCKED MODEL SPREAD LOGIC — VALIDATION TESTS")
    print("🔒"*40)
    
    try:
        test_positive_model_spread()
        test_negative_model_spread()
        test_close_spreads()
        test_large_underdog_spread()
        test_pick_em()
        
        print("\n" + "="*80)
        print("✅ ALL TESTS PASSED")
        print("="*80)
        print("\n✅ Sharp side selection logic is LOCKED and CORRECT")
        print("✅ UI can safely use these display strings:")
        print("   - market_spread_display")
        print("   - model_spread_display")
        print("   - sharp_side_display")
        print("\n")
        
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        raise
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        raise


if __name__ == "__main__":
    run_all_tests()
