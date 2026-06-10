#!/usr/bin/env python3
"""
Verify FIX-07 required API contract fields on live /api/games/{league}/{game_id}/decisions.
"""

from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any

import requests

ROOT = Path('/Users/rohithaditya/Downloads/Permutation-Carlos')
sys.path.insert(0, str(ROOT / 'backend'))
from db.mongo import db  # noqa: E402

BASE_URL = 'http://127.0.0.1:8000'

SPORT_TO_LEAGUE = {
    'basketball_nba': 'NBA',
    'basketball_ncaab': 'NCAAB',
    'americanfootball_nfl': 'NFL',
    'americanfootball_ncaaf': 'NCAAF',
    'icehockey_nhl': 'NHL',
    'baseball_mlb': 'MLB',
}

REQUIRED_KEYS = [
    'classification',
    'market_type_display',
    'selection_label',
    'edge_points',
    'model_probability',
    'market_implied_probability',
]


def to_league(sport_key: str | None) -> str:
    if not sport_key:
        return 'NBA'
    return SPORT_TO_LEAGUE.get(sport_key.lower(), 'NBA')


def collect_decisions(payload: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for market_key in ('spread', 'moneyline', 'total'):
        item = payload.get(market_key)
        if item:
            out.append(item)
    return out


def has_required_fields(decision: dict[str, Any]) -> bool:
    return all(k in decision for k in REQUIRED_KEYS)


def compact_view(decision: dict[str, Any]) -> dict[str, Any]:
    return {
        'game_id': decision.get('game_id'),
        'market_type': decision.get('market_type'),
        'market_type_display': decision.get('market_type_display'),
        'classification': decision.get('classification'),
        'release_status': decision.get('release_status'),
        'selection_id': decision.get('selection_id'),
        'selection_label': decision.get('selection_label'),
        'edge_points': decision.get('edge_points'),
        'model_probability': decision.get('model_probability'),
        'market_implied_probability': decision.get('market_implied_probability'),
    }


def main() -> int:
    edge_case: dict[str, Any] | None = None
    blocked_case: dict[str, Any] | None = None
    null_classification_count = 0
    checked_decisions = 0
    missing_key_count = 0

    cursor = db.events.find({}, {'id': 1, 'event_id': 1, 'sport_key': 1}).limit(800)

    for ev in cursor:
        game_id = ev.get('id') or ev.get('event_id')
        if not game_id:
            continue
        league = to_league(ev.get('sport_key'))
        url = f'{BASE_URL}/api/games/{league}/{game_id}/decisions'

        try:
            resp = requests.get(url, timeout=8)
        except Exception:
            continue

        if resp.status_code != 200:
            continue

        try:
            payload = resp.json()
        except Exception:
            continue

        for decision in collect_decisions(payload):
            checked_decisions += 1

            if not has_required_fields(decision):
                missing_key_count += 1

            if decision.get('classification') is None:
                null_classification_count += 1

            if decision.get('classification') == 'EDGE' and edge_case is None:
                edge_case = compact_view(decision)

            if decision.get('classification') == 'BLOCKED' and blocked_case is None:
                blocked_case = compact_view(decision)

        if edge_case and blocked_case and checked_decisions >= 25:
            break

    print('=' * 96)
    print('FIX-07 API CONTRACT LIVE VERIFICATION')
    print('=' * 96)
    print(f'checked_decisions: {checked_decisions}')
    print(f'missing_required_keys: {missing_key_count}')
    print(f'null_classification_count: {null_classification_count}')
    print()

    print('EDGE_CASE:')
    print(json.dumps(edge_case, indent=2, sort_keys=True))
    print()

    print('BLOCKED_CASE:')
    print(json.dumps(blocked_case, indent=2, sort_keys=True))
    print()

    ok = (
        checked_decisions > 0
        and missing_key_count == 0
        and null_classification_count == 0
        and edge_case is not None
        and blocked_case is not None
    )

    if ok:
        print('RESULT: PASS')
        return 0

    print('RESULT: FAIL')
    return 1


if __name__ == '__main__':
    raise SystemExit(main())
