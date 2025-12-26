"""
AI Analyzer - Sport-Specific Context Builders
Builds context flags and reason codes per sport based on game state.
"""

from typing import List, Dict, Any, Optional
from .ai_analyzer_schemas import (
    ContextFlags,
    ReasonCode,
    VolatilityLevel,
    ConfidenceFlag
)


class SportContextBuilder:
    """
    Base class for sport-specific context building.
    Extracts relevant flags from game state for AI explanation.
    """
    
    def build_context(self, game_data: Dict[str, Any]) -> ContextFlags:
        """
        Build ContextFlags from game data.
        
        Args:
            game_data: Game state dict from database
        
        Returns:
            ContextFlags with sport-specific fields populated
        """
        raise NotImplementedError("Subclass must implement build_context")
    
    def extract_reason_codes(
        self,
        game_data: Dict[str, Any],
        metrics: Dict[str, Any]
    ) -> List[ReasonCode]:
        """
        Extract reason codes from game state and metrics.
        
        Args:
            game_data: Game state dict
            metrics: Model metrics dict
        
        Returns:
            List of ReasonCode enums
        """
        raise NotImplementedError("Subclass must implement extract_reason_codes")


class NBAContextBuilder(SportContextBuilder):
    """NBA-specific context builder"""
    
    def build_context(self, game_data: Dict[str, Any]) -> ContextFlags:
        """Build NBA context flags"""
        
        injury_status = self._get_injury_status(game_data)
        
        return ContextFlags(
            injury_status=injury_status,
            back_to_back=game_data.get("back_to_back", False),
            rest_disparity=game_data.get("rest_disparity"),
            late_injury_risk=game_data.get("late_injury_risk", "UNKNOWN"),
            blowout_risk_flag=game_data.get("blowout_risk_flag", "NONE"),
            pace_flag=game_data.get("pace_flag", "NORMAL"),
            minutes_fatigue_flag=game_data.get("minutes_fatigue_flag", "UNKNOWN")
        )
    
    def extract_reason_codes(
        self,
        game_data: Dict[str, Any],
        metrics: Dict[str, Any]
    ) -> List[ReasonCode]:
        """Extract NBA-specific reason codes"""
        
        codes = []
        
        # Market-based codes
        if metrics.get("edge_pts", 0) > 6:
            codes.append(ReasonCode.MARKET_GAP_DETECTED)
        
        if metrics.get("clv_forecast_pct", 0) > 0.2:
            codes.append(ReasonCode.CLV_FORECAST_POSITIVE)
        
        # Volatility codes
        volatility = metrics.get("volatility", "MEDIUM")
        if volatility == "HIGH":
            codes.append(ReasonCode.VOLATILITY_HIGH)
        elif volatility == "EXTREME":
            codes.append(ReasonCode.VOLATILITY_EXTREME)
        
        # Confidence codes
        confidence = metrics.get("confidence_flag", "UNKNOWN")
        if confidence == "UNSTABLE":
            codes.append(ReasonCode.CONFIDENCE_UNSTABLE)
        elif confidence == "DIVERGENT":
            codes.append(ReasonCode.CONFIDENCE_DIVERGENT)
        elif confidence == "STABLE":
            codes.append(ReasonCode.CONFIDENCE_STABLE)
        
        # Context codes
        if game_data.get("back_to_back"):
            codes.append(ReasonCode.FATIGUE_RISK_ELEVATED)
        
        if self._has_injury_impact(game_data):
            codes.append(ReasonCode.INJURY_IMPACT_DETECTED)
        
        if game_data.get("blowout_risk_flag") == "HIGH":
            codes.append(ReasonCode.BLOWOUT_RISK_HIGH)
        
        if game_data.get("pace_flag") == "EXTREME_MISMATCH":
            codes.append(ReasonCode.PACE_MISMATCH_DETECTED)
        
        # Signal quality
        if len(codes) >= 4 and volatility in ["LOW", "MEDIUM"]:
            codes.append(ReasonCode.SIGNAL_QUALITY_HIGH)
        elif volatility == "EXTREME":
            codes.append(ReasonCode.SIGNAL_QUALITY_LOW)
        
        return codes[:10]  # Max 10 codes
    
    def _get_injury_status(self, game_data: Dict[str, Any]) -> str:
        """Determine injury status: CLEAR | MINOR | SIGNIFICANT | UNKNOWN"""
        injuries = game_data.get("injuries", [])
        
        if not injuries:
            return "CLEAR"
        
        significant_injuries = [
            inj for inj in injuries 
            if inj.get("impact") == "SIGNIFICANT"
        ]
        
        if significant_injuries:
            return "SIGNIFICANT"
        
        if len(injuries) > 0:
            return "MINOR"
        
        return "UNKNOWN"
    
    def _has_injury_impact(self, game_data: Dict[str, Any]) -> bool:
        """Check if injuries have meaningful impact"""
        return self._get_injury_status(game_data) in ["SIGNIFICANT", "MINOR"]


class NFLContextBuilder(SportContextBuilder):
    """NFL-specific context builder"""
    
    def build_context(self, game_data: Dict[str, Any]) -> ContextFlags:
        """Build NFL context flags"""
        
        return ContextFlags(
            injury_status=self._get_injury_status(game_data),
            qb_status=game_data.get("qb_status", "UNKNOWN"),
            weather_severity=game_data.get("weather_severity", "NONE"),
            weather_flag=game_data.get("weather_flag", "N/A"),
            key_number_flag=self._is_near_key_number(game_data),
            injury_cluster_flag=self._has_injury_cluster(game_data),
            late_news_risk=game_data.get("late_news_risk", False)
        )
    
    def extract_reason_codes(
        self,
        game_data: Dict[str, Any],
        metrics: Dict[str, Any]
    ) -> List[ReasonCode]:
        """Extract NFL-specific reason codes"""
        
        codes = []
        
        # Market codes
        if metrics.get("edge_pts", 0) > 4:
            codes.append(ReasonCode.MARKET_GAP_DETECTED)
        
        if metrics.get("clv_forecast_pct", 0) > 0.2:
            codes.append(ReasonCode.CLV_FORECAST_POSITIVE)
        
        # Volatility
        volatility = metrics.get("volatility", "MEDIUM")
        if volatility == "HIGH":
            codes.append(ReasonCode.VOLATILITY_HIGH)
        elif volatility == "EXTREME":
            codes.append(ReasonCode.VOLATILITY_EXTREME)
        
        # Confidence
        confidence = metrics.get("confidence_flag", "UNKNOWN")
        if confidence == "UNSTABLE":
            codes.append(ReasonCode.CONFIDENCE_UNSTABLE)
        elif confidence == "STABLE":
            codes.append(ReasonCode.CONFIDENCE_STABLE)
        
        # Context
        qb_status = game_data.get("qb_status", "UNKNOWN")
        if qb_status in ["QUESTIONABLE", "OUT"]:
            codes.append(ReasonCode.QB_STATUS_IMPACT)
        
        if game_data.get("weather_severity") in ["SIGNIFICANT", "EXTREME"]:
            codes.append(ReasonCode.WEATHER_IMPACT_DETECTED)
        
        if self._is_near_key_number(game_data):
            codes.append(ReasonCode.KEY_NUMBER_PROXIMITY)
        
        if game_data.get("late_news_risk"):
            codes.append(ReasonCode.LATE_NEWS_RISK)
        
        if self._has_injury_cluster(game_data):
            codes.append(ReasonCode.INJURY_IMPACT_DETECTED)
        
        return codes[:10]
    
    def _get_injury_status(self, game_data: Dict[str, Any]) -> str:
        """Determine injury status"""
        injuries = game_data.get("injuries", [])
        
        if not injuries:
            return "CLEAR"
        
        significant = [inj for inj in injuries if inj.get("impact") == "SIGNIFICANT"]
        
        if significant:
            return "SIGNIFICANT"
        
        if len(injuries) > 0:
            return "MINOR"
        
        return "UNKNOWN"
    
    def _is_near_key_number(self, game_data: Dict[str, Any]) -> bool:
        """Check if spread near key numbers (3, 7, 10)"""
        spread = abs(game_data.get("current_spread", 0))
        key_numbers = [3, 7, 10]
        
        for key_num in key_numbers:
            if abs(spread - key_num) <= 0.5:
                return True
        
        return False
    
    def _has_injury_cluster(self, game_data: Dict[str, Any]) -> bool:
        """Check if multiple significant injuries"""
        injuries = game_data.get("injuries", [])
        significant = [inj for inj in injuries if inj.get("impact") == "SIGNIFICANT"]
        return len(significant) >= 2


class NCAABContextBuilder(SportContextBuilder):
    """NCAAB-specific context builder"""
    
    def build_context(self, game_data: Dict[str, Any]) -> ContextFlags:
        """Build NCAAB context flags"""
        
        return ContextFlags(
            injury_status=self._get_injury_status(game_data),
            blowout_noise_flag=game_data.get("blowout_noise_flag", False),
            scheme_variance_flag=game_data.get("scheme_variance_flag", "NORMAL"),
            roster_uncertainty=game_data.get("roster_uncertainty", "LOW"),
            volatility_band=game_data.get("volatility_band", "NORMAL")
        )
    
    def extract_reason_codes(
        self,
        game_data: Dict[str, Any],
        metrics: Dict[str, Any]
    ) -> List[ReasonCode]:
        """Extract NCAAB-specific reason codes"""
        
        codes = []
        
        # Market
        if metrics.get("edge_pts", 0) > 5:
            codes.append(ReasonCode.MARKET_GAP_DETECTED)
        
        # Volatility
        volatility = metrics.get("volatility", "MEDIUM")
        if volatility == "HIGH":
            codes.append(ReasonCode.VOLATILITY_HIGH)
        elif volatility == "EXTREME":
            codes.append(ReasonCode.VOLATILITY_EXTREME)
        
        # Confidence
        confidence = metrics.get("confidence_flag", "UNKNOWN")
        if confidence == "UNSTABLE":
            codes.append(ReasonCode.CONFIDENCE_UNSTABLE)
        
        # Context
        if game_data.get("blowout_noise_flag"):
            codes.append(ReasonCode.BLOWOUT_RISK_HIGH)
        
        if game_data.get("roster_uncertainty") in ["MEDIUM", "HIGH"]:
            codes.append(ReasonCode.LINEUP_UNCERTAINTY)
        
        if game_data.get("volatility_band") == "EXTREME":
            codes.append(ReasonCode.VARIANCE_ELEVATED)
        
        return codes[:10]
    
    def _get_injury_status(self, game_data: Dict[str, Any]) -> str:
        """Determine injury status"""
        injuries = game_data.get("injuries", [])
        if not injuries:
            return "CLEAR"
        if len(injuries) > 2:
            return "SIGNIFICANT"
        return "MINOR"


class NCAAFContextBuilder(NCAABContextBuilder):
    """NCAAF-specific context builder (similar to NCAAB with QB focus)"""
    
    def build_context(self, game_data: Dict[str, Any]) -> ContextFlags:
        """Build NCAAF context flags"""
        
        base_context = super().build_context(game_data)
        base_context.qb_status = game_data.get("qb_status", "UNKNOWN")
        base_context.motivation_flags = game_data.get("motivation_flags", [])
        
        return base_context
    
    def extract_reason_codes(
        self,
        game_data: Dict[str, Any],
        metrics: Dict[str, Any]
    ) -> List[ReasonCode]:
        """Extract NCAAF-specific reason codes"""
        
        codes = super().extract_reason_codes(game_data, metrics)
        
        # Add QB-specific codes
        qb_status = game_data.get("qb_status", "UNKNOWN")
        if qb_status in ["QUESTIONABLE", "OUT"]:
            codes.append(ReasonCode.QB_STATUS_IMPACT)
        
        return codes[:10]


class MLBContextBuilder(SportContextBuilder):
    """MLB-specific context builder"""
    
    def build_context(self, game_data: Dict[str, Any]) -> ContextFlags:
        """Build MLB context flags"""
        
        return ContextFlags(
            injury_status=self._get_injury_status(game_data),
            pitcher_confirmed=game_data.get("pitcher_confirmed", "UNKNOWN"),
            lineup_confirmed=game_data.get("lineup_confirmed", False),
            bullpen_fatigue_flag=game_data.get("bullpen_fatigue_flag", "NONE"),
            weather_park_flag=game_data.get("weather_park_flag", "NEUTRAL")
        )
    
    def extract_reason_codes(
        self,
        game_data: Dict[str, Any],
        metrics: Dict[str, Any]
    ) -> List[ReasonCode]:
        """Extract MLB-specific reason codes"""
        
        codes = []
        
        # Market
        if metrics.get("edge_pts", 0) > 0.15:  # MLB uses runs, lower threshold
            codes.append(ReasonCode.MARKET_GAP_DETECTED)
        
        # Volatility
        volatility = metrics.get("volatility", "MEDIUM")
        if volatility == "HIGH":
            codes.append(ReasonCode.VOLATILITY_HIGH)
        
        # Confidence
        confidence = metrics.get("confidence_flag", "UNKNOWN")
        if confidence == "STABLE":
            codes.append(ReasonCode.CONFIDENCE_STABLE)
        elif confidence == "UNSTABLE":
            codes.append(ReasonCode.CONFIDENCE_UNSTABLE)
        
        # Context
        if game_data.get("pitcher_confirmed") == "ACE_VS_WEAK":
            codes.append(ReasonCode.PITCHER_EDGE_DETECTED)
        
        if not game_data.get("lineup_confirmed"):
            codes.append(ReasonCode.LINEUP_UNCERTAINTY)
        
        if game_data.get("bullpen_fatigue_flag") in ["MODERATE", "HIGH"]:
            codes.append(ReasonCode.FATIGUE_RISK_ELEVATED)
        
        if game_data.get("weather_park_flag") in ["WIND_SIGNIFICANT", "COORS"]:
            codes.append(ReasonCode.WEATHER_IMPACT_DETECTED)
        
        return codes[:10]
    
    def _get_injury_status(self, game_data: Dict[str, Any]) -> str:
        """Determine injury status"""
        pitcher_status = game_data.get("pitcher_confirmed", "UNKNOWN")
        if pitcher_status in ["SCRATCHED", "UNCERTAIN"]:
            return "SIGNIFICANT"
        
        injuries = game_data.get("injuries", [])
        if len(injuries) > 3:
            return "SIGNIFICANT"
        elif len(injuries) > 0:
            return "MINOR"
        
        return "CLEAR"


class NHLContextBuilder(SportContextBuilder):
    """NHL-specific context builder"""
    
    def build_context(self, game_data: Dict[str, Any]) -> ContextFlags:
        """Build NHL context flags"""
        
        return ContextFlags(
            injury_status=self._get_injury_status(game_data),
            goalie_confirmed=game_data.get("goalie_confirmed", "UNKNOWN"),
            back_to_back=game_data.get("back_to_back", False),
            travel=game_data.get("travel", False),
            high_randomness_flag=game_data.get("high_randomness_flag", False),
            overtime_variance_flag=game_data.get("overtime_variance_flag", False)
        )
    
    def extract_reason_codes(
        self,
        game_data: Dict[str, Any],
        metrics: Dict[str, Any]
    ) -> List[ReasonCode]:
        """Extract NHL-specific reason codes"""
        
        codes = []
        
        # Market
        if metrics.get("edge_pts", 0) > 0.3:  # NHL uses goals, very low threshold
            codes.append(ReasonCode.MARKET_GAP_DETECTED)
        
        # Volatility
        volatility = metrics.get("volatility", "MEDIUM")
        if volatility in ["HIGH", "EXTREME"]:
            codes.append(ReasonCode.VOLATILITY_HIGH)
        
        # Confidence
        confidence = metrics.get("confidence_flag", "UNKNOWN")
        if confidence == "UNSTABLE":
            codes.append(ReasonCode.CONFIDENCE_UNSTABLE)
        
        # Context
        goalie_status = game_data.get("goalie_confirmed", "UNKNOWN")
        if goalie_status == "BACKUP":
            codes.append(ReasonCode.GOALIE_VARIANCE_HIGH)
        
        if game_data.get("back_to_back"):
            codes.append(ReasonCode.FATIGUE_RISK_ELEVATED)
        
        if game_data.get("high_randomness_flag"):
            codes.append(ReasonCode.VARIANCE_ELEVATED)
        
        if game_data.get("overtime_variance_flag"):
            codes.append(ReasonCode.VARIANCE_ELEVATED)
        
        return codes[:10]
    
    def _get_injury_status(self, game_data: Dict[str, Any]) -> str:
        """Determine injury status"""
        goalie_status = game_data.get("goalie_confirmed", "UNKNOWN")
        if goalie_status in ["OUT", "EMERGENCY_BACKUP"]:
            return "SIGNIFICANT"
        
        injuries = game_data.get("injuries", [])
        if len(injuries) > 2:
            return "SIGNIFICANT"
        elif len(injuries) > 0:
            return "MINOR"
        
        return "CLEAR"


# Factory function to get appropriate builder
def get_context_builder(sport: str) -> SportContextBuilder:
    """
    Get sport-specific context builder.
    
    Args:
        sport: Sport identifier (NBA, NFL, NCAAB, NCAAF, MLB, NHL)
    
    Returns:
        SportContextBuilder instance
    
    Raises:
        ValueError: If sport not supported
    """
    builders = {
        "NBA": NBAContextBuilder,
        "NFL": NFLContextBuilder,
        "NCAAB": NCAABContextBuilder,
        "NCAAF": NCAAFContextBuilder,
        "MLB": MLBContextBuilder,
        "NHL": NHLContextBuilder
    }
    
    if sport not in builders:
        raise ValueError(f"Unsupported sport: {sport}")
    
    return builders[sport]()
