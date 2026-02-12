#!/usr/bin/env python3
"""
Test fail-closed behavior by finding a game WITHOUT simulation
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from db.mongo import db

print("Finding game with odds but NO simulation to test fail-closed...\n")

# Get events with odds
events_with_odds = list(db["events"].find(
    {
        "$or": [
            {"odds.spreads": {"$exists": True, "$ne": []}},
            {"odds.totals": {"$exists": True, "$ne": []}}
        ]
    },
    {
        "game_id": 1,
        "league": 1,
        "home_team": 1,
        "away_team": 1,
        "_id": 0
    }
).limit(100))

print(f"Found {len(events_with_odds)} events with odds")

# Find one WITHOUT simulation
for event in events_with_odds:
    game_id = event.get('game_id')
    if not game_id:
        continue
    
    # Check if simulation exists
    sim = db["monte_carlo_simulations"].find_one({"game_id": game_id})
    
    if not sim:
        print(f"✅ FOUND game WITHOUT simulation:\n")
        print(f"League: {event.get('league')}")
        print(f"Game: {event.get('away_team', 'Away')} @ {event.get('home_team', 'Home')}")
        print(f"game_id: {game_id}")
        print(f"\nFAIL-CLOSED CURL:")
        print(f"curl -s 'https://beta.beatvegas.app/api/games/{event.get('league')}/{game_id}/decisions'")
        print(f"\nExpected: HTTP 503 OR 'BLOCKED_BY_INTEGRITY' with risk.blocked_reason")
        sys.exit(0)

print("\n⚠️  All events have simulations - cannot test natural fail-closed")
print("\nTesting with FAKE game_id instead:")
print("\nFAIL-CLOSED CURL (fake game_id):")
print("curl -s 'https://beta.beatvegas.app/api/games/NCAAB/fake_game_id_no_sim_test_123/decisions'")
print("\nExpected: HTTP 404 or error indicating game/simulation not found")
