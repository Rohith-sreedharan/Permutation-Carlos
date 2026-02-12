#!/usr/bin/env python3
"""
Find EDGE spread with abs(edge) >= 2.0 AND (prob >= 0.55 OR prob <= 0.45)
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from db.mongo import db

print("Searching for EDGE spread (abs(edge) >= 2.0 AND prob threshold)...\n")

# Get ALL simulations with spread data
sims = list(db["monte_carlo_simulations"].find(
    {
        "sharp_analysis.spread.model_spread": {"$exists": True, "$ne": None},
        "team_a_win_probability": {"$exists": True, "$ne": None}
    },
    {
        "game_id": 1,
        "sharp_analysis.spread.model_spread": 1,
        "team_a_win_probability": 1,
        "_id": 0
    }
).limit(500))

print(f"Found {len(sims)} simulations with spread data")
print(f"Checking for EDGE matches (abs(edge) >= 2.0 AND prob >= 0.55/0.45)...\n")

edge_spreads = []
checked = 0

for sim in sims:
    game_id = sim.get('game_id')
    if not game_id:
        continue
    
    checked += 1
    
    # Get event
    event = db["events"].find_one(
        {"game_id": game_id},
        {"game_id": 1, "league": 1, "home_team": 1, "away_team": 1, "odds.spreads": 1}
    )
    
    if not event:
        continue
        
    spreads = event.get('odds', {}).get('spreads')
    if not spreads or len(spreads) == 0:
        continue
    
    model_spread = sim.get('sharp_analysis', {}).get('spread', {}).get('model_spread')
    market_spread = spreads[0].get('points')
    home_win_prob = sim.get('team_a_win_probability')
    
    if model_spread is None or market_spread is None or home_win_prob is None:
        continue
    
    edge = abs(model_spread - market_spread)
    
    # Check EDGE criteria: abs(edge) >= 2.0 AND (prob >= 0.55 OR <= 0.45)
    meets_prob_threshold = (home_win_prob >= 0.55 or home_win_prob <= 0.45)
    
    if edge >= 2.0 and meets_prob_threshold:
        edge_spreads.append({
            'game_id': game_id,
            'league': event.get('league'),
            'home_team': event.get('home_team'),
            'away_team': event.get('away_team'),
            'model_spread': model_spread,
            'market_spread': market_spread,
            'edge': edge,
            'home_win_prob': home_win_prob
        })
        
        if len(edge_spreads) >= 5:
            break

print(f"Checked {checked} games with both sim and event data")

if edge_spreads:
    print(f"\n✅ FOUND {len(edge_spreads)} EDGE SPREAD(S):\n")
    for idx, game in enumerate(edge_spreads, 1):
        print(f"[{idx}] {game['league']}: {game.get('away_team', 'Away')} @ {game.get('home_team', 'Home')}")
        print(f"    game_id: {game['game_id']}")
        print(f"    model_spread: {game['model_spread']:.2f}")
        print(f"    market_spread: {game['market_spread']}")
        print(f"    edge: {game['edge']:.3f} pts (>= 2.0 threshold) ✅")
        print(f"    home_win_prob: {game['home_win_prob']:.2%} (>= 0.55 OR <= 0.45) ✅")
        print(f"\n    Curl command:")
        print(f"    curl -s 'https://beta.beatvegas.app/api/games/{game['league']}/{game['game_id']}/decisions' | jq '.spread'")
        print()
else:
    print(f"\n❌ NO EDGE spreads found with abs(edge) >= 2.0 AND prob threshold in {checked} games")
    print("    Current market lacks extreme mispricings on spreads")
    print("\n💡 RECOMMENDATION: Either wait for market inefficiency or accept")
    print("    that EDGE TOTAL artifact demonstrates classification logic works.")
