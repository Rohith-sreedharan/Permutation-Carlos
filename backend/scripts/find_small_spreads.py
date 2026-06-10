#!/usr/bin/env python3
import sys
import os
sys.path.insert(0, '/Users/rohithaditya/Downloads/Permutation-Carlos/backend')
from dotenv import load_dotenv
load_dotenv('/Users/rohithaditya/Downloads/Permutation-Carlos/backend/.env')
from db.mongo import db

LEAGUE_MAP = {
    'americanfootball_nfl': 'NFL',
    'americanfootball_ncaaf': 'NCAAF', 
    'basketball_nba': 'NBA',
    'basketball_ncaab': 'NCAAB',
}

events = list(db['events'].find({'status': {'$ne': 'finished'}}).limit(500))
for event in events:
    game_id = event.get('event_id')
    sport_key = event.get('sport_key', '')
    league = LEAGUE_MAP.get(sport_key)
    if not league:
        continue
    
    bookmakers = event.get('bookmakers', [])
    if not bookmakers:
        continue
    
    for book in bookmakers:
        markets = {m['key']: m for m in book.get('markets', [])}
        spread_market = markets.get('spreads', {})
        for outcome in spread_market.get('outcomes', []):
            line = abs(outcome.get('point', 0))
            if 0 < line < 1.0:
                print(f"{league}/{game_id}: line={outcome.get('point')} (abs={line})")
                break
