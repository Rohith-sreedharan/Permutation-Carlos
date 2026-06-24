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
    seen = 0
    for ev in db.events.find({}, {'id': 1, 'event_id': 1, 'sport_key': 1}).limit(1500):
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
        seen += 1
        payload = resp.json()
        spread = payload.get('spread')
        total = payload.get('total')
        moneyline = payload.get('moneyline')
        print('URL', url)
        if spread:
            print(' spread', spread.get('classification'), spread.get('release_status'), spread.get('edge_points'), spread.get('model_probability'))
        if total:
            print(' total ', total.get('classification'), total.get('release_status'), total.get('edge_points'), total.get('model_probability'))
        if moneyline:
            print(' ml    ', moneyline.get('classification'), moneyline.get('release_status'), moneyline.get('edge_points'), moneyline.get('model_probability'))
        print('-' * 80)
    print('TOTAL_200', seen)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
