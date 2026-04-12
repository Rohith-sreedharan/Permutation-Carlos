#!/usr/bin/env python3
import random
import requests

BASE = "http://localhost:8000"
MIN_LEAN_GAP = 0.01


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


email = f"gateev_{random.randint(1000,9999)}@example.com"
password = "ProofPass123!"
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

r = requests.get(f"{BASE}/api/odds/list?upcoming_only=true&limit=220", timeout=20)
r.raise_for_status()
obj = r.json()
events = obj.get("events", []) if isinstance(obj, dict) else obj

edge_gate_example = None
lean_gate_example = None

for ev in events:
    game_id = ev.get("id") or ev.get("event_id")
    league = league_from_sport_key(ev.get("sport_key", ""))
    if not game_id or not league:
        continue

    d = requests.get(f"{BASE}/api/games/{league}/{game_id}/decisions", headers=headers, timeout=12)
    if d.status_code != 200:
        continue
    payload = d.json()

    for market in ("spread", "total"):
        item = payload.get(market)
        if not item:
            continue

        mp = item.get("model_probability")
        mip = item.get("market_implied_probability")
        cls = item.get("classification")
        if mp is None or mip is None:
            continue

        if edge_gate_example is None and mp <= mip and cls != "EDGE":
            edge_gate_example = {
                "league": league,
                "game_id": game_id,
                "away_team": ev.get("away_team"),
                "home_team": ev.get("home_team"),
                "market": market,
                "model_probability": mp,
                "market_implied_probability": mip,
                "classification": cls,
            }

        gap = mp - mip
        if lean_gate_example is None and gap < MIN_LEAN_GAP and cls == "MARKET_ALIGNED":
            lean_gate_example = {
                "league": league,
                "game_id": game_id,
                "away_team": ev.get("away_team"),
                "home_team": ev.get("home_team"),
                "market": market,
                "model_probability": mp,
                "market_implied_probability": mip,
                "gap": gap,
                "classification": cls,
            }

    if edge_gate_example and lean_gate_example:
        break

print("EDGE_GATE_EXAMPLE", edge_gate_example)
print("LEAN_GATE_EXAMPLE", lean_gate_example)
