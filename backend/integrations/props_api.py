"""
Player Props API Integration - The Odds API
Fetches REAL player props from DraftKings, FanDuel, BetMGM, Caesars

Markets available:
- player_pass_tds: Passing touchdowns
- player_pass_yds: Passing yards  
- player_rush_yds: Rushing yards
- player_receptions: Receptions
- player_receiving_yds: Receiving yards (when available)

Source: https://the-odds-api.com/liveapi/guides/v4/#get-odds
"""

import os
import requests
from typing import Dict, List, Any, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

API_KEY = os.getenv("ODDS_API_KEY")
BASE_URL = os.getenv("ODDS_BASE_URL", "https://api.the-odds-api.com/v4")

# Priority sportsbooks (in order of reliability)
PRIORITY_BOOKS = ["draftkings", "fanduel", "betmgm", "williamhill_us"]  # williamhill_us is Caesars

# Map Odds API market keys to display names
MARKET_NAMES = {
    "player_pass_yds": "Passing Yards",
    "player_rush_yds": "Rushing Yards",
    "player_receptions": "Receptions",
    "player_pass_tds": "Passing TDs",
    "player_receiving_yds": "Receiving Yards"
}


class PropsApiError(Exception):
    """Props API error"""
    pass


def fetch_event_props(event_id: str, sport_key: str = "americanfootball_nfl") -> Dict[str, Any]:
    """
    Fetch player props for a specific event
    
    Args:
        event_id: The Odds API event ID
        sport_key: Sport key (americanfootball_nfl, basketball_nba)
    
    Returns:
        Dict with props organized by player and market
    """
    if not API_KEY:
        raise PropsApiError("ODDS_API_KEY not set")
    
    # Determine markets based on sport
    if "basketball" in sport_key:
        markets = "player_points,player_rebounds,player_assists,player_threes"
    elif "football" in sport_key:
        markets = "player_pass_yds,player_rush_yds,player_receptions,player_pass_tds"
    else:
        markets = "player_points"
    
    url = f"{BASE_URL}/sports/{sport_key}/events/{event_id}/odds"
    params = {
        "apiKey": API_KEY,
        "regions": "us",
        "markets": markets,
        "oddsFormat": "american"
    }
    
    try:
        response = requests.get(url, params=params, timeout=15)
        
        if response.status_code == 404:
            logger.warning(f"No props available for event {event_id}")
            return {"bookmakers": [], "props_count": 0}
        
        if response.status_code != 200:
            raise PropsApiError(f"API error {response.status_code}: {response.text}")
        
        data = response.json()
        logger.info(f"✅ Fetched props for event {event_id}: {len(data.get('bookmakers', []))} bookmakers")
        
        return data
        
    except requests.exceptions.RequestException as e:
        raise PropsApiError(f"Request failed: {e}")


def normalize_props(event_props: Dict[str, Any], home_team: str, away_team: str) -> List[Dict[str, Any]]:
    """
    Normalize props from multiple bookmakers into unified format
    
    Args:
        event_props: Raw event props from Odds API
        home_team: Home team name
        away_team: Away team name
    
    Returns:
        List of normalized props with multi-book validation
    """
    # Group props by (player, market, line)
    props_by_key = {}
    
    for bookmaker in event_props.get("bookmakers", []):
        book_key = bookmaker["key"]
        book_name = bookmaker["title"]
        
        # Skip non-priority books for now (focus on majors)
        if book_key not in PRIORITY_BOOKS:
            continue
        
        for market in bookmaker.get("markets", []):
            market_key = market["key"]
            market_name = MARKET_NAMES.get(market_key, market_key)
            
            # Group outcomes by player
            player_props = {}
            for outcome in market.get("outcomes", []):
                player_name = outcome.get("description")
                if not player_name:
                    continue
                
                if player_name not in player_props:
                    player_props[player_name] = {
                        "over": None,
                        "under": None,
                        "line": outcome.get("point")
                    }
                
                if outcome.get("name") == "Over":
                    player_props[player_name]["over"] = outcome.get("price")
                elif outcome.get("name") == "Under":
                    player_props[player_name]["under"] = outcome.get("price")
            
            # Add to grouped props
            for player_name, prop_data in player_props.items():
                line = prop_data["line"]
                key = (player_name, market_key, line)
                
                if key not in props_by_key:
                    props_by_key[key] = {
                        "player_name": player_name,
                        "market": market_key,
                        "market_name": market_name,
                        "line": line,
                        "books": []
                    }
                
                props_by_key[key]["books"].append({
                    "book_key": book_key,
                    "book_name": book_name,
                    "over_price": prop_data["over"],
                    "under_price": prop_data["under"]
                })
    
    # Convert to list and filter
    normalized_props = []
    
    for prop_data in props_by_key.values():
        # Require at least 2 books for validation (multi-book consensus)
        if len(prop_data["books"]) < 2:
            continue
        
        # Calculate edge (simple no-vig calculation)
        best_over = max((b["over_price"] for b in prop_data["books"] if b["over_price"]), default=None)
        best_under = max((b["under_price"] for b in prop_data["books"] if b["under_price"]), default=None)
        
        if best_over and best_under:
            # Convert American odds to implied probability
            over_prob = american_to_prob(best_over)
            under_prob = american_to_prob(best_under)
            
            # Calculate no-vig fair probability
            total_prob = over_prob + under_prob
            fair_over_prob = over_prob / total_prob if total_prob > 0 else 0.5
            fair_under_prob = under_prob / total_prob if total_prob > 0 else 0.5
            
            # Edge = our projection vs fair probability (placeholder for now)
            # TODO: Calculate actual projection from Monte Carlo
            prop_data["best_over_odds"] = best_over
            prop_data["best_under_odds"] = best_under
            prop_data["fair_over_prob"] = round(fair_over_prob, 4)
            prop_data["fair_under_prob"] = round(fair_under_prob, 4)
            prop_data["book_count"] = len(prop_data["books"])
        
        normalized_props.append(prop_data)
    
    logger.info(f"✅ Normalized {len(normalized_props)} multi-book validated props")
    return normalized_props


def american_to_prob(american_odds: int) -> float:
    """Convert American odds to implied probability"""
    if american_odds > 0:
        return 100 / (american_odds + 100)
    else:
        return abs(american_odds) / (abs(american_odds) + 100)


def prob_to_american(prob: float) -> int:
    """Convert probability to American odds"""
    if prob >= 0.5:
        return int(-100 * prob / (1 - prob))
    else:
        return int(100 * (1 - prob) / prob)


def calculate_prop_edge(prop: Dict[str, Any], model_projection: Optional[float] = None) -> Dict[str, Any]:
    """
    Calculate edge for a prop based on model projection.
    Currently disabled - returns props with market data only.
    Edge calculation requires Monte Carlo simulation integration.
    
    Args:
        prop: Normalized prop data
        model_projection: Model's projection for this stat (optional, unused)
    
    Returns:
        Prop with market data (edge calculation disabled)
    """
    # Edge calculation requires full Monte Carlo integration
    # For now, return props with fair probabilities only
    prop["edge"] = 0.0
    prop["ev_percent"] = 0.0
    prop["recommendation"] = "HOLD"  # No recommendation without model
    
    return prop
