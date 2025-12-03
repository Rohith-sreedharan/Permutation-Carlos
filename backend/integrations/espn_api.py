"""
ESPN API Integration - Free Sports Data
Source: https://scrapecreators.com/blog/espn-api-free-sports-data

Provides real player rosters and stats for:
- NBA: Player rosters, stats, injury data
- NFL: Player rosters, stats, injury data
- MLB: Player rosters, stats
- NHL: Player rosters, stats

NO API KEY REQUIRED - Free public endpoints
"""

import requests
from typing import Dict, List, Any, Optional
import logging

logger = logging.getLogger(__name__)

# ESPN API Base URLs
ESPN_BASE_URL = "https://site.api.espn.com/apis/site/v2/sports"


class ESPNApiError(Exception):
    """ESPN API error"""
    pass


def fetch_nba_teams() -> List[Dict[str, Any]]:
    """
    Fetch all NBA teams from ESPN API
    
    Returns:
        List of team objects with id, name, abbreviation, etc.
    """
    url = f"{ESPN_BASE_URL}/basketball/nba/teams"
    
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        teams = []
        for sport in data.get("sports", []):
            for league in sport.get("leagues", []):
                for team in league.get("teams", []):
                    team_data = team.get("team", {})
                    teams.append({
                        "id": team_data.get("id"),
                        "name": team_data.get("displayName"),
                        "abbreviation": team_data.get("abbreviation"),
                        "location": team_data.get("location"),
                        "nickname": team_data.get("name"),
                        "logo": team_data.get("logos", [{}])[0].get("href") if team_data.get("logos") else None
                    })
        
        logger.info(f"Fetched {len(teams)} NBA teams from ESPN")
        return teams
        
    except Exception as e:
        logger.error(f"Error fetching NBA teams: {e}")
        return []


def fetch_nba_roster(team_id: str) -> List[Dict[str, Any]]:
    """
    Fetch NBA team roster from ESPN API
    
    Args:
        team_id: ESPN team ID (e.g., "5" for Boston Celtics)
    
    Returns:
        List of player objects with stats
    """
    url = f"{ESPN_BASE_URL}/basketball/nba/teams/{team_id}/roster"
    
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        players = []
        for athlete in data.get("athletes", []):
            player_data = athlete.get("athlete", athlete)
            
            # Extract player info
            player = {
                "id": player_data.get("id"),
                "name": player_data.get("displayName"),
                "first_name": player_data.get("firstName"),
                "last_name": player_data.get("lastName"),
                "jersey": player_data.get("jersey"),
                "position": player_data.get("position", {}).get("abbreviation"),
                "position_name": player_data.get("position", {}).get("displayName"),
                "height": player_data.get("displayHeight"),
                "weight": player_data.get("displayWeight"),
                "age": player_data.get("age"),
                "status": athlete.get("status", {}).get("name", "ACTIVE"),  # ACTIVE, OUT, QUESTIONABLE
                "injury": athlete.get("injuries", [{}])[0] if athlete.get("injuries") else None,
                "headshot": player_data.get("headshot", {}).get("href"),
                "experience": player_data.get("experience", {}).get("years", 0),
            }
            
            players.append(player)
        
        logger.info(f"Fetched {len(players)} players for team {team_id}")
        return players
        
    except Exception as e:
        logger.error(f"Error fetching roster for team {team_id}: {e}")
        return []


def fetch_nfl_teams() -> List[Dict[str, Any]]:
    """Fetch all NFL teams from ESPN API"""
    url = f"{ESPN_BASE_URL}/football/nfl/teams"
    
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        teams = []
        for sport in data.get("sports", []):
            for league in sport.get("leagues", []):
                for team in league.get("teams", []):
                    team_data = team.get("team", {})
                    teams.append({
                        "id": team_data.get("id"),
                        "name": team_data.get("displayName"),
                        "abbreviation": team_data.get("abbreviation"),
                        "location": team_data.get("location"),
                        "nickname": team_data.get("name"),
                        "logo": team_data.get("logos", [{}])[0].get("href") if team_data.get("logos") else None
                    })
        
        logger.info(f"Fetched {len(teams)} NFL teams from ESPN")
        return teams
        
    except Exception as e:
        logger.error(f"Error fetching NFL teams: {e}")
        return []


def fetch_nfl_roster(team_id: str) -> List[Dict[str, Any]]:
    """
    Fetch NFL team roster from ESPN API
    
    Args:
        team_id: ESPN team ID (e.g., "22" for Arizona Cardinals)
    
    Returns:
        List of player objects
    """
    url = f"{ESPN_BASE_URL}/football/nfl/teams/{team_id}/roster"
    
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        players = []
        
        # NFL roster is grouped by position category (offense, defense, special teams)
        for group in data.get("athletes", []):
            position_category = group.get("position")  # "offense", "defense", etc.
            
            for player_data in group.get("items", []):
                # Get position info
                position_info = player_data.get("position")
                if isinstance(position_info, dict):
                    position_abbr = position_info.get("abbreviation")
                    position_name = position_info.get("name")
                elif isinstance(position_info, str):
                    position_abbr = position_info
                    position_name = position_info
                else:
                    position_abbr = None
                    position_name = None
                
                # Get status
                status_info = player_data.get("status")
                if isinstance(status_info, dict):
                    status = status_info.get("name", "ACTIVE")
                else:
                    status = "ACTIVE"
                
                # Get headshot
                headshot = None
                if player_data.get("headshot"):
                    if isinstance(player_data["headshot"], dict):
                        headshot = player_data["headshot"].get("href")
                    elif isinstance(player_data["headshot"], str):
                        headshot = player_data["headshot"]
                
                player = {
                    "id": player_data.get("id"),
                    "name": player_data.get("displayName"),
                    "first_name": player_data.get("firstName"),
                    "last_name": player_data.get("lastName"),
                    "jersey": player_data.get("jersey"),
                    "position": position_abbr,
                    "position_name": position_name,
                    "position_category": position_category,  # offense/defense/special
                    "height": player_data.get("displayHeight"),
                    "weight": player_data.get("displayWeight"),
                    "age": player_data.get("age"),
                    "status": status,
                    "injury": player_data.get("injuries", [{}])[0] if player_data.get("injuries") else None,
                    "headshot": headshot,
                    "experience": player_data.get("experience", {}).get("years", 0) if isinstance(player_data.get("experience"), dict) else 0,
                }
                
                players.append(player)
        
        logger.info(f"Fetched {len(players)} players for NFL team {team_id}")
        return players
        
    except Exception as e:
        logger.error(f"Error fetching NFL roster for team {team_id}: {e}")
        return []


def get_espn_team_id_from_name(team_name: str, sport: str = "nba") -> Optional[str]:
    """
    Map team name to ESPN team ID
    
    Args:
        team_name: Team name (e.g., "Boston Celtics", "Arizona Cardinals")
        sport: "nba" or "nfl"
    
    Returns:
        ESPN team ID or None
    """
    if sport.lower() == "nba":
        teams = fetch_nba_teams()
    elif sport.lower() == "nfl":
        teams = fetch_nfl_teams()
    else:
        return None
    
    # Try exact match first
    for team in teams:
        if team["name"].lower() == team_name.lower():
            return team["id"]
    
    # Try partial match
    team_name_lower = team_name.lower()
    for team in teams:
        if team_name_lower in team["name"].lower() or team["name"].lower() in team_name_lower:
            return team["id"]
    
    return None


def fetch_player_stats(player_id: str, sport: str = "nba") -> Dict[str, Any]:
    """
    Fetch player statistics from ESPN
    
    Args:
        player_id: ESPN player ID
        sport: "nba", "nfl", etc.
    
    Returns:
        Player stats dict
    """
    if sport.lower() == "nba":
        url = f"{ESPN_BASE_URL}/basketball/nba/athletes/{player_id}/statistics"
    elif sport.lower() == "nfl":
        url = f"{ESPN_BASE_URL}/football/nfl/athletes/{player_id}/statistics"
    else:
        return {}
    
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        # Extract season stats
        stats = {}
        for split in data.get("splits", {}).get("categories", []):
            category_name = split.get("name")
            for stat in split.get("stats", []):
                stats[stat.get("name")] = stat.get("value")
        
        return stats
        
    except Exception as e:
        logger.error(f"Error fetching stats for player {player_id}: {e}")
        return {}


# Team name to ESPN ID mappings (cached for performance)
NBA_TEAM_IDS = {
    "Boston Celtics": "2",
    "Brooklyn Nets": "17",
    "New York Knicks": "18",
    "Philadelphia 76ers": "20",
    "Toronto Raptors": "28",
    "Chicago Bulls": "4",
    "Cleveland Cavaliers": "5",
    "Detroit Pistons": "8",
    "Indiana Pacers": "11",
    "Milwaukee Bucks": "15",
    "Atlanta Hawks": "1",
    "Charlotte Hornets": "30",
    "Miami Heat": "14",
    "Orlando Magic": "19",
    "Washington Wizards": "27",
    "Denver Nuggets": "7",
    "Minnesota Timberwolves": "16",
    "Oklahoma City Thunder": "25",
    "Portland Trail Blazers": "22",
    "Utah Jazz": "26",
    "Golden State Warriors": "9",
    "LA Clippers": "12",
    "Los Angeles Lakers": "13",
    "Phoenix Suns": "21",
    "Sacramento Kings": "23",
    "Dallas Mavericks": "6",
    "Houston Rockets": "10",
    "Memphis Grizzlies": "29",
    "New Orleans Pelicans": "3",
    "San Antonio Spurs": "24",
}

NFL_TEAM_IDS = {
    "Arizona Cardinals": "22",
    "Atlanta Falcons": "1",
    "Baltimore Ravens": "33",
    "Buffalo Bills": "2",
    "Carolina Panthers": "29",
    "Chicago Bears": "3",
    "Cincinnati Bengals": "4",
    "Cleveland Browns": "5",
    "Dallas Cowboys": "6",
    "Denver Broncos": "7",
    "Detroit Lions": "8",
    "Green Bay Packers": "9",
    "Houston Texans": "34",
    "Indianapolis Colts": "11",
    "Jacksonville Jaguars": "30",
    "Kansas City Chiefs": "12",
    "Las Vegas Raiders": "13",
    "Los Angeles Chargers": "24",
    "Los Angeles Rams": "14",
    "Miami Dolphins": "15",
    "Minnesota Vikings": "16",
    "New England Patriots": "17",
    "New Orleans Saints": "18",
    "New York Giants": "19",
    "New York Jets": "20",
    "Philadelphia Eagles": "21",
    "Pittsburgh Steelers": "23",
    "San Francisco 49ers": "25",
    "Seattle Seahawks": "26",
    "Tampa Bay Buccaneers": "27",
    "Tennessee Titans": "10",
    "Washington Commanders": "28",
}
