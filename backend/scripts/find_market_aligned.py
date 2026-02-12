#!/usr/bin/env python3
"""
Find MARKET_ALIGNED spread with abs(edge) < 0.5
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from db.mongo import db

print("Searching for MARKET_ALIGNED spread (abs(edge) < 0.5)...\n")

# Get ALL simulations with spread data (no extra filters)
sims = list(db["monte_carlo_simulations"].find(
    {
        "sharp_analysis.spread.model_spread": {"$exists": True, "$ne": None}
    },
    {
        "game_id": 1,
        "sharp_analysis.spread.model_spread": 1,
        "_id": 0
    }
).limit(500))

print(f"Found {len(sims)} simulations with spread data")
print(f"Checking for MARKET_ALIGNED matches (abs(edge) < 0.5)...\n")

market_aligned_spreads = []
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
    
    if model_spread is None or market_spread is None:
        continue
    
    edge = abs(model_spread - market_spread)
    
    # Check MARKET_ALIGNED criteria: abs(edge) < 0.5
    if edge < 0.5:
        market_aligned_spreads.append({
            'game_id': game_id,
            'league': event.get('league'),
            'home_team': event.get('home_team'),
            'away_team': event.get('away_team'),
            'model_spread': model_spread,
            'market_spread': market_spread,
            'edge': edge
        })
        
        if len(market_aligned_spreads) >= 5:
            break

print(f"Checked {checked} games with both sim and event data")

if market_aligned_spreads:
    print(f"\n✅ FOUND {len(market_aligned_spreads)} MARKET_ALIGNED SPREAD(S):\n")
    for idx, game in enumerate(market_aligned_spreads, 1):
        print(f"[{idx}] {game['league']}: {game.get('away_team', 'Away')} @ {game.get('home_team', 'Home')}")
        print(f"    game_id: {game['game_id']}")
        print(f"    model_spread: {game['model_spread']:.2f}")
        print(f"    market_spread: {game['market_spread']}")
        print(f"    edge: {game['edge']:.3f} pts (< 0.5 threshold) ✅")
        print(f"\n    Curl command:")
        print(f"    curl -s 'https://beta.beatvegas.app/api/games/{game['league']}/{game['game_id']}/decisions' | jq '.spread'")
        print()
else:
    print(f"\n❌ NO MARKET_ALIGNED spreads found with abs(edge) < 0.5 in {checked} games")
    print("    Current market is too efficient - all edges >= 0.5 pts")
    print("\n💡 RECOMMENDATION: Accept that MARKET_ALIGNED threshold may need adjustment,")
    print("    or wait for odds updates to create tighter spread markets.")
