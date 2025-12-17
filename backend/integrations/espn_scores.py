"""
ESPN Scores API Integration
============================

Fetches live scores and final results for games to enable automatic grading.
ESPN provides free, public APIs for sports scores.
"""
import requests
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)

class ESPNScoresAPI:
    """
    ESPN API client for fetching game scores and results.
    
    Supports: NBA, NFL, NCAAB, NCAAF, MLB, NHL
    """
    
    BASE_URL = "https://site.api.espn.com/apis/site/v2/sports"
    
    # Map our sport keys to ESPN league identifiers
    SPORT_MAP = {
        'basketball_nba': ('basketball', 'nba'),
        'basketball_ncaab': ('basketball', 'mens-college-basketball'),
        'americanfootball_nfl': ('football', 'nfl'),
        'americanfootball_ncaaf': ('football', 'college-football'),
        'baseball_mlb': ('baseball', 'mlb'),
        'icehockey_nhl': ('hockey', 'nhl'),
    }
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'BeatVegas/1.0'
        })
    
    def fetch_scores(self, sport_key: str, date: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Fetch scores for a specific sport.
        
        Args:
            sport_key: Our sport key (e.g., 'basketball_nba')
            date: Optional date in YYYYMMDD format (e.g., '20251207')
        
        Returns:
            List of game results with scores
        """
        if sport_key not in self.SPORT_MAP:
            logger.warning(f"Sport {sport_key} not supported by ESPN API")
            return []
        
        sport, league = self.SPORT_MAP[sport_key]
        
        # Build URL
        url = f"{self.BASE_URL}/{sport}/{league}/scoreboard"
        params = {}
        
        if date:
            params['dates'] = date
        
        try:
            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            return self._parse_scoreboard(data, sport_key)
            
        except Exception as e:
            logger.error(f"Error fetching ESPN scores for {sport_key}: {e}")
            return []
    
    def _parse_scoreboard(self, data: Dict, sport_key: str) -> List[Dict[str, Any]]:
        """
        Parse ESPN scoreboard response into our format.
        """
        results = []
        
        events = data.get('events', [])
        
        for event in events:
            try:
                game_result = self._parse_event(event, sport_key)
                if game_result:
                    results.append(game_result)
            except Exception as e:
                logger.error(f"Error parsing ESPN event: {e}")
                continue
        
        return results
    
    def _parse_event(self, event: Dict, sport_key: str) -> Optional[Dict[str, Any]]:
        """
        Parse a single ESPN event into our game result format.
        """
        # Check if game is completed
        status = event.get('status', {})
        status_type = status.get('type', {}).get('name', '')
        
        if status_type not in ['STATUS_FINAL', 'STATUS_FINAL_OVERTIME']:
            return None  # Game not finished
        
        competitions = event.get('competitions', [])
        if not competitions:
            return None
        
        competition = competitions[0]
        competitors = competition.get('competitors', [])
        
        if len(competitors) != 2:
            return None
        
        # Parse teams and scores
        home_team = None
        away_team = None
        home_score = None
        away_score = None
        
        for competitor in competitors:
            team_name = competitor.get('team', {}).get('displayName', '')
            score = int(competitor.get('score', 0))
            is_home = competitor.get('homeAway') == 'home'
            
            if is_home:
                home_team = team_name
                home_score = score
            else:
                away_team = team_name
                away_score = score
        
        if not all([home_team, away_team, home_score is not None, away_score is not None]):
            return None
        
        # Type assertion: scores are guaranteed to be int here due to check above
        assert home_score is not None and away_score is not None
        
        # Get game ID and date
        game_id = event.get('id')
        game_date = event.get('date')
        
        return {
            'espn_id': game_id,
            'sport_key': sport_key,
            'home_team': home_team,
            'away_team': away_team,
            'home_score': home_score,
            'away_score': away_score,
            'total_score': home_score + away_score,
            'status': 'final',
            'completed_at': game_date,
            'is_overtime': status_type == 'STATUS_FINAL_OVERTIME'
        }
    
    def find_matching_event(
        self, 
        home_team: str, 
        away_team: str, 
        sport_key: str,
        date: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Find a specific game's result by team names.
        
        Args:
            home_team: Home team name
            away_team: Away team name
            sport_key: Sport identifier
            date: Optional date in YYYYMMDD format
        
        Returns:
            Game result if found and completed
        """
        scores = self.fetch_scores(sport_key, date)
        
        # Normalize team names for matching
        home_normalized = self._normalize_team_name(home_team)
        away_normalized = self._normalize_team_name(away_team)
        
        for game in scores:
            game_home = self._normalize_team_name(game['home_team'])
            game_away = self._normalize_team_name(game['away_team'])
            
            if game_home == home_normalized and game_away == away_normalized:
                return game
        
        return None
    
    def _normalize_team_name(self, team: str) -> str:
        """
        Normalize team name for matching (lowercase, remove extra spaces).
        """
        return ' '.join(team.lower().split())


# Singleton instance
espn_scores_api = ESPNScoresAPI()
