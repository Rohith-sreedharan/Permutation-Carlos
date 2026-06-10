#!/usr/bin/env python3
from pymongo import MongoClient
import requests

client=MongoClient('mongodb://localhost:27017')
db=client['beatvegas']

def league(sport_key: str | None) -> str | None:
    s=(sport_key or '').lower()
    if 'basketball_nba' in s: return 'NBA'
    if 'basketball_ncaab' in s: return 'NCAAB'
    if 'americanfootball_nfl' in s: return 'NFL'
    if 'americanfootball_ncaaf' in s: return 'NCAAF'
    if 'icehockey_nhl' in s: return 'NHL'
    if 'baseball_mlb' in s: return 'MLB'
    return None

# generate simulations for a chunk of live events
rows=list(db.events.find({}, {'event_id':1,'sport_key':1,'away_team':1,'home_team':1}).limit(20))
for ev in rows:
    eid=ev['event_id']
    try:
        r=requests.get(f'http://localhost:8000/api/simulations/{eid}', timeout=45)
        print('generate', eid[:8], r.status_code)
    except Exception as exc:
        print('generate', eid[:8], 'ERR', exc)

counts={}
examples={}
for ev in rows:
    lg=league(ev.get('sport_key'))
    if not lg:
        continue
    eid=ev['event_id']
    try:
        r=requests.get(f'http://localhost:8000/api/games/{lg}/{eid}/decisions', timeout=15)
        if r.status_code != 200:
            print('decisions', eid[:8], r.status_code, r.text[:120])
            continue
        data=r.json()
    except Exception as exc:
        print('decisions', eid[:8], 'ERR', exc)
        continue
    for market in ('spread','moneyline','total'):
        d=data.get(market)
        if not d:
            continue
        cls=str(d.get('classification') or 'UNKNOWN').upper()
        counts[cls]=counts.get(cls,0)+1
        if cls not in examples:
            examples[cls]=(lg,eid,ev.get('away_team'),ev.get('home_team'),market,d.get('selection_label'))

print('counts', counts)
for k in sorted(examples):
    print('example', k, examples[k])