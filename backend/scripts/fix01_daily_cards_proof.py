import sys
from datetime import datetime, timezone

sys.path.append('backend')
from db.mongo import db
from integrations.odds_api import fetch_odds
from services.daily_cards import get_market_by_key


def old_moneyline_from_fallback(bookmaker, home_team, away_team):
    home_odds = None
    away_odds = None
    for market in bookmaker.get('markets', []):
        if market.get('key') == 'h2h':
            outcomes = market.get('outcomes', [])
            for outcome in outcomes:
                if outcome.get('name') == home_team:
                    home_odds = outcome.get('price')
                elif outcome.get('name') == away_team:
                    away_odds = outcome.get('price')
    return home_odds, away_odds


def new_moneyline_from_fallback(bookmaker, home_team, away_team):
    moneyline_market = get_market_by_key(bookmaker, 'h2h')
    if moneyline_market is None:
        return None, None
    outcomes = moneyline_market.get('outcomes', [])
    if len(outcomes) != 2:
        return None, None

    home_odds = None
    away_odds = None
    for outcome in outcomes:
        if outcome.get('name') == home_team:
            home_odds = outcome.get('price')
        elif outcome.get('name') == away_team:
            away_odds = outcome.get('price')
    return home_odds, away_odds


def sign_label(a, b):
    if a is None or b is None:
        return 'UNAVAILABLE'
    if a > 0 and b > 0:
        return 'BOTH_POS'
    if a < 0 and b < 0:
        return 'BOTH_NEG'
    return 'OPPOSITE_SIGNS'


# 1) Pull broken NHL samples from stored events (3-outcome h2h with old both-positive)
broken_samples = []
for ev in db.events.find({'sport_key': 'icehockey_nhl'}).limit(3000):
    bookmakers = ev.get('bookmakers') or []
    if not bookmakers:
        continue
    bookmaker = bookmakers[0]
    h2h = get_market_by_key(bookmaker, 'h2h')
    if not h2h:
        continue
    outcomes = h2h.get('outcomes', [])
    if len(outcomes) < 3:
        continue

    home_team = ev.get('home_team')
    away_team = ev.get('away_team')
    old_home, old_away = old_moneyline_from_fallback(bookmaker, home_team, away_team)
    new_home, new_away = new_moneyline_from_fallback(bookmaker, home_team, away_team)

    old_state = sign_label(old_home, old_away)
    if old_state == 'BOTH_POS':
        broken_samples.append({
            'matchup': f"{away_team} @ {home_team}",
            'event_id': ev.get('event_id') or ev.get('id'),
            'market_keys': [m.get('key') for m in bookmaker.get('markets', [])],
            'h2h_outcomes': [(o.get('name'), o.get('price')) for o in outcomes],
            'before': (old_home, old_away, old_state),
            'after': (new_home, new_away, sign_label(new_home, new_away)),
        })

print('ROOT_CAUSE_DB_SAMPLES', len(broken_samples))
print('')
print('BROKEN_BEFORE_AFTER_2')
for sample in broken_samples[:2]:
    print(sample['matchup'])
    print('  EVENT_ID:', sample['event_id'])
    print('  MARKET_KEYS:', sample['market_keys'])
    print('  H2H_OUTCOMES:', sample['h2h_outcomes'])
    print('  BEFORE_HOME_AWAY:', sample['before'])
    print('  AFTER_HOME_AWAY :', sample['after'])

# 2) Post-fix validation for 5 NHL cards from live odds API
print('')
print('POSTFIX_NHL_5')
nhl_live = fetch_odds(sport='icehockey_nhl', region='us', markets='h2h,spreads,totals', odds_format='decimal')
count = 0
for ev in nhl_live:
    if count >= 5:
        break
    bookmakers = ev.get('bookmakers') or []
    if not bookmakers:
        continue
    bookmaker = bookmakers[0]
    home_team = ev.get('home_team')
    away_team = ev.get('away_team')
    new_home, new_away = new_moneyline_from_fallback(bookmaker, home_team, away_team)

    state = sign_label(new_home, new_away)
    print(f"{away_team} @ {home_team}")
    print('  RESOLVED_H2H:', (new_home, new_away), state)
    count += 1

# 3) Regression proof for NBA and NCAAB (2 each)
print('')
print('REGRESSION_NBA_2')
nba_live = fetch_odds(sport='basketball_nba', region='us', markets='h2h,spreads,totals', odds_format='decimal')
shown = 0
for ev in nba_live:
    if shown >= 2:
        break
    bookmakers = ev.get('bookmakers') or []
    if not bookmakers:
        continue
    bookmaker = bookmakers[0]
    home_team = ev.get('home_team')
    away_team = ev.get('away_team')
    new_home, new_away = new_moneyline_from_fallback(bookmaker, home_team, away_team)
    print(f"{away_team} @ {home_team}")
    print('  RESOLVED_H2H:', (new_home, new_away), sign_label(new_home, new_away))
    shown += 1

print('')
print('REGRESSION_NCAAB_2')
ncaab_live = fetch_odds(sport='basketball_ncaab', region='us', markets='h2h,spreads,totals', odds_format='decimal')
shown = 0
for ev in ncaab_live:
    if shown >= 2:
        break
    bookmakers = ev.get('bookmakers') or []
    if not bookmakers:
        continue
    bookmaker = bookmakers[0]
    home_team = ev.get('home_team')
    away_team = ev.get('away_team')
    new_home, new_away = new_moneyline_from_fallback(bookmaker, home_team, away_team)
    print(f"{away_team} @ {home_team}")
    print('  RESOLVED_H2H:', (new_home, new_away), sign_label(new_home, new_away))
    shown += 1

# 4) API payload fragment for one NHL event, showing canonical h2h resolution
print('')
print('API_PAYLOAD_FRAGMENT_1_NHL')
for ev in nhl_live:
    bookmakers = ev.get('bookmakers') or []
    if not bookmakers:
        continue
    bookmaker = bookmakers[0]
    h2h = get_market_by_key(bookmaker, 'h2h')
    if not h2h:
        continue
    print('EVENT_ID:', ev.get('id'))
    print('MATCHUP:', f"{ev.get('away_team')} @ {ev.get('home_team')}")
    print('BOOKMAKER:', bookmaker.get('key'), bookmaker.get('title'))
    print('MARKET_KEYS:', [m.get('key') for m in bookmaker.get('markets', [])])
    print('H2H_MARKET:', {
        'key': h2h.get('key'),
        'outcomes': h2h.get('outcomes', []),
    })
    break
