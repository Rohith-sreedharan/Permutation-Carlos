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

    counts: dict[str, int] = {}
    examples: dict[str, tuple] = {}

    for ev in db.events.find({}, {'event_id': 1, 'sport_key': 1, 'away_team': 1, 'home_team': 1}).limit(40):
        lg = league(ev.get('sport_key'))
        if not lg:
            continue
        eid = ev.get('event_id')
        if not eid:
            continue

        try:
            response = requests.get(f'http://localhost:8000/api/games/{lg}/{eid}/decisions', timeout=8)
            if response.status_code != 200:
                continue
            payload = response.json()
        except Exception:
            continue

        for market in ('spread', 'moneyline', 'total'):
            decision = payload.get(market)
            if not decision:
                continue
            classification = str(decision.get('classification') or 'UNKNOWN').upper()
            counts[classification] = counts.get(classification, 0) + 1
            if classification not in examples:
                examples[classification] = (
                    lg,
                    eid,
                    ev.get('away_team'),
                    ev.get('home_team'),
                    market,
                    decision.get('selection_label'),
                )

    print('counts', counts)
    for key in sorted(examples):
        print('example', key, examples[key])

    return 0


if __name__ == '__main__':
    raise SystemExit(main())
