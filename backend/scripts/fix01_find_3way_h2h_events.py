import sys
sys.path.append('backend')
from db.mongo import db

found = []
for ev in db.events.find({"sport_key": "icehockey_nhl"}).limit(2000):
    for bookmaker in ev.get('bookmakers', []):
        for market in bookmaker.get('markets', []):
            if market.get('key') != 'h2h':
                continue
            outcomes = market.get('outcomes', [])
            if len(outcomes) >= 3:
                found.append({
                    'event_id': ev.get('event_id') or ev.get('id'),
                    'matchup': f"{ev.get('away_team')} @ {ev.get('home_team')}",
                    'outcomes': [(o.get('name'), o.get('price')) for o in outcomes],
                })
                break
        if found and found[-1].get('event_id') == (ev.get('event_id') or ev.get('id')):
            break

print('FOUND_3WAY_H2H_EVENTS', len(found))
for item in found[:10]:
    print(item['event_id'], item['matchup'])
    print('  OUTCOMES:', item['outcomes'])
