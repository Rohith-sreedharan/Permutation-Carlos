#!/usr/bin/env python
"""
VERIFICATION TEST: Zero-Gap LEAN Classification Fix
Tests that Detroit Red Wings @ NY Rangers case (model=60%, market=60%) 
correctly produces NO_ACTION instead of LEAN.
"""
import sys
sys.path.insert(0, '/Users/rohithaditya/Downloads/Permutation-Carlos/backend')

from core.compute_market_decision import MarketDecisionComputer
from core.market_decision import Classification

def test_zero_gap_lean_case():
    """
    Test case: Detroit Red Wings @ NY Rangers
    Model probability: 60%
    Market implied probability: 60%
    Probability gap: 0% (ZERO GAP)
    Edge magnitude: 2.5 (above threshold)
    """
    print("=" * 80)
    print("TEST: Zero-Gap LEAN Classification Fix")
    print("=" * 80)
    
    test_cases = [
        {
            "name": "Zero-Gap Case (Model=60%, Market=60%)",
            "model_prob": 0.60,
            "market_prob": 0.60,
            "edge_points": 2.5,
            "expected": Classification.NO_ACTION,
            "reason": "Gate 1: model_prob (0.60) <= market_prob (0.60) is TRUE"
        },
        {
            "name": "Sub-Threshold Gap Case (Model=60.5%, Market=60%)",
            "model_prob": 0.605,
            "market_prob": 0.60,
            "edge_points": 2.5,
            "expected": Classification.MARKET_ALIGNED,
            "reason": "Gate 1 passes, but Gate 2: gap (0.005) < 0.01 is TRUE"
        },
        {
            "name": "Exact-Threshold Gap Case (Model=61%, Market=60%)",
            "model_prob": 0.61,
            "market_prob": 0.60,
            "edge_points": 2.5,
            "expected": Classification.LEAN,
            "reason": "Both gates pass: model_prob (0.61) > market (0.60), gap (0.01) >= 0.01"
        },
        {
            "name": "Model Below Market (Model=55%, Market=60%)",
            "model_prob": 0.55,
            "market_prob": 0.60,
            "edge_points": 2.5,
            "expected": Classification.NO_ACTION,
            "reason": "Gate 1: model_prob (0.55) <= market_prob (0.60) is TRUE"
        },
    ]
    
    config = {
        'edge_threshold': 2.0,
        'lean_threshold': 0.5,
        'prob_threshold': 0.55,
        'min_prob_gap_for_lean': 0.01,
    }
    
    # Create dummy computer instance (we'll call method directly)
    computer = MarketDecisionComputer(league='nba', game_id='test', odds_event_id='test')
    
    all_passed = True
    
    for i, test in enumerate(test_cases, 1):
        print(f"\nTest Case {i}: {test['name']}")
        print(f"  Input: model={test['model_prob']:.1%}, market={test['market_prob']:.1%}, gap={test['model_prob']-test['market_prob']:.1%}")
        print(f"  Edge points: {test['edge_points']}")
        
        result = computer._classify_spread(
            edge_points=test['edge_points'],
            model_prob=test['model_prob'],
            market_implied_prob=test['market_prob'],
            config=config
        )
        
        status = "✅ PASS" if result == test['expected'] else "❌ FAIL"
        print(f"  Result: {result}")
        print(f"  Expected: {test['expected']}")
        print(f"  Status: {status}")
        print(f"  Gate Logic: {test['reason']}")
        
        if result != test['expected']:
            all_passed = False
    
    print("\n" + "=" * 80)
    if all_passed:
        print("✅ ALL TESTS PASSED - Zero-gap LEAN fix verified")
        print("\nKey Finding:")
        print("  Detroit Red Wings @ NY Rangers (60% vs 60%) correctly produces NO_ACTION")
        print("  Fix mechanism: Gate 1 at line 376 enforces model_prob <= market_prob check")
    else:
        print("❌ SOME TESTS FAILED - Review gate logic")
    print("=" * 80)
    
    return all_passed

if __name__ == '__main__':
    try:
        success = test_zero_gap_lean_case()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"Error running tests: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
