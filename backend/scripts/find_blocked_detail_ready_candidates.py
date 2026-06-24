import os
#!/usr/bin/env python3
import random
import requests

BASE = "http://localhost:8000"


def league_from_sport_key(sport_key: str) -> str | None:
    key = (sport_key or "").lower()
    if "basketball_nba" in key:
        return "NBA"
    if "basketball_ncaab" in key:
        return "NCAAB"
    if "americanfootball_nfl" in key:
        return "NFL"
    if "americanfootball_ncaaf" in key:
        return "NCAAF"
    if "icehockey_nhl" in key:
        return "NHL"
    if "baseball_mlb" in key:
        return "MLB"
    return None


def has_blocked(decisions: dict) -> bool:
    for market in ("spread", "moneyline", "total"):
        item = decisions.get(market) or {}
        if str(item.get("classification", "")).upper() == "BLOCKED":
            return True
    return False


email = f"blkready_{random.randint(1000,9999)}@example.com"
password = os.getenv("PROOF_PASS", "")
requests.post(
    f"{BASE}/api/auth/register",
    json={"email": email, "username": email.split("@")[0], "password": password},
    timeout=10,
)
login = requests.post(
    f"{BASE}/api/token",
    headers={"Content-Type": "application/x-www-form-urlencoded"},
    data={"username": email, "password": password},
    timeout=10,
)
login.raise_for_status()
token = login.json()["access_token"]
headers = {"Authorization": f"Bearer {token}"}

resp = requests.get(f"{BASE}/api/odds/list?upcoming_only=true&limit=250", timeout=20)
resp.raise_for_status()
obj = resp.json()
events = obj.get("events", []) if isinstance(obj, dict) else obj

print("events", len(events))
matches = []
for ev in events:
    event_id = ev.get("id") or ev.get("event_id")
    if not event_id:
        continue
    league = league_from_sport_key(ev.get("sport_key", ""))
    if not league:
        continue

    d = requests.get(f"{BASE}/api/games/{league}/{event_id}/decisions", headers=headers, timeout=10)
    if d.status_code != 200:
        continue
    decisions = d.json()
    if not has_blocked(decisions):
        continue

    sim = requests.get(f"{BASE}/api/simulations/{event_id}", headers=headers, timeout=10)
    sim_ok = sim.status_code == 200
    sim_has_event = False
    if sim_ok:
        data = sim.json()
        sim_has_event = isinstance(data.get("event"), dict)

    matches.append({
        "league": league,
        "id": event_id,
        "away": ev.get("away_team"),
        "home": ev.get("home_team"),
        "sim_status": sim.status_code,
        "sim_has_event": sim_has_event,
    })

print("blocked_matches", len(matches))
for row in matches[:20]:
    print(row)

ready = [m for m in matches if m["sim_status"] == 200 and m["sim_has_event"]]
print("ready", len(ready))
for row in ready[:10]:
    print("READY", row)
