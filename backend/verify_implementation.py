#!/usr/bin/env python3
"""
Final verification of Universal EDGE/LEAN Classification implementation
"""

from core.universal_tier_classifier import run_stress_tests
from core.tier_classification_adapter import classify_simulation, Tier
from services.analytics_service import AnalyticsService
from datetime import datetime, timezone

def main():
    print('=' * 60)
    print('FINAL VERIFICATION - Universal EDGE/LEAN Classification')
    print('=' * 60)
    print()
    
    all_passed = True
    
    # Test 1: Core stress tests
    print('[1] Running core stress tests...')
    if run_stress_tests():
        print('    ✅ PASS')
    else:
        print('    ❌ FAIL')
        all_passed = False
    print()
    
    # Test 2: Adapter integration
    print('[2] Testing adapter integration...')
    sim = {
        'sport': 'NBA',
        'game_id': 'test',
        'home_team': 'Lakers',
        'away_team': 'Warriors',
        'sim_count': 50000,
        'home_win_probability': 0.60,
        'away_win_probability': 0.40,
        'timestamp': datetime.now(timezone.utc)
    }
    market = {
        'spread_line': -3.5,
        'spread_home_price': -110,
        'spread_away_price': -110
    }
    result = classify_simulation(sim, market, 'SPREAD')
    if result and result.tier == Tier.EDGE:
        edge_display = f"{result.prob_edge*100:.1f}%" if result.prob_edge is not None else "N/A"
        print(f'    ✅ PASS - Tier: {result.tier.value}, Edge: {edge_display}')
    else:
        print('    ❌ FAIL')
        all_passed = False
    print()
    
    # Test 3: Analytics service integration
    print('[3] Testing analytics service integration...')
    classification = AnalyticsService.classify_bet_strength(
        model_prob=0.58,
        implied_prob=0.524,
        confidence=75,
        volatility='MEDIUM',
        sim_count=50000,
        american_odds=-110,
        opp_american_odds=-110
    )
    if classification['classification'] == 'EDGE':
        print(f"    ✅ PASS - Classification: {classification['classification']}")
        print(f"       Prob Edge: {classification['prob_edge']*100:.1f}%")
        print(f"       EV: {classification['ev']*100:.1f}%")
    else:
        print('    ❌ FAIL')
        all_passed = False
    print()
    
    # Test 4: Regression test - volatility should NOT affect tier
    print('[4] Testing regression protection (volatility ignored)...')
    classification_high_vol = AnalyticsService.classify_bet_strength(
        model_prob=0.60,
        implied_prob=0.50,
        confidence=75,
        volatility='HIGH',  # Should NOT affect tier
        sim_count=50000,
        american_odds=-110,
        opp_american_odds=-110
    )
    if classification_high_vol['classification'] == 'EDGE':
        print(f"    ✅ PASS - High volatility correctly ignored")
        print(f"       Classification: {classification_high_vol['classification']}")
        print(f"       Metadata volatility: {classification_high_vol['metadata']['volatility']}")
    else:
        print('    ❌ FAIL - Volatility incorrectly affected classification')
        all_passed = False
    print()
    
    # Final summary
    print('=' * 60)
    if all_passed:
        print('✅ ALL VERIFICATIONS PASSED')
        print()
        print('Implementation is complete and ready for production.')
    else:
        print('❌ SOME VERIFICATIONS FAILED')
        print()
        print('Please review failed tests above.')
    print('=' * 60)
    
    return 0 if all_passed else 1

if __name__ == '__main__':
    exit(main())
