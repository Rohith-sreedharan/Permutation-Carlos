#!/usr/bin/env python3
from pymongo import MongoClient
import requests

BACKEND_URL='http://localhost:8000'
TOKEN='user:69cc659e2e46df6f143380eb'
seeded_ids={
    'BLOCKED':'7d18651bc9124e2b06c6ffbc3af06ee6',
    'EDGE':'2ba4ff0cef51aafdf9c5509533b14091',
    'LEAN':'7bab999d0c94806e44c5de1d60333079',
    'MARKET_ALIGNED':'cb56684da584f70f8c48dec3ad5bdb7c',
}

def map_league(sport_key):
    key=(sport_key or '').lower()
    if 'basketball_nba' in key:
        return 'NBA'
    if 'basketball_ncaab' in key:
        return 'NCAAB'
    if 'americanfootball_nfl' in key:
        return 'NFL'
    if 'americanfootball_ncaaf' in key:
        return 'NCAAF'
    if 'icehockey_nhl' in key:
        return 'NHL'
    if 'baseball_mlb' in key:
        return 'MLB'
    return None

client=MongoClient('mongodb://localhost:27017')
db=client['beatvegas']
headers={'Authorization':f'Bearer {TOKEN}'}

for label, event_id in seeded_ids.items():
    ev=db.events.find_one({'event_id':event_id}, {'event_id':1,'sport_key':1,'home_team':1,'away_team':1})
    print('\nLABEL', label)
    print('event', ev)
    league=map_league(ev.get('sport_key') if ev else None)
    print('league', league)
    if not league:
        continue
    url=f'{BACKEND_URL}/api/games/{league}/{event_id}/decisions'
    r=requests.get(url, headers=headers, timeout=10)
    print('status', r.status_code)
    print(r.text[:600])
