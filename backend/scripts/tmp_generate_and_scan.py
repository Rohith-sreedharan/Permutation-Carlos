#!/usr/bin/env python3
import requests
from pymongo import MongoClient


def league(sport_key: str | None) -> str | None:
    s = (sport_key or '').lower()
    if 'basketball_nba' in s:
        return 'NBA'
    if 'basketball_ncaab' in s:
        return 'NCAAB'
    if 'americanfootball_nfl' in s:
        return 'NFL'
    if 'americanfootball_ncaaf' in s:
        return 'NCAAF'
    if 'icehockey_nhl' in s:
        return 'NHL'
    if 'baseball_mlb' in s:
        return 'MLB'
    return None


def main() -> int:
    client = MongoClient('mongodb://localhost:27017')
    db = client['beatvegas']

    events = list(db.events.find({}, {'event_id': 1, 'sport_key': 1, 'away_team': 1, 'home_team': 1}).limit(50))
    generated = 0
    for ev in events:
        eid = ev.get('event_id')
        if not eid:
            continue
        try:
            r = requests.get(f'http://localhost:8000/api/simulations/{eid}', timeout=20)
            if r.status_code == 200:
                generated += 1
        except Exception:
            pass

    counts: dict[str, int] = {}
    examples: dict[str, tuple] = {}

    for ev in events:
        lg = league(ev.get('sport_key'))
        if not lg:
            continue
        eid = ev.get('event_id')
        if not eid:
            continue

        try:
            resp = requests.get(f'http://localhost:8000/api/games/{lg}/{eid}/decisions', timeout=10)
            if resp.status_code != 200:
                continue
            payload = resp.json()
        except Exception:
            continue

        for market in ('spread', 'moneyline', 'total'):
            d = payload.get(market)
            if not d:
                continue
            c = str(d.get('classification') or 'UNKNOWN').upper()
            counts[c] = counts.get(c, 0) + 1
            if c not in examples:
                examples[c] = (lg, eid, ev.get('away_team'), ev.get('home_team'), market, d.get('selection_label'))

    print('generated', generated)
    print('counts', counts)
    for k in sorted(examples):
        print('example', k, examples[k])

    return 0


if __name__ == '__main__':
    raise SystemExit(main())
