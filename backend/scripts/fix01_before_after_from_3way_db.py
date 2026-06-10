import sys
sys.path.append('backend')
from db.mongo import db
from db import mongo as m


def old_convert(price):
    p = float(price)
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


samples = []
for ev in db.events.find({"sport_key": "icehockey_nhl"}).limit(3000):
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
    if len(outcomes) < 3:
        continue

    old_two = [(o.get('name'), old_convert(o.get('price'))) for o in outcomes[:2]]
    new_two = m._extract_canonical_h2h_outcomes(h2h, ev.get('home_team', ''), ev.get('away_team', ''))

    row = {
        'matchup': f"{ev.get('away_team')} @ {ev.get('home_team')}",
        'raw': [(o.get('name'), o.get('price')) for o in outcomes],
        'before': old_two,
        'after': new_two,
        'before_pol': polarity(old_two),
        'after_pol': polarity(new_two),
    }
    if row['before_pol'] == 'BOTH_POS':
        samples.append(row)

print('THREE_WAY_BOTH_POS_BEFORE', len(samples))
for r in samples[:5]:
    print(r['matchup'])
    print('  RAW:', r['raw'])
    print('  BEFORE:', r['before'], r['before_pol'])
    print('  AFTER :', r['after'], r['after_pol'])
