"""
Market Line Integrity Configuration
Configurable thresholds for odds staleness, validation rules, and integrity policies
"""

from typing import Dict
from datetime import timedelta


# Sport-specific maximum odds age (in hours)
# After this threshold, odds are marked as "stale" but simulations can still run
MAX_ODDS_AGE_HOURS: Dict[str, float] = {
    "americanfootball_nfl": 72.0,      # NFL games, odds stable longer
    "americanfootball_ncaaf": 72.0,    # College football
    "basketball_nba": 24.0,             # NBA, faster moving lines
    "basketball_ncaab": 36.0,           # College basketball
    "baseball_mlb": 48.0,               # MLB
    "icehockey_nhl": 48.0,              # NHL
    "default": 48.0                     # Fallback for unknown sports
}

# Live markets require much fresher odds
LIVE_MARKET_MAX_AGE_MINUTES = 10

# Critical staleness threshold - beyond this, we should attempt auto-refresh
# This is shorter than MAX_ODDS_AGE to trigger refresh before hitting max age
AUTO_REFRESH_TRIGGER_HOURS: Dict[str, float] = {
    "americanfootball_nfl": 48.0,
    "americanfootball_ncaaf": 48.0,
    "basketball_nba": 12.0,
    "basketball_ncaab": 18.0,
    "baseball_mlb": 24.0,
    "icehockey_nhl": 24.0,
    "default": 24.0
}

# Sport-specific line validity ranges (structural validation)
LINE_VALIDITY_RANGES = {
    "americanfootball_nfl": {"min": 30.0, "max": 70.0},
    "americanfootball_ncaaf": {"min": 35.0, "max": 85.0},
    "basketball_nba": {"min": 180.0, "max": 260.0},
    "basketball_ncaab": {"min": 110.0, "max": 180.0},
    "baseball_mlb": {"min": 5.0, "max": 14.0},
    "icehockey_nhl": {"min": 4.0, "max": 9.0}
}


def get_max_odds_age(sport_key: str) -> timedelta:
    """Get maximum acceptable odds age for a sport"""
    hours = MAX_ODDS_AGE_HOURS.get(sport_key, MAX_ODDS_AGE_HOURS["default"])
    return timedelta(hours=hours)


def get_auto_refresh_trigger(sport_key: str) -> timedelta:
    """Get age threshold that triggers automatic odds refresh"""
    hours = AUTO_REFRESH_TRIGGER_HOURS.get(sport_key, AUTO_REFRESH_TRIGGER_HOURS["default"])
    return timedelta(hours=hours)


def should_auto_refresh(sport_key: str, odds_age: timedelta) -> bool:
    """Determine if odds age warrants an automatic refresh attempt"""
    trigger = get_auto_refresh_trigger(sport_key)
    return odds_age >= trigger
