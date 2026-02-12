#!/usr/bin/env python3
"""
Find MARKET_ALIGNED spread with abs(edge) < 0.5
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from db.mongo import db

print("Searching for MARKET_ALIGNED spread (abs(edge) < 0.5)...\n")

# Get simulation_results with spread data
sims = list(db["simulation_results"].find(
    {
        "median_margin": {"$exists": True, "$ne": None},
        "market_spread": {"$exists": True, "$ne": None}
    },
    {
        "event_id": 1,
        "median_margin": 1,
        "market_spread": 1,
        "_id": 0
    }
).limit(500))

print(f"Found {len(sims)} simulations with spread data")
print(f"Checking for MARKET_ALIGNED matches (abs(edge) < 0.5)...\n")

market_aligned_spreads = []
checked = 0

for sim in sims:
    event_id = sim.get('event_id')
    if not event_id:
        continue
    
    checked += 1
    
    # Get event
    event = db["events"].find_one(
        {"event_id": event_id},
        {"event_id": 1, "sport_key": 1, "home_team": 1, "away_team": 1, "_id": 0}
    )
    
    if not event:
        continue
    
    model_spread = sim.get('median_margin')
    market_spread = sim.get('market_spread')
    
    if model_spread is None or market_spread is None:
        continue
    
    edge = abs(model_spread - market_spread)
    
    # Check MARKET_ALIGNED criteria: abs(edge) < 0.5
    if edge < 0.5:
        market_aligned_spreads.append({
            'event_id': event_id,
            'sport_key': event.get('sport_key'),
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
        # Convert sport_key to API league format
        league_map = {'basketball_nba': 'NBA', 'basketball_ncaab': 'NCAAB', 'americanfootball_nfl': 'NFL', 'americanfootball_ncaaf': 'NCAAF'}
        league = league_map.get(game['sport_key'], game['sport_key'].upper())
        
        print(f"[{idx}] {league}: {game.get('away_team', 'Away')} @ {game.get('home_team', 'Home')}")
        print(f"    event_id: {game['event_id']}")
        print(f"    model_spread: {game['model_spread']:.2f}")
        print(f"    market_spread: {game['market_spread']}")
        print(f"    edge: {game['edge']:.3f} pts (< 0.5 threshold) ✅")
        print(f"\n    Curl command:")
        print(f"    curl -s 'https://beta.beatvegas.app/api/games/{league}/{game['event_id']}/decisions' | jq '.spread'")
        print()
else:
    print(f"\n❌ NO MARKET_ALIGNED spreads found with abs(edge) < 0.5 in {checked} games")
    print("    Current market is too efficient - all edges >= 0.5 pts")
    print("\n💡 RECOMMENDATION: Accept that MARKET_ALIGNED threshold may need adjustment,")
    print("    or wait for odds updates to create tighter spread markets.")
