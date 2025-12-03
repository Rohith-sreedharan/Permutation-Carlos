"""
Injury Data Integration
Fetches real injury reports from ESPN and CollegeFootballData
"""
import requests
from typing import Dict, List, Any, Optional
from bs4 import BeautifulSoup
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

# ESPN Injury Report URLs
ESPN_INJURY_URLS = {
    "nfl": "https://www.espn.com/nfl/injuries",
    "nba": "https://www.espn.com/nba/injuries",
    "mlb": "https://www.espn.com/mlb/injuries",
    "nhl": "https://www.espn.com/nhl/injuries",
    # NCAAF: ESPN doesn't have a clean injuries page - 404 errors
    # NCAAB: Using mens-college-basketball path
    "ncaab": "https://www.espn.com/mens-college-basketball/injuries"
}

# CollegeFootballData API
CFB_BASE_URL = "https://api.collegefootballdata.com"
CFB_API_KEY = None  # Set in .env file if available (free tier: 1000 req/day)
CFB_API_KEY = None  # Set in .env file if available (free tier: 1000 req/day)


def fetch_espn_injuries(sport_key: str) -> List[Dict[str, Any]]:
    """
    Scrape injury reports from ESPN
    
    Args:
        sport_key: Sport identifier (basketball_nba, americanfootball_nfl, etc.)
    
    Returns:
        List of injury data:
        [{
            "player_name": "Jaylen Brown",
            "team": "Boston Celtics",
            "position": "SG",
            "injury": "Hip",
            "status": "Out",
            "date_updated": "2025-11-30"
        }]
    """
    # Map sport_key to ESPN injury page
    sport_map = {
        "basketball_nba": "nba",
        "americanfootball_nfl": "nfl",
        "baseball_mlb": "mlb",
        "icehockey_nhl": "nhl",
        "americanfootball_ncaaf": "ncaaf",
        "basketball_ncaab": "ncaab"
    }
    
    espn_sport = sport_map.get(sport_key)
    if not espn_sport:
        logger.warning(f"No ESPN injury page for sport: {sport_key}")
        return []
    
    url = ESPN_INJURY_URLS.get(espn_sport)
    if not url:
        return []
    
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        }
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        injuries = []
        
        # ESPN injury table structure:
        # <div class="ResponsiveTable">
        #   <table class="Table">
        #     <tbody class="Table__TBODY">
        #       <tr class="Table__TR">
        #         <td> Player Name </td>
        #         <td> Position </td>
        #         <td> Injury </td>
        #         <td> Status </td>
        #         <td> Comment </td>
        
        # Find all injury tables (one per team)
        tables = soup.find_all('div', class_='ResponsiveTable')
        
        for table_wrapper in tables:
            # Get team name from header - ESPN structure: <div class="Table__Title">Team Name</div>
            team_name = "Unknown"
            
            # Try multiple selectors for team name
            # 1. Look for parent section with team info
            parent_section = table_wrapper.find_parent('section') or table_wrapper.find_parent('div', class_='mb5')
            if parent_section:
                team_title = parent_section.find('div', class_='Table__Title')
                if team_title:
                    team_name = team_title.get_text(strip=True)
            
            # 2. Look for preceding header
            if team_name == "Unknown":
                team_header = table_wrapper.find_previous_sibling('div', class_='Table__Title')
                if not team_header:
                    team_header = table_wrapper.find_previous('div', class_='Table__Title')
                if team_header:
                    team_name = team_header.get_text(strip=True)
            
            # 3. Look for h2 or h3 with team name
            if team_name == "Unknown":
                team_header = table_wrapper.find_previous(['h2', 'h3'])
                if team_header:
                    team_name = team_header.get_text(strip=True)
            
            # Clean team name (remove extra text)
            team_name = team_name.replace(' Injuries', '').replace('Injuries', '').strip()
            
            # Skip if we couldn't find team name
            if team_name == "Unknown" or not team_name:
                logger.warning(f"Could not parse team name for injury table, skipping")
                continue
            
            # Parse table rows
            table = table_wrapper.find('table')
            if not table:
                continue
            
            tbody = table.find('tbody')
            if not tbody:
                continue
            
            rows = tbody.find_all('tr', class_='Table__TR')
            
            for row in rows:
                cols = row.find_all('td')
                if len(cols) < 4:
                    continue
                
                player_cell = cols[0]
                position_cell = cols[1] if len(cols) > 1 else None
                injury_cell = cols[2] if len(cols) > 2 else None
                status_cell = cols[3] if len(cols) > 3 else None
                
                # Extract player name
                player_link = player_cell.find('a')
                player_name = player_link.get_text(strip=True) if player_link else player_cell.get_text(strip=True)
                
                # Extract position
                position = position_cell.get_text(strip=True) if position_cell else "Unknown"
                
                # Extract injury description
                injury_desc = injury_cell.get_text(strip=True) if injury_cell else "Undisclosed"
                
                # Extract status (Out, Questionable, Doubtful, Day-To-Day)
                status = status_cell.get_text(strip=True) if status_cell else "Unknown"
                
                injuries.append({
                    "player_name": player_name,
                    "team": team_name,
                    "position": position,
                    "injury": injury_desc,
                    "status": status,
                    "date_updated": datetime.now().strftime("%Y-%m-%d"),
                    "source": "ESPN"
                })
        
        logger.info(f"✅ Scraped {len(injuries)} injuries from ESPN {espn_sport.upper()}")
        return injuries
    
    except Exception as e:
        logger.error(f"❌ Failed to scrape ESPN injuries for {sport_key}: {e}")
        return []


def fetch_cfb_injuries(team: Optional[str] = None, year: int = 2025) -> List[Dict[str, Any]]:
    """
    Fetch NCAAF injuries from CollegeFootballData API
    
    Args:
        team: Team name (optional filter)
        year: Season year (default: 2025)
    
    Returns:
        List of injury data from CFB API
    """
    try:
        # Roster endpoint includes injury status
        url = f"{CFB_BASE_URL}/roster"
        params: Dict[str, Any] = {"year": year}
        if team:
            params["team"] = team
        
        headers = {
            'User-Agent': 'Permutation-Carlos/1.0'
        }
        
        # Add API key if available (get from environment)
        import os
        cfb_key = os.getenv('CFB_API_KEY') or CFB_API_KEY
        if not cfb_key:
            logger.error("❌ CFB_API_KEY not configured. Get your free API key from https://collegefootballdata.com/key")
            raise ValueError("CFB_API_KEY required for CollegeFootballData API. Sign up at https://collegefootballdata.com/")
        
        headers['Authorization'] = f'Bearer {cfb_key}'
        
        response = requests.get(url, params=params, headers=headers, timeout=10)
        response.raise_for_status()
        
        roster_data = response.json()
        injuries = []
        
        # Parse roster for injury tags
        for player in roster_data:
            # CFB API doesn't have explicit injury endpoint
            # But roster includes status indicators
            if not isinstance(player, dict):
                continue
            
            player_name = player.get("first_name", "") + " " + player.get("last_name", "")
            team_name = player.get("team", "Unknown")
            position = player.get("position", "Unknown")
            
            # Note: CFB API limited on injury details
            # Use ESPN scraping as primary for NCAAF injuries
            
        logger.info(f"✅ Fetched {len(injuries)} injuries from CollegeFootballData")
        return injuries
    
    except Exception as e:
        logger.error(f"❌ Failed to fetch CFB injuries: {e}")
        return []


def fetch_cfb_roster(team: str, year: int = 2025) -> List[Dict[str, Any]]:
    """
    Fetch NCAAF roster from CollegeFootballData API
    
    Args:
        team: Team name (e.g., "Alabama", "Ohio State")
        year: Season year (default: 2025)
    
    Returns:
        List of player data:
        [{
            "name": "John Doe",
            "position": "QB",
            "jersey": "12",
            "year": "Junior",
            "height": "6-2",
            "weight": "210"
        }]
    """
    try:
        url = f"{CFB_BASE_URL}/roster"
        params: Dict[str, Any] = {
            "team": team,
            "year": year
        }
        
        headers = {
            'User-Agent': 'Permutation-Carlos/1.0'
        }
        
        # Add API key if available (get from environment)
        import os
        cfb_key = os.getenv('CFB_API_KEY') or CFB_API_KEY
        if not cfb_key:
            logger.error("❌ CFB_API_KEY not configured. Get your free API key from https://collegefootballdata.com/key")
            raise ValueError("CFB_API_KEY required for CollegeFootballData API. Sign up at https://collegefootballdata.com/")
        
        headers['Authorization'] = f'Bearer {cfb_key}'
        
        response = requests.get(url, params=params, headers=headers, timeout=10)
        response.raise_for_status()
        
        roster_data = response.json()
        players = []
        
        for player in roster_data:
            if not isinstance(player, dict):
                continue
            
            first_name = player.get("first_name", "")
            last_name = player.get("last_name", "")
            full_name = f"{first_name} {last_name}".strip()
            
            if not full_name:
                continue
            
            players.append({
                "name": full_name,
                "position": player.get("position", "Unknown"),
                "jersey": player.get("jersey", ""),
                "year": player.get("year", ""),
                "height": player.get("height", ""),
                "weight": player.get("weight", ""),
                "hometown": player.get("hometown", ""),
                "team": player.get("team", team),
                "cfb_id": player.get("id"),
                "source": "CollegeFootballData"
            })
        
        logger.info(f"✅ Fetched {len(players)} players from CFB roster for {team}")
        return players
    
    except Exception as e:
        logger.error(f"❌ Failed to fetch CFB roster for {team}: {e}")
        return []


def get_injury_impact(status: str) -> float:
    """
    Calculate injury impact multiplier based on status
    
    Args:
        status: Injury status (Out, Questionable, Doubtful, Day-To-Day, Probable)
    
    Returns:
        Impact multiplier (0.0 = out, 1.0 = healthy)
    """
    status_lower = status.lower()
    
    if "out" in status_lower or "ir" in status_lower:
        return 0.0  # Completely out
    elif "doubtful" in status_lower:
        return 0.2  # 20% effectiveness
    elif "questionable" in status_lower:
        return 0.6  # 60% effectiveness
    elif "day-to-day" in status_lower or "day to day" in status_lower:
        return 0.75  # 75% effectiveness
    elif "probable" in status_lower:
        return 0.9  # 90% effectiveness
    else:
        return 1.0  # Healthy


def get_injuries_for_team(team_name: str, sport_key: str) -> List[Dict[str, Any]]:
    """
    Get all injuries for a specific team
    
    Args:
        team_name: Team name (e.g., "Boston Celtics", "Alabama")
        sport_key: Sport identifier
    
    Returns:
        List of injuries for that team
    """
    all_injuries = fetch_espn_injuries(sport_key)
    
    # Normalize team name for matching
    team_lower = team_name.lower().strip()
    team_keywords = team_name.split()
    
    # Build comprehensive match patterns
    match_patterns = [
        team_lower,  # "boston celtics"
        team_lower.replace(' ', ''),  # "bostonceltics"
    ]
    
    # Add individual keywords (but skip common words)
    skip_words = {'city', 'fc', 'united', 'state', 'university', 'college'}
    for keyword in team_keywords:
        if len(keyword) > 3 and keyword.lower() not in skip_words:
            match_patterns.append(keyword.lower())
    
    # Add known aliases from ESPN_TEAM_ALIASES
    for official_name, aliases in ESPN_TEAM_ALIASES.items():
        if team_lower == official_name.lower() or team_lower in [a.lower() for a in aliases]:
            match_patterns.extend([a.lower() for a in aliases])
            match_patterns.append(official_name.lower())
            break
    
    # Filter injuries with fuzzy matching
    team_injuries = []
    for injury in all_injuries:
        injury_team = injury.get("team", "").lower().strip()
        
        # Skip if no team found
        if not injury_team or injury_team == "unknown":
            continue
        
        # Check if any pattern matches
        for pattern in match_patterns:
            if pattern in injury_team or injury_team in pattern:
                team_injuries.append(injury)
                break
    
    # For NCAAF, also check CollegeFootballData (not yet implemented)
    if "ncaaf" in sport_key:
        # CFB injuries not yet available
        pass
    
    if team_injuries:
        logger.info(f"✅ Found {len(team_injuries)} injuries for {team_name}")
    else:
        logger.warning(f"⚠️ No injuries found for {team_name} (ESPN might not have data or team name mismatch)")
    
    return team_injuries


def apply_injury_to_player(player_data: Dict[str, Any], injuries: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Apply injury data to player stats
    
    Args:
        player_data: Player dictionary with stats
        injuries: List of all injuries
    
    Returns:
        Updated player data with injury adjustments
    """
    player_name = player_data.get("name", "")
    
    # Find matching injury
    player_injury = None
    for injury in injuries:
        if injury.get("player_name", "").lower() == player_name.lower():
            player_injury = injury
            break
    
    if player_injury:
        status = player_injury.get("status", "")
        impact = get_injury_impact(status)
        
        # Update player data
        player_data["injury_status"] = status
        player_data["injury_description"] = player_injury.get("injury", "")
        player_data["injury_impact"] = impact
        player_data["injury_updated"] = player_injury.get("date_updated", "")
        
        # Adjust stats based on impact
        if impact < 1.0:
            for stat_key in ["ppg", "apg", "rpg", "per"]:
                if stat_key in player_data:
                    player_data[stat_key] *= impact
            
            logger.info(f"⚠️ {player_name} injury impact: {status} ({impact*100:.0f}% effectiveness)")
    else:
        # No injury - mark as healthy
        player_data["injury_status"] = "Healthy"
        player_data["injury_impact"] = 1.0
    
    return player_data


# Team name normalization for ESPN scraping
ESPN_TEAM_ALIASES = {
    # NBA
    "Boston Celtics": ["celtics", "boston", "bos", "cel"],
    "Los Angeles Lakers": ["lakers", "la lakers", "lal", "l.a. lakers"],
    "Golden State Warriors": ["warriors", "golden state", "gsw", "gs warriors"],
    "Milwaukee Bucks": ["bucks", "milwaukee", "mil"],
    "Atlanta Hawks": ["hawks", "atlanta", "atl"],
    
    # NFL
    "Arizona Cardinals": ["cardinals", "arizona", "ari", "az cardinals"],
    "Tampa Bay Buccaneers": ["buccaneers", "tampa bay", "tb", "bucs", "tampa"],
    "Kansas City Chiefs": ["chiefs", "kansas city", "kc", "k.c."],
    "Buffalo Bills": ["bills", "buffalo", "buf"],
    "Dallas Cowboys": ["cowboys", "dallas", "dal"],
    
    # Add more as needed - this gets populated from ESPN data
}


def normalize_team_name(team_name: str, sport_key: str) -> str:
    """
    Normalize team name for ESPN injury matching
    
    Args:
        team_name: Raw team name
        sport_key: Sport identifier
    
    Returns:
        Normalized team name
    """
    team_lower = team_name.lower().strip()
    
    for official_name, aliases in ESPN_TEAM_ALIASES.items():
        if team_lower in aliases or team_lower == official_name.lower():
            return official_name
    
    return team_name
