#!/usr/bin/env python3
"""Check market state distribution to diagnose parlay issue"""
import sys
sys.path.insert(0, '.')

from db.mongo import db
from collections import Counter

print("🔍 Checking market_state distribution...\n")

# Get all market states
states = list(db.market_state.find({}))
print(f"📊 Total market states in database: {len(states)}\n")

if len(states) == 0:
    print("❌ No market states found! This explains why parlays can't be generated.")
    print("\n💡 Market states are created by:")
    print("   1. Edge Scheduler running simulations")
    print("   2. Market state classifier determining EDGE/PICK/LEAN")
    print("   3. Data being written to market_state collection")
    sys.exit(1)

# Analyze pick_state distribution
pick_states = [s.get('pick_state', 'UNKNOWN') for s in states]
pick_state_counts = Counter(pick_states)

print("📈 Pick State Distribution:")
for state, count in pick_state_counts.most_common():
    percentage = (count / len(states)) * 100
    print(f"  {state}: {count} ({percentage:.1f}%)")

# Check how many are parlay-eligible
parlay_eligible = [s for s in states if s.get('pick_state') in ['EDGE', 'PICK']]
print(f"\n✅ Parlay-eligible legs (EDGE + PICK): {len(parlay_eligible)}")

lean_legs = [s for s in states if s.get('pick_state') == 'LEAN']
print(f"⚠️  LEAN legs (requires toggle ON): {len(lean_legs)}")

no_play_legs = [s for s in states if s.get('pick_state') == 'NO_PLAY']
print(f"🚫 NO_PLAY legs: {len(no_play_legs)}")

# Show sample of parlay-eligible legs
if parlay_eligible:
    print(f"\n📋 Sample parlay-eligible legs (showing first 5):")
    for state in parlay_eligible[:5]:
        game_id = state.get('game_id', 'N/A')
        market = state.get('market', 'N/A')
        pick_state = state.get('pick_state', 'N/A')
        confidence = state.get('confidence', 0)
        ev = state.get('ev', 0)
        print(f"  • {game_id[:8]}... | {market:10} | {pick_state:4} | Conf: {confidence:.1f}% | EV: {ev:.2f}%")
else:
    print("\n❌ No parlay-eligible legs found!")
    print("\n🔍 Showing sample of LEAN legs (need toggle ON):")
    for state in lean_legs[:5]:
        game_id = state.get('game_id', 'N/A')
        market = state.get('market', 'N/A')
        confidence = state.get('confidence', 0)
        print(f"  • {game_id[:8]}... | {market:10} | Conf: {confidence:.1f}%")

# Check sports distribution
sports = [s.get('sport_key', 'UNKNOWN') for s in states]
sport_counts = Counter(sports)
print(f"\n🏀 Sports Distribution:")
for sport, count in sport_counts.most_common():
    print(f"  {sport}: {count}")

print("\n" + "="*60)
print("💡 DIAGNOSIS:")
if len(parlay_eligible) < 2:
    print("❌ PROBLEM: Not enough PICK/EDGE state legs for parlay construction")
    print(f"   Need: 2+ legs")
    print(f"   Have: {len(parlay_eligible)} PICK/EDGE legs")
    if len(lean_legs) > 0:
        print(f"\n✅ SOLUTION: Enable 'Include Higher Risk' toggle to use {len(lean_legs)} LEAN legs")
    else:
        print("\n🔄 SOLUTION: Wait for Edge Scheduler to classify more games")
        print("   Or check if simulations are being generated")
else:
    print(f"✅ SUFFICIENT: {len(parlay_eligible)} parlay-eligible legs available")
    print("   Parlays should work. Check frontend filters/settings.")
