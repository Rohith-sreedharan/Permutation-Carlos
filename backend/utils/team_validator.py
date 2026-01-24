"""
Team Identity Validator - Ensures team_key consistency across all pipelines
"""
import logging
from typing import Dict, Any, Optional, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class TeamIdentity:
    """Canonical team identity"""
    team_key: str  # Primary key (never changes)
    team_name: str  # Display name (can vary)
    is_home: bool  # Position in game


class TeamIdentityValidator:
    """
    🚨 HARD RULE: TEAM NAMES ARE NEVER TRUSTED
    
    Every pipeline stage must use team_key for matching.
    This prevents the Milwaukee/Denver mapping disasters.
    """
    
    def __init__(self):
        # Team name normalization map (handles API inconsistencies)
        self.name_to_key = {
            # NBA
            "milwaukee bucks": "MIL",
            "bucks": "MIL",
            "denver nuggets": "DEN",
            "nuggets": "DEN",
            "philadelphia 76ers": "PHI",
            "76ers": "PHI",
            "philadelphia": "PHI",
            "houston rockets": "HOU",
            "rockets": "HOU",
            "utah jazz": "UTA",
            "jazz": "UTA",
            "miami heat": "MIA",
            "heat": "MIA",
            "portland trail blazers": "POR",
            "trail blazers": "POR",
            # Add more as needed - this should be comprehensive
        }
    
    def get_team_key(self, team_name: str) -> str:
        """
        Convert team name to canonical team_key
        
        Raises ValueError if team not found (hard fail)
        """
        normalized = team_name.strip().lower()
        
        if normalized in self.name_to_key:
            return self.name_to_key[normalized]
        
        # Try partial match (last word)
        words = normalized.split()
        if words:
            last_word = words[-1]
            if last_word in self.name_to_key:
                return self.name_to_key[last_word]
        
        # HARD FAIL - team not recognized
        logger.error(f"❌ UNKNOWN TEAM: '{team_name}' - Add to name_to_key map!")
        raise ValueError(f"Unknown team: {team_name}")
    
    def validate_team_consistency(
        self,
        odds_home_key: str,
        odds_away_key: str,
        sim_home_key: str,
        sim_away_key: str,
        ui_home_key: Optional[str] = None,
        ui_away_key: Optional[str] = None
    ) -> Tuple[bool, str]:
        """
        REQUIRED ASSERTION: odds_team_key == sim_team_key == ui_team_key
        
        Returns: (is_valid, error_message)
        """
        # Check odds vs sim
        if odds_home_key != sim_home_key:
            error = f"HOME KEY MISMATCH: odds={odds_home_key} vs sim={sim_home_key}"
            logger.error(f"🚨 TEAM MAPPING ERROR: {error}")
            return False, error
        
        if odds_away_key != sim_away_key:
            error = f"AWAY KEY MISMATCH: odds={odds_away_key} vs sim={sim_away_key}"
            logger.error(f"🚨 TEAM MAPPING ERROR: {error}")
            return False, error
        
        # Check UI if provided
        if ui_home_key and ui_home_key != odds_home_key:
            error = f"UI HOME KEY MISMATCH: ui={ui_home_key} vs odds={odds_home_key}"
            logger.error(f"🚨 TEAM MAPPING ERROR: {error}")
            return False, error
        
        if ui_away_key and ui_away_key != odds_away_key:
            error = f"UI AWAY KEY MISMATCH: ui={ui_away_key} vs odds={odds_away_key}"
            logger.error(f"🚨 TEAM MAPPING ERROR: {error}")
            return False, error
        
        return True, ""
    
    def create_team_identity(
        self,
        team_name: str,
        is_home: bool
    ) -> TeamIdentity:
        """
        Create canonical team identity from name
        """
        team_key = self.get_team_key(team_name)
        
        return TeamIdentity(
            team_key=team_key,
            team_name=team_name,
            is_home=is_home
        )


class ExtremeEdgeValidator:
    """
    Validates extreme edges (>30% deviation from market) before allowing EDGE state
    
    Catches:
    - Team swaps
    - Market mismatches  
    - Formula inversions
    """
    
    EXTREME_EDGE_THRESHOLD = 0.30  # 30%
    
    @staticmethod
    def calculate_implied_probability(american_odds: int) -> float:
        """
        Convert American odds to implied probability
        
        Examples:
        -150 → 0.60 (60%)
        +200 → 0.333 (33.3%)
        """
        if american_odds < 0:
            return abs(american_odds) / (abs(american_odds) + 100)
        else:
            return 100 / (american_odds + 100)
    
    @classmethod
    def validate_extreme_edge(
        cls,
        event_id: str,
        market_type: str,
        team_key: str,
        team_name: str,
        model_prob: float,
        market_odds: Optional[int],
        fair_line: Optional[float] = None
    ) -> Tuple[bool, Optional[str]]:
        """
        Trigger when: |model_prob − implied_prob| > 30%
        
        Returns: (is_valid, error_message)
        """
        if market_odds is None:
            return True, None  # Can't validate without odds
        
        implied_prob = cls.calculate_implied_probability(market_odds)
        deviation = abs(model_prob - implied_prob)
        
        if deviation > cls.EXTREME_EDGE_THRESHOLD:
            # EXTREME EDGE DETECTED - Require verification
            logger.warning(
                f"⚠️ EXTREME EDGE DETECTED: {event_id} - {market_type}\n"
                f"  Team: {team_name} ({team_key})\n"
                f"  Model prob: {model_prob*100:.1f}%\n"
                f"  Market implied: {implied_prob*100:.1f}%\n"
                f"  Deviation: {deviation*100:.1f}%\n"
                f"  Market odds: {market_odds:+d}\n"
                f"  Fair line: {fair_line}\n"
                f"  🚨 VERIFY BEFORE POSTING"
            )
            
            # For now, allow but log for manual review
            # In production, could require manual approval
            return True, f"EXTREME_EDGE: {deviation*100:.1f}% deviation - verify before posting"
        
        return True, None


# Global instances
team_identity_validator = TeamIdentityValidator()
extreme_edge_validator = ExtremeEdgeValidator()
