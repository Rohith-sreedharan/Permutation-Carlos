from typing import Dict, Any, List
from datetime import datetime, timezone

CANONICAL_FIELDS = ["teams", "odds", "confidence", "timestamp", "source", "event_id", "sport_key"]


def normalize_event(raw: Dict[str, Any]) -> Dict[str, Any]:
    """Produce canonical normalized structure independent of sport.
    Expected raw schema contains: event_id, sport_key, teams (list), bookmakers (list), commence_time.
    """
    teams = raw.get("teams") or [raw.get("home_team"), raw.get("away_team")] if raw.get("home_team") else []
    bookmakers = raw.get("bookmakers", [])
    odds: List[Dict[str, Any]] = []
    for bk in bookmakers:
        bk_key = bk.get("key")
        for market in bk.get("markets", []):
            market_key = market.get("key")
            for outcome in market.get("outcomes", []):
                odds.append({
                    "bookmaker": bk_key,
                    "market": market_key,
                    "name": outcome.get("name"),
                    "price": outcome.get("price"),
                    "point": outcome.get("point")
                })
    # Basic confidence heuristic: diversity of bookmakers and markets
    unique_books = {o["bookmaker"] for o in odds}
    unique_markets = {o["market"] for o in odds}
    confidence = round(min(1.0, (len(unique_books) * 0.05 + len(unique_markets) * 0.1)), 3)
    normalized = {
        "event_id": raw.get("id") or raw.get("event_id"),
        "sport_key": raw.get("sport_key"),
        "teams": teams,
        "odds": odds,
        "confidence": confidence,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "source": "odds_api_v4",
    }
    return normalized


def normalize_batch(events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [normalize_event(e) for e in events]
