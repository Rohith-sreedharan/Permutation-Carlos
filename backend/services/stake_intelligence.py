"""
Stake Intelligence Service
===========================

Provides AI-powered CONTEXT on parlay risk and payout potential.

This is NOT betting advice, bankroll management, or stake recommendations.
This is INTERPRETATION of:
- Risk level relative to payout
- Hit probability context
- Expected value math
- Volatility alignment

BeatVegas is a sports intelligence platform - we interpret data, not manage money.
"""
from typing import Dict, Optional, List
from db.mongo import db
import logging

logger = logging.getLogger(__name__)


class StakeIntelligenceService:
    """
    Interprets parlay risk and payout context.
    
    Does NOT recommend stakes, warn about money, or suggest bet sizing.
    Only provides intelligent interpretation of risk vs reward.
    """
    
    def __init__(self):
        self.db = db
    
    def interpret_stake_context(
        self,
        stake_amount: float,
        parlay_confidence: str,  # 'SPECULATIVE', 'MODERATE', 'HIGH'
        parlay_risk: str,  # 'Low', 'Medium', 'High', 'Extreme'
        leg_count: int,
        combined_probability: float,  # 0-1 (e.g., 0.041 = 4.1%)
        total_odds: float,
        potential_payout: float,
        ev_percent: float
    ) -> Dict:
        """
        Interpret parlay context - NOT betting advice.
        
        Args:
            stake_amount: User-entered stake ($)
            parlay_confidence: SPECULATIVE/MODERATE/HIGH
            parlay_risk: Low/Medium/High/Extreme
            leg_count: Number of legs
            combined_probability: Model's true win probability (0-1)
            total_odds: Decimal odds
            potential_payout: Stake × odds
            ev_percent: Expected value percentage
        
        Returns:
            {
                "hit_probability": 4.1,  # Percentage
                "hit_probability_label": "Very Low",
                "risk_level": "High 🔥",
                "ev_interpretation": "Negative",
                "context_message": "This parlay has a longshot payout. High risk, high reward.",
                "payout_context": "Your potential payout of $107.80 represents a high-risk, high-reward scenario.",
                "volatility_alignment": "This payout aligns with the model's volatility rating — this is a pure longshot play."
            }
        """
        hit_probability_pct = combined_probability * 100
        profit = potential_payout - stake_amount
        
        # 1. Hit Probability Label
        hit_label = self._get_hit_probability_label(hit_probability_pct, leg_count)
        
        # 2. Risk Level Display
        risk_display = self._get_risk_level_display(parlay_risk)
        
        # 3. EV Interpretation (math, not advice)
        ev_interpretation = self._interpret_ev(ev_percent)
        
        # 4. Context Message (main summary)
        context_message = self._generate_context_message(
            hit_probability_pct, parlay_risk, parlay_confidence, leg_count
        )
        
        # 5. Payout Context
        payout_context = self._generate_payout_context(
            potential_payout, profit, hit_probability_pct, parlay_risk
        )
        
        # 6. Volatility Alignment
        volatility_alignment = self._generate_volatility_alignment(
            parlay_risk, hit_probability_pct, total_odds
        )
        
        return {
            "hit_probability": round(hit_probability_pct, 1),
            "hit_probability_label": hit_label,
            "risk_level": risk_display,
            "ev_interpretation": ev_interpretation,
            "context_message": context_message,
            "payout_context": payout_context,
            "volatility_alignment": volatility_alignment
        }
    
    def _get_hit_probability_label(self, probability_pct: float, leg_count: int) -> str:
        """
        Label probability in context of leg count.
        
        Returns: "Very Low" | "Low" | "Moderate" | "Good" | "High"
        """
        if leg_count >= 5:
            # 5+ leg parlays are inherently low probability
            if probability_pct < 3:
                return "Very Low"
            elif probability_pct < 8:
                return "Low"
            elif probability_pct < 15:
                return "Moderate"
            else:
                return "Good"
        elif leg_count >= 3:
            # 3-4 leg parlays
            if probability_pct < 5:
                return "Very Low"
            elif probability_pct < 12:
                return "Low"
            elif probability_pct < 20:
                return "Moderate"
            elif probability_pct < 30:
                return "Good"
            else:
                return "High"
        else:
            # 2 leg parlays
            if probability_pct < 15:
                return "Low"
            elif probability_pct < 30:
                return "Moderate"
            elif probability_pct < 45:
                return "Good"
            else:
                return "High"
    
    def _get_risk_level_display(self, risk: str) -> str:
        """Add emoji to risk level for visual context."""
        risk_map = {
            'Low': 'Low ✅',
            'Medium': 'Medium ⚡',
            'High': 'High 🔥',
            'Extreme': 'Extreme 🚨'
        }
        return risk_map.get(risk, risk)
    
    def _interpret_ev(self, ev_percent: float) -> str:
        """
        Interpret EV as pure math - NOT betting advice.
        
        Returns: "Positive" | "Neutral" | "Negative"
        """
        if ev_percent > 5:
            return "Positive"
        elif ev_percent > -5:
            return "Neutral"
        else:
            return "Negative"
    
    def _generate_context_message(
        self,
        hit_probability: float,
        risk: str,
        confidence: str,
        leg_count: int
    ) -> str:
        """
        Generate main context message - interpretation, not advice.
        """
        if hit_probability < 5:
            return f"This parlay has a longshot payout. High risk, high reward."
        elif hit_probability < 12:
            if confidence == 'SPECULATIVE':
                return f"Low hit probability ({hit_probability:.1f}%) — typical for speculative {leg_count}-leg parlays."
            else:
                return f"Hit probability is {hit_probability:.1f}% — moderate for a {leg_count}-leg parlay."
        elif hit_probability < 25:
            return f"Hit probability is {hit_probability:.1f}% — this is less speculative than typical multi-leg parlays."
        else:
            return f"With a model hit chance of {hit_probability:.1f}%, this parlay is relatively solid for a {leg_count}-legger."
    
    def _generate_payout_context(
        self,
        payout: float,
        profit: float,
        hit_probability: float,
        risk: str
    ) -> str:
        """
        Context about payout relative to probability - NOT financial advice.
        """
        if hit_probability < 5:
            return f"Your potential payout of ${payout:.2f} represents a high-risk, high-reward scenario."
        elif hit_probability < 15:
            if risk in ['High', 'Extreme']:
                return f"Your potential return of ${payout:.2f} matches the model's volatility label ({risk})."
            else:
                return f"Potential profit of ${profit:.2f} reflects moderate risk for this probability level."
        else:
            return f"Your potential profit of ${profit:.2f} reflects a balanced risk-to-reward ratio."
    
    def _generate_volatility_alignment(
        self,
        risk: str,
        hit_probability: float,
        total_odds: float
    ) -> str:
        """
        How payout aligns with model's risk assessment - interpretation only.
        """
        if risk == 'Extreme':
            return "This payout is extremely high relative to the probability — proceed for entertainment purposes only."
        elif risk == 'High':
            if total_odds > 10:
                return "This payout aligns with the model's volatility rating — this is a pure longshot play."
            else:
                return "Payout is typical for this level of risk."
        elif risk == 'Medium':
            return "Payout is typical for this level of risk."
        else:  # Low
            return "Payout makes sense relative to the hit probability."


# Singleton instance
stake_intelligence_service = StakeIntelligenceService()
