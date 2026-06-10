import sys
sys.path.append('backend')

from integrations.odds_api import fetch_odds
from db import mongo as m


def old_convert(price):
    try:
        p = float(price)
    except Exception:
        return None
    if abs(p) < 50:
        if p >= 2.0:
            return int((p - 1) * 100)
        if p > 1.0:
            return int(-100 / (p - 1))
        return 100
    return int(p)


def polarity(vals):
    if len(vals) != 2:
        return 'INVALID'
    a, b = vals[0][1], vals[1][1]
    if a > 0 and b > 0:
        return 'BOTH_POS'
    if a < 0 and b < 0:
        return 'BOTH_NEG'
    return 'VALID_1_NEG_1_POS'


def inspect_sport(sport_key: str, max_rows: int = 10):
    events = fetch_odds(sport=sport_key, region='us', markets='h2h,spreads,totals', odds_format='decimal')
    rows = []
    for ev in events:
        home = ev.get('home_team', '')
        away = ev.get('away_team', '')
        bookmaker = (ev.get('bookmakers') or [None])[0]
        if not bookmaker:
            continue

        h2h = None
        for mk in bookmaker.get('markets', []):
            if mk.get('key') == 'h2h':
                h2h = mk
                break
        if not h2h:
            continue

        outcomes = h2h.get('outcomes', [])
        old_two = []
        for o in outcomes[:2]:
            ao = old_convert(o.get('price'))
            if ao is not None:
                old_two.append((o.get('name'), ao))

        new_two = m._extract_canonical_h2h_outcomes(h2h, home, away)

        rows.append({
            'matchup': f"{away} @ {home}",
            'raw': [(o.get('name'), o.get('price')) for o in outcomes],
            'old': old_two,
            'new': new_two,
            'old_pol': polarity(old_two),
            'new_pol': polarity(new_two),
        })

    print(f"SPORT {sport_key} EVENTS {len(rows)}")
    affected = [r for r in rows if r['old_pol'] == 'BOTH_POS']
    print('AFFECTED_BEFORE_BOTH_POS', len(affected))
    for r in rows[:max_rows]:
        print(r['matchup'])
        print('  RAW:', r['raw'])
        print('  BEFORE:', r['old'], r['old_pol'])
        print('  AFTER :', r['new'], r['new_pol'])

    return rows


if __name__ == '__main__':
    nhl_rows = inspect_sport('icehockey_nhl', max_rows=12)
    print('')
    nba_rows = inspect_sport('basketball_nba', max_rows=4)
    print('')
    ncaab_rows = inspect_sport('basketball_ncaab', max_rows=4)
