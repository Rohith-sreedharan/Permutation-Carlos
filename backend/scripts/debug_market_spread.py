#!/usr/bin/env python3
"""
Debug: Check why market_spread is 0 for NBA games
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from db.mongo import db

print("=== DEBUGGING MARKET_SPREAD = 0 ISSUE ===\n")

# Get a simulation_results with market_spread = 0
sim_with_zero = db["simulation_results"].find_one({
    "market_spread": 0,
    "median_margin": {"$exists": True, "$ne": None}
})

if sim_with_zero:
    event_id = sim_with_zero.get('event_id')
    print(f"Found sim with market_spread = 0:")
    print(f"  event_id: {event_id}")
    print(f"  median_margin: {sim_with_zero.get('median_margin')}")
    print(f"  market_spread: {sim_with_zero.get('market_spread')}")
    print(f"  market_total: {sim_with_zero.get('market_total')}")
    
    # Get the event and check its odds
    event = db["events"].find_one({"event_id": event_id})
    if event:
        print(f"\nEvent data:")
        print(f"  sport: {event.get('sport_key')}")
        print(f"  home: {event.get('home_team')}")
        print(f"  away: {event.get('away_team')}")
        print(f"\n  Odds data (first 5):")
        
        odds = event.get('odds', [])
        print(f"  Total odds entries: {len(odds)}")
        
        # Find spread odds
        spread_odds = [o for o in odds if 'spread' in o.get('market_key', '')]
        print(f"  Spread odds entries: {len(spread_odds)}")
        
        if spread_odds:
            print(f"\n  Sample spread odds:")
            for odd in spread_odds[:3]:
                print(f"    bookmaker: {odd.get('bookmaker_key')}")
                print(f"    market: {odd.get('market_key')}")
                print(f"    outcome: {odd.get('outcome_name')}")
                print(f"    point: {odd.get('point')}")
                print(f"    price: {odd.get('price')}")
                print()
        
        # Find h2h (moneyline) odds
        h2h_odds = [o for o in odds if o.get('market_key') == 'h2h']
        print(f"  Moneyline (h2h) odds entries: {len(h2h_odds)}")

# Now find a sim with NON-ZERO market_spread
print("\n" + "="*60)
print("Finding sim with NON-ZERO market_spread for comparison...\n")

sim_non_zero = db["simulation_results"].find_one({
    "market_spread": {"$ne": 0, "$exists": True, "$ne": None},
    "median_margin": {"$exists": True, "$ne": None}
})

if sim_non_zero:
    event_id2 = sim_non_zero.get('event_id')
    print(f"Found sim with market_spread != 0:")
    print(f"  event_id: {event_id2}")
    print(f"  median_margin: {sim_non_zero.get('median_margin')}")
    print(f"  market_spread: {sim_non_zero.get('market_spread')}")
    
    event2 = db["events"].find_one({"event_id": event_id2})
    if event2:
        print(f"\nEvent data:")
        print(f"  sport: {event2.get('sport_key')}")
        print(f"  home: {event2.get('home_team')}")
        
        odds2 = event2.get('odds', [])
        spread_odds2 = [o for o in odds2 if 'spread' in o.get('market_key', '')]
        
        if spread_odds2:
            print(f"\n  Sample spread odds (working):")
            for odd in spread_odds2[:3]:
                print(f"    point: {odd.get('point')}, price: {odd.get('price')}")
