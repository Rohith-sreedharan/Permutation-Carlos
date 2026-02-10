#!/usr/bin/env python3
"""
Finds production games that match specific UI states for verification.
- MARKET_ALIGNED spreads
- EDGE spreads
"""
import os
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from pymongo import MongoClient
from dotenv import load_dotenv

# Find the project root by looking for the .git directory
project_root = os.path.dirname(os.path.abspath(__file__))
while not os.path.exists(os.path.join(project_root, '.git')):
    project_root = os.path.dirname(project_root)

dotenv_path = os.path.join(project_root, '.env')
print(f"Loading .env file from: {dotenv_path}")
load_dotenv(dotenv_path=dotenv_path)

MONGO_URI = os.getenv("MONGO_URI")
if not MONGO_URI:
    raise ValueError("MONGO_URI not found in environment variables")

client = MongoClient(MONGO_URI)
db = client.beatvegas

BASE_URL = "https://beta.beatvegas.app"

def get_game_ids_from_db():
    """Fetches recent, unique game_ids from the events collection."""
    # Exclude test game_ids
    exclude_ids = [
        "7030f28cdeb54fbd95dfc13725bb710f", # NCAAB test
        "e6a15b6d5f35a7f9e74e6321a4f5b6c7"  # NFL test
    ]
    
    # Query for recent, non-test events that are not finished
    events = db.events.find(
        {
            "status": {"$ne": "finished"},
            "event_id": {"$nin": exclude_ids}
        },
        {"event_id": 1, "sport_key": 1}
    ).sort("commence_time", -1).    limit(500)
    
    return [(event["event_id"], event["sport_key"]) for event in events]

def check_game(game_info):
    """Fetches decision for a single game and checks its classification."""
    game_id, sport_key = game_info
    
    league_map = {
        "americanfootball_nfl": "NFL",
        "americanfootball_ncaaf": "NCAAF",
        "basketball_nba": "NBA",
        "basketball_ncaab": "NCAAB",
    }
    league = league_map.get(sport_key)
    if not league:
        # print(f"Skipping game {game_id} with unknown sport_key: {sport_key}")
        return None

    url = f"{BASE_URL}/api/games/{league}/{game_id}/decisions"
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()

        # Check spread market
        spread_market = data.get("spread", {})
        spread_classification = spread_market.get("classification")
        spread_line = spread_market.get("market", {}).get("line")
        spread_odds = spread_market.get("market", {}).get("odds")

        # Check total market
        total_market = data.get("total", {})
        total_classification = total_market.get("classification")

        return {
            "game_id": game_id,
            "league": league,
            "spread_classification": spread_classification,
            "spread_line": spread_line,
            "spread_odds": spread_odds,
            "total_classification": total_classification,
            "url": url,
            "json": data
        }
    except requests.exceptions.RequestException as e:
        # print(f"Could not fetch {url}: {e}")
        return None

def find_examples():
    """
    Scans games to find examples of MARKET_ALIGNED and EDGE classifications.
    """
    print("Scanning for production game examples...")
    game_ids = get_game_ids_from_db()
    print(f"Found {len(game_ids)} recent games to scan.")

    market_aligned_example = None
    edge_example = None

    with ThreadPoolExecutor(max_workers=10) as executor:
        future_to_game = {executor.submit(check_game, game_info): game_info for game_info in game_ids}
        
        for i, future in enumerate(as_completed(future_to_game)):
            result = future.result()
            if not result:
                continue

            print(f"  ({i+1}/{len(game_ids)}) Checked {result['game_id']} -> Spread: {result['spread_classification']}, Total: {result['total_classification']}")

            # Find MARKET_ALIGNED example
            if not market_aligned_example:
                if (result["spread_classification"] == "MARKET_ALIGNED" and 
                    result["spread_line"] is not None and result["spread_line"] != 0 and
                    result["spread_odds"] is not None):
                    market_aligned_example = result
                    print(f"\n>>> Found valid MARKET_ALIGNED example (spread): {result['game_id']}\n")
                elif result["total_classification"] == "MARKET_ALIGNED":
                    market_aligned_example = result
                    print(f"\n>>> Found valid MARKET_ALIGNED example (total): {result['game_id']}\n")

            # Find EDGE example (accept LEAN as a fallback)
            if not edge_example:
                if result["spread_classification"] in ["EDGE", "LEAN"]:
                    edge_example = result
                    print(f"\n>>> Found valid {result['spread_classification']} example: {result['game_id']}\n")

            if market_aligned_example and edge_example:
                print("Found both required examples. Stopping scan.")
                break
    
    print("\n" + "="*80)
    print("RESULTS")
    print("="*80 + "\n")

    if market_aligned_example:
        print("✅ Found valid MARKET_ALIGNED spread example:\n")
        print(f"Game ID: {market_aligned_example['game_id']}")
        print(f"League: {market_aligned_example['league']}")
        print(f"Spread Line: {market_aligned_example['spread_line']}")
        print(f"Spread Odds: {market_aligned_example['spread_odds']}")
        print(f"Curl Command:")
        print(f"curl '{market_aligned_example['url']}' | jq\n")
        with open("MARKET_ALIGNED_EXAMPLE.json", "w") as f:
            import json
            json.dump(market_aligned_example['json'], f, indent=2)
        print("Full JSON response saved to MARKET_ALIGNED_EXAMPLE.json\n")
    else:
        print("❌ Could not find a valid MARKET_ALIGNED spread example.\n")

    if edge_example:
        print("✅ Found valid EDGE spread example:\n")
        print(f"Game ID: {edge_example['game_id']}")
        print(f"League: {edge_example['league']}")
        print(f"Curl Command:")
        print(f"curl '{edge_example['url']}' | jq\n")
        with open("EDGE_EXAMPLE.json", "w") as f:
            import json
            json.dump(edge_example['json'], f, indent=2)
        print("Full JSON response saved to EDGE_EXAMPLE.json\n")
    else:
        print("❌ Could not find an EDGE spread example.\n")


if __name__ == "__main__":
    find_examples()
