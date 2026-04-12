#!/usr/bin/env python3
"""
FIX-01 Confirmation: Check if live Odds API returns 2-way or 3-way h2h for NHL games.
If 2-way: UNAVAILABLE is temporary artifact of stored data → YES to proceed
If 3-way: UNAVAILABLE is correct expected behavior → Still YES, but permanent
"""

import os
import sys
import json
from datetime import datetime, timedelta

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import os

ODDS_API_KEY = os.getenv("ODDS_API_KEY")
import requests

def probe_live_nhl_markets():
        """Query live Odds API for NHL games and inspect h2h market structure."""
    
        if not ODDS_API_KEY:
            print("❌ ODDS_API_KEY environment variable not set")
            return {"status": "no_api_key"}
    """Query live Odds API for NHL games and inspect h2h market structure."""
    
    url = "https://api.the-odds-api.com/v4/sports/nhl/odds"
    params = {
        "apiKey": ODDS_API_KEY,
        "regions": "us",
        "markets": "h2h",
        "oddsFormat": "decimal",
        "dateFormat": "iso"
    }
    
    print("=" * 80)
    print("FIX-01 CONFIRMATION: Live Odds API h2h Market Structure Check")
    print("=" * 80)
    print()
    
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        games = response.json()
        
        if not games:
            print("⚠️  No upcoming NHL games found in Odds API")
            return {"status": "no_games"}
        
        # Look for Minnesota Wild games
        wild_games = [g for g in games if "Minnesota" in g.get("home_team", "") or "Minnesota" in g.get("away_team", "")]
        
        if not wild_games:
            # Use first available game as proxy
            game_to_check = games[0]
            print(f"No Minnesota Wild upcoming; using proxy: {game_to_check['home_team']} @ {game_to_check['away_team']}")
        else:
            game_to_check = wild_games[0]
            print(f"Found Minnesota Wild game: {game_to_check['home_team']} @ {game_to_check['away_team']}")
        
        print(f"Commence time: {game_to_check.get('commence_time', 'unknown')}")
        print()
        
        # Inspect h2h market structure
        bookmakers = game_to_check.get("bookmakers", [])
        if not bookmakers:
            print("❌ No bookmakers found")
            return {"status": "no_bookmakers"}
        
        first_book = bookmakers[0]
        markets = first_book.get("markets", [])
        h2h_market = None
        for m in markets:
            if m.get("key") == "h2h":
                h2h_market = m
                break
        
        if not h2h_market:
            print("❌ h2h market not found in bookmaker")
            return {"status": "no_h2h_market"}
        
        outcomes = h2h_market.get("outcomes", [])
        outcome_count = len(outcomes)
        
        print(f"h2h Market from: {first_book.get('title', 'unknown')}")
        print(f"Outcome count: {outcome_count}")
        print()
        
        # Show outcome details
        print("Outcomes:")
        for i, outcome in enumerate(outcomes, 1):
            name = outcome.get("name", "unknown")
            price = outcome.get("price", "unknown")
            print(f"  {i}. {name}: {price}")
        
        print()
        print("=" * 80)
        
        if outcome_count == 2:
            print("✅ LIVE API RETURNS 2-WAY h2h")
            print()
            print("INTERPRETATION:")
            print("- UNAVAILABLE in stored data is a temporary artifact of old 3-way markets")
            print("- Fresh API re-fetch will resolve to valid 2-way odds")
            print("- FIX-01 fail-closed behavior is correct but not permanent for these games")
            return {"status": "confirmed_2way", "outcome_count": 2}
        elif outcome_count == 3:
            print("✅ LIVE API STILL RETURNS 3-WAY h2h")
            print()
            print("INTERPRETATION:")
            print("- These matchups natively include draw markets")
            print("- UNAVAILABLE rendering is correct expected behavior (fail closed)")
            print("- This is permanent for NHL games with draw options")
            print("- FIX-01 success: prevents leaked draw outcomes in moneyline rendering")
            return {"status": "confirmed_3way", "outcome_count": 3}
        else:
            print(f"⚠️  UNEXPECTED: h2h has {outcome_count} outcomes (expected 2 or 3)")
            return {"status": "unexpected_count", "outcome_count": outcome_count}
    
    except Exception as e:
        print(f"❌ Error probing Odds API: {e}")
        return {"status": "error", "error": str(e)}

if __name__ == "__main__":
    result = probe_live_nhl_markets()
    print()
    print(f"Result: {json.dumps(result, indent=2)}")
