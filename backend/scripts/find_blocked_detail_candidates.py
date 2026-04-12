#!/usr/bin/env python3
from pymongo import MongoClient
import requests

client = MongoClient('mongodb://localhost:27017')
db = client['beatvegas']


def league(sk):
    s=(sk or '').lower()
    if 'basketball_nba' in s: return 'NBA'
    if 'basketball_ncaab' in s: return 'NCAAB'
    if 'americanfootball_nfl' in s: return 'NFL'
    if 'americanfootball_ncaaf' in s: return 'NCAAF'
    if 'icehockey_nhl' in s: return 'NHL'
    if 'baseball_mlb' in s: return 'MLB'
    return None

blocked=[]
lean=[]
for ev in db.events.find({}, {'event_id':1,'sport_key':1,'away_team':1,'home_team':1}).limit(120):
    lg=league(ev.get('sport_key'))
    if not lg:
        continue
    eid=ev['event_id']
    sim=requests.get(f'http://localhost:8000/api/simulations/{eid}', timeout=20)
    if sim.status_code!=200:
        continue
    dec=requests.get(f'http://localhost:8000/api/games/{lg}/{eid}/decisions', timeout=20)
    if dec.status_code!=200:
        continue
    data=dec.json()
    for m in ('spread','moneyline','total'):
        d=data.get(m)
        if not d:
            continue
        c=(d.get('classification') or '').upper()
        if c=='BLOCKED' and len(blocked)<4:
            blocked.append((lg,eid,ev.get('away_team'),ev.get('home_team'),m,d.get('selection_label')))
        if c=='LEAN' and len(lean)<4:
            lean.append((lg,eid,ev.get('away_team'),ev.get('home_team'),m,d.get('selection_label')))

print('blocked', blocked)
print('lean', lean)
