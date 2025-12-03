"""
Test structured reasoning engine
Shows quantitative factor breakdown for debugging Rockets vs Jazz
"""
import sys
import os
os.chdir('/Users/rohithaditya/Downloads/Permutation-Carlos/backend')
sys.path.insert(0, os.getcwd())

from core.sharp_analysis import calculate_structured_reasoning
import json

# Rockets vs Jazz simulation context (from debug run)
simulation_context = {
    'injury_impact': 0.0,        # No injury data
    'pace_factor': 1.0000,        # Normal pace
    'variance': 201.7,            # Moderate variance
    'confidence_score': 61,       # Medium confidence
    'team_a_projection': 120.7,
    'team_b_projection': 116.9
}

model_total = 237.4
vegas_total = 228.5
edge_points = 8.9

print("="*100)
print("🔬 STRUCTURED REASONING ENGINE TEST - ROCKETS VS JAZZ")
print("="*100)
print()

# Calculate structured reasoning
structured = calculate_structured_reasoning(
    market_type='total',
    model_value=model_total,
    vegas_value=vegas_total,
    edge_points=edge_points,
    simulation_context=simulation_context
)

print("📊 QUANTITATIVE FACTOR BREAKDOWN:")
print("="*100)
print()

print(f"Core Metrics:")
print(f"  Injury Impact: {structured['injury_impact_points']:+.2f} pts")
print(f"  Pace Adjustment: {structured['pace_adjustment_percent']:+.2f}%")
print(f"  Variance (σ): {structured['variance_sigma']:.1f}")
print(f"  Convergence Score: {structured['convergence_score']:.1f}%")
print(f"  Model Projection: {structured['median_sim_total']:.1f} pts")
print(f"  Vegas Line: {structured['vegas_total']:.1f} pts")
print(f"  Delta: {structured['delta_vs_vegas']:+.2f} pts")
print()

print(f"Confidence Assessment:")
print(f"  Numeric: {structured['confidence_numeric']:.2f} ({structured['confidence_numeric']*100:.0f}%)")
print(f"  Bucket: {structured['confidence_bucket']}")
print(f"  Contrarian: {structured['contrarian']}")
print()

print("="*100)
print("🎯 PRIMARY FACTOR ANALYSIS:")
print("="*100)
print()

print(f"  Primary Factor: {structured['primary_factor']}")
print(f"  Impact: {structured['primary_factor_impact_pts']:.2f} pts")
print()

if structured['factor_contributions']:
    print(f"  Factor Contributions:")
    for i, factor in enumerate(structured['factor_contributions'], 1):
        print(f"    {i}. {factor['factor']}: {factor['impact_points']:.2f} pts ({factor['contribution_pct']:.1f}% of delta)")
        if 'note' in factor:
            print(f"       Note: {factor['note']}")
print()

print(f"  Residual (Unexplained): {structured['residual_unexplained_pts']:.2f} pts")
print()

print("="*100)
print("⚠️  RISK FACTORS:")
print("="*100)
print()

if structured['risk_factors']:
    for i, risk in enumerate(structured['risk_factors'], 1):
        severity_icon = "🔴" if risk['severity'] == 'HIGH' else "🟡" if risk['severity'] == 'MEDIUM' else "🟢"
        print(f"  {i}. {severity_icon} [{risk['severity']}] {risk['risk']}")
        print(f"     {risk['description']}")
        print()
else:
    print("  ✅ No significant risk factors identified")
    print()

print(f"  Overall Risk Level: {structured['overall_risk_level']}")
print()

print("="*100)
print("🎓 CALIBRATION ENGINE METADATA:")
print("="*100)
print()

print(f"  Backtest Ready: {structured['backtest_ready']}")
print(f"  Calibration Bucket: {structured['calibration_bucket']}")
print(f"  Edge Grade (Numeric): {structured['edge_grade_numeric']}/6")
print()

print("="*100)
print("💡 INTERPRETATION:")
print("="*100)
print()

# Interpret the results
print("Why Model Diverges from Market:")
print()

if structured['primary_factor'] == 'baseline_projection':
    print("  🔍 PRIMARY CAUSE: Model Baseline Projection")
    print(f"     The {structured['delta_vs_vegas']:.1f} point gap is NOT explained by:")
    print(f"       • Injury adjustments ({structured['injury_impact_points']:.1f} pts)")
    print(f"       • Pace adjustments ({structured['pace_adjustment_percent']:.1f}%)")
    print()
    print("     This means the gap comes from BASELINE TEAM RATINGS.")
    print("     Model's inherent team strength projections differ from market.")
    print()

if structured['residual_unexplained_pts'] > 5:
    print(f"  ⚠️  HIGH RESIDUAL: {structured['residual_unexplained_pts']:.1f} pts unexplained")
    print("     Most of the edge is NOT from injury/pace factors.")
    print("     Edge is driven by model's baseline team ratings vs market consensus.")
    print()

if structured['confidence_bucket'] == 'MEDIUM':
    print(f"  ⚠️  MEDIUM CONFIDENCE: {structured['convergence_score']:.0f}% convergence")
    print("     Simulations did NOT strongly converge.")
    print("     This increases uncertainty around the projection.")
    print()

if any(r['risk'] == 'missing_context' for r in structured['risk_factors']):
    print("  ⚠️  MISSING CONTEXT: No injury/pace adjustments")
    print("     Model may be missing key information:")
    print("       • Lineup changes")
    print("       • Player rest/fatigue")
    print("       • Recent form changes")
    print("     Market may have information model doesn't.")
    print()

print()
print("="*100)
print("🚨 FAILURE MODE ANALYSIS:")
print("="*100)
print()

print("If game goes UNDER (model was wrong), likely reasons:")
print()

failure_probability = 0
explanations = []

if structured['confidence_bucket'] != 'HIGH':
    prob = 0.25
    failure_probability += prob
    explanations.append(f"  1. Medium confidence ({prob*100:.0f}% failure contribution)")
    explanations.append(f"     Only {structured['convergence_score']:.0f}% convergence suggests less reliable projection")

if structured['residual_unexplained_pts'] > 5:
    prob = 0.35
    failure_probability += prob
    explanations.append(f"  2. High residual unexplained ({prob*100:.0f}% failure contribution)")
    explanations.append(f"     {structured['residual_unexplained_pts']:.1f} pts gap from baseline ratings could be wrong")

if any(r['risk'] == 'missing_context' for r in structured['risk_factors']):
    prob = 0.30
    failure_probability += prob
    explanations.append(f"  3. Missing context ({prob*100:.0f}% failure contribution)")
    explanations.append(f"     Market likely has lineup/motivation info model doesn't")

explanations.append(f"  4. Random variance (10% failure contribution)")
explanations.append(f"     Any single game can deviate from expected value")

for line in explanations:
    print(line)

print()
print(f"  Estimated Failure Probability: ~{min(failure_probability + 0.10, 0.50)*100:.0f}%")
print()

print("="*100)
print("✅ STRUCTURED DATA AVAILABLE FOR:")
print("="*100)
print()
print("  ✓ Backtesting - Compare structured factors vs actual results")
print("  ✓ Calibration - Track accuracy by calibration_bucket")
print("  ✓ Brier/MAE/RMSE - Calculate prediction error metrics")
print("  ✓ Drift Detection - Monitor when factor contributions change")
print("  ✓ Factor Attribution - Identify which factors drive accuracy")
print("  ✓ Risk Management - Quantify uncertainty for bet sizing")
print()

print("="*100)
print("📦 FULL STRUCTURED OUTPUT (JSON):")
print("="*100)
print()
print(json.dumps(structured, indent=2))
