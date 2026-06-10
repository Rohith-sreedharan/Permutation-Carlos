#!/usr/bin/env python3
from pathlib import Path
import sys
import requests

ROOT = Path('/Users/rohithaditya/Downloads/Permutation-Carlos')
sys.path.insert(0, str(ROOT / 'backend'))
from db.mongo import db  # noqa: E402

MAPK = {
    'basketball_nba': 'NBA',
    'basketball_ncaab': 'NCAAB',
    'americanfootball_nfl': 'NFL',
    'americanfootball_ncaaf': 'NCAAF',
    'icehockey_nhl': 'NHL',
    'baseball_mlb': 'MLB',
}


def main() -> int:
    checked = 0
    for ev in db.events.find({}, {'id': 1, 'event_id': 1, 'sport_key': 1}).limit(2000):
        gid = ev.get('id') or ev.get('event_id')
        if not gid:
            continue
        league = MAPK.get((ev.get('sport_key') or '').lower(), 'NBA')
        url = f'http://127.0.0.1:8000/api/games/{league}/{gid}/decisions'
        try:
            resp = requests.get(url, timeout=8)
        except Exception:
            continue
        if resp.status_code != 200:
            continue
        checked += 1
        payload = resp.json()
        for market_key in ('spread', 'moneyline', 'total'):
            decision = payload.get(market_key)
            if not decision:
                continue
            if decision.get('classification') == 'EDGE':
                print('EDGE_URL', url)
                print('EDGE_MARKET', market_key)
                print('EDGE_CLASSIFICATION', decision.get('classification'))
                print('EDGE_RELEASE_STATUS', decision.get('release_status'))
                print('EDGE_SELECTION_LABEL', decision.get('selection_label'))
                print('EDGE_POINTS', decision.get('edge_points'))
                print('EDGE_MODEL_PROB', decision.get('model_probability'))
                print('EDGE_MARKET_IMPLIED', decision.get('market_implied_probability'))
                print('CHECKED_200_RESPONSES', checked)
                return 0
    print('EDGE_NOT_FOUND')
    print('CHECKED_200_RESPONSES', checked)
    return 1


if __name__ == '__main__':
    raise SystemExit(main())
