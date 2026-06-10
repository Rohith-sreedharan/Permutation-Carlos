import sys
from datetime import datetime, timezone

sys.path.append('backend')
from db.mongo import db
from db import mongo as m


def old_convert(price):
    try:
        p = float(price)
    except Exception:
        return None
    if abs(p) < 50:
        if p >= 2.0:
            american = int((p - 1) * 100)
        elif p > 1.0:
            american = int(-100 / (p - 1))
        else:
            american = 100
    else:
        american = int(p)
    return american


def polarity(vals):
    if len(vals) != 2:
        return 'INVALID'
    signs = [v[1] for v in vals]
    if signs[0] > 0 and signs[1] > 0:
        return 'BOTH_POS'
    if signs[0] < 0 and signs[1] < 0:
        return 'BOTH_NEG'
    return 'VALID_1_NEG_1_POS'


rows = []
for ev in db.events.find({"sport_key": "icehockey_nhl"}).limit(500):
    ct = ev.get('commence_time')
    if not ct:
        continue

    try:
        dt = datetime.fromisoformat(ct.replace('Z', '+00:00'))
        if dt < datetime.now(timezone.utc):
            continue
    except Exception:
        pass

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

    new_two = m._extract_canonical_h2h_outcomes(
        h2h,
        ev.get('home_team', ''),
        ev.get('away_team', ''),
    )

    rows.append({
        'matchup': f"{ev.get('away_team')} @ {ev.get('home_team')}",
        'raw': [(o.get('name'), o.get('price')) for o in outcomes],
        'old': old_two,
        'new': new_two,
        'old_pol': polarity(old_two),
        'new_pol': polarity(new_two),
    })

rows.sort(key=lambda r: r['matchup'])
affected = [r for r in rows if r['old_pol'] == 'BOTH_POS']

print('TOTAL_UPCOMING_NHL_WITH_H2H', len(rows))
print('AFFECTED_BEFORE_BOTH_POS', len(affected))
print('')
print('BEFORE_AFTER_SAMPLE_2')
for r in affected[:2]:
    print(r['matchup'])
    print('  RAW:', r['raw'])
    print('  BEFORE:', r['old'], r['old_pol'])
    print('  AFTER :', r['new'], r['new_pol'])

print('')
print('POSTFIX_VALIDATION_5')
for r in rows[:5]:
    print(r['matchup'])
    print('  AFTER:', r['new'], r['new_pol'])
