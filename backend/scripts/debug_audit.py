import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from db.mongo import db

print("=" * 70)
print("AUDIT SIMULATION CHECK")
print("=" * 70)

simulations = list(db.monte_carlo_simulations.find().limit(5))
print(f"\nFound {len(simulations)} simulations")

for i, sim in enumerate(simulations):
    sport_key = sim.get('sport_key', 'unknown')
    print(f"  {i+1}. sport_key = '{sport_key}', has distribution_curve: {'distribution_curve' in sim}, has volatility_score: {'volatility_score' in sim}")

sports = set(sim.get('sport_key', 'unknown') for sim in simulations)
print(f"\nDistinct sports: {sports}")
print(f"Count: {len(sports)}")
print(f"Multi-sport (>1): {len(sports) > 1}")

# Check other fields
has_distribution = any('distribution_curve' in sim for sim in simulations)
has_volatility = any('volatility_score' in sim for sim in simulations)

print(f"\nHas distribution curves: {has_distribution}")
print(f"Has volatility scoring: {has_volatility}")

# Check collections
print(f"\nuser_bets exists: {'user_bets' in db.list_collection_names()}")
print(f"api_keys exists: {'api_keys' in db.list_collection_names()}")
print(f"prediction_logs count: {db.prediction_logs.count_documents({})}")
print(f"parlay_analysis count: {db.parlay_analysis.count_documents({})}")

print("\n" + "=" * 70)
