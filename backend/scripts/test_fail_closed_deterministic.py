#!/usr/bin/env python3
"""
DETERMINISTIC FAIL-CLOSED TEST

SAFETY: This script ONLY runs if TEST_MODE=1 environment variable is set.
It will temporarily modify database state to prove fail-closed behavior.

Creates a controlled test condition by finding an event with a simulation
and temporarily hiding required fields to trigger fail-closed behavior.

Steps:
1. Find an event with complete simulation data
2. Show curl command WITH simulation (should work)
3. Temporarily remove median_margin field to simulate missing data
4. Show curl command WITHOUT complete simulation (should fail-closed)
5. Restore the field

This proves deterministic fail-closed when simulation is missing.
"""
import os
import sys

# SAFETY GATE: Require explicit TEST_MODE=1 to run
if os.environ.get('TEST_MODE') != '1':
    print("❌ ERROR: This script modifies database state for testing.")
    print("   Set TEST_MODE=1 to run:")
    print("   TEST_MODE=1 python3 test_fail_closed_deterministic.py")
    sys.exit(1)

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from db.mongo import db

print("=== DETERMINISTIC FAIL-CLOSED TEST ===\n")

# Find a complete simulation in monte_carlo_simulations (what the API actually uses)
sim = db["monte_carlo_simulations"].find_one({
    "sharp_analysis.spread.model_spread": {"$exists": True, "$ne": None},
    "$or": [{"event_id": {"$exists": True}}, {"game_id": {"$exists": True}}]
})

if not sim:
    print("❌ No simulation found in monte_carlo_simulations")
    sys.exit(1)

event_id = sim.get('event_id') or sim.get('game_id')
sim_id = sim.get('_id')
model_spread = sim.get('sharp_analysis', {}).get('spread', {}).get('model_spread')

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

print("STEP 2: HIDE simulation data (THIS SCRIPT WILL DO IT):")
print(f"  Will rename sharp_analysis.spread.model_spread to trigger missing data")
print()

print("STEP 3: Verify simulation INCOMPLETE (curl should fail-closed)")
print(f"  curl -s 'https://beta.beatvegas.app/api/games/{league}/{event_id}/decisions' | jq '.spread.release_status, .spread.risk.blocked_reason'")
print()
print("  Expected: HTTP 503 with 'FAIL-CLOSED: No model_spread'")
print()

print("STEP 4: RESTORE simulation data (THIS SCRIPT WILL DO IT)")
print(f"  Will restore sharp_analysis.spread.model_spread = {model_spread}")
print()

print("=" * 70)
print("READY TO RUN TEST")
print("=" * 70)
print()
print("Press ENTER to continue (or Ctrl+C to abort)...")
input()

# Execute the test
print("\n>>> Hiding simulation data (renaming sharp_analysis.spread.model_spread)...")
result = db["monte_carlo_simulations"].update_one(
    {"_id": sim_id},
    {"$rename": {"sharp_analysis.spread.model_spread": "sharp_analysis.spread.model_spread_backup"}}
)
print(f"    Modified {result.modified_count} document(s)")

print(f"\n>>> Test this curl (should return HTTP 503):")
print(f"    curl -s 'https://beta.beatvegas.app/api/games/{league}/{event_id}/decisions'")
print()
print("Press ENTER after running curl to restore data...")
input()

# Restore
print("\n>>> Restoring simulation data...")
result = db["monte_carlo_simulations"].update_one(
    {"_id": sim_id},
    {"$rename": {"sharp_analysis.spread.model_spread_backup": "sharp_analysis.spread.model_spread
print(f"    Restored {result.modified_count} document(s)")

print("\n✅ Test complete - data restored")
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
