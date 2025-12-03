"""
Parlay Probability & EV Calculator
===================================

Calculates true parlay probability and expected value for multi-leg parlays.

Key Features:
- Multi-leg probability calculation
- Simple correlation detection
- Expected value (EV%) calculation
- Volatility classification
"""
from typing import Dict, List, Optional, Tuple
import logging
from enum import Enum

logger = logging.getLogger(__name__)


class CorrelationType(str, Enum):
    """Correlation types between parlay legs"""
    POSITIVE = "positive"      # Legs likely to hit together (e.g., both overs)
    NEGATIVE = "negative"      # Legs unlikely to hit together (e.g., opposite spreads)
    NEUTRAL = "neutral"        # No significant correlation


class ParlayCalculatorService:
    """
    Calculate parlay probabilities, EV%, and provide quant context.
    
    This is pure math - no betting advice, just probability calculations.
    """
    
    def calculate_parlay_probability(
        self,
        legs: List[Dict]
    ) -> Dict:
        """
        Calculate multi-leg parlay win probability.
        
        Args:
            legs: List of leg objects, each containing:
                {
                    "event_id": str,
                    "pick_type": str,  # "spread", "total", "moneyline"
                    "selection": str,  # e.g., "Miami -5", "Over 215.5"
                    "true_probability": float,  # 0-1 (from simulation)
                    "american_odds": int,  # e.g., -110
                    "sport": str
                }
        
        Returns:
            {
                "combined_probability": 0.124,  # 12.4%
                "correlation_type": "neutral",
                "correlation_label": "Legs uncorrelated",
                "correlation_adjustment": 0.0,  # -0.05 to +0.05
                "leg_probabilities": [0.52, 0.48, 0.55, 0.95],
                "independent_probability": 0.118,  # Before correlation adjustment
                "notes": "Simple correlation detection applied"
            }
        """
        if not legs or len(legs) == 0:
            return {
                "combined_probability": 0.0,
                "correlation_type": "neutral",
                "correlation_label": "No legs provided",
                "correlation_adjustment": 0.0,
                "leg_probabilities": [],
                "independent_probability": 0.0,
                "notes": "Empty parlay"
            }
        
        # Extract leg probabilities
        leg_probs = [leg.get("true_probability", 0.5) for leg in legs]
        
        # Calculate independent probability (no correlation)
        independent_prob = self._calculate_independent_probability(leg_probs)
        
        # Detect simple correlations
        correlation_type, correlation_adjustment = self._detect_correlation(legs)
        
        # Apply correlation adjustment
        combined_prob = max(0.001, min(0.999, independent_prob + correlation_adjustment))
        
        # Get correlation label
        correlation_label = self._get_correlation_label(correlation_type, len(legs))
        
        return {
            "combined_probability": round(combined_prob, 4),
            "correlation_type": correlation_type,
            "correlation_label": correlation_label,
            "correlation_adjustment": round(correlation_adjustment, 4),
            "leg_probabilities": [round(p, 3) for p in leg_probs],
            "independent_probability": round(independent_prob, 4),
            "notes": "Simple correlation detection applied. Advanced correlation modeling coming soon."
        }
    
    def calculate_parlay_ev(
        self,
        parlay_probability: float,  # 0-1 scale (e.g., 0.124 = 12.4%)
        decimal_odds: float  # e.g., 10.78
    ) -> Dict:
        """
        Calculate Expected Value (EV%) for parlay.
        
        Formula: EV% = (Probability × Payout) - 1
        
        Args:
            parlay_probability: True win probability (0-1)
            decimal_odds: Decimal odds (e.g., 10.78 for +978 American)
        
        Returns:
            {
                "ev_percent": 20.0,  # +20% EV
                "ev_interpretation": "Positive",
                "ev_label": "Strong Edge",
                "expected_return_per_dollar": 1.20,  # For every $1, expect $1.20 back
                "notes": "Pure math - not betting advice"
            }
        """
        # EV% = (Probability × DecimalOdds) - 1
        expected_return = parlay_probability * decimal_odds
        ev_percent = (expected_return - 1) * 100
        
        # Interpretation
        ev_interpretation = self._interpret_ev(ev_percent)
        ev_label = self._get_ev_label(ev_percent)
        
        return {
            "ev_percent": round(ev_percent, 2),
            "ev_interpretation": ev_interpretation,
            "ev_label": ev_label,
            "expected_return_per_dollar": round(expected_return, 3),
            "notes": "Pure math - not betting advice"
        }
    
    def calculate_volatility_level(
        self,
        parlay_probability: float,
        leg_count: int,
        odds: float
    ) -> str:
        """
        Classify parlay volatility: Low, Medium, High, Extreme
        
        Args:
            parlay_probability: Combined probability (0-1)
            leg_count: Number of legs
            odds: Decimal odds
        
        Returns:
            "Low" | "Medium" | "High" | "Extreme"
        """
        # Extreme: <5% probability or 5+ legs with <15% prob
        if parlay_probability < 0.05:
            return "Extreme"
        
        if leg_count >= 5 and parlay_probability < 0.15:
            return "Extreme"
        
        # High: <15% probability or 4+ legs with <25% prob
        if parlay_probability < 0.15:
            return "High"
        
        if leg_count >= 4 and parlay_probability < 0.25:
            return "High"
        
        # Medium: 15-30% probability or 3+ legs
        if parlay_probability < 0.30 or leg_count >= 3:
            return "Medium"
        
        # Low: >30% probability and 2 legs
        return "Low"
    
    # ==================== PRIVATE METHODS ====================
    
    def _calculate_independent_probability(self, probabilities: List[float]) -> float:
        """Multiply all leg probabilities (assumes independence)."""
        result = 1.0
        for prob in probabilities:
            result *= prob
        return result
    
    def _detect_correlation(self, legs: List[Dict]) -> Tuple[str, float]:
        """
        Simple correlation detection between parlay legs.
        
        Returns: (correlation_type, adjustment_value)
        
        Positive correlation (+0.01 to +0.05): Legs likely to hit together
        Negative correlation (-0.01 to -0.05): Legs unlikely to hit together
        Neutral (0.0): No correlation detected
        """
        if len(legs) < 2:
            return (CorrelationType.NEUTRAL, 0.0)
        
        # Check for same-game correlations
        event_ids = [leg.get("event_id") for leg in legs]
        unique_events = set(event_ids)
        
        # If all legs are from same game
        if len(unique_events) == 1:
            return self._detect_same_game_correlation(legs)
        
        # Check for multi-game patterns
        pick_types = [leg.get("pick_type", "").lower() for leg in legs]
        selections = [leg.get("selection", "").lower() for leg in legs]
        
        # All overs = slight positive correlation (pace-up environment)
        if all("over" in sel for sel in selections):
            return (CorrelationType.POSITIVE, 0.01)
        
        # All unders = slight positive correlation (pace-down environment)
        if all("under" in sel for sel in selections):
            return (CorrelationType.POSITIVE, 0.01)
        
        # Mix of overs/unders = neutral
        return (CorrelationType.NEUTRAL, 0.0)
    
    def _detect_same_game_correlation(self, legs: List[Dict]) -> Tuple[str, float]:
        """Detect correlation when all legs are from same game."""
        selections = [leg.get("selection", "").lower() for leg in legs]
        
        # Team total over + game total over = positive correlation
        if "over" in selections[0] and "over" in selections[1]:
            return (CorrelationType.POSITIVE, 0.03)
        
        # Team total under + game total under = positive correlation
        if "under" in selections[0] and "under" in selections[1]:
            return (CorrelationType.POSITIVE, 0.03)
        
        # Spread + total in opposite directions = negative correlation
        # (e.g., Miami -10 + Under 210 = blowout + low scoring)
        has_spread = any("spread" in leg.get("pick_type", "").lower() for leg in legs)
        has_total = any("total" in leg.get("pick_type", "").lower() for leg in legs)
        
        if has_spread and has_total:
            # This is simplified - in reality, need deeper analysis
            return (CorrelationType.NEUTRAL, 0.0)
        
        return (CorrelationType.NEUTRAL, 0.0)
    
    def _get_correlation_label(self, correlation_type: str, leg_count: int) -> str:
        """Get human-readable correlation label."""
        if correlation_type == CorrelationType.POSITIVE:
            return "Legs correlate positively"
        elif correlation_type == CorrelationType.NEGATIVE:
            return "Legs correlate negatively"
        else:
            if leg_count == 2:
                return "Legs uncorrelated"
            return "Legs appear uncorrelated"
    
    def _interpret_ev(self, ev_percent: float) -> str:
        """Interpret EV as Positive/Neutral/Negative."""
        if ev_percent > 5:
            return "Positive"
        elif ev_percent > -5:
            return "Neutral"
        else:
            return "Negative"
    
    def _get_ev_label(self, ev_percent: float) -> str:
        """Get edge label based on EV%."""
        if ev_percent > 15:
            return "Strong Edge"
        elif ev_percent > 5:
            return "Medium Edge"
        elif ev_percent > -5:
            return "Fair Line"
        elif ev_percent > -15:
            return "Slight Disadvantage"
        else:
            return "Significant Disadvantage"


# Singleton instance
parlay_calculator_service = ParlayCalculatorService()
