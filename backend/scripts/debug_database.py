#!/usr/bin/env python3
"""
Debug: Check database collections and data
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from db.mongo import db

print("=== DATABASE DIAGNOSTIC ===\n")

# Check collections
print("Collections in database:")
collections = db.list_collection_names()
for coll in sorted(collections):
    count = db[coll].count_documents({})
    print(f"  {coll}: {count} documents")

print("\n=== EVENTS COLLECTION ===")

# Sample event
sample_event = db["events"].find_one()
if sample_event:
    print(f"\nSample event structure:")
    print(f"  ALL KEYS: {list(sample_event.keys())}")
    print(f"  _id: {sample_event.get('_id')}")
    print(f"  id: {sample_event.get('id')}")
    print(f"  event_id: {sample_event.get('event_id')}")
    print(f"  game_id: {sample_event.get('game_id')}")
    print(f"  league: {sample_event.get('league')}")  
    print(f"  home_team: {sample_event.get('home_team')}")
    print(f"  away_team: {sample_event.get('away_team')}")
    print(f"  has odds: {bool(sample_event.get('odds'))}")
    if sample_event.get('odds'):
        odds = sample_event['odds']
        if isinstance(odds, list):
            print(f"  odds is LIST with {len(odds)} items")
            if len(odds) > 0:
                print(f"  odds[0] keys: {list(odds[0].keys()) if isinstance(odds[0], dict) else 'not a dict'}")
        else:
            print(f"  odds is DICT with keys: {list(odds.keys())}")
else:
    print("  NO events found")

print("\n=== SIMULATIONS COLLECTION ===")

# Sample sim from monte_carlo_simulations
sample_sim = db["monte_carlo_simulations"].find_one()
if sample_sim:
    print(f"\nSample monte_carlo_simulations:")
    print(f"  ALL KEYS: {list(sample_sim.keys())}")
    print(f"  event_id: {sample_sim.get('event_id')}")
    print(f"  sport_key: {sample_sim.get('sport_key')}")
    print(f"  has sharp_analysis: {bool(sample_sim.get('sharp_analysis'))}")

# Sample from simulation_results
sample_result = db["simulation_results"].find_one()
if sample_result:
    print(f"\nSample simulation_results:")
    print(f"  ALL KEYS: {list(sample_result.keys())}")
    print(f"  event_id: {sample_result.get('event_id')}")
    print(f"  game_id: {sample_result.get('game_id')}")
    print(f"  sport_key: {sample_result.get('sport_key')}")
    print(f"  has sharp_analysis: {bool(sample_result.get('sharp_analysis'))}")
    if sample_result.get('sharp_analysis'):
        sa = sample_result['sharp_analysis']
        print(f"  sharp_analysis keys: {list(sa.keys())}")
        if 'spread' in sa:
            print(f"    spread.model_spread: {sa['spread'].get('model_spread')}")
    print(f"  team_a_win_probability: {sample_result.get('team_a_win_probability')}")
else:
    print("  NO simulations found")

print("\n=== CHECKING FOR MATCHES ===")

# Try matching event_id between simulation_results and events
matches = 0
checked = 0

for sim in db["simulation_results"].find().limit(10):
    checked += 1
    event_id = sim.get('event_id') or sim.get('game_id')
    if not event_id:
        continue
    
    event = db["events"].find_one({"event_id": event_id})
    if event:
        matches += 1
        print(f"  ✅ Match found: {event_id[:30]}... (sport: {event.get('sport_key')})")
        
        # Show if this sim has spread data
        if sim.get('sharp_analysis', {}).get('spread'):
            spread = sim['sharp_analysis']['spread']
            print(f"     model_spread: {spread.get('model_spread')}, team_a_prob: {sim.get('team_a_win_probability')}")

print(f"\nChecked {checked} simulation_results, {matches} have matching events")
