#!/usr/bin/env python3
"""
Find valid MARKET_ALIGNED and EDGE spread examples from production.
"""
import os
import sys
import json

# Setup path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env'))

from db.mongo import db
import requests

BASE_URL = "https://beta.beatvegas.app"

# Map sport_key to league
LEAGUE_MAP = {
    'americanfootball_nfl': 'NFL',
    'americanfootball_ncaaf': 'NCAAF',
    'basketball_nba': 'NBA',
    'basketball_ncaab': 'NCAAB',
}


def has_valid_spread_in_event(event):
    """Check if event has non-zero spread lines in bookmakers data."""
    bookmakers = event.get('bookmakers', [])
    if not bookmakers:
        return False
    
    for book in bookmakers:
        markets = {m['key']: m for m in book.get('markets', [])}
        spread_market = markets.get('spreads', {})
        spread_outcomes = spread_market.get('outcomes', [])
        
        for outcome in spread_outcomes:
            line = outcome.get('point', 0)
            if line != 0:
                return True
    return False


def check_game_api(league, game_id):
    """Fetch game decisions from production API and analyze."""
    url = f"{BASE_URL}/api/games/{league}/{game_id}/decisions"
    try:
        resp = requests.get(url, timeout=10)
        if resp.status_code != 200:
            return None, None
        
        data = resp.json()
        spread = data.get('spread', {})
        
        result = {
            'url': url,
            'classification': spread.get('classification'),
            'line': spread.get('market', {}).get('line'),
            'odds': spread.get('market', {}).get('odds'),
            'validator_failures': spread.get('validator_failures', []),
            'full_json': data
        }
        
        return result, None
    except Exception as e:
        return None, str(e)


def find_artifacts():
    print("Searching for valid MARKET_ALIGNED and EDGE spread examples...\n")
    
    market_aligned_found = None
    edge_found = None
    
    # Get recent non-finished events
    events = list(db['events'].find(
        {'status': {'$ne': 'finished'}}
    ).sort('commence_time', -1).limit(200))
    
    print(f"Found {len(events)} events to check\n")
    
    for i, event in enumerate(events):
        game_id = event.get('event_id')
        sport_key = event.get('sport_key', '')
        
        league = LEAGUE_MAP.get(sport_key)
        if not league:
            continue
        
        # Pre-filter: check if event has valid spread data in bookmakers
        if not has_valid_spread_in_event(event):
            continue
        
        result, error = check_game_api(league, game_id)
        if not result:
            continue
        
        classification = result['classification']
        line = result['line']
        odds = result['odds']
        failures = result['validator_failures']
        
        # Check for MARKET_ALIGNED
        if not market_aligned_found:
            if (classification == 'MARKET_ALIGNED' and 
                line is not None and line != 0 and 
                odds is not None and 
                len(failures) == 0):
                market_aligned_found = result
                print(f"✅ FOUND VALID MARKET_ALIGNED: {league}/{game_id}")
                print(f"   spread.line={line}, odds={odds}, failures={failures}")
        
        # Check for EDGE
        if not edge_found:
            if classification == 'EDGE' and len(failures) == 0:
                edge_found = result
                print(f"✅ FOUND VALID EDGE: {league}/{game_id}")
                print(f"   spread.line={line}, odds={odds}")
        
        if market_aligned_found and edge_found:
            break
    
    print("\n" + "="*80)
    print("RESULTS")
    print("="*80 + "\n")
    
    if market_aligned_found:
        print("=" * 40)
        print("MARKET_ALIGNED SPREAD ARTIFACT")
        print("=" * 40)
        print(f"\ncurl command:")
        print(f"curl -s '{market_aligned_found['url']}'\n")
        
        # Save to file
        with open('MARKET_ALIGNED_EXAMPLE.json', 'w') as f:
            json.dump(market_aligned_found['full_json'], f, indent=2)
        print("Full JSON saved to MARKET_ALIGNED_EXAMPLE.json\n")
    else:
        print("❌ No valid MARKET_ALIGNED spread found\n")
    
    if edge_found:
        print("=" * 40)
        print("EDGE SPREAD ARTIFACT")
        print("=" * 40)
        print(f"\ncurl command:")
        print(f"curl -s '{edge_found['url']}'\n")
        
        # Save to file
        with open('EDGE_EXAMPLE.json', 'w') as f:
            json.dump(edge_found['full_json'], f, indent=2)
        print("Full JSON saved to EDGE_EXAMPLE.json\n")
    else:
        print("❌ No valid EDGE spread found\n")


if __name__ == "__main__":
    find_artifacts()
