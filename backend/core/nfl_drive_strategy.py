"""
NFL-Specific Simulation Strategy with Anti-Over Bias Corrections
Implements drive-based simulation with proper clock management, defensive regression, and market anchoring
"""
import numpy as np
from typing import Dict, Any
import random


class NFLDriveBasedStrategy:
    """
    NFL simulation using DRIVE-BASED physics (not simple normal distribution)
    
    KEY ANTI-OVER CORRECTIONS:
    1. Drive termination modeling (punts, turnovers, field position stalls)
    2. Defensive mean reversion to league averages
    3. Market total as soft anchor with divergence penalties
    4. High variance reduces confidence (not coexists with directional bias)
    5. Clock management and game script modeling
    """
    
    def __init__(self):
        # League average baselines (2024 NFL season)
        self.LEAGUE_AVG_POINTS_PER_DRIVE = 1.85  # ~30% score TDs, ~30% FGs, ~40% no points
        self.LEAGUE_AVG_DRIVES_PER_TEAM = 11.5   # Per game
        self.LEAGUE_AVG_RED_ZONE_TD_PCT = 0.58   # 58% of red zone trips end in TD
        
        # Drive outcome probabilities (defensive regression anchors)
        self.DRIVE_OUTCOMES = {
            'touchdown': 0.22,      # 22% of drives
            'field_goal': 0.17,     # 17% of drives
            'punt': 0.42,           # 42% of drives
            'turnover': 0.10,       # 10% of drives
            'downs': 0.06,          # 6% turnover on downs
            'end_of_half': 0.03     # 3% clock runs out
        }
        
        # Clock bleed factors (game script modeling)
        self.CLOCK_BLEED_FACTORS = {
            'first_half': 1.0,      # Normal pace
            'second_half_close': 0.92,  # 8% fewer possessions when close
            'second_half_blowout': 0.85  # 15% fewer possessions in blowouts
        }
        
        # Market divergence penalty (soft anchor)
        self.MAX_DIVERGENCE_NO_PENALTY = 3.5  # Can deviate ±3.5 pts without penalty
        self.DIVERGENCE_PENALTY_RATE = 0.15   # 15% confidence reduction per point over threshold
    
    def simulate_game(
        self,
        team_a_rating: float,
        team_b_rating: float,
        iterations: int,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Simulate NFL game using drive-based model
        
        Args:
            team_a_rating: Home team offensive efficiency (pts/drive expected)
            team_b_rating: Away team offensive efficiency (pts/drive expected)
            iterations: Number of Monte Carlo simulations
            context: Game context (market total, injuries, weather, etc.)
        
        Returns:
            Simulation results with anti-over bias corrections applied
        """
        # Extract market context
        market_total = context.get('total_line', None)
        weather_impact = self._calculate_weather_impact(context.get('weather', {}))
        
        # Apply market anchor to ratings (soft adjustment)
        if market_total:
            implied_ppd_per_team = (market_total / 2) / self.LEAGUE_AVG_DRIVES_PER_TEAM
            team_a_rating_adjusted = self._apply_market_anchor(
                team_a_rating, implied_ppd_per_team, strength=0.15
            )
            team_b_rating_adjusted = self._apply_market_anchor(
                team_b_rating, implied_ppd_per_team, strength=0.15
            )
        else:
            team_a_rating_adjusted = team_a_rating
            team_b_rating_adjusted = team_b_rating
        
        # Apply weather impact (reduce scoring in bad weather)
        team_a_rating_adjusted *= (1.0 - weather_impact)
        team_b_rating_adjusted *= (1.0 - weather_impact)
        
        # Run simulations
        team_a_wins = 0
        team_b_wins = 0
        pushes = 0
        team_a_total_points = 0.0
        team_b_total_points = 0.0
        margins = []
        totals = []
        
        for i in range(iterations):
            # Simulate single game
            team_a_score, team_b_score = self._simulate_single_game(
                team_a_rating_adjusted,
                team_b_rating_adjusted,
                context
            )
            
            margin = team_a_score - team_b_score
            total = team_a_score + team_b_score
            
            margins.append(margin)
            totals.append(total)
            team_a_total_points += team_a_score
            team_b_total_points += team_b_score
            
            # Determine winner
            if abs(margin) < 0.5:
                pushes += 1
            elif margin > 0:
                team_a_wins += 1
            else:
                team_b_wins += 1
        
        # Calculate divergence from market (for confidence penalty)
        median_total = np.median(totals)
        divergence_penalty = 0.0
        if market_total:
            divergence = abs(median_total - market_total)
            if divergence > self.MAX_DIVERGENCE_NO_PENALTY:
                excess_divergence = divergence - self.MAX_DIVERGENCE_NO_PENALTY
                divergence_penalty = excess_divergence * self.DIVERGENCE_PENALTY_RATE
        
        return {
            'team_a_wins': team_a_wins,
            'team_b_wins': team_b_wins,
            'pushes': pushes,
            'team_a_total': team_a_total_points,
            'team_b_total': team_b_total_points,
            'margins': margins,
            'totals': totals,
            'divergence_penalty': divergence_penalty,  # NEW: Confidence reduction
            'weather_impact': weather_impact,
            'market_anchor_applied': market_total is not None
        }
    
    def _simulate_single_game(
        self,
        team_a_ppd: float,
        team_b_ppd: float,
        context: Dict[str, Any]
    ) -> tuple:
        """
        Simulate a single NFL game using drive-based physics
        
        Returns:
            (team_a_score, team_b_score) tuple
        """
        team_a_score = 0
        team_b_score = 0
        
        # Determine number of drives (with variance)
        base_drives = self.LEAGUE_AVG_DRIVES_PER_TEAM
        drive_variance = random.gauss(0, 1.2)  # ±1.2 drives std dev
        num_drives_per_team = max(8, min(14, int(base_drives + drive_variance)))
        
        # Simulate drives for each team
        for _ in range(num_drives_per_team):
            team_a_score += self._simulate_drive(team_a_ppd, 'offense')
            team_b_score += self._simulate_drive(team_b_ppd, 'offense')
        
        # Apply defensive regression (pull toward league average)
        team_a_score = self._apply_defensive_regression(team_a_score, num_drives_per_team)
        team_b_score = self._apply_defensive_regression(team_b_score, num_drives_per_team)
        
        # Apply clock management (late-game bleed)
        if abs(team_a_score - team_b_score) > 14:
            # Blowout: fewer late possessions
            reduction = random.uniform(0.0, 0.15)
            team_a_score *= (1.0 - reduction)
            team_b_score *= (1.0 - reduction)
        
        return (round(team_a_score), round(team_b_score))
    
    def _simulate_drive(self, ppd_expected: float, drive_type: str) -> float:
        """
        Simulate a single drive outcome
        
        Args:
            ppd_expected: Expected points per drive for this team
            drive_type: 'offense' or 'defense'
        
        Returns:
            Points scored on this drive (0, 3, or 7 typically)
        """
        # Determine drive outcome based on league probabilities + team efficiency
        # Higher ppd_expected → more likely to score
        
        # Adjust outcome probabilities based on team efficiency
        efficiency_factor = ppd_expected / self.LEAGUE_AVG_POINTS_PER_DRIVE
        
        # Boost scoring outcomes, reduce punt outcomes
        touchdown_prob = self.DRIVE_OUTCOMES['touchdown'] * min(1.5, efficiency_factor)
        field_goal_prob = self.DRIVE_OUTCOMES['field_goal'] * min(1.3, efficiency_factor)
        no_score_prob = 1.0 - touchdown_prob - field_goal_prob
        
        # Roll for outcome
        rand = random.random()
        
        if rand < touchdown_prob:
            return 7.0  # Touchdown + PAT
        elif rand < (touchdown_prob + field_goal_prob):
            return 3.0  # Field goal
        else:
            return 0.0  # No score (punt/turnover/downs)
    
    def _apply_defensive_regression(self, raw_score: float, num_drives: int) -> float:
        """
        Apply defensive mean reversion
        Pulls extreme scores back toward league average
        
        This prevents unrealistic 45+ point games from a hot offensive run
        """
        league_avg_total_points = self.LEAGUE_AVG_POINTS_PER_DRIVE * num_drives
        
        # Calculate regression strength (stronger for larger deviations)
        deviation = abs(raw_score - league_avg_total_points)
        regression_strength = min(0.25, deviation / 20.0)  # Max 25% regression
        
        # Pull score toward league average
        regressed_score = raw_score * (1.0 - regression_strength) + \
                          league_avg_total_points * regression_strength
        
        return regressed_score
    
    def _apply_market_anchor(
        self,
        model_rating: float,
        market_implied_rating: float,
        strength: float = 0.15
    ) -> float:
        """
        Soft anchor to market expectation
        15% weight to market, 85% weight to model
        
        Prevents extreme divergences without ignoring model edge
        """
        return model_rating * (1.0 - strength) + market_implied_rating * strength
    
    def _calculate_weather_impact(self, weather: Dict[str, Any]) -> float:
        """
        Calculate weather impact on scoring
        
        Returns:
            Impact factor (0.0 - 0.3, where 0.3 = 30% scoring reduction)
        """
        impact = 0.0
        
        # Wind impact (passing game disruption)
        wind_speed = weather.get('wind_speed', 0)
        if wind_speed > 15:
            impact += 0.10  # 10% reduction
        if wind_speed > 25:
            impact += 0.10  # Additional 10% (total 20%)
        
        # Precipitation impact
        precip_prob = weather.get('precipitation_probability', 0)
        if precip_prob > 0.5:
            impact += 0.08  # 8% reduction
        
        # Temperature impact (extreme cold)
        temp = weather.get('temperature', 70)
        if temp < 32:
            impact += 0.05  # 5% reduction
        if temp < 20:
            impact += 0.07  # Additional 7% (total 12%)
        
        return min(impact, 0.3)  # Cap at 30% total reduction
    
    def get_volatility_thresholds(self) -> Dict[str, float]:
        """NFL volatility thresholds"""
        return {
            'stable': 8.0,
            'moderate': 12.0
        }
