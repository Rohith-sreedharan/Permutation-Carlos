"""
NBA Garbage-Time Volatility Module

Prevents Unders from being blown up by Q4 chaos pace spikes
Applies to: basketball_nba only

Per Engine Upgrade Spec Section 6:
- Detection: Q4, last 3:00, 10+ point lead
- Modes: Slow (70%) vs Chaos (30%)
- Impact: Possession length, efficiency, 3P rate, TOs
- Penalties: Confidence reduction, volatility boost
"""

import random
import numpy as np
from typing import Dict, Any, Tuple, Optional
from dataclasses import dataclass
import logging

from core.engine_config import GarbageTimeConfig, get_garbage_time_config

logger = logging.getLogger(__name__)


@dataclass
class GarbageTimeState:
    """State tracking for garbage-time during simulation"""
    is_active: bool = False
    mode: Optional[str] = None  # 'slow' or 'chaos'
    activated_at_seconds: Optional[int] = None
    lead_margin: Optional[float] = None
    leading_team: Optional[str] = None


class GarbageTimeModule:
    """
    NBA Late-Game Volatility Module
    
    Detects and adjusts for garbage-time scenarios where:
    - Game is decided (10+ point lead)
    - Clock is running out (<3:00 in Q4)
    - Teams change behavior patterns
    """
    
    def __init__(self, sport_key: str):
        """
        Initialize garbage-time module
        
        Args:
            sport_key: Sport identifier (e.g., 'basketball_nba')
        """
        self.config = get_garbage_time_config(sport_key)
        self.is_nba = sport_key == "basketball_nba"
        
        # Metrics for this game
        self.total_sims = 0
        self.garbage_sims = 0
        self.slow_mode_sims = 0
        self.chaos_mode_sims = 0
        
        logger.info(f"Garbage-Time Module initialized: {sport_key}, enabled={self.config.enabled}")
    
    def detect_garbage_time(
        self,
        quarter: int,
        time_remaining_seconds: int,
        home_score: float,
        away_score: float
    ) -> bool:
        """
        Detect if current game state qualifies as garbage time
        
        Args:
            quarter: Current quarter (1-4)
            time_remaining_seconds: Seconds remaining in quarter
            home_score: Current home score
            away_score: Current away score
            
        Returns:
            True if garbage time conditions met
        """
        if not self.config.enabled:
            return False
        
        if not self.is_nba:
            return False
        
        # Must be Q4
        if quarter != self.config.quarter:
            return False
        
        # Must be in final minutes
        if time_remaining_seconds > self.config.time_threshold_seconds:
            return False
        
        # Must have significant lead
        margin = abs(home_score - away_score)
        if margin < self.config.lead_threshold_points:
            return False
        
        return True
    
    def select_garbage_mode(self) -> str:
        """
        Select garbage-time mode: 'slow' or 'chaos'
        
        Slow mode (70%): Teams slow down, preserve Under
        Chaos mode (30%): Teams go chaotic, blow up totals
        
        Returns:
            'slow' or 'chaos'
        """
        r = random.random()
        
        if r < self.config.prob_slow_mode:
            self.slow_mode_sims += 1
            return 'slow'
        else:
            self.chaos_mode_sims += 1
            return 'chaos'
    
    def get_possession_multipliers(
        self,
        mode: str,
        is_leading_team: bool
    ) -> float:
        """
        Get possession length multiplier for garbage time
        
        Args:
            mode: 'slow' or 'chaos'
            is_leading_team: True if this is the leading team
            
        Returns:
            Possession length multiplier (1.0 = normal)
        """
        if mode == 'slow':
            # Slow mode: Both teams slow down, leading team more
            return (self.config.slow_possession_leading if is_leading_team 
                    else self.config.slow_possession_trailing)
        
        elif mode == 'chaos':
            # Chaos mode: Both teams speed up, trailing team more
            return (self.config.chaos_possession_leading if is_leading_team
                    else self.config.chaos_possession_trailing)
        
        else:
            return 1.0
    
    def get_efficiency_multipliers(
        self,
        mode: str,
        is_leading_team: bool
    ) -> float:
        """
        Get offensive efficiency multiplier for garbage time
        
        Args:
            mode: 'slow' or 'chaos'
            is_leading_team: True if this is the leading team
            
        Returns:
            Efficiency multiplier (1.0 = normal)
        """
        if mode == 'slow':
            # Slow mode: Lower efficiency (starters out, bench in)
            return (self.config.slow_offensive_eff_leading if is_leading_team
                    else self.config.slow_offensive_eff_trailing)
        
        elif mode == 'chaos':
            # Chaos mode: Higher efficiency (desperation, open shots)
            return (self.config.chaos_offensive_eff_leading if is_leading_team
                    else self.config.chaos_offensive_eff_trailing)
        
        else:
            return 1.0
    
    def get_shooting_adjustments(self, mode: str) -> Dict[str, float]:
        """
        Get shooting behavior adjustments for garbage time
        
        Args:
            mode: 'slow' or 'chaos'
            
        Returns:
            Dict with three_point_boost and turnover_boost
        """
        if mode == 'chaos':
            return {
                'three_point_boost': self.config.chaos_three_point_rate_boost,
                'turnover_boost': self.config.chaos_turnover_rate_boost
            }
        else:
            return {
                'three_point_boost': 0.0,
                'turnover_boost': 0.0
            }
    
    def apply_garbage_time_adjustments(
        self,
        quarter: int,
        time_remaining_seconds: int,
        home_score: float,
        away_score: float,
        home_possessions_remaining: int,
        away_possessions_remaining: int,
        home_offensive_rating: float,
        away_offensive_rating: float
    ) -> Dict[str, Any]:
        """
        Apply garbage-time adjustments to simulation
        
        Args:
            quarter: Current quarter
            time_remaining_seconds: Seconds remaining
            home_score: Home team score
            away_score: Away team score
            home_possessions_remaining: Estimated home possessions left
            away_possessions_remaining: Estimated away possessions left
            home_offensive_rating: Home offensive rating
            away_offensive_rating: Away offensive rating
            
        Returns:
            Dict with adjusted values and metadata
        """
        is_garbage = self.detect_garbage_time(
            quarter, time_remaining_seconds, home_score, away_score
        )
        
        # Track total simulations
        self.total_sims += 1
        
        if not is_garbage:
            return {
                'is_garbage_time': False,
                'mode': None,
                'home_possessions': home_possessions_remaining,
                'away_possessions': away_possessions_remaining,
                'home_offensive_rating': home_offensive_rating,
                'away_offensive_rating': away_offensive_rating,
                'three_point_boost': 0.0,
                'turnover_boost': 0.0
            }
        
        # Garbage time detected
        self.garbage_sims += 1
        
        # Select mode
        mode = self.select_garbage_mode()
        
        # Determine leading team
        is_home_leading = home_score > away_score
        
        # Apply possession multipliers
        home_possession_mult = self.get_possession_multipliers(mode, is_home_leading)
        away_possession_mult = self.get_possession_multipliers(mode, not is_home_leading)
        
        # Adjust possessions (multiplier affects pace)
        # Higher multiplier = slower pace = fewer possessions
        adjusted_home_poss = int(home_possessions_remaining / home_possession_mult)
        adjusted_away_poss = int(away_possessions_remaining / away_possession_mult)
        
        # Apply efficiency multipliers
        home_eff_mult = self.get_efficiency_multipliers(mode, is_home_leading)
        away_eff_mult = self.get_efficiency_multipliers(mode, not is_home_leading)
        
        adjusted_home_off = home_offensive_rating * home_eff_mult
        adjusted_away_off = away_offensive_rating * away_eff_mult
        
        # Get shooting adjustments
        shooting_adj = self.get_shooting_adjustments(mode)
        
        return {
            'is_garbage_time': True,
            'mode': mode,
            'home_possessions': adjusted_home_poss,
            'away_possessions': adjusted_away_poss,
            'home_offensive_rating': adjusted_home_off,
            'away_offensive_rating': adjusted_away_off,
            'three_point_boost': shooting_adj['three_point_boost'],
            'turnover_boost': shooting_adj['turnover_boost'],
            'original_home_poss': home_possessions_remaining,
            'original_away_poss': away_possessions_remaining
        }
    
    def calculate_confidence_penalty(self, base_confidence: int) -> int:
        """
        Calculate confidence penalty based on garbage-time frequency
        
        Args:
            base_confidence: Base confidence score (0-100)
            
        Returns:
            Adjusted confidence score
        """
        if self.total_sims == 0:
            return base_confidence
        
        # Calculate garbage-time share
        garbage_share = self.garbage_sims / self.total_sims
        
        # Apply penalty
        penalty = garbage_share * self.config.confidence_penalty_per_garbage_share
        
        final_confidence = max(0, base_confidence - int(penalty))
        
        logger.info(
            f"Confidence penalty: garbage_share={garbage_share:.2%}, "
            f"penalty={penalty:.1f}, base={base_confidence}, final={final_confidence}"
        )
        
        return final_confidence
    
    def calculate_volatility_boost(self, base_volatility: float) -> float:
        """
        Calculate volatility boost based on garbage-time frequency
        
        Args:
            base_volatility: Base volatility score
            
        Returns:
            Adjusted volatility score
        """
        if self.total_sims == 0:
            return base_volatility
        
        garbage_share = self.garbage_sims / self.total_sims
        
        # Boost volatility
        volatility_mult = 1.0 + (garbage_share * self.config.volatility_boost_multiplier)
        final_volatility = base_volatility * volatility_mult
        
        logger.info(
            f"Volatility boost: garbage_share={garbage_share:.2%}, "
            f"mult={volatility_mult:.2f}, base={base_volatility:.2f}, final={final_volatility:.2f}"
        )
        
        return final_volatility
    
    def get_metrics(self) -> Dict[str, Any]:
        """
        Get garbage-time metrics for logging/analysis
        
        Returns:
            Dict with all garbage-time metrics
        """
        if self.total_sims == 0:
            return {
                'garbage_share': 0.0,
                'slow_mode_pct': 0.0,
                'chaos_mode_pct': 0.0,
                'total_sims': 0
            }
        
        garbage_share = self.garbage_sims / self.total_sims
        slow_pct = self.slow_mode_sims / self.total_sims
        chaos_pct = self.chaos_mode_sims / self.total_sims
        
        return {
            'garbage_share': garbage_share,
            'slow_mode_pct': slow_pct,
            'chaos_mode_pct': chaos_pct,
            'total_sims': self.total_sims,
            'garbage_sims': self.garbage_sims,
            'slow_mode_sims': self.slow_mode_sims,
            'chaos_mode_sims': self.chaos_mode_sims
        }
    
    def get_dev_log(
        self,
        event_id: str,
        sport_key: str,
        base_confidence: int,
        final_confidence: int,
        final_total_variance: float
    ) -> Dict[str, Any]:
        """
        Generate dev log for auditing
        
        Per spec 6.5: Log JSON record per event
        
        Args:
            event_id: Game identifier
            sport_key: Sport key
            base_confidence: Confidence before garbage-time penalty
            final_confidence: Confidence after garbage-time penalty
            final_total_variance: Final total variance
            
        Returns:
            Dev log dict
        """
        metrics = self.get_metrics()
        
        return {
            'event_id': event_id,
            'sport': sport_key,
            'sim_count': self.total_sims,
            'garbage_share': metrics['garbage_share'],
            'slow_mode_pct': metrics['slow_mode_pct'],
            'chaos_mode_pct': metrics['chaos_mode_pct'],
            'base_confidence': base_confidence,
            'final_confidence': final_confidence,
            'final_total_variance': final_total_variance,
            'config': {
                'enabled': self.config.enabled,
                'lead_threshold': self.config.lead_threshold_points,
                'time_threshold_sec': self.config.time_threshold_seconds,
                'prob_slow': self.config.prob_slow_mode,
                'prob_chaos': self.config.prob_chaos_mode
            }
        }
