import os
import requests
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("ODDS_API_KEY")
BASE_URL = os.getenv("ODDS_BASE_URL", "https://api.the-odds-api.com/v4")


class OddsApiError(Exception):
    pass


def _check_response(res: requests.Response):
    try:
        data = res.json()
    except ValueError:
        raise OddsApiError(f"Invalid JSON response: {res.text[:200]}")

    if res.status_code != 200:
        # Odds API returns error message in JSON sometimes
        msg = data if isinstance(data, dict) else res.text
        raise OddsApiError(f"Odds API error ({res.status_code}): {msg}")
    return data


def fetch_sports():
    """Fetch list of supported sports from The Odds API.

    Returns a list of sports objects (each has "key", "title", ...)
    """
    if not API_KEY:
        raise OddsApiError("ODDS_API_KEY is not set in environment")
    res = requests.get(f"{BASE_URL}/sports", params={"apiKey": API_KEY})
    return _check_response(res)


def fetch_odds(sport="basketball_nba", region="us", markets="h2h,spreads", odds_format="decimal"):
    """Fetch odds for a sport from The Odds API.

    Default: basketball_nba, regions=us, markets=h2h,spreads
    Returns JSON list of event objects.
    """
    if not API_KEY:
        raise OddsApiError("ODDS_API_KEY is not set in environment")

    url = f"{BASE_URL}/sports/{sport}/odds/"
    params = {
        "apiKey": API_KEY,
        "regions": region,
        "markets": markets,
        "oddsFormat": odds_format,
    }
    res = requests.get(url, params=params, timeout=20)
    return _check_response(res)


def fetch_scores(sport="basketball_nba"):
    if not API_KEY:
        raise OddsApiError("ODDS_API_KEY is not set in environment")
    url = f"{BASE_URL}/sports/{sport}/scores/"
    res = requests.get(url, params={"apiKey": API_KEY})
    return _check_response(res)


def normalize_event(event: dict) -> dict:
    """Normalize an Odds API event object into our DB event structure.

    Picks common keys: id -> event_id, sport_key, sport_title, commence_time, home_team, away_team, bookmakers
    Also collects simplified markets/odds summary for easy queries.
    """
    out = {
        "event_id": event.get("id") or event.get("event_id"),
        "sport_key": event.get("sport_key"),
        "sport_title": event.get("sport_title") or event.get("sport_nice"),
        "home_team": event.get("home_team"),
        "away_team": event.get("away_team"),
        "commence_time": event.get("commence_time"),
        "bookmakers": event.get("bookmakers", []),
        "raw_markets": event.get("markets", []),
        "created_at": datetime.utcnow().isoformat(),
    }

    # build simple flattened 'odds' list for quick lookups
    odds = []
    for b in out["bookmakers"]:
        b_key = b.get("key")
        b_title = b.get("title")
        for m in b.get("markets", []):
            m_key = m.get("key")
            for o in m.get("outcomes", []):
                odds.append({
                    "bookmaker_key": b_key,
                    "bookmaker": b_title,
                    "market_key": m_key,
                    "outcome_name": o.get("name"),
                    "price": o.get("price"),
                    "point": o.get("point"),
                })
    out["odds"] = odds
    return out
