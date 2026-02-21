#!/usr/bin/env python3
"""
Find potential EDGE spreads with abs(edge) >= 2.0 and valid market data.

NOTE: This script filters by EDGE magnitude only. The API computes cover probability
      on-the-fly and applies the probability gate (>= 55% or <= 45%). 
      The script CANNOT predict final classification - verify via curl.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from db.mongo import db

print("Searching for high-edge spreads (abs(edge) >= 2.0 with valid market data)...\n")
print("⚠️  Script filters by edge only. API applies probability gate separately.\n")

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
print(f"Checking for high edge (abs(edge) >= 2.0) with valid market odds...\n")

edge_spreads = []
checked = 0

for sim in sims:
    event_id = sim.get('event_id')
    if not event_id:
        continue
    
    checked += 1
    
    # Get event with odds data
    event = db["events"].find_one(
        {"event_id": event_id},
        {"event_id": 1, "sport_key": 1, "home_team": 1, "away_team": 1, "odds": 1, "_id": 0}
    )
    
    if not event:
        continue
    
    # Calculate edge from median_margin (model spread) vs market_spread
    model_spread = sim.get('median_margin')
    market_spread = sim.get('market_spread')
    
    if model_spread is None or market_spread is None:
        continue
    
    # CRITICAL: Skip if market data is invalid (would get blocked)
    if market_spread == 0:
        continue
    
    edge = abs(model_spread - market_spread)
    
    # Filter by edge magnitude only (>= 2.0)
    # API will compute cover probability and apply probability gate
    if edge < 2.0:
        continue
    
    # Verify event has valid odds before adding
    # Check if event has spread odds with non-zero points
    has_valid_odds = False
    if event.get('odds'):
        odds_list = event['odds']
        for odd in odds_list:
            if odd.get('market_key') == 'h2h_spread' or 'spread' in odd.get('market_key', ''):
                if odd.get('point') and odd.get('point') != 0 and odd.get('price'):
                    has_valid_odds = True
                    break
    
    if not has_valid_odds:
        continue
    
    # All criteria met - add to results
    if True:
        edge_spreads.append({
            'event_id': event_id,
            'sport_key': event.get('sport_key'),
            'home_team': event.get('home_team'),
            'away_team': event.get('away_team'),
            'model_spread': model_spread,
            'market_spread': market_spread,
            'edge': edge
        })
        
        if len(edge_spreads) >= 5:
            break

print(f"Checked {checked} games with both sim and event data")

if edge_spreads:
    print(f"\n✅ FOUND {len(edge_spreads)} HIGH-EDGE SPREAD CANDIDATE(S):\n")
    print("IMPORTANT: Verify API classification via curl - only EDGE if prob gate met!\n")
    for idx, game in enumerate(edge_spreads, 1):
        # Convert sport_key to API league format
        league_map = {'basketball_nba': 'NBA', 'basketball_ncaab': 'NCAAB', 'americanfootball_nfl': 'NFL', 'americanfootball_ncaaf': 'NCAAF'}
        league = league_map.get(game['sport_key'], game['sport_key'].upper())
        
        print(f"[{idx}] {league}: {game.get('away_team', 'Away')} @ {game.get('home_team', 'Home')}")
        print(f"    event_id: {game['event_id']}")
        print(f"    model_spread: {game['model_spread']:.2f}")
        print(f"    market_spread: {game['market_spread']}")
        print(f"    edge: {game['edge']:.3f} pts (>= 2.0) ✅")
        print(f"\n    Verify classification:")
        print(f"    curl -s 'https://beta.beatvegas.app/api/games/{league}/{game['event_id']}/decisions' | jq '.spread.classification, .spread.probabilities.model_prob'")
        print(f"\n    Full response:")
        print(f"    curl -s 'https://beta.beatvegas.app/api/games/{league}/{game['event_id']}/decisions' | jq '.spread'")
        print()
else:
    print(f"\n❌ NO high-edge spreads found with abs(edge) >= 2.0 in {checked} games")
    print("    Current market lacks extreme mispricings on spreads")
