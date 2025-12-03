"""
PHASE 15: Sport-Specific Constants and Position Maps

Defines position groupings for player props organization by sport.
Prevents showing "Guards" for NFL games or "Quarterbacks" for NBA games.
"""

from typing import Dict, List

# Sport-specific position groupings
POSITION_MAPS: Dict[str, List[str]] = {
    # Basketball (NBA)
    "basketball_nba": ["Guard", "Forward", "Center"],
    "basketball_ncaab": ["Guard", "Forward", "Center"],  # NCAA Basketball
    
    # American Football (NFL)
    "americanfootball_nfl": ["Quarterback", "Running Back", "Wide Receiver", "Tight End"],
    "americanfootball_ncaaf": ["Quarterback", "Running Back", "Wide Receiver", "Tight End"],  # NCAA Football
    
    # Baseball (MLB)
    "baseball_mlb": ["Pitcher", "Batter"],
    
    # Ice Hockey (NHL)
    "icehockey_nhl": ["Center", "Winger", "Defenseman", "Goalie"]
}

# Detailed position abbreviations for data mapping
POSITION_ABBREVIATIONS: Dict[str, Dict[str, str]] = {
    "basketball_nba": {
        "PG": "Guard",
        "SG": "Guard",
        "SF": "Forward",
        "PF": "Forward",
        "C": "Center"
    },
    "basketball_ncaab": {  # NCAA Basketball
        "PG": "Guard",
        "SG": "Guard",
        "SF": "Forward",
        "PF": "Forward",
        "C": "Center"
    },
    "americanfootball_nfl": {
        "QB": "Quarterback",
        "RB": "Running Back",
        "WR": "Wide Receiver",
        "TE": "Tight End",
        "FB": "Running Back",  # Fullback maps to RB
        "K": "Kicker",
        "P": "Punter"
    },
    "americanfootball_ncaaf": {  # NCAA Football
        "QB": "Quarterback",
        "RB": "Running Back",
        "WR": "Wide Receiver",
        "TE": "Tight End",
        "FB": "Running Back",
        "K": "Kicker",
        "P": "Punter"
    },
    "baseball_mlb": {
        "SP": "Pitcher",
        "RP": "Pitcher",
        "1B": "Batter",
        "2B": "Batter",
        "3B": "Batter",
        "SS": "Batter",
        "OF": "Batter",
        "C": "Batter",  # Catcher is a batter
        "DH": "Batter"
    },
    "icehockey_nhl": {
        "C": "Center",
        "LW": "Winger",
        "RW": "Winger",
        "D": "Defenseman",
        "G": "Goalie"
    }
}

# Prop markets by sport (for validation)
PROP_TYPES: Dict[str, List[str]] = {
    "basketball_nba": [
        "Points",
        "Rebounds",
        "Assists",
        "Threes Made",
        "Steals",
        "Blocks",
        "Turnovers",
        "Points + Rebounds + Assists"
    ],
    "basketball_ncaab": [  # NCAA Basketball
        "Points",
        "Rebounds",
        "Assists",
        "Threes Made",
        "Steals",
        "Blocks",
        "Turnovers",
        "Points + Rebounds + Assists"
    ],
    "americanfootball_nfl": [
        "Passing Yards",
        "Passing Touchdowns",
        "Interceptions",
        "Rushing Yards",
        "Rushing Touchdowns",
        "Receptions",
        "Receiving Yards",
        "Receiving Touchdowns"
    ],
    "americanfootball_ncaaf": [  # NCAA Football
        "Passing Yards",
        "Passing Touchdowns",
        "Interceptions",
        "Rushing Yards",
        "Rushing Touchdowns",
        "Receptions",
        "Receiving Yards",
        "Receiving Touchdowns"
    ],
    "baseball_mlb": [
        "Hits",
        "Home Runs",
        "RBIs",
        "Strikeouts",
        "Walks",
        "Total Bases",
        "Pitcher Strikeouts",
        "Earned Runs"
    ],
    "icehockey_nhl": [
        "Goals",
        "Assists",
        "Points",
        "Shots on Goal",
        "Saves",
        "Goals Against"
    ]
}

# Sport display names
SPORT_DISPLAY_NAMES: Dict[str, str] = {
    "basketball_nba": "NBA",
    "basketball_ncaab": "NCAAB",
    "americanfootball_nfl": "NFL",
    "americanfootball_ncaaf": "NCAAF",
    "baseball_mlb": "MLB",
    "icehockey_nhl": "NHL"
}

# PHASE 15: First Half (1H) Simulation Constants

# Game duration in minutes (regulation time)
GAME_DURATION_MINUTES: Dict[str, int] = {
    "basketball_nba": 48,  # 4 x 12 minute quarters
    "basketball_ncaab": 40,  # 2 x 20 minute halves
    "americanfootball_nfl": 60,  # 4 x 15 minute quarters
    "americanfootball_ncaaf": 60,  # 4 x 15 minute quarters
    "baseball_mlb": 0,  # No time limit (innings-based)
    "icehockey_nhl": 60  # 3 x 20 minute periods
}

# First half duration ratio (0.5 = 50% of game time)
FIRST_HALF_RATIO: Dict[str, float] = {
    "basketball_nba": 0.5,  # 24 minutes (2 quarters)
    "basketball_ncaab": 0.5,  # 20 minutes (1 half)
    "americanfootball_nfl": 0.5,  # 30 minutes (2 quarters)
    "americanfootball_ncaaf": 0.5,  # 30 minutes (2 quarters)
    "baseball_mlb": 0.555,  # ~5 innings (not exactly 50%)
    "icehockey_nhl": 0.5  # 30 minutes (1.5 periods)
}

# Early game tempo multipliers (1H pace is typically faster)
EARLY_GAME_TEMPO: Dict[str, float] = {
    "basketball_nba": 1.03,  # 3% faster pace in 1H
    "basketball_ncaab": 1.04,  # 4% faster pace in 1H (more variable than NBA)
    "americanfootball_nfl": 1.02,  # 2% faster pace in 1H
    "americanfootball_ncaaf": 1.03,  # 3% faster pace in 1H (more aggressive than NFL)
    "baseball_mlb": 1.0,  # No tempo effect
    "icehockey_nhl": 1.04  # 4% faster pace in 1st period
}

# Starter impact multiplier for 1H (starters play more minutes in first half)
STARTER_FIRST_HALF_BOOST: Dict[str, float] = {
    "basketball_nba": 1.20,  # +20% starter minutes in 1H
    "basketball_ncaab": 1.25,  # +25% starter minutes in 1H (less depth than NBA)
    "americanfootball_nfl": 1.15,  # +15% starter snaps in 1H
    "americanfootball_ncaaf": 1.18,  # +18% starter snaps in 1H (less depth than NFL)
    "baseball_mlb": 1.10,  # +10% starter plate appearances in 1H
    "icehockey_nhl": 1.18  # +18% starter ice time in 1H
}


def get_position_groups(sport_key: str) -> List[str]:
    """
    Get position groupings for a sport.
    
    Args:
        sport_key: Sport identifier (e.g., 'basketball_nba')
    
    Returns:
        List of position group names
    
    Example:
        >>> get_position_groups('basketball_nba')
        ['Guard', 'Forward', 'Center']
        >>> get_position_groups('americanfootball_nfl')
        ['Quarterback', 'Running Back', 'Wide Receiver', 'Tight End']
    """
    return POSITION_MAPS.get(sport_key, ["Player"])


def map_position_abbreviation(sport_key: str, position_abbr: str) -> str:
    """
    Map position abbreviation to display group.
    
    Args:
        sport_key: Sport identifier
        position_abbr: Position abbreviation (e.g., 'PG', 'QB')
    
    Returns:
        Position group name (e.g., 'Guard', 'Quarterback')
    
    Example:
        >>> map_position_abbreviation('basketball_nba', 'PG')
        'Guard'
        >>> map_position_abbreviation('americanfootball_nfl', 'QB')
        'Quarterback'
    """
    sport_positions = POSITION_ABBREVIATIONS.get(sport_key, {})
    return sport_positions.get(position_abbr, "Player")


def get_prop_markets_for_sport(sport_key: str) -> List[str]:
    """
    Get valid prop markets for a sport.
    
    Args:
        sport_key: Sport identifier
    
    Returns:
        List of prop market names
    """
    return PROP_TYPES.get(sport_key, [])


def get_sport_display_name(sport_key: str) -> str:
    """
    Get human-readable sport name.
    
    Args:
        sport_key: Sport identifier
    
    Returns:
        Display name (e.g., 'NBA', 'NFL')
    """
    return SPORT_DISPLAY_NAMES.get(sport_key, sport_key.upper())


# PHASE 15: 1H Simulation Helper Functions

def get_game_duration(sport_key: str) -> int:
    """Get regulation game duration in minutes."""
    return GAME_DURATION_MINUTES.get(sport_key, 60)


def get_first_half_ratio(sport_key: str) -> float:
    """Get the ratio of 1H time to full game time."""
    return FIRST_HALF_RATIO.get(sport_key, 0.5)


def get_early_tempo_multiplier(sport_key: str) -> float:
    """Get the early game tempo multiplier for 1H sims."""
    return EARLY_GAME_TEMPO.get(sport_key, 1.0)


def get_starter_boost_multiplier(sport_key: str) -> float:
    """Get the starter impact boost for first half."""
    return STARTER_FIRST_HALF_BOOST.get(sport_key, 1.0)
