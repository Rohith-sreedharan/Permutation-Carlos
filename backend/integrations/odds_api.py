import os
import requests
import logging
from datetime import datetime
from zoneinfo import ZoneInfo
from dotenv import load_dotenv
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.timezone import parse_iso_to_est, format_est_date, format_est_datetime, now_utc
from core.sim_integrity import normalize_spread_from_odds_api, CanonicalOdds

load_dotenv()

logger = logging.getLogger(__name__)

# API Key Failover Strategy
# Primary key from environment, fallback keys hardcoded
PRIMARY_API_KEY = os.getenv("ODDS_API_KEY")
FALLBACK_API_KEYS = [
    "375cdd357271d75f22fe67f0e52b6206",  # Key 1
    "98f5a42b2a126cbcdca22b71a0f5bba5",  # Key 2
    "5fb2e5b28f4f698bdee43481041008d6",  # Key 3
]

# Build complete key pool (primary + fallbacks, deduplicated)
ALL_API_KEYS = []
if PRIMARY_API_KEY:
    ALL_API_KEYS.append(PRIMARY_API_KEY)
for key in FALLBACK_API_KEYS:
    if key not in ALL_API_KEYS:
        ALL_API_KEYS.append(key)

# Track current working key index
_current_key_index = 0
_last_working_key = ALL_API_KEYS[0] if ALL_API_KEYS else None

BASE_URL = os.getenv("ODDS_BASE_URL", "https://api.the-odds-api.com/v4")


class OddsApiError(Exception):
    pass


def _get_current_api_key():
    """Get currently active API key"""
    global _last_working_key
    if not ALL_API_KEYS:
        raise OddsApiError("No API keys configured")
    return _last_working_key or ALL_API_KEYS[_current_key_index]


def _rotate_api_key():
    """Rotate to next API key in pool"""
    global _current_key_index, _last_working_key
    _current_key_index = (_current_key_index + 1) % len(ALL_API_KEYS)
    _last_working_key = ALL_API_KEYS[_current_key_index]
    key_preview = _last_working_key[:8] + "..." if _last_working_key else "None"
    print(f"🔄 Rotating to API key #{_current_key_index + 1}: {key_preview}")
    return _last_working_key


def _check_response(res: requests.Response, is_retry=False):
    """Check API response and handle quota exhaustion with key rotation"""
    try:
        data = res.json()
    except ValueError:
        raise OddsApiError(f"Invalid JSON response: {res.text[:200]}")

    if res.status_code == 401:
        # Check if it's a quota error
        error_data = data if isinstance(data, dict) else {}
        error_code = error_data.get("error_code", "")
        
        if error_code == "OUT_OF_USAGE_CREDITS" and not is_retry:
            # Try rotating to next key
            current_key = _get_current_api_key()
            key_preview = current_key[:8] + "..." if current_key else "None"
            print(f"⚠️ API key {key_preview} quota exhausted - attempting failover")
            
            new_key = _rotate_api_key()
            if new_key != current_key:
                # Successfully rotated to a different key
                print(f"✅ Failover to new API key - retry pending")
                raise OddsApiError(f"QUOTA_EXHAUSTED_RETRY_AVAILABLE")
            else:
                # No more keys to try
                print(f"❌ All API keys exhausted - no failover available")
                raise OddsApiError(f"All API keys exhausted: {error_data}")
        else:
            # Other 401 error
            raise OddsApiError(f"Authentication error ({res.status_code}): {data}")
    
    if res.status_code != 200:
        # Odds API returns error message in JSON sometimes
        msg = data if isinstance(data, dict) else res.text
        raise OddsApiError(f"Odds API error ({res.status_code}): {msg}")
    
    return data


def fetch_sports():
    """Fetch list of supported sports from The Odds API.

    Returns a list of sports objects (each has "key", "title", ...)
    
    Includes automatic failover to backup API keys if quota exhausted.
    """
    api_key = _get_current_api_key()
    if not api_key:
        raise OddsApiError("No API keys available")
    
    # Try with current key
    res = requests.get(f"{BASE_URL}/sports", params={"apiKey": api_key})
    
    try:
        return _check_response(res, is_retry=False)
    except OddsApiError as e:
        if "QUOTA_EXHAUSTED_RETRY_AVAILABLE" in str(e):
            # Retry with rotated key
            new_key = _get_current_api_key()
            res = requests.get(f"{BASE_URL}/sports", params={"apiKey": new_key})
            return _check_response(res, is_retry=True)
        raise


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
    
    Includes automatic failover to backup API keys if quota exhausted.
    """
    api_key = _get_current_api_key()
    if not api_key:
        raise OddsApiError("No API keys available")

    url = f"{BASE_URL}/sports/{sport}/odds/"
    params = {
        "apiKey": api_key,
        "regions": region,
        "markets": markets,  # Can include totals_1h for first half lines
        "oddsFormat": odds_format,
    }
    
    # Try with current key
    res = requests.get(url, params=params, timeout=20)
    
    try:
        return _check_response(res, is_retry=False)
    except OddsApiError as e:
        if "QUOTA_EXHAUSTED_RETRY_AVAILABLE" in str(e):
            # Retry with rotated key
            new_key = _get_current_api_key()
            params["apiKey"] = new_key
            res = requests.get(url, params=params, timeout=20)
            return _check_response(res, is_retry=True)
        raise


def fetch_scores(sport="basketball_nba"):
    """Fetch scores for completed games.
    
    Includes automatic failover to backup API keys if quota exhausted.
    """
    api_key = _get_current_api_key()
    if not api_key:
        raise OddsApiError("No API keys available")
    
    url = f"{BASE_URL}/sports/{sport}/scores/"
    
    # Try with current key
    res = requests.get(url, params={"apiKey": api_key})
    
    try:
        return _check_response(res, is_retry=False)
    except OddsApiError as e:
        if "QUOTA_EXHAUSTED_RETRY_AVAILABLE" in str(e):
            # Retry with rotated key
            new_key = _get_current_api_key()
            res = requests.get(url, params={"apiKey": new_key})
            return _check_response(res, is_retry=True)
        raise


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
                # Extract both home and away spreads for validation
                spread_home = None
                spread_away = None
                home_team_name = event.get("home_team")
                away_team_name = event.get("away_team")
                
                for outcome in outcomes:
                    outcome_name = outcome.get("name", "")
                    outcome_point = outcome.get("point")
                    
                    # Match home team (case-insensitive, strip whitespace)
                    if outcome_name.strip().lower() == home_team_name.strip().lower():
                        spread_home = outcome_point
                    # Match away team
                    elif outcome_name.strip().lower() == away_team_name.strip().lower():
                        spread_away = outcome_point
                
                # SIM INTEGRITY: Use canonical normalization (hard fails on invalid spreads)
                canonical_odds = normalize_spread_from_odds_api(
                    home_team=home_team_name,
                    away_team=away_team_name,
                    home_spread_raw=spread_home,
                    away_spread_raw=spread_away,
                    tolerance=0.01  # Strict tolerance
                )
                
                if canonical_odds is None:
                    logger.error(
                        f"❌ REJECTING ODDS SNAPSHOT: {event.get('event_id')} "
                        f"Spread integrity validation failed. DO NOT SIMULATE."
                    )
                    spread_line = None  # Mark as invalid
                else:
                    spread_line = canonical_odds.home_spread
                    logger.info(
                        f"✅ Canonical spread validated: {home_team_name} {spread_line:+.1f} "
                        f"(Favorite: {canonical_odds.market_favorite_team}, "
                        f"Underdog: {canonical_odds.market_underdog_team})"
                    )
            
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
