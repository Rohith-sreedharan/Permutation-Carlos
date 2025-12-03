import os
import requests
from datetime import datetime
from zoneinfo import ZoneInfo
from dotenv import load_dotenv
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.timezone import parse_iso_to_est, format_est_date, format_est_datetime, now_utc

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


def fetch_odds(sport="basketball_nba", region="us", markets="h2h,spreads,totals", odds_format="decimal"):
    """Fetch odds for a sport from The Odds API.

    Default: basketball_nba, regions=us, markets=h2h,spreads,totals
    
    Supported markets:
    - h2h (moneyline)
    - spreads
    - totals (over/under)
    - totals_1h (1st half totals)
    - h2h_1h (1st half moneyline)
    
    Returns JSON list of event objects.
    """
    if not API_KEY:
        raise OddsApiError("ODDS_API_KEY is not set in environment")

    url = f"{BASE_URL}/sports/{sport}/odds/"
    params = {
        "apiKey": API_KEY,
        "regions": region,
        "markets": markets,  # Can include totals_1h for first half lines
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
    # Parse commence_time and compute EST-local date/time strings
    commence_iso = event.get("commence_time")
    est_date = None
    est_datetime = None
    try:
        if commence_iso:
            dt_est = parse_iso_to_est(commence_iso)
            if dt_est:
                est_date = format_est_date(dt_est)
                est_datetime = format_est_datetime(dt_est)
    except Exception:
        pass

    out = {
        "event_id": event.get("id") or event.get("event_id"),
        "sport_key": event.get("sport_key"),
        "sport_title": event.get("sport_title") or event.get("sport_nice"),
        "home_team": event.get("home_team"),
        "away_team": event.get("away_team"),
        "commence_time": event.get("commence_time"),
        "local_date_est": est_date,
        "local_datetime_est": est_datetime,
        "bookmakers": event.get("bookmakers", []),
        "raw_markets": event.get("markets", []),
        "created_at": now_utc().isoformat(),
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


def extract_market_lines(event: dict) -> dict:
    """
    Extract spread and total lines from event bookmakers data
    
    Args:
        event: Event document with bookmakers array
    
    Returns:
        dict with current_spread, total_line, odds_timestamp, bookmaker_source, and public_betting_pct
    """
    bookmakers = event.get("bookmakers", [])
    
    spread_line = None
    total_line = None
    bookmaker_name = None
    odds_timestamp = datetime.now().isoformat()  # Default to now if not available
    
    # Use first bookmaker with available markets (DraftKings, FanDuel, etc.)
    for bookmaker in bookmakers:
        bookmaker_name = bookmaker.get("title", "Unknown")
        last_update = bookmaker.get("last_update")
        if last_update:
            odds_timestamp = last_update
            
        markets = bookmaker.get("markets", [])
        
        for market in markets:
            market_key = market.get("key")
            outcomes = market.get("outcomes", [])
            
            # Extract spread
            if market_key == "spreads" and spread_line is None and len(outcomes) >= 2:
                # Use home team spread
                for outcome in outcomes:
                    if outcome.get("name") == event.get("home_team"):
                        spread_line = outcome.get("point", 0)
                        break
            
            # Extract total
            if market_key == "totals" and total_line is None and len(outcomes) > 0:
                total_line = outcomes[0].get("point")
        
        # Break if we found both
        if spread_line is not None and total_line is not None:
            break
    
    # Sport-specific defaults if no lines found
    sport_key = event.get("sport_key", "basketball_nba")
    default_totals = {
        "basketball_nba": 220.0,
        "americanfootball_nfl": 47.0,
        "baseball_mlb": 8.5,
        "icehockey_nhl": 6.5
    }
    
    return {
        "current_spread": spread_line if spread_line is not None else 0.0,
        "total_line": total_line if total_line is not None else default_totals.get(sport_key, 220.0),
        "bookmaker_source": bookmaker_name or "Consensus",
        "odds_timestamp": odds_timestamp,
        "public_betting_pct": 0.50,  # Default 50/50, would need separate API for real data
        "sport_key": sport_key
    }


def extract_first_half_line(event: dict) -> dict:
    """
    Extract 1H total line from event bookmakers data
    
    Args:
        event: Event document with bookmakers array
    
    Returns:
        dict with first_half_total, book_source, and available flag
    """
    bookmakers = event.get("bookmakers", [])
    
    first_half_total = None
    book_source = None
    
    # Look for totals_1h market
    for bookmaker in bookmakers:
        markets = bookmaker.get("markets", [])
        
        for market in markets:
            if market.get("key") == "totals_1h":
                outcomes = market.get("outcomes", [])
                if len(outcomes) > 0:
                    first_half_total = outcomes[0].get("point")
                    book_source = bookmaker.get("title", "Sportsbook")
                    break
        
        if first_half_total is not None:
            break
    
    if first_half_total is not None:
        return {
            "first_half_total": first_half_total,
            "book_source": book_source,
            "available": True,
            "message": f"{book_source} 1H line"
        }
    else:
        return {
            "first_half_total": None,
            "book_source": None,
            "available": False,
            "message": "No bookmaker 1H line available — showing BeatVegas projection only"
        }
