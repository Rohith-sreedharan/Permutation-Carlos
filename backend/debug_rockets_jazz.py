"""
Debug script to analyze Rockets vs Jazz UNDER prediction
Identifies exact factors that led to model calling UNDER when market shows OVER
"""
import sys
import os
os.chdir('/Users/rohithaditya/Downloads/Permutation-Carlos/backend')
sys.path.insert(0, os.getcwd())

from core.monte_carlo_engine import MonteCarloEngine
import json

# Test event: Rockets vs Jazz
test_event = {
    "id": "debug_rockets_jazz_20251202",
    "sport_key": "basketball_nba",
    "sport_title": "NBA",
    "commence_time": "2025-12-02T19:00:00Z",
    "home_team": "Houston Rockets",
    "away_team": "Utah Jazz",
    "bookmakers": [
        {
            "key": "fanduel",
            "title": "FanDuel",
            "markets": [
                {
                    "key": "totals",
                    "outcomes": [
                        {"name": "Over", "price": -110, "point": 228.5},
                        {"name": "Under", "price": -110, "point": 228.5}
                    ]
                },
                {
                    "key": "spreads",
                    "outcomes": [
                        {"name": "Houston Rockets", "price": -110, "point": -8.5},
                        {"name": "Utah Jazz", "price": -110, "point": 8.5}
                    ]
                }
            ]
        },
        {
            "key": "draftkings",
            "title": "DraftKings",
            "markets": [
                {
                    "key": "totals",
                    "outcomes": [
                        {"name": "Over", "price": -105, "point": 229.0},
                        {"name": "Under", "price": -115, "point": 229.0}
                    ]
                }
            ]
        }
    ]
}

print("="*100)
print("🔬 ROCKETS VS JAZZ DEBUG ANALYSIS")
print("="*100)
print(f"\n📊 MARKET CONSENSUS:")
print(f"  FanDuel Total: 228.5")
print(f"  DraftKings Total: 229.0")
print(f"  Average: 228.75")
print(f"  ALL BOOKS SHOWING: OVER")
print()

# Initialize engine
engine = MonteCarloEngine()

print("⚙️  Running 100,000 Monte Carlo simulations...")
print()

# Prepare team data (simplified for debug - would normally come from stats API)
team_a_data = {
    "name": "Houston Rockets",
    "offensive_rating": 115.2,
    "defensive_rating": 108.5,
    "pace": 99.5,
    "injuries": []  # Would be populated from injury API
}

team_b_data = {
    "name": "Utah Jazz",
    "offensive_rating": 110.8,
    "defensive_rating": 112.3,
    "pace": 98.2,
    "injuries": []
}

market_context = {
    "sport_key": "basketball_nba",
    "spread": -8.5,
    "total": 228.5,
    "total_line": 228.5,  # Required field
    "home_team": "Houston Rockets",
    "bookmaker_source": "fanduel",
    "odds_timestamp": "2025-12-02T18:00:00Z"
}

# Run simulation
result = engine.run_simulation(
    event_id=test_event["id"],
    team_a=team_a_data,
    team_b=team_b_data,
    market_context=market_context,
    iterations=100000,
    mode="full"
)

print("="*100)
print("📈 SIMULATION OUTPUT:")
print("="*100)

print(f"\nTeam Projections:")
print(f"  Houston Rockets (Home): {result['avg_team_a_score']:.2f} points")
print(f"  Utah Jazz (Away): {result['avg_team_b_score']:.2f} points")
print(f"  ────────────────────────────────────")
print(f"  PROJECTED TOTAL: {result.get('avg_total_score', 0):.2f} points")

print(f"\nSimulation Quality Metrics:")
print(f"  Iterations: {result['iterations']:,}")
print(f"  Variance (σ): {result.get('variance', 0):.2f}")
print(f"  Confidence Score: {result.get('confidence_score', 0):.1f}%")
print(f"  Volatility Index: {result.get('volatility_index', 'N/A')}")

# Sharp Analysis
sharp = result.get('sharp_analysis', {})
if sharp:
    print()
    print("="*100)
    print("🎯 SHARP ANALYSIS - WHY MODEL DISAGREES WITH MARKET:")
    print("="*100)
    
    total_analysis = sharp.get('total', {})
    if total_analysis and total_analysis.get('has_edge'):
        vegas_total = total_analysis.get('vegas_total')
        model_total = total_analysis.get('model_total')
        edge_points = total_analysis.get('edge_points')
        sharp_side = total_analysis.get('sharp_side')
        
        print(f"\n📉 TOTAL MARKET EDGE:")
        print(f"  Vegas Consensus: {vegas_total}")
        print(f"  BeatVegas Model: {model_total:.2f}")
        print(f"  Difference: {edge_points:.2f} points")
        print(f"  Sharp Side: {sharp_side}")
        print(f"  Edge Grade: {total_analysis.get('edge_grade')}")
        
        reasoning = total_analysis.get('edge_reasoning', {})
        if reasoning:
            print()
            print("─" * 100)
            print("🔍 ROOT CAUSE ANALYSIS - WHY MODEL CALLED UNDER:")
            print("─" * 100)
            
            print(f"\n🎯 PRIMARY FACTOR:")
            print(f"  {reasoning.get('primary_factor')}")
            
            factors = reasoning.get('contributing_factors', [])
            if factors:
                print(f"\n📊 CONTRIBUTING FACTORS:")
                for i, factor in enumerate(factors, 1):
                    print(f"  {i}. {factor}")
            
            print(f"\n💡 MODEL REASONING:")
            print(f"  {reasoning.get('model_reasoning')}")
            
            print(f"\n🏦 MARKET POSITIONING:")
            print(f"  {reasoning.get('market_positioning')}")
            
            if reasoning.get('contrarian_indicator'):
                print(f"\n⚠️  CONTRARIAN ALERT:")
                print(f"  This is a SIGNIFICANT contrarian position")
                print(f"  Model sees value where market doesn't")
                print(f"  Confidence Level: {reasoning.get('confidence_level')}")

# Injury Analysis
injury_summary = result.get('injury_summary', {})
if injury_summary:
    print()
    print("="*100)
    print("🏥 INJURY IMPACT BREAKDOWN:")
    print("="*100)
    
    offensive = injury_summary.get('total_offensive_impact', 0)
    defensive = injury_summary.get('total_defensive_impact', 0)
    net_impact = injury_summary.get('combined_net_impact', 0)
    
    print(f"\n  Offensive Impact: {offensive:+.2f} points")
    print(f"  Defensive Impact: {defensive:+.2f} points")
    print(f"  ────────────────────────")
    print(f"  NET IMPACT: {net_impact:+.2f} points")
    
    key_injuries = injury_summary.get('key_injuries', [])
    if key_injuries:
        print(f"\n  Key Injuries Affecting Projection:")
        for inj in key_injuries[:5]:
            print(f"    • {inj.get('player')} ({inj.get('team')}) - {inj.get('position')} - {inj.get('status')}")

# Pace Analysis
pace = result.get('pace_factor')
if pace:
    print()
    print("="*100)
    print("⚡ PACE FACTOR ANALYSIS:")
    print("="*100)
    
    print(f"\n  Pace Factor: {pace:.4f}")
    
    if pace < 0.95:
        pct_slower = (1 - pace) * 100
        print(f"  📉 Game projected {pct_slower:.1f}% SLOWER than season average")
        print(f"  Fewer possessions = Lower scoring")
    elif pace > 1.05:
        pct_faster = (pace - 1) * 100
        print(f"  📈 Game projected {pct_faster:.1f}% FASTER than season average")
        print(f"  More possessions = Higher scoring")
    else:
        print(f"  ➡️  Normal pace (within ±5% of season average)")

# Quantitative Breakdown
print()
print("="*100)
print("🔢 QUANTITATIVE FACTOR BREAKDOWN:")
print("="*100)

# Initialize variables with defaults
injury_impact = abs(injury_summary.get('combined_net_impact', 0)) if injury_summary else 0
pace_impact = abs(1 - pace) * 100 if pace else 0
variance_weight = result.get('variance', 0)
confidence = result.get('confidence_score', 0)
model_total = result.get('avg_total_score', 0)
vegas_total = sharp.get('total', {}).get('vegas_total', 0)
delta = vegas_total - model_total if vegas_total and model_total else 0

if sharp.get('total', {}).get('sharp_side') == 'UNDER':
    print(f"\n  Vegas says: {vegas_total} (OVER)")
    print(f"  Model says: {model_total:.2f} (UNDER)")
    print(f"  Gap: {delta:.2f} points")
    print()
    
    # Calculate factor contributions
    print("  Factor Contributions to UNDER call:")
    print("  ────────────────────────────────────")
    
    factors = []
    
    if injury_impact > 3:
        factors.append({
            'name': 'Injury Impact',
            'value': injury_impact,
            'contribution': f'{injury_impact:.1f} pts reduction in scoring'
        })
    
    if pace_impact > 3:
        pace_pts = pace_impact / 100 * model_total
        factors.append({
            'name': 'Pace Adjustment',
            'value': pace_impact,
            'contribution': f'{pace_impact:.1f}% slower pace ≈ {pace_pts:.1f} pts lower'
        })
    
    if variance_weight > 300:
        factors.append({
            'name': 'High Variance',
            'value': variance_weight,
            'contribution': f'σ={variance_weight:.1f} creates wider outcome range'
        })
    
    if confidence >= 70:
        factors.append({
            'name': 'High Confidence',
            'value': confidence,
            'contribution': f'{confidence:.1f}% simulation convergence'
        })
    
    for i, factor in enumerate(factors, 1):
        print(f"  {i}. {factor['name']}: {factor['contribution']}")

# Model Accuracy Check
print()
print("="*100)
print("🎓 MODEL CALIBRATION STATUS:")
print("="*100)
print(f"\n  ⚠️  This is a LIVE prediction - accuracy unknown until game completes")
print(f"  📊 Prediction will be stored for post-game grading")
print(f"  📈 Brier Score, MAE, and RMSE will be calculated after result")
print()

# What Could Go Wrong
print("="*100)
print("⚠️  POTENTIAL FAILURE MODES:")
print("="*100)
print()
print("  Why model MIGHT be wrong (if game goes OVER):")
print("  ─────────────────────────────────────────────")

failure_modes = []

if injury_impact > 5:
    failure_modes.append("1. Injury impact overestimated - replacement players perform better than expected")

if pace_impact > 5:
    failure_modes.append("2. Pace projection incorrect - game tempo faster than model predicted")

if variance_weight > 350:
    failure_modes.append("3. High variance outcome - game falls in upper tail of distribution")

failure_modes.append("4. Market has information model doesn't (lineup changes, weather, motivation)")
failure_modes.append("5. Random variance - any single game can deviate from expected value")

for mode in failure_modes:
    print(f"  {mode}")

print()
print("="*100)
print("💡 RECOMMENDATION:")
print("="*100)
print()
if abs(delta) >= 7:
    print(f"  🔴 STRONG EDGE: {delta:.1f} point gap warrants action")
    print(f"  ✅ Sharp Side: {sharp['total']['sharp_side']} {vegas_total}")
    print(f"  🎯 Grade: {sharp['total']['edge_grade']}")
else:
    print(f"  🟡 MODERATE EDGE: {delta:.1f} point gap is borderline")
    print(f"  ⚠️  Requires additional handicapping confirmation")

print()
print("="*100)
