#!/usr/bin/env python3
"""
Test fail-closed behavior by finding a game WITHOUT simulation
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from db.mongo import db

print("Finding game with odds but NO simulation to test fail-closed...\n")

# Get events with odds (simpler query - just check if odds object exists)
events_with_odds = list(db["events"].find(
    {"odds": {"$exists": True}},
    {
        "game_id": 1,
        "league": 1,
        "home_team": 1,
        "away_team": 1,
        "odds": 1,
        "_id": 0
    }
).limit(100))

print(f"Found {len(events_with_odds)} events with odds")

# Find one WITHOUT simulation
for event in events_with_odds:
    event_id = event.get('event_id')
    if not event_id:
        continue
    
    # Check if simulation exists (check both collections)
    sim1 = db["monte_carlo_simulations"].find_one({"event_id": event_id})
    sim2 = db["simulation_results"].find_one({"event_id": event_id})
    
    if not sim1 and not sim2:
        print(f"✅ FOUND game WITHOUT simulation:\n")
        print(f"Sport: {event.get('sport_key')}")
        print(f"Game: {event.get('away_team', 'Away')} @ {event.get('home_team', 'Home')}")
        print(f"event_id: {event_id}")
        
        # Convert sport_key to API league format
        league_map = {'basketball_nba': 'NBA', 'basketball_ncaab': 'NCAAB', 'americanfootball_nfl': 'NFL', 'americanfootball_ncaaf': 'NCAAF'}
        league = league_map.get(event.get('sport_key'), event.get('sport_key', 'NCAAB').upper())
        
        print(f"\nFAIL-CLOSED CURL:")
        print(f"curl -s 'https://beta.beatvegas.app/api/games/{league}/{event_id}/decisions'")
        print(f"\nExpected: HTTP 503 OR 'BLOCKED_BY_INTEGRITY' with risk.blocked_reason")
        sys.exit(0)

print("\n⚠️  All events have simulations - cannot test natural fail-closed")
print("\nTesting with FAKE game_id instead:")
print("\nFAIL-CLOSED CURL (fake game_id):")
print("curl -s 'https://beta.beatvegas.app/api/games/NCAAB/fake_game_id_no_sim_test_123/decisions'")
print("\nExpected: HTTP 404 or error indicating game/simulation not found")
