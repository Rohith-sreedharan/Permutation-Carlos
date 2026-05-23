import os
#!/usr/bin/env python3
import random

import requests
from pymongo import MongoClient


def map_league(sport_key: str | None) -> str | None:
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


def main() -> int:
    base = "http://localhost:8000"
    email = f"proof_{random.randint(10000, 99999)}@example.com"
    password = os.getenv("PROOF_PASS", "")

    register = requests.post(
        f"{base}/api/auth/register",
        json={"email": email, "username": email.split("@")[0], "password": password},
        timeout=10,
    )
    if register.status_code not in (200, 201):
        print("register_failed", register.status_code)
        print(register.text[:300])
        return 1

    token = register.json().get("access_token")
    if not token:
        login = requests.post(
            f"{base}/api/auth/login",
            json={"email": email, "password": password},
            timeout=10,
        )
        token = login.json().get("access_token")

    if not token:
        print("token_failed")
        return 1

    headers = {"Authorization": f"Bearer {token}"}

    client = MongoClient("mongodb://localhost:27017", serverSelectionTimeoutMS=3000)
    db = client["beatvegas"]

    counts: dict[str, int] = {}
    examples: dict[str, tuple] = {}
    events = list(db.events.find({}, {"_id": 1, "sport_key": 1, "home_team": 1, "away_team": 1}).limit(160))
    print("events", len(events))

    for event in events:
        league = map_league(event.get("sport_key"))
        if not league:
            continue

        game_id = str(event["_id"])
        try:
            response = requests.get(
                f"{base}/api/games/{league}/{game_id}/decisions",
                headers=headers,
                timeout=8,
            )
            if response.status_code != 200:
                continue
            payload = response.json()
        except Exception:
            continue

        for market in ("spread", "moneyline", "total"):
            decision = payload.get(market)
            if not decision:
                continue
            classification = decision.get("classification", "UNKNOWN")
            counts[classification] = counts.get(classification, 0) + 1
            examples.setdefault(
                classification,
                (
                    league,
                    game_id,
                    event.get("away_team"),
                    event.get("home_team"),
                    market,
                    decision.get("selection_label"),
                    decision.get("market_type_display"),
                ),
            )

    print("counts", counts)
    for key in sorted(examples):
        print("example", key, examples[key])

    return 0


if __name__ == "__main__":
    raise SystemExit(main())