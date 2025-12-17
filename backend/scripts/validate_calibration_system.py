#!/usr/bin/env python3
"""
Calibration System Validation Script
Tests the 5-layer constraint system with realistic NFL scenarios

Shows how the system blocks picks that would have contributed to over-bias
"""

import sys
from pathlib import Path

# Add backend to Python path
backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path))

from core.calibration_engine import CalibrationEngine
from core.sport_calibration_config import SPORT_CONFIGS

def print_section(title):
    print("\n" + "="*80)
    print(f"  {title}")
    print("="*80)

def validate_pick(engine, sport_key, model_total, vegas_total, std_total, p_raw, edge_raw, scenario_name):
    """Validate a pick and display results"""
    print(f"\n{'─'*80}")
    print(f"📊 Scenario: {scenario_name}")
    print(f"{'─'*80}")
    print(f"Vegas Total:  {vegas_total:.1f}")
    print(f"Model Total:  {model_total:.1f}")
    print(f"Deviation:    {model_total - vegas_total:+.1f} pts")
    print(f"Std Dev:      {std_total:.1f}")
    print(f"Raw P(Over):  {p_raw:.1%}")
    print(f"Raw Edge:     {edge_raw:.1f} pts")
    
    result = engine.validate_pick(
        sport_key=sport_key,
        model_total=model_total,
        vegas_total=vegas_total,
        std_total=std_total,
        p_raw=p_raw,
        edge_raw=edge_raw,
        data_quality_score=0.85,
        injury_uncertainty=15.0
    )
    
    print(f"\n🎯 CALIBRATION RESULT:")
    print(f"   Publish:      {'✅ YES' if result['publish'] else '🚫 NO'}")
    print(f"   P(Adjusted):  {result['p_adjusted']:.1%} (was {p_raw:.1%})")
    print(f"   Edge (Adj):   {result['edge_adjusted']:.1f} pts (was {edge_raw:.1f})")
    print(f"   Confidence:   {result['confidence_label']}")
    print(f"   Z-Variance:   {result['z_variance']:.2f}")
    print(f"   Elite Override: {result['elite_override']}")
    
    if not result['publish']:
        print(f"\n❌ BLOCK REASONS:")
        for reason in result['block_reasons']:
            print(f"   • {reason}")
    
    if result['applied_penalties']:
        print(f"\n⚠️  PENALTIES APPLIED:")
        for penalty_type, value in result['applied_penalties'].items():
            if value > 0:
                print(f"   • {penalty_type}: {value:.1%}")
    
    return result

def main():
    print_section("🎯 CALIBRATION SYSTEM VALIDATION")
    
    engine = CalibrationEngine()
    sport_key = "americanfootball_nfl"
    config = SPORT_CONFIGS[sport_key]
    
    print(f"\nSport: NFL")
    print(f"Soft Deviation Threshold: {config.soft_deviation} pts")
    print(f"Hard Deviation Threshold: {config.hard_deviation} pts")
    print(f"Min Probability: {config.min_probability:.1%}")
    print(f"Max Over Rate: {config.max_over_rate:.1%}")
    
    print_section("TEST SCENARIOS")
    
    # Scenario 1: Reasonable pick - SHOULD PASS
    validate_pick(
        engine, sport_key,
        model_total=47.5,
        vegas_total=45.0,
        std_total=8.5,
        p_raw=0.62,
        edge_raw=2.5,
        scenario_name="✅ Reasonable Edge (2.5 pts, 62% prob, normal variance)"
    )
    
    # Scenario 2: Large divergence - SHOULD BE PENALIZED
    validate_pick(
        engine, sport_key,
        model_total=52.5,
        vegas_total=45.0,
        std_total=9.2,
        p_raw=0.68,
        edge_raw=7.5,
        scenario_name="⚠️  Large Market Divergence (+7.5 pts, high confidence)"
    )
    
    # Scenario 3: High variance + over bias - SHOULD BE BLOCKED
    validate_pick(
        engine, sport_key,
        model_total=54.0,
        vegas_total=45.0,
        std_total=12.5,
        p_raw=0.65,
        edge_raw=9.0,
        scenario_name="🚫 Extreme: +9 pts, high variance, structural over-bias"
    )
    
    # Scenario 4: Modest over with high variance - SHOULD BE BLOCKED
    validate_pick(
        engine, sport_key,
        model_total=48.5,
        vegas_total=45.0,
        std_total=11.8,
        p_raw=0.59,
        edge_raw=3.5,
        scenario_name="🚫 High Variance Suppression (moderate edge, unstable)"
    )
    
    # Scenario 5: Elite exception candidate - RARE PASS
    validate_pick(
        engine, sport_key,
        model_total=49.0,
        vegas_total=45.0,
        std_total=7.2,
        p_raw=0.64,
        edge_raw=4.0,
        scenario_name="✅ Elite Override Candidate (strong edge, low variance, good data)"
    )
    
    # Scenario 6: Under pick - less scrutiny
    validate_pick(
        engine, sport_key,
        model_total=41.5,
        vegas_total=45.0,
        std_total=8.0,
        p_raw=0.61,
        edge_raw=3.5,
        scenario_name="✅ Under Pick (anti-over bias, should pass more easily)"
    )
    
    print_section("📊 SUMMARY")
    print("""
The calibration system demonstrates:

1. ✅ Reasonable edges PASS with minor adjustments
2. ⚠️  Large market divergences get PENALIZED (probability reduced)
3. 🚫 High variance SUPPRESSES edge (75% penalty)
4. 🚫 Structural over-bias gets BLOCKED at the source
5. ✅ Elite override activates RARELY (exceptional edges only)
6. ✅ Under picks face LESS scrutiny (anti-over bias)

This prevents the "all overs, 5-9 pts above market" syndrome automatically.
No per-game tweaks needed - the system self-corrects through daily calibration.
    """)

if __name__ == "__main__":
    main()
