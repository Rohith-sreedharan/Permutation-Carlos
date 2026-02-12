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
    print(f"  game_id: {sample_event.get('game_id')}")
    print(f"  league: {sample_event.get('league')}")  
    print(f"  home_team: {sample_event.get('home_team')}")
    print(f"  has odds: {bool(sample_event.get('odds'))}")
    if sample_event.get('odds'):
        odds = sample_event['odds']
        print(f"  odds keys: {list(odds.keys())}")
        if 'spreads' in odds:
            print(f"  spreads count: {len(odds.get('spreads', []))}")
        if 'totals' in odds:
            print(f"  totals count: {len(odds.get('totals', []))}")
else:
    print("  NO events found")

print("\n=== SIMULATIONS COLLECTION ===")

# Sample sim
sample_sim = db["monte_carlo_simulations"].find_one()
if sample_sim:
    print(f"\nSample simulation structure:")
    print(f"  game_id: {sample_sim.get('game_id')}")
    print(f"  has sharp_analysis: {bool(sample_sim.get('sharp_analysis'))}")
    if sample_sim.get('sharp_analysis'):
        sa = sample_sim['sharp_analysis']
        print(f"  sharp_analysis keys: {list(sa.keys())}")
        if 'spread' in sa:
            spread = sa['spread']
            print(f"  spread.model_spread: {spread.get('model_spread')}")
    print(f"  team_a_win_probability: {sample_sim.get('team_a_win_probability')}")
else:
    print("  NO simulations found")

print("\n=== CHECKING FOR MATCHES ===")

# Find sims with events
sims_with_events = 0
total_checked = 0

for sim in db["monte_carlo_simulations"].find().limit(10):
    total_checked += 1
    game_id = sim.get('game_id')
    if not game_id:
        continue
    
    event = db["events"].find_one({"game_id": game_id})
    if event:
        sims_with_events += 1
        print(f"  ✅ Match found: {game_id[:20]}... (league: {event.get('league')})")

print(f"\nChecked {total_checked} sims, {sims_with_events} have matching events")
