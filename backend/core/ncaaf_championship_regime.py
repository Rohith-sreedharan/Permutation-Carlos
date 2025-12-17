"""
NCAA Football Championship/Postseason Regime Logic
Implements special pace/scoring adjustments for high-stakes games.

Key adjustments:
- Pace compression (12% slower)
- Early game-control slowdown
- Losing-team scoring floor collapse (3-7 pts allowed)
- Red-zone TD suppression
- Rematch familiarity penalty
- Public ceiling clamp (60th percentile)
"""
from typing import Dict, Any, Optional
import logging
import numpy as np

logger = logging.getLogger(__name__)

# ============================================================================
# REGIME DETECTION
# ============================================================================

CHAMPIONSHIP_KEYWORDS = [
    "championship", "playoff", "bowl", "final", "semi-final", "semifinal",
    "cfp", "college football playoff", "national championship"
]

POSTSEASON_KEYWORDS = CHAMPIONSHIP_KEYWORDS + [
    "bowl game", "postseason"
]

def detect_ncaaf_context(
    event_name: str,
    league: Optional[str] = None,
    week: Optional[int] = None,
    **metadata
) -> Dict[str, bool]:
    """
    Auto-detect if this is a championship or postseason game
    
    Returns:
        {
            "is_postseason": bool,
            "is_championship": bool,
            "is_bowl_game": bool,
            "is_rematch": bool
        }
    """
    event_lower = event_name.lower()
    
    is_championship = any(kw in event_lower for kw in ["championship", "final", "cfp"])
    is_bowl = "bowl" in event_lower
    is_playoff = "playoff" in event_lower or "semi" in event_lower
    
    is_postseason = is_championship or is_bowl or is_playoff
    
    # Check if teams have played before this season (rematch detection)
    is_rematch = metadata.get("is_rematch", False)  # Passed from caller if known
    
    return {
        "is_postseason": is_postseason,
        "is_championship": is_championship,
        "is_bowl_game": is_bowl,
        "is_rematch": is_rematch
    }


# ============================================================================
# PACE COMPRESSION
# ============================================================================

class NCAAFChampionshipPaceModel:
    """
    Adjusts pace for championship/postseason games
    """
    
    @staticmethod
    def apply_pace_compression(
        base_pace: float,
        is_postseason: bool,
        is_championship: bool
    ) -> float:
        """
        Championship/postseason games run 8-12% slower
        
        Args:
            base_pace: possessions per game (e.g., 12.5)
            is_postseason: bool
            is_championship: bool
        
        Returns:
            adjusted_pace: float
        """
        pace = base_pace
        
        if is_championship:
            pace *= 0.88  # 12% reduction for championships
            logger.info(f"Championship pace compression: {base_pace:.1f} → {pace:.1f}")
        elif is_postseason:
            pace *= 0.92  # 8% reduction for other postseason
            logger.info(f"Postseason pace compression: {base_pace:.1f} → {pace:.1f}")
        
        return pace
    
    @staticmethod
    def apply_early_game_control_slowdown(
        pace: float,
        win_probability: float,
        quarter: int,
        score_differential: float
    ) -> float:
        """
        When favorite is clearly in control, slow pace early (not just Q4)
        
        Args:
            pace: current pace
            win_probability: 0-1 (e.g., 0.75 = 75% favorite)
            quarter: 1-4
            score_differential: positive if winning
        
        Returns:
            adjusted_pace: float
        """
        # If winning team has >75% win prob and it's Q2+, slow it down
        if win_probability > 0.75 and quarter >= 2:
            reduction = 0.7  # 30% reduction
            pace *= reduction
            logger.info(
                f"Early game-control slowdown: Q{quarter}, WP={win_probability:.1%}, "
                f"pace reduced by {(1-reduction)*100:.0f}%"
            )
        
        # Additional slowdown for big leads
        if score_differential > 14 and quarter >= 2:
            pace *= 0.85
            logger.info(f"Blowout slowdown: {score_differential:.0f} pt lead")
        
        return pace


# ============================================================================
# SCORING ADJUSTMENTS
# ============================================================================

class NCAAFChampionshipScoringModel:
    """
    Adjusts scoring efficiency for championship/postseason games
    """
    
    @staticmethod
    def get_losing_team_floor(
        is_championship: bool,
        is_strong_defense: bool
    ) -> tuple[int, int]:
        """
        In championship/defense-heavy games, losing team can score 3-7 pts
        (not the usual 14-21 floor)
        
        Returns:
            (min_points, max_points): tuple of ints
        """
        if is_championship and is_strong_defense:
            return (3, 7)  # Very low floor
        elif is_championship:
            return (7, 14)  # Moderate floor
        else:
            return (14, 21)  # Normal floor
    
    @staticmethod
    def apply_redzone_td_suppression(
        base_redzone_td_rate: float,
        is_championship: bool,
        is_postseason: bool
    ) -> float:
        """
        Championship defenses tighten in red zone
        More FGs, fewer TDs
        
        Args:
            base_redzone_td_rate: e.g., 0.60 (60% of RZ trips = TD)
        
        Returns:
            adjusted_rate: float
        """
        rate = base_redzone_td_rate
        
        if is_championship:
            rate *= 0.75  # 25% reduction
            logger.info(f"Championship RZ TD suppression: {base_redzone_td_rate:.2%} → {rate:.2%}")
        elif is_postseason:
            rate *= 0.85  # 15% reduction
        
        return rate
    
    @staticmethod
    def apply_rematch_familiarity_penalty(
        explosive_play_rate: float,
        offensive_efficiency: float,
        is_rematch: bool
    ) -> tuple[float, float]:
        """
        If teams already played this season, offense becomes more predictable
        
        Returns:
            (adjusted_explosive_rate, adjusted_efficiency)
        """
        if is_rematch:
            explosive_play_rate *= 0.90  # 10% fewer big plays
            offensive_efficiency *= 0.95  # 5% efficiency drop
            logger.info("Rematch familiarity penalty applied")
        
        return explosive_play_rate, offensive_efficiency
    
    @staticmethod
    def clamp_public_total_projection(
        simulation_distribution: np.ndarray,
        percentile: int = 60
    ) -> float:
        """
        For public display, clamp total to median or 60th percentile
        (not 95th percentile which shows absurd ceilings)
        
        Args:
            simulation_distribution: array of simulated totals
            percentile: which percentile to use (default 60)
        
        Returns:
            public_total: float (clamped expectation)
        """
        public_total = np.percentile(simulation_distribution, percentile)
        
        median = np.median(simulation_distribution)
        p95 = np.percentile(simulation_distribution, 95)
        
        logger.info(
            f"Public total clamped: median={median:.1f}, "
            f"p60={public_total:.1f}, p95={p95:.1f}"
        )
        
        return float(public_total)


# ============================================================================
# POSSESSION-BASED SCORING ENGINE
# ============================================================================

class PossessionBasedScoringEngine:
    """
    NCAAF scoring must be possession-based, not simple PPG math.
    Each possession has an outcome: TD, FG, punt, turnover, turnover on downs.
    """
    
    @staticmethod
    def simulate_game_possessions(
        num_possessions_home: int,
        num_possessions_away: int,
        home_offensive_efficiency: float,
        away_offensive_efficiency: float,
        home_redzone_td_rate: float,
        away_redzone_td_rate: float,
        is_championship: bool,
        is_postseason: bool
    ) -> Dict[str, Any]:
        """
        Simulate game drive-by-drive
        
        Args:
            num_possessions_home: int (e.g., 12)
            num_possessions_away: int (e.g., 11)
            home_offensive_efficiency: 0-1 (probability of scoring drive)
            away_offensive_efficiency: 0-1
            home_redzone_td_rate: 0-1
            away_redzone_td_rate: 0-1
        
        Returns:
            {
                "home_score": int,
                "away_score": int,
                "home_tds": int,
                "home_fgs": int,
                "away_tds": int,
                "away_fgs": int,
                "total_score": int
            }
        """
        # Apply championship suppression
        if is_championship:
            home_redzone_td_rate *= 0.75
            away_redzone_td_rate *= 0.75
        
        home_score = 0
        away_score = 0
        home_tds = 0
        home_fgs = 0
        away_tds = 0
        away_fgs = 0
        
        # Simulate home possessions
        for _ in range(num_possessions_home):
            if np.random.random() < home_offensive_efficiency:
                # Scoring drive
                if np.random.random() < home_redzone_td_rate:
                    # Touchdown
                    home_score += 7
                    home_tds += 1
                else:
                    # Field goal
                    home_score += 3
                    home_fgs += 1
            # else: punt/turnover (no points)
        
        # Simulate away possessions
        for _ in range(num_possessions_away):
            if np.random.random() < away_offensive_efficiency:
                # Scoring drive
                if np.random.random() < away_redzone_td_rate:
                    # Touchdown
                    away_score += 7
                    away_tds += 1
                else:
                    # Field goal
                    away_score += 3
                    away_fgs += 1
        
        return {
            "home_score": home_score,
            "away_score": away_score,
            "home_tds": home_tds,
            "home_fgs": home_fgs,
            "away_tds": away_tds,
            "away_fgs": away_fgs,
            "total_score": home_score + away_score
        }


# ============================================================================
# MASTER REGIME CONTROLLER
# ============================================================================

class NCAAFChampionshipRegimeController:
    """
    Master controller that orchestrates all championship/postseason adjustments
    """
    
    def __init__(self):
        self.pace_model = NCAAFChampionshipPaceModel()
        self.scoring_model = NCAAFChampionshipScoringModel()
        self.possession_engine = PossessionBasedScoringEngine()
    
    def apply_regime_adjustments(
        self,
        base_pace_home: float,
        base_pace_away: float,
        offensive_efficiency_home: float,
        offensive_efficiency_away: float,
        redzone_td_rate_home: float,
        redzone_td_rate_away: float,
        explosive_play_rate_home: float,
        explosive_play_rate_away: float,
        event_context: Dict[str, bool],
        game_state: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Apply all championship/postseason regime adjustments
        
        Args:
            base_pace_home/away: possessions per game
            offensive_efficiency_home/away: scoring drive probability
            redzone_td_rate_home/away: TD rate in red zone
            explosive_play_rate_home/away: big play frequency
            event_context: output from detect_ncaaf_context()
            game_state: optional current game state (quarter, score diff, win prob)
        
        Returns:
            {
                "adjusted_pace_home": float,
                "adjusted_pace_away": float,
                "adjusted_offensive_efficiency_home": float,
                "adjusted_offensive_efficiency_away": float,
                "adjusted_redzone_td_rate_home": float,
                "adjusted_redzone_td_rate_away": float,
                "adjusted_explosive_rate_home": float,
                "adjusted_explosive_rate_away": float,
                "regime_flags": dict,
                "adjustments_applied": list[str]
            }
        """
        adjustments_applied = []
        
        # Extract context flags
        is_postseason = event_context.get("is_postseason", False)
        is_championship = event_context.get("is_championship", False)
        is_rematch = event_context.get("is_rematch", False)
        
        # 1. Pace compression
        adjusted_pace_home = self.pace_model.apply_pace_compression(
            base_pace_home, is_postseason, is_championship
        )
        adjusted_pace_away = self.pace_model.apply_pace_compression(
            base_pace_away, is_postseason, is_championship
        )
        if adjusted_pace_home != base_pace_home:
            adjustments_applied.append("pace_compression")
        
        # 2. Early game-control slowdown (if game state provided)
        if game_state:
            adjusted_pace_home = self.pace_model.apply_early_game_control_slowdown(
                adjusted_pace_home,
                game_state.get("home_win_probability", 0.5),
                game_state.get("quarter", 1),
                game_state.get("score_differential", 0)
            )
            if "game_control" in str(game_state):
                adjustments_applied.append("early_game_control_slowdown")
        
        # 3. Red-zone TD suppression
        adjusted_redzone_td_rate_home = self.scoring_model.apply_redzone_td_suppression(
            redzone_td_rate_home, is_championship, is_postseason
        )
        adjusted_redzone_td_rate_away = self.scoring_model.apply_redzone_td_suppression(
            redzone_td_rate_away, is_championship, is_postseason
        )
        if adjusted_redzone_td_rate_home != redzone_td_rate_home:
            adjustments_applied.append("redzone_td_suppression")
        
        # 4. Rematch familiarity penalty
        adjusted_explosive_rate_home, adjusted_offensive_efficiency_home = \
            self.scoring_model.apply_rematch_familiarity_penalty(
                explosive_play_rate_home, offensive_efficiency_home, is_rematch
            )
        adjusted_explosive_rate_away, adjusted_offensive_efficiency_away = \
            self.scoring_model.apply_rematch_familiarity_penalty(
                explosive_play_rate_away, offensive_efficiency_away, is_rematch
            )
        if is_rematch:
            adjustments_applied.append("rematch_familiarity_penalty")
        
        return {
            "adjusted_pace_home": adjusted_pace_home,
            "adjusted_pace_away": adjusted_pace_away,
            "adjusted_offensive_efficiency_home": adjusted_offensive_efficiency_home,
            "adjusted_offensive_efficiency_away": adjusted_offensive_efficiency_away,
            "adjusted_redzone_td_rate_home": adjusted_redzone_td_rate_home,
            "adjusted_redzone_td_rate_away": adjusted_redzone_td_rate_away,
            "adjusted_explosive_rate_home": adjusted_explosive_rate_home,
            "adjusted_explosive_rate_away": adjusted_explosive_rate_away,
            "regime_flags": event_context,
            "adjustments_applied": adjustments_applied
        }
