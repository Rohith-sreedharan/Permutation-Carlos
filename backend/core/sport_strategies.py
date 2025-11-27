"""
Sport-Specific Strategy Pattern for Monte Carlo Simulations
Handles different scoring distributions across sports
"""
from abc import ABC, abstractmethod
import numpy as np
from typing import Dict, Any, List
import random


class SportStrategy(ABC):
    """
    Abstract base class for sport-specific simulation strategies.
    Different sports have different scoring patterns and variance.
    """
    
    @abstractmethod
    def simulate_game(
        self,
        team_a_rating: float,
        team_b_rating: float,
        iterations: int,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Run sport-specific simulation"""
        pass
    
    @abstractmethod
    def get_volatility_thresholds(self) -> Dict[str, float]:
        """Return sport-specific volatility thresholds"""
        pass


class HighScoringStrategy(SportStrategy):
    """
    Strategy for high-scoring sports (NBA, NFL)
    Uses Normal Distribution for point spreads
    """
    
    def simulate_game(
        self,
        team_a_rating: float,
        team_b_rating: float,
        iterations: int,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        NBA/NFL simulation using Normal Distribution
        
        Logic:
        - Team scores follow normal distribution around rating
        - Higher variance in NFL (single game, weather, turnovers)
        - Lower variance in NBA (more possessions, scoring more predictable)
        """
        sport_key = context.get('sport_key', 'basketball_nba')
        
        # Sport-specific variance
        if 'football' in sport_key:
            # NFL: Higher variance due to single-game volatility
            base_variance = 14.0
            home_advantage = 2.5
        else:
            # NBA: Lower variance due to high possession count
            base_variance = 10.0
            home_advantage = 3.5
        
        # Apply home court/field advantage
        is_team_a_home = context.get('is_team_a_home', True)
        if is_team_a_home:
            team_a_rating += home_advantage
        else:
            team_b_rating += home_advantage
        
        # Run simulations
        team_a_wins = 0
        team_b_wins = 0
        pushes = 0
        team_a_total = 0.0
        team_b_total = 0.0
        margins = []
        totals = []
        
        for _ in range(iterations):
            # Generate scores using normal distribution
            team_a_score = np.random.normal(team_a_rating, base_variance)
            team_b_score = np.random.normal(team_b_rating, base_variance)
            
            # Ensure non-negative scores
            team_a_score = max(0, team_a_score)
            team_b_score = max(0, team_b_score)
            
            margin = team_a_score - team_b_score
            total = team_a_score + team_b_score
            
            margins.append(margin)
            totals.append(total)
            team_a_total += team_a_score
            team_b_total += team_b_score
            
            # Determine winner (handle ties)
            if abs(margin) < 0.5:
                pushes += 1
            elif margin > 0:
                team_a_wins += 1
            else:
                team_b_wins += 1
        
        return {
            'team_a_wins': team_a_wins,
            'team_b_wins': team_b_wins,
            'pushes': pushes,
            'team_a_total': team_a_total,
            'team_b_total': team_b_total,
            'margins': margins,
            'totals': totals
        }
    
    def get_volatility_thresholds(self) -> Dict[str, float]:
        """NBA/NFL volatility thresholds based on margin std dev"""
        return {
            'stable': 8.0,    # Low variance games
            'moderate': 12.0  # High variance games
        }


class LowScoringStrategy(SportStrategy):
    """
    Strategy for low-scoring sports (MLB, NHL)
    Uses Poisson Distribution for run/goal totals
    """
    
    def simulate_game(
        self,
        team_a_rating: float,
        team_b_rating: float,
        iterations: int,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        MLB/NHL simulation using Poisson Distribution
        
        Logic:
        - Run/goal scoring follows Poisson distribution
        - Rating represents expected runs/goals per game
        - Lower variance than NBA (fewer scoring events)
        - Home advantage is smaller
        """
        sport_key = context.get('sport_key', 'baseball_mlb')
        
        # Sport-specific parameters
        if 'baseball' in sport_key:
            # MLB: Expected runs per game (typically 4-5)
            home_advantage = 0.3  # Runs
            min_rating = 2.0
            max_rating = 8.0
        else:
            # NHL: Expected goals per game (typically 2-4)
            home_advantage = 0.2  # Goals
            min_rating = 1.5
            max_rating = 6.0
        
        # Ensure ratings are in valid range for Poisson
        team_a_rating = np.clip(team_a_rating, min_rating, max_rating)
        team_b_rating = np.clip(team_b_rating, min_rating, max_rating)
        
        # Apply home advantage
        is_team_a_home = context.get('is_team_a_home', True)
        if is_team_a_home:
            team_a_rating += home_advantage
        else:
            team_b_rating += home_advantage
        
        # Run simulations
        team_a_wins = 0
        team_b_wins = 0
        pushes = 0
        team_a_total = 0.0
        team_b_total = 0.0
        margins = []
        totals = []
        
        for _ in range(iterations):
            # Generate scores using Poisson distribution
            team_a_score = np.random.poisson(team_a_rating)
            team_b_score = np.random.poisson(team_b_rating)
            
            margin = team_a_score - team_b_score
            total = team_a_score + team_b_score
            
            margins.append(float(margin))
            totals.append(float(total))
            team_a_total += team_a_score
            team_b_total += team_b_score
            
            # Determine winner (ties are rare in baseball/hockey but possible)
            if margin == 0:
                pushes += 1
            elif margin > 0:
                team_a_wins += 1
            else:
                team_b_wins += 1
        
        return {
            'team_a_wins': team_a_wins,
            'team_b_wins': team_b_wins,
            'pushes': pushes,
            'team_a_total': team_a_total,
            'team_b_total': team_b_total,
            'margins': margins,
            'totals': totals
        }
    
    def get_volatility_thresholds(self) -> Dict[str, float]:
        """MLB/NHL volatility thresholds (lower than NBA/NFL due to discrete scoring)"""
        return {
            'stable': 2.0,    # Pitcher's duel / defensive game
            'moderate': 3.5   # High-scoring affair
        }


class SportStrategyFactory:
    """
    Factory to select appropriate strategy based on sport type
    """
    
    @staticmethod
    def get_strategy(sport_key: str) -> SportStrategy:
        """
        Return appropriate strategy for given sport
        
        Args:
            sport_key: Sport identifier from Odds API
                - basketball_nba, americanfootball_nfl (High Scoring)
                - baseball_mlb, icehockey_nhl (Low Scoring)
        
        Returns:
            SportStrategy instance
        """
        # High scoring sports (Normal Distribution)
        if any(s in sport_key for s in ['basketball', 'football']):
            return HighScoringStrategy()
        
        # Low scoring sports (Poisson Distribution)
        elif any(s in sport_key for s in ['baseball', 'hockey']):
            return LowScoringStrategy()
        
        # Default to high scoring for unknown sports
        else:
            return HighScoringStrategy()
    
    @staticmethod
    def get_expected_score_range(sport_key: str) -> tuple:
        """
        Return typical score range for sport (for rating normalization)
        
        Returns:
            (min_score, max_score) tuple
        """
        if 'basketball' in sport_key:
            return (90, 130)  # NBA typical scores
        elif 'football_nfl' in sport_key:
            return (14, 35)   # NFL typical scores
        elif 'baseball' in sport_key:
            return (2, 8)     # MLB typical runs
        elif 'hockey' in sport_key:
            return (1, 6)     # NHL typical goals
        elif 'football_ncaaf' in sport_key:
            return (20, 50)   # College football (higher scoring)
        else:
            return (80, 120)  # Generic default
