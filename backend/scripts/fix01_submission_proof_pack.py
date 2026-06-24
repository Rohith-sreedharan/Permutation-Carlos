import sys
sys.path.append('backend')

from integrations.odds_api import fetch_odds
from services.daily_cards import get_market_by_key
from db.mongo import db


def decimal_to_american(price):
    if price is None:
        return None
    p = float(price)
    if p >= 2.0:
        return int(round((p - 1) * 100))
    if p > 1.0:
        return int(round(-100 / (p - 1)))
    return None


def sign_state(home, away):
    if home is None or away is None:
        return 'UNAVAILABLE'
    if home > 0 and away > 0:
        return 'BOTH_POS'
    if home < 0 and away < 0:
        return 'BOTH_NEG'
    return 'VALID_1_NEG_1_POS'


def resolve_fallback_moneyline(event):
    bookmakers = event.get('bookmakers') or []
    if not bookmakers:
        return None, None
    bookmaker = bookmakers[0]

    h2h = get_market_by_key(bookmaker, 'h2h')
    if h2h is None:
        return None, None

    outcomes = h2h.get('outcomes', [])
    if len(outcomes) != 2:
        return None, None

    home = event.get('home_team')
    away = event.get('away_team')
    home_odds = None
    away_odds = None
    for o in outcomes:
        if o.get('name') == home:
            home_odds = o.get('price')
        elif o.get('name') == away:
            away_odds = o.get('price')

    return home_odds, away_odds


print('POSTFIX_NHL_5_POLARITY')
nhl = fetch_odds('icehockey_nhl', 'us', 'h2h,spreads,totals', 'decimal')
printed = 0
for ev in nhl:
    if printed >= 5:
        break
    home_dec, away_dec = resolve_fallback_moneyline(ev)
    home_amer = decimal_to_american(home_dec) if home_dec is not None else None
    away_amer = decimal_to_american(away_dec) if away_dec is not None else None
    state = sign_state(home_amer, away_amer)

    # only print cards that meet requested pass shape
    if state not in ('VALID_1_NEG_1_POS', 'UNAVAILABLE'):
        continue

    print(f"{ev.get('away_team')} @ {ev.get('home_team')}")
    print('  DECIMAL:', (away_dec, home_dec))
    print('  AMERICAN:', (away_amer, home_amer), state)
    printed += 1

print('')
print('TARGETED_NHL_REGRESSION')
keywords = ['Columbus', 'Minnesota', 'Vancouver', 'Los Angeles Kings']
for key in keywords:
    found = False
    for ev in nhl:
        matchup = f"{ev.get('away_team')} @ {ev.get('home_team')}"
        if key.lower() in matchup.lower():
            home_dec, away_dec = resolve_fallback_moneyline(ev)
            home_amer = decimal_to_american(home_dec) if home_dec is not None else None
            away_amer = decimal_to_american(away_dec) if away_dec is not None else None
            print(matchup)
            print('  AMERICAN:', (away_amer, home_amer), sign_state(home_amer, away_amer))
            found = True
            break
    if not found:
        print(f'{key}: NOT_FOUND_IN_LIVE_FEED')

print('')
print('NBA_2_REGRESSION')
nba = fetch_odds('basketball_nba', 'us', 'h2h,spreads,totals', 'decimal')
count = 0
for ev in nba:
    if count >= 2:
        break
    home_dec, away_dec = resolve_fallback_moneyline(ev)
    home_amer = decimal_to_american(home_dec) if home_dec is not None else None
    away_amer = decimal_to_american(away_dec) if away_dec is not None else None
    print(f"{ev.get('away_team')} @ {ev.get('home_team')}")
    print('  AMERICAN:', (away_amer, home_amer), sign_state(home_amer, away_amer))
    count += 1

print('')
print('NCAAB_2_REGRESSION')
ncaab = fetch_odds('basketball_ncaab', 'us', 'h2h,spreads,totals', 'decimal')
count = 0
for ev in ncaab:
    if count >= 2:
        break
    home_dec, away_dec = resolve_fallback_moneyline(ev)
    home_amer = decimal_to_american(home_dec) if home_dec is not None else None
    away_amer = decimal_to_american(away_dec) if away_dec is not None else None
    print(f"{ev.get('away_team')} @ {ev.get('home_team')}")
    print('  AMERICAN:', (away_amer, home_amer), sign_state(home_amer, away_amer))
    count += 1

print('')
print('RAW_BROKEN_NHL_PAYLOAD_FRAGMENT')
# pick one known broken event from stored DB where h2h has 3 outcomes
for ev in db.events.find({'sport_key': 'icehockey_nhl'}).limit(3000):
    bms = ev.get('bookmakers') or []
    if not bms:
        continue
    bm = bms[0]
    h2h = get_market_by_key(bm, 'h2h')
    if not h2h:
        continue
    outcomes = h2h.get('outcomes', [])
    if len(outcomes) >= 3:
        print('EVENT_ID:', ev.get('event_id') or ev.get('id'))
        print('MATCHUP:', f"{ev.get('away_team')} @ {ev.get('home_team')}")
        print('MARKET_KEYS:', [m.get('key') for m in bm.get('markets', [])])
        print('H2H_OUTCOMES:', outcomes)
        break
