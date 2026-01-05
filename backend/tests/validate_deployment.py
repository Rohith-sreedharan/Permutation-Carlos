#!/usr/bin/env python3
"""
Pre-Deployment Validation Script

Run this before deploying to ensure Model Spread logic is correctly implemented.
"""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend.core.sharp_side_selection import select_sharp_side_spread, validate_sharp_side_alignment
from backend.core.sport_configs import VolatilityLevel, EdgeState
from backend.utils.spread_formatter import format_spread_for_api, validate_spread_response


def check_backend_implementation():
    """Validate backend sharp side selection works"""
    print("\n🔍 Checking Backend Implementation...")
    
    try:
        # Test basic call
        selection = select_sharp_side_spread(
            home_team="Team A",
            away_team="Team B",
            market_spread_home=-5.5,
            model_spread=8.0,
            volatility=VolatilityLevel.LOW
        )
        
        # Check required fields exist
        required_fields = [
            'sharp_side',
            'sharp_action',
            'market_spread_display',
            'model_spread_display',
            'sharp_side_display',
            'edge_magnitude',
            'reasoning'
        ]
        
        for field in required_fields:
            if not hasattr(selection, field):
                print(f"   ❌ Missing field: {field}")
                return False
        
        # Check display strings are populated
        if not selection.market_spread_display:
            print("   ❌ market_spread_display is empty")
            return False
        
        if not selection.model_spread_display:
            print("   ❌ model_spread_display is empty")
            return False
        
        if not selection.sharp_side_display:
            print("   ❌ sharp_side_display is empty")
            return False
        
        print("   ✅ Backend implementation correct")
        print(f"   ✅ Sample output: {selection.sharp_side_display}")
        return True
        
    except Exception as e:
        print(f"   ❌ Backend error: {e}")
        return False


def check_api_formatter():
    """Validate API formatter works"""
    print("\n🔍 Checking API Formatter...")
    
    try:
        display_data = format_spread_for_api(
            home_team="Knicks",
            away_team="Hawks",
            market_spread_home=-5.5,
            model_spread=12.3,
            sharp_side="Knicks -5.5"
        )
        
        required_keys = [
            'market_spread_display',
            'model_spread_display',
            'sharp_side_display',
            'market_favorite',
            'market_underdog'
        ]
        
        for key in required_keys:
            if key not in display_data:
                print(f"   ❌ Missing key: {key}")
                return False
        
        # Check team labels present
        if 'Hawks' not in display_data['market_spread_display']:
            print("   ❌ market_spread_display missing team label")
            return False
        
        if 'Hawks' not in display_data['model_spread_display']:
            print("   ❌ model_spread_display missing team label")
            return False
        
        print("   ✅ API formatter correct")
        print(f"   ✅ Market: {display_data['market_spread_display']}")
        print(f"   ✅ Model:  {display_data['model_spread_display']}")
        print(f"   ✅ Sharp:  {display_data['sharp_side_display']}")
        return True
        
    except Exception as e:
        print(f"   ❌ Formatter error: {e}")
        return False


def check_validation_logic():
    """Validate edge/sharp_side alignment checks work"""
    print("\n🔍 Checking Validation Logic...")
    
    try:
        # Test valid case
        valid_selection = select_sharp_side_spread(
            home_team="Team A",
            away_team="Team B",
            market_spread_home=-5.5,
            model_spread=8.0,
            volatility=VolatilityLevel.LOW
        )
        
        is_valid, error = validate_sharp_side_alignment(EdgeState.EDGE, valid_selection)
        if not is_valid:
            print(f"   ❌ Valid case failed: {error}")
            return False
        
        # Test invalid case (edge without sharp side)
        is_valid, error = validate_sharp_side_alignment(EdgeState.EDGE, None)
        if is_valid:
            print("   ❌ Should have rejected EDGE without sharp_side")
            return False
        
        print("   ✅ Validation logic correct")
        print("   ✅ Blocks EDGE without sharp_side")
        return True
        
    except Exception as e:
        print(f"   ❌ Validation error: {e}")
        return False


def check_sharp_side_rule():
    """Validate core sharp side rule"""
    print("\n🔍 Checking Core Sharp Side Rule...")
    
    test_cases = [
        # (market_spread, model_spread, expected_action, description)
        (5.5, 12.3, "LAY_POINTS", "Positive model > market → FAVORITE"),
        (5.5, -3.2, "TAKE_POINTS", "Negative model < market → UNDERDOG"),
        (-7.0, -10.5, "LAY_POINTS", "Negative model < negative market → FAVORITE"),
        (-7.0, -4.0, "TAKE_POINTS", "Negative model > negative market → UNDERDOG"),
    ]
    
    try:
        for market, model, expected_action, description in test_cases:
            selection = select_sharp_side_spread(
                home_team="Home",
                away_team="Away",
                market_spread_home=market,
                model_spread=model,
                volatility=VolatilityLevel.LOW
            )
            
            if selection.sharp_action != expected_action:
                print(f"   ❌ {description}")
                print(f"      Expected: {expected_action}, Got: {selection.sharp_action}")
                return False
            
            print(f"   ✅ {description}")
        
        print("   ✅ Core rule validated")
        return True
        
    except Exception as e:
        print(f"   ❌ Rule validation error: {e}")
        return False


def check_display_strings():
    """Validate display strings have team labels"""
    print("\n🔍 Checking Display Strings...")
    
    try:
        selection = select_sharp_side_spread(
            home_team="New York Knicks",
            away_team="Atlanta Hawks",
            market_spread_home=-5.5,
            model_spread=12.3,
            volatility=VolatilityLevel.MEDIUM
        )
        
        # Check market display has underdog team
        if "Hawks" not in selection.market_spread_display:
            print(f"   ❌ market_spread_display missing team: {selection.market_spread_display}")
            return False
        
        # Check model display has underdog team
        if "Hawks" not in selection.model_spread_display:
            print(f"   ❌ model_spread_display missing team: {selection.model_spread_display}")
            return False
        
        # Check sharp side display has team
        if "Knicks" not in selection.sharp_side_display and "Hawks" not in selection.sharp_side_display:
            print(f"   ❌ sharp_side_display missing team: {selection.sharp_side_display}")
            return False
        
        # Check sign is present in model display
        if '+' not in selection.model_spread_display and '-' not in selection.model_spread_display:
            print(f"   ❌ model_spread_display missing sign: {selection.model_spread_display}")
            return False
        
        print("   ✅ All display strings have team labels")
        print(f"   ✅ {selection.market_spread_display}")
        print(f"   ✅ {selection.model_spread_display}")
        print(f"   ✅ {selection.sharp_side_display}")
        return True
        
    except Exception as e:
        print(f"   ❌ Display string error: {e}")
        return False


def main():
    """Run all pre-deployment checks"""
    print("="*80)
    print("🔒 MODEL SPREAD LOGIC — PRE-DEPLOYMENT VALIDATION")
    print("="*80)
    
    checks = [
        ("Backend Implementation", check_backend_implementation),
        ("API Formatter", check_api_formatter),
        ("Validation Logic", check_validation_logic),
        ("Sharp Side Rule", check_sharp_side_rule),
        ("Display Strings", check_display_strings),
    ]
    
    results = []
    for name, check_func in checks:
        result = check_func()
        results.append((name, result))
    
    # Summary
    print("\n" + "="*80)
    print("VALIDATION SUMMARY")
    print("="*80)
    
    all_passed = True
    for name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status} - {name}")
        if not passed:
            all_passed = False
    
    print("="*80)
    
    if all_passed:
        print("\n✅ ALL CHECKS PASSED — READY FOR DEPLOYMENT")
        print("\nNext steps:")
        print("  1. Deploy backend changes")
        print("  2. Deploy frontend changes")
        print("  3. Test with real simulation")
        print("  4. Verify Telegram posts use sharp_side_display")
        print("  5. Monitor first 10 signals")
        return 0
    else:
        print("\n❌ VALIDATION FAILED — DO NOT DEPLOY")
        print("\nFix the failing checks before deploying.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
