#!/usr/bin/env python3
"""
Find EDGE spread with abs(edge) >= 2.0 AND (prob >= 0.55 OR prob <= 0.45)
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from db.mongo import db

print("Searching for EDGE spread (abs(edge) >= 2.0 AND prob threshold)...\n")

# Get simulation_results with spread data
sims = list(db["simulation_results"].find(
    {
        "median_margin": {"$exists": True, "$ne": None},
        "market_spread": {"$exists": True, "$ne": None},
        "home_win_prob": {"$exists": True, "$ne": None}
    },
    {
        "event_id": 1,
        "median_margin": 1,
        "market_spread": 1,
        "home_win_prob": 1,
        "_id": 0
    }
).limit(500))

print(f"Found {len(sims)} simulations with spread data")
print(f"Checking for EDGE matches (abs(edge) >= 2.0 AND prob >= 0.55/0.45)...\n")

edge_spreads = []
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
    
    # Calculate edge from median_margin (model spread) vs market_spread
    model_spread = sim.get('median_margin')
    market_spread = sim.get('market_spread')
    home_win_prob = sim.get('home_win_prob')
    
    if model_spread is None or market_spread is None or home_win_prob is None:
        continue
    
    edge = abs(model_spread - market_spread)
    
    # Check EDGE criteria: abs(edge) >= 2.0 AND (prob >= 0.55 OR <= 0.45)
    meets_prob_threshold = (home_win_prob >= 0.55 or home_win_prob <= 0.45)
    
    if edge >= 2.0 and meets_prob_threshold:
        edge_spreads.append({
            'event_id': event_id,
            'sport_key': event.get('sport_key'),
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
        # Convert sport_key to API league format
        league_map = {'basketball_nba': 'NBA', 'basketball_ncaab': 'NCAAB', 'americanfootball_nfl': 'NFL', 'americanfootball_ncaaf': 'NCAAF'}
        league = league_map.get(game['sport_key'], game['sport_key'].upper())
        
        print(f"[{idx}] {league}: {game.get('away_team', 'Away')} @ {game.get('home_team', 'Home')}")
        print(f"    event_id: {game['event_id']}")
        print(f"    model_spread: {game['model_spread']:.2f}")
        print(f"    market_spread: {game['market_spread']}")
        print(f"    edge: {game['edge']:.3f} pts (>= 2.0 threshold) ✅")
        print(f"    home_win_prob: {game['home_win_prob']:.2%} (>= 0.55 OR <= 0.45) ✅")
        print(f"\n    Curl command:")
        print(f"    curl -s 'https://beta.beatvegas.app/api/games/{league}/{game['event_id']}/decisions' | jq '.spread'")
        print()
else:
    print(f"\n❌ NO EDGE spreads found with abs(edge) >= 2.0 AND prob threshold in {checked} games")
    print("    Current market lacks extreme mispricings on spreads")
    print("\n💡 RECOMMENDATION: Either wait for market inefficiency or accept")
    print("    that EDGE TOTAL artifact demonstrates classification logic works.")
