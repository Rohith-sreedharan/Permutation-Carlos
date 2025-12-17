#!/usr/bin/env python3
"""
Test ESPN Scores Integration
"""
import sys
sys.path.insert(0, '/Users/rohithaditya/Downloads/Permutation-Carlos/backend')

from integrations.espn_scores import espn_scores_api
from datetime import datetime

print("=" * 60)
print("ESPN SCORES API TEST")
print("=" * 60)

# Test fetching NBA scores from today
print("\n📊 Fetching NBA scores from today...")
today = datetime.now().strftime('%Y%m%d')
nba_scores = espn_scores_api.fetch_scores('basketball_nba', today)

print(f"\nFound {len(nba_scores)} completed NBA games:")
for game in nba_scores[:5]:  # Show first 5
    print(f"\n  {game['away_team']} @ {game['home_team']}")
    print(f"  Score: {game['away_score']} - {game['home_score']}")
    print(f"  Total: {game['total_score']}")
    print(f"  Status: {game['status']}")
    if game.get('is_overtime'):
        print(f"  ⏱️  OVERTIME")

# Test NFL
print("\n\n🏈 Fetching NFL scores from today...")
nfl_scores = espn_scores_api.fetch_scores('americanfootball_nfl', today)
print(f"Found {len(nfl_scores)} completed NFL games")

# Test NCAAB
print("\n🏀 Fetching NCAAB scores from today...")
ncaab_scores = espn_scores_api.fetch_scores('basketball_ncaab', today)
print(f"Found {len(ncaab_scores)} completed NCAAB games")

print("\n" + "=" * 60)
if nba_scores or nfl_scores or ncaab_scores:
    print("✅ ESPN INTEGRATION WORKING!")
    print("The scheduler will automatically grade predictions using these scores.")
else:
    print("ℹ️  No completed games found today.")
    print("This is normal if no games have finished yet.")
print("=" * 60)
