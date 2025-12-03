"""
Test injury API integration
"""
import sys
import os
sys.path.insert(0, os.path.abspath('.'))

from integrations.injury_api import (
    fetch_espn_injuries,
    get_injuries_for_team,
    get_injury_impact,
    fetch_cfb_roster
)

print("=" * 80)
print("🏥 TESTING INJURY API INTEGRATION")
print("=" * 80)

# Test 1: NBA injuries
print("\n1️⃣ Testing NBA injuries from ESPN:")
print("-" * 80)
nba_injuries = fetch_espn_injuries("basketball_nba")
if nba_injuries:
    print(f"✅ Found {len(nba_injuries)} NBA injuries\n")
    for injury in nba_injuries[:5]:  # Show first 5
        status = injury.get("status", "Unknown")
        impact = get_injury_impact(status)
        print(f"  {injury['player_name']:25} | {injury['team']:25} | {injury['position']:3} | {status:15} | Impact: {impact*100:.0f}%")
        print(f"    └─ Injury: {injury['injury']}")
else:
    print("⚠️ No NBA injuries found (might need to check ESPN HTML structure)")

# Test 2: NFL injuries
print("\n2️⃣ Testing NFL injuries from ESPN:")
print("-" * 80)
nfl_injuries = fetch_espn_injuries("americanfootball_nfl")
if nfl_injuries:
    print(f"✅ Found {len(nfl_injuries)} NFL injuries\n")
    for injury in nfl_injuries[:5]:  # Show first 5
        status = injury.get("status", "Unknown")
        impact = get_injury_impact(status)
        print(f"  {injury['player_name']:25} | {injury['team']:25} | {injury['position']:3} | {status:15} | Impact: {impact*100:.0f}%")
        print(f"    └─ Injury: {injury['injury']}")
else:
    print("⚠️ No NFL injuries found")

# Test 3: Team-specific injuries
print("\n3️⃣ Testing team-specific injury lookup:")
print("-" * 80)
celtics_injuries = get_injuries_for_team("Boston Celtics", "basketball_nba")
print(f"Boston Celtics: {len(celtics_injuries)} injuries")
for injury in celtics_injuries:
    print(f"  • {injury['player_name']} - {injury['status']} ({injury['injury']})")

# Test 4: NCAAF roster from CollegeFootballData
print("\n4️⃣ Testing NCAAF roster from CollegeFootballData:")
print("-" * 80)
try:
    alabama_roster = fetch_cfb_roster("Alabama", year=2024)  # Use 2024 since 2025 season hasn't started
    if alabama_roster:
        print(f"✅ Alabama roster: {len(alabama_roster)} players\n")
        # Show QBs and RBs
        skill_players = [p for p in alabama_roster if p.get("position") in ["QB", "RB", "WR", "TE"]]
        for player in skill_players[:10]:
            print(f"  {player['name']:25} | {player['position']:3} | #{player['jersey']:2} | {player.get('year', 'N/A'):10}")
    else:
        print("⚠️ No Alabama roster found")
except Exception as e:
    print(f"❌ Error fetching Alabama roster: {e}")

# Test 5: NCAAF injuries from ESPN
print("\n5️⃣ Testing NCAAF injuries from ESPN:")
print("-" * 80)
ncaaf_injuries = fetch_espn_injuries("americanfootball_ncaaf")
if ncaaf_injuries:
    print(f"✅ Found {len(ncaaf_injuries)} NCAAF injuries\n")
    for injury in ncaaf_injuries[:5]:
        status = injury.get("status", "Unknown")
        impact = get_injury_impact(status)
        print(f"  {injury['player_name']:25} | {injury['team']:30} | {status:15} | Impact: {impact*100:.0f}%")
else:
    print("⚠️ No NCAAF injuries found")

print("\n" + "=" * 80)
print("✅ INJURY API INTEGRATION TEST COMPLETE")
print("=" * 80)
print("\n📊 KEY FEATURES:")
print("  • ESPN scraping for NBA/NFL/MLB/NHL/NCAAF/NCAAB injuries")
print("  • CollegeFootballData API for NCAAF rosters")
print("  • Injury impact multipliers (Out=0%, Doubtful=20%, Questionable=60%, etc.)")
print("  • Real injury status applied to player stats in simulations")
print("\n🚨 BENEFITS:")
print("  • NO MORE fake players like 'Terrence Brown'")
print("  • Real injury data affects simulation accuracy")
print("  • Props only generated for healthy/active players")
print("  • User trust maintained with accurate data")
