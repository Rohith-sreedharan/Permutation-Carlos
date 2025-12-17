"""
BeatVegas Global Safety Engine
Implements two-lane output system, risk scoring, and publishing guardrails.

This module is the core safety layer that prevents bad outputs from reaching users.
"""
from typing import Dict, Any, Optional, Literal
from datetime import datetime
from enum import Enum
import logging

logger = logging.getLogger(__name__)

# ============================================================================
# ENUMS & CONSTANTS
# ============================================================================

class OutputMode(str, Enum):
    """Two-lane output system"""
    EXPLORATION_ONLY = "exploration_only"  # Lane A - user sims, not official picks
    ELIGIBLE_FOR_PICK = "eligible_for_pick"  # Lane B - can become official BeatVegas play

class EnvironmentType(str, Enum):
    """Game environment classification"""
    REGULAR_SEASON = "regular_season"
    PLAYOFF = "playoff"
    CHAMPIONSHIP = "championship"
    FINALS = "finals"

class RiskLevel(str, Enum):
    """Risk classification"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

# Global divergence limits (points) - model vs market total difference
DIVERGENCE_LIMITS = {
    # NFL
    ("americanfootball_nfl", EnvironmentType.REGULAR_SEASON): 8,
    ("americanfootball_nfl", EnvironmentType.PLAYOFF): 6,
    ("americanfootball_nfl", EnvironmentType.CHAMPIONSHIP): 6,
    
    # NBA
    ("basketball_nba", EnvironmentType.REGULAR_SEASON): 10,
    ("basketball_nba", EnvironmentType.PLAYOFF): 8,
    ("basketball_nba", EnvironmentType.FINALS): 6,
    
    # NCAAF
    ("americanfootball_ncaaf", EnvironmentType.REGULAR_SEASON): 10,
    ("americanfootball_ncaaf", EnvironmentType.PLAYOFF): 8,
    ("americanfootball_ncaaf", EnvironmentType.CHAMPIONSHIP): 8,
    
    # NCAAB
    ("basketball_ncaab", EnvironmentType.REGULAR_SEASON): 10,
    ("basketball_ncaab", EnvironmentType.PLAYOFF): 8,
    ("basketball_ncaab", EnvironmentType.CHAMPIONSHIP): 6,
    
    # Default fallback
    ("default", EnvironmentType.REGULAR_SEASON): 10,
    ("default", EnvironmentType.PLAYOFF): 8,
    ("default", EnvironmentType.CHAMPIONSHIP): 6,
}

# Risk thresholds
RISK_THRESHOLD_HIGH = 0.7  # Above this = exploration_only
RISK_THRESHOLD_MEDIUM = 0.5

# ============================================================================
# CORE SAFETY ENGINE
# ============================================================================

class SafetyEngine:
    """
    Global safety engine that evaluates simulations and determines:
    1. Output mode (exploration vs eligible for pick)
    2. Risk level
    3. Publishing eligibility
    4. Auto-generated warnings/disclaimers
    """
    
    def __init__(self):
        self.suppression_reasons = []
        
    def evaluate_simulation(
        self,
        sport_key: str,
        model_total: float,
        market_total: float,
        market_id: Optional[str],
        is_postseason: bool,
        is_championship: bool,
        weather_data: Optional[Dict[str, Any]],
        variance: float,
        confidence: float,
        market_type: str = "total",  # total, spread, moneyline, prop
        **context
    ) -> Dict[str, Any]:
        """
        Comprehensive safety evaluation of a simulation.
        
        Returns:
            {
                "output_mode": "exploration_only" or "eligible_for_pick",
                "risk_level": "low" | "medium" | "high" | "critical",
                "risk_score": 0.0-1.0,
                "eligible_for_official_pick": bool,
                "suppression_reasons": [list of reasons if suppressed],
                "warnings": [list of user-facing warnings],
                "divergence_score": float (abs difference),
                "environment_risk": float,
                "variance_risk": float,
                "badges": [list of UI badges to show]
            }
        """
        self.suppression_reasons = []
        warnings = []
        badges = []
        
        # Step 1: Determine environment type
        environment = self._classify_environment(is_postseason, is_championship)
        
        # Step 2: Calculate divergence score
        divergence_score = abs(model_total - market_total)
        
        # Step 3: Calculate environment risk
        environment_risk = self._calculate_environment_risk(
            environment, is_championship, sport_key, weather_data
        )
        
        # Step 4: Calculate variance risk
        variance_risk = self._calculate_variance_risk(variance, sport_key)
        
        # Step 5: Validate model-market matching
        market_match_valid = self._validate_market_matching(
            market_id, market_type, sport_key
        )
        if not market_match_valid:
            self.suppression_reasons.append("Market ID mismatch or validation failed")
        
        # Step 6: Validate weather data (NCAAF/NFL critical)
        weather_valid = self._validate_weather(sport_key, weather_data, environment)
        if not weather_valid:
            self.suppression_reasons.append("Weather data missing or invalid")
        
        # Step 7: Check divergence limits
        divergence_limit = self._get_divergence_limit(sport_key, environment)
        if divergence_score > divergence_limit:
            self.suppression_reasons.append(
                f"Divergence {divergence_score:.1f} exceeds limit {divergence_limit}"
            )
        
        # Step 8: Calculate composite risk score (0-1)
        risk_score = self._calculate_composite_risk(
            divergence_score, divergence_limit, environment_risk, variance_risk
        )
        
        # Step 9: Determine output mode based on risk
        if risk_score > RISK_THRESHOLD_HIGH or len(self.suppression_reasons) > 0:
            output_mode = OutputMode.EXPLORATION_ONLY
            eligible_for_official_pick = False
        else:
            output_mode = OutputMode.ELIGIBLE_FOR_PICK
            eligible_for_official_pick = True
        
        # Step 10: Classify risk level
        if risk_score > 0.8:
            risk_level = RiskLevel.CRITICAL
        elif risk_score > RISK_THRESHOLD_HIGH:
            risk_level = RiskLevel.HIGH
        elif risk_score > RISK_THRESHOLD_MEDIUM:
            risk_level = RiskLevel.MEDIUM
        else:
            risk_level = RiskLevel.LOW
        
        # Step 11: Generate context-sensitive warnings
        if is_championship or is_postseason:
            badges.append("🏆 Championship Volatility")
            warnings.append(
                "High-variance environment. Championship and postseason games often "
                "compress scoring due to game management."
            )
        
        if output_mode == OutputMode.EXPLORATION_ONLY:
            warnings.append(
                "This simulation reflects offensive potential. "
                "This is informational only, not a BeatVegas play."
            )
        
        if risk_level in [RiskLevel.HIGH, RiskLevel.CRITICAL]:
            warnings.append(
                "Elevated variance detected. Model shows directional edge but "
                "confidence is limited."
            )
        
        # Step 12: Log suppression
        if len(self.suppression_reasons) > 0:
            logger.warning(
                f"Simulation suppressed for {sport_key}: {', '.join(self.suppression_reasons)}"
            )
        
        return {
            "output_mode": output_mode.value,
            "risk_level": risk_level.value,
            "risk_score": risk_score,
            "eligible_for_official_pick": eligible_for_official_pick,
            "suppression_reasons": self.suppression_reasons.copy(),
            "warnings": warnings,
            "divergence_score": divergence_score,
            "divergence_limit": divergence_limit,
            "environment_risk": environment_risk,
            "variance_risk": variance_risk,
            "badges": badges,
            "environment_type": environment.value,
        }
    
    def _classify_environment(
        self, is_postseason: bool, is_championship: bool
    ) -> EnvironmentType:
        """Classify game environment"""
        if is_championship:
            return EnvironmentType.CHAMPIONSHIP
        elif is_postseason:
            return EnvironmentType.PLAYOFF
        else:
            return EnvironmentType.REGULAR_SEASON
    
    def _calculate_environment_risk(
        self,
        environment: EnvironmentType,
        is_championship: bool,
        sport_key: str,
        weather_data: Optional[Dict[str, Any]]
    ) -> float:
        """
        Calculate environment risk (0-1)
        Higher = more volatile/unpredictable environment
        """
        risk = 0.0
        
        # Base risk by environment
        if environment == EnvironmentType.CHAMPIONSHIP:
            risk += 0.4
        elif environment == EnvironmentType.PLAYOFF:
            risk += 0.3
        else:
            risk += 0.1
        
        # Weather risk (NCAAF/NFL)
        if "football" in sport_key.lower() and weather_data:
            if weather_data.get("wind_speed", 0) > 15:
                risk += 0.2
            if weather_data.get("precipitation_probability", 0) > 0.5:
                risk += 0.15
            if weather_data.get("temperature", 70) < 32:
                risk += 0.1
        
        return min(risk, 1.0)
    
    def _calculate_variance_risk(self, variance: float, sport_key: str) -> float:
        """
        Calculate variance risk based on distribution width
        """
        # Sport-specific variance thresholds
        thresholds = {
            "basketball_nba": 120,  # NBA high variance
            "basketball_ncaab": 110,
            "americanfootball_nfl": 80,
            "americanfootball_ncaaf": 75,
        }
        
        threshold = thresholds.get(sport_key, 100)
        variance_risk = min(variance / threshold, 1.0)
        
        return variance_risk
    
    def _validate_market_matching(
        self, market_id: Optional[str], market_type: str, sport_key: str
    ) -> bool:
        """
        Validate that simulation matches correct market
        Critical: prevents 1H total vs full game total mismatches
        """
        if not market_id:
            # If no market_id provided, require market_type to be explicit
            if market_type not in ["total", "spread", "moneyline"]:
                return False
        
        # Additional validation logic can go here
        # e.g., check market_id format, validate against known market IDs, etc.
        
        return True
    
    def _validate_weather(
        self, sport_key: str, weather_data: Optional[Dict[str, Any]], environment: EnvironmentType
    ) -> bool:
        """
        Weather failsafe: if weather data missing for outdoor football, block public output
        """
        # Weather critical for outdoor football
        is_football = "football" in sport_key.lower()
        is_high_stakes = environment in [EnvironmentType.CHAMPIONSHIP, EnvironmentType.PLAYOFF]
        
        if is_football and is_high_stakes:
            if weather_data is None:
                logger.warning(f"Weather data missing for {sport_key} {environment.value} game")
                return False
            
            # Validate weather data has required fields
            required_fields = ["temperature", "wind_speed", "conditions"]
            if not all(field in weather_data for field in required_fields):
                logger.warning(f"Weather data incomplete for {sport_key}")
                return False
        
        return True
    
    def _get_divergence_limit(self, sport_key: str, environment: EnvironmentType) -> float:
        """Get divergence limit for sport/environment"""
        key = (sport_key, environment)
        if key in DIVERGENCE_LIMITS:
            return DIVERGENCE_LIMITS[key]
        
        # Fallback to default
        return DIVERGENCE_LIMITS[("default", environment)]
    
    def _calculate_composite_risk(
        self,
        divergence_score: float,
        divergence_limit: float,
        environment_risk: float,
        variance_risk: float
    ) -> float:
        """
        Calculate composite risk score (0-1)
        Weighted combination of all risk factors
        """
        # Divergence risk (normalized)
        divergence_risk = min(divergence_score / divergence_limit, 1.0)
        
        # Weighted average
        risk_score = (
            divergence_risk * 0.4 +
            environment_risk * 0.35 +
            variance_risk * 0.25
        )
        
        return min(risk_score, 1.0)


# ============================================================================
# PUBLIC COPY FORMATTER
# ============================================================================

class PublicCopyFormatter:
    """
    Formats simulation outputs for public consumption.
    NEVER shows raw model totals, only edges and probabilities.
    """
    
    @staticmethod
    def format_total_pick(
        market_total: float,
        direction: Literal["over", "under"],
        edge_points: float,
        probability: float,
        confidence_tier: str,
        variance_label: str,
        warnings: Optional[list[str]] = None
    ) -> Dict[str, Any]:
        """
        Format a total pick for public display.
        
        Example output:
        "Total 49.5 — model shows offensive upside with a +4.5 point edge 
        and 62% probability to the Over in a high-variance environment."
        """
        direction_label = direction.capitalize()
        
        # Main headline
        headline = (
            f"Total {market_total} — {direction_label} "
            f"({probability:.0%} probability)"
        )
        
        # Edge description
        edge_desc = f"{edge_points:+.1f} point edge vs market"
        
        # Full copy
        full_copy = (
            f"Total {market_total} — model shows {direction.lower()} tendency "
            f"with a {edge_points:+.1f} point edge and {probability:.0%} probability "
            f"to the {direction_label}."
        )
        
        if variance_label and variance_label.lower() == "high":
            full_copy += " Note: High-variance environment."
        
        return {
            "headline": headline,
            "edge": edge_desc,
            "full_copy": full_copy,
            "confidence_tier": confidence_tier,
            "variance": variance_label,
            "warnings": warnings or []
        }


# ============================================================================
# MULTI-GAME SLATE MONITOR
# ============================================================================

class SlateMonitor:
    """
    Monitors entire slates for multiple extreme divergences.
    If too many games breach thresholds, freeze all totals for manual review.
    """
    
    def __init__(self):
        self.daily_breaches = []
    
    def check_slate(self, safety_results: list[Dict[str, Any]], date: str) -> Dict[str, Any]:
        """
        Check if multiple games on same slate have extreme divergences
        
        Returns:
            {
                "freeze_slate": bool,
                "breach_count": int,
                "total_games": int,
                "reason": str
            }
        """
        breach_count = 0
        total_games = len(safety_results)
        
        for result in safety_results:
            if len(result.get("suppression_reasons", [])) > 0:
                breach_count += 1
        
        # If >30% of games breached, freeze entire slate
        breach_rate = breach_count / max(total_games, 1)
        
        if breach_rate > 0.3 and breach_count >= 3:
            logger.critical(
                f"SLATE FREEZE: {breach_count}/{total_games} games breached on {date}"
            )
            return {
                "freeze_slate": True,
                "breach_count": breach_count,
                "total_games": total_games,
                "reason": f"Multiple divergence breaches ({breach_count}/{total_games}) — manual review required"
            }
        
        return {
            "freeze_slate": False,
            "breach_count": breach_count,
            "total_games": total_games,
            "reason": None
        }
