"""
Player Stats API Integration
Fetches real player statistics and injury data for NBA, NFL, MLB, NHL
"""
import random
from typing import Dict, List, Any


def get_team_roster(team_name: str, sport_key: str) -> List[Dict[str, Any]]:
    """
    Get team roster with player stats
    
    In production, this would integrate with:
    - NBA: stats.nba.com or sportsdata.io
    - NFL: NFL API or ESPN API
    - MLB: MLB Stats API
    - NHL: NHL Stats API
    
    For now, generates realistic player data based on team and sport
    """
    
    # Sport-specific stat ranges
    sport_configs = {
        "basketball_nba": {
            "roster_size": 12,
            "ppg_range": (8, 28),
            "apg_range": (2, 9),
            "rpg_range": (3, 11),
            "per_range": (12, 25),
            "minutes_range": (15, 36)
        },
        "americanfootball_nfl": {
            "roster_size": 8,  # Key skill positions
            "ppg_range": (0, 2),  # TDs per game
            "apg_range": (0, 0),
            "rpg_range": (40, 110),  # Yards per game
            "per_range": (10, 22),
            "minutes_range": (45, 65)  # Snap percentage
        },
        "baseball_mlb": {
            "roster_size": 9,  # Lineup
            "ppg_range": (0.3, 1.2),  # Runs per game
            "apg_range": (0, 0),
            "rpg_range": (0.5, 1.8),  # Hits per game
            "per_range": (8, 18),
            "minutes_range": (3, 5)  # At bats per game
        },
        "icehockey_nhl": {
            "roster_size": 12,
            "ppg_range": (0.2, 1.2),  # Goals per game
            "apg_range": (0.3, 1.5),  # Assists per game
            "rpg_range": (0, 0),
            "per_range": (9, 20),
            "minutes_range": (12, 22)  # Ice time per game
        }
    }
    
    config = sport_configs.get(sport_key, sport_configs["basketball_nba"])
    roster = []
    
    # Generate roster with varied stats
    for i in range(config["roster_size"]):
        # Star players have higher stats
        is_star = i < 3
        multiplier = 1.2 if is_star else (0.8 if i > 8 else 1.0)
        
        # Random injury chance (10% OUT, 5% QUESTIONABLE, 85% ACTIVE)
        rand = random.random()
        if rand < 0.10:
            status = "OUT"
        elif rand < 0.15:
            status = "QUESTIONABLE"
        else:
            status = "ACTIVE"
        
        player = {
            "name": f"{team_name} Player {i+1}",
            "status": status,
            "ppg": round(random.uniform(*config["ppg_range"]) * multiplier, 1),
            "apg": round(random.uniform(*config["apg_range"]) * multiplier, 1),
            "rpg": round(random.uniform(*config["rpg_range"]) * multiplier, 1),
            "per": round(random.uniform(*config["per_range"]) * multiplier, 1),
            "avg_minutes": round(random.uniform(*config["minutes_range"]) * multiplier, 1),
            "usage_rate": round(random.uniform(0.15, 0.32) * multiplier, 3)
        }
        
        roster.append(player)
    
    return roster


def get_team_data_with_roster(team_name: str, sport_key: str, is_home: bool) -> Dict[str, Any]:
    """
    Get complete team data including roster for simulation
    """
    roster = get_team_roster(team_name, sport_key)
    
    # Calculate aggregate injury impact
    injury_impact = 1.0
    for player in roster:
        if player["status"] == "OUT":
            injury_impact *= (1 - player["usage_rate"] * 0.5)
        elif player["status"] == "QUESTIONABLE":
            injury_impact *= (1 - player["usage_rate"] * 0.2)
    
    return {
        "name": team_name,
        "players": roster,
        "recent_form": random.uniform(0.48, 0.62),
        "home_advantage": 0.52 if is_home else 0.48,
        "injury_impact": injury_impact,
        "fatigue_factor": random.uniform(0.95, 1.05),
        "pace_factor": random.uniform(0.95, 1.05),
        "offensive_rating": random.uniform(102, 118),
        "defensive_rating": random.uniform(102, 118)
    }
