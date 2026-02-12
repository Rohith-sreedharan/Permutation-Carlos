#!/usr/bin/env python3
"""
DETERMINISTIC FAIL-CLOSED TEST

Creates a controlled test condition by finding an event with a simulation
and temporarily hiding required fields to trigger fail-closed behavior.

Steps:
1. Find an event with complete simulation data
2. Show curl command WITH simulation (should work)
3. Instruct to rename the simulation doc's _id to hide it
4. Show curl command WITHOUT simulation (should fail-closed)
5. Instruct to restore the _id

This proves deterministic fail-closed when simulation is missing.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from db.mongo import db

print("=== DETERMINISTIC FAIL-CLOSED TEST ===\n")

# Find a complete simulation
sim = db["simulation_results"].find_one({
    "median_margin": {"$exists": True, "$ne": None},
    "market_spread": {"$exists": True, "$ne": None},
    "event_id": {"$exists": True}
})

if not sim:
    print("❌ No simulation found")
    sys.exit(1)

event_id = sim.get('event_id')
sim_id = sim.get('_id')

# Get event
event = db["events"].find_one({"event_id": event_id})
if not event:
    print(f"❌ No event found for {event_id}")
    sys.exit(1)

league_map = {'basketball_nba': 'NBA', 'basketball_ncaab': 'NCAAB'}
league = league_map.get(event.get('sport_key'), 'NBA')

print(f"Found test candidate:")
print(f"  Event: {event.get('away_team')} @ {event.get('home_team')}")
print(f"  League: {league}")
print(f"  event_id: {event_id}")
print(f"  simulation _id: {sim_id}")
print()

print("=" * 70)
print("FAIL-CLOSED TEST PROCEDURE:")
print("=" * 70)
print()

print("STEP 1: Verify simulation EXISTS (should return OFFICIAL or INFO_ONLY)")
print(f"curl -s 'https://beta.beatvegas.app/api/games/{league}/{event_id}/decisions' | jq '.spread.release_status, .spread.risk.blocked_reason'")
print()

print("STEP 2: HIDE the simulation (run this in MongoDB shell):")
print(f"db.simulation_results.updateOne({{_id: ObjectId('{sim_id}')}}, {{$set: {{hidden_for_test: true}}, $unset: {{median_margin: '', market_spread: ''}}}});")
print()

print("STEP 3: Verify simulation MISSING (should return BLOCKED_BY_INTEGRITY)")
print(f"curl -s 'https://beta.beatvegas.app/api/games/{league}/{event_id}/decisions' | jq '.spread'")
print()
print("Expected: release_status = 'BLOCKED_BY_INTEGRITY' OR HTTP 503")
print("Expected: risk.blocked_reason should explain missing simulation data")
print()

print("STEP 4: RESTORE the simulation (run this in MongoDB shell):")
print(f"db.simulation_results.updateOne({{_id: ObjectId('{sim_id}')}}, {{$set: {{median_margin: {sim.get('median_margin')}, market_spread: {sim.get('market_spread')}}}, $unset: {{hidden_for_test: ''}}}});")
print()

print("=" * 70)
print("ALTERNATIVE: Find an event WITHOUT simulation")
print("=" * 70)
print()

# Try to find event without simulation
events_without_sim = []
for event in db["events"].find({"odds": {"$exists": True}}).limit(100):
    eid = event.get('event_id')
    if not eid:
        continue
    
    sim_check = db["simulation_results"].find_one({"event_id": eid}, {"_id": 1})
    if not sim_check:
        events_without_sim.append(event)
        if len(events_without_sim) >= 3:
            break

if events_without_sim:
    print(f"Found {len(events_without_sim)} event(s) WITHOUT simulation:")
    print()
    for evt in events_without_sim:
        league = league_map.get(evt.get('sport_key'), 'NBA')
        eid = evt.get('event_id')
        print(f"  {evt.get('away_team')} @ {evt.get('home_team')}")
        print(f"  curl -s 'https://beta.beatvegas.app/api/games/{league}/{eid}/decisions' | jq '.spread.release_status, .spread.risk.blocked_reason'")
        print()
else:
    print("All events have simulations - use STEP 2-4 above for deterministic test")
