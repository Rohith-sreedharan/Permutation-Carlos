"""
Parlay Construction Agent
Selects high-EV legs and calculates true combined probability with correlation
"""
import asyncio
from typing import List, Dict, Any, Optional
from datetime import datetime
import math
import logging

logger = logging.getLogger(__name__)


class ParlayAgent:
    """
    Parlay Builder Agent
    - Consumes simulation.responses for true probabilities
    - Identifies high Expected Value (EV) legs
    - Calculates correlation between legs
    - Outputs combined hit probability (non-independent)
    """
    
    def __init__(self, event_bus):
        self.bus = event_bus
        self.simulation_cache = {}  # Cache simulation results
        
    async def start(self):
        """Start agent and subscribe to topics"""
        await self.bus.subscribe("parlay.requests", self.handle_parlay_request)
        await self.bus.subscribe("simulation.responses", self.handle_simulation_response)
        logger.info("🎯 Parlay Agent started")
        
    async def handle_simulation_response(self, message: Dict[str, Any]):
        """Cache simulation results for parlay building"""
        data = message.get("data", {})
        event_id = data.get("event_id")
        if event_id:
            self.simulation_cache[event_id] = data
            logger.debug(f"Cached simulation for {event_id}")
            
    async def handle_parlay_request(self, message: Dict[str, Any]):
        """
        Process parlay build request
        Message format:
        {
            "type": "build",
            "legs": [
                {"event_id": "evt_123", "bet_type": "spread", "team": "Lakers", "line": -5.5, "odds": -110},
                {"event_id": "evt_456", "bet_type": "total", "side": "over", "line": 220.5, "odds": -105}
            ],
            "user_id": "user_123"
        }
        """
        try:
            data = message.get("data", {})
            legs = data.get("legs", [])
            user_id = data.get("user_id")
            
            if not legs:
                await self._respond_error(user_id, "No legs provided")
                return
                
            # Calculate EV and select optimal legs
            analyzed_legs = []
            for leg in legs:
                leg_analysis = await self._analyze_leg(leg)
                analyzed_legs.append(leg_analysis)
                
            # Calculate correlation between legs
            correlation_score = await self._calculate_correlation(analyzed_legs)
            
            # Calculate true combined probability
            combined_prob = await self._calculate_combined_probability(
                analyzed_legs, 
                correlation_score
            )
            
            # Calculate risk metrics
            risk_score = await self._calculate_risk_score(analyzed_legs, correlation_score)
            
            # Expected value of parlay
            parlay_odds = self._calculate_parlay_odds(legs)
            expected_value = (combined_prob * parlay_odds) - (1 - combined_prob)
            
            response = {
                "type": "parlay_analysis",
                "user_id": user_id,
                "legs": analyzed_legs,
                "combined_probability": round(combined_prob * 100, 2),
                "correlation_score": round(correlation_score, 3),
                "risk_score": risk_score,
                "expected_value": round(expected_value * 100, 2),
                "parlay_odds": parlay_odds,
                "recommendation": self._get_recommendation(expected_value, risk_score),
                "timestamp": datetime.utcnow().isoformat()
            }
            
            # Publish to parlay.responses
            await self.bus.publish("parlay.responses", response)
            
            # Request risk assessment
            await self.bus.publish("risk.alerts", {
                "type": "parlay_risk_check",
                "user_id": user_id,
                "parlay_data": response
            })
            
            logger.info(f"✅ Parlay analysis complete for user {user_id}: EV={expected_value:.2%}")
            
        except Exception as e:
            logger.error(f"❌ Parlay request failed: {e}")
            # user_id already defined before try block from message.get(\"data\", {}).get(\"user_id\")
            await self._respond_error(None, str(e))
            
    async def _analyze_leg(self, leg: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze single parlay leg for EV
        Returns leg with true probability and EV calculation
        """
        event_id = leg.get("event_id")
        bet_type = leg.get("bet_type")
        odds = leg.get("odds", -110)
        
        # Get simulation data if available
        sim_data = self.simulation_cache.get(event_id, {})
        
        # Extract true probability from simulation
        true_prob = await self._extract_probability(sim_data, leg)
        
        # Convert odds to implied probability
        implied_prob = self._odds_to_probability(odds)
        
        # Calculate Expected Value
        ev = (true_prob * self._odds_to_decimal(odds)) - 1
        
        return {
            **leg,
            "true_probability": round(true_prob, 4),
            "implied_probability": round(implied_prob, 4),
            "expected_value": round(ev * 100, 2),
            "edge": round((true_prob - implied_prob) * 100, 2)
        }
        
    async def _extract_probability(self, sim_data: Dict[str, Any], leg: Dict[str, Any]) -> float:
        """Extract true probability from simulation results"""
        if not sim_data:
            # Fallback: use implied probability
            return self._odds_to_probability(leg.get("odds", -110))
            
        bet_type = leg.get("bet_type")
        
        if bet_type == "moneyline":
            team = leg.get("team")
            win_probs = sim_data.get("win_probabilities", {})
            return win_probs.get(team, 0.5)
            
        elif bet_type == "spread":
            # Use spread distribution
            spread_dist = sim_data.get("spread_distribution", {})
            line = leg.get("line")
            if line is None:
                line = 0.0
            # Sum probabilities of outcomes covering the spread
            return self._calculate_spread_prob(spread_dist, line)
            
        elif bet_type == "total":
            # Use total distribution
            total_dist = sim_data.get("total_distribution", {})
            line = leg.get("line")
            if line is None:
                line = 0.0
            side = leg.get("side", "over")
            return self._calculate_total_prob(total_dist, line, side)
            
        return 0.5  # Default 50/50
        
    def _calculate_spread_prob(self, spread_dist: Dict[str, float], line: float) -> float:
        """Calculate probability of covering spread from distribution"""
        if not spread_dist:
            return 0.5
            
        prob = 0.0
        for margin_str, freq in spread_dist.items():
            try:
                margin = float(margin_str)
                if margin > line:  # Covers spread
                    prob += freq
            except ValueError:
                continue
        return prob
        
    def _calculate_total_prob(self, total_dist: Dict[str, float], line: float, side: str) -> float:
        """Calculate probability of total going over/under"""
        if not total_dist:
            return 0.5
            
        prob = 0.0
        for total_str, freq in total_dist.items():
            try:
                total = float(total_str)
                if (side == "over" and total > line) or (side == "under" and total < line):
                    prob += freq
            except ValueError:
                continue
        return prob
        
    async def _calculate_correlation(self, legs: List[Dict[str, Any]]) -> float:
        """
        Calculate correlation score between legs
        Returns 0.0 (independent) to 1.0 (fully correlated)
        
        Correlation factors:
        - Same game: High correlation (0.7-0.95)
        - Same sport/same day: Medium correlation (0.15-0.30)
        - Cross-sport: Independent (0.0)
        - Opposing sides (e.g., over + team spread): Moderate correlation
        
        PHASE 7 ENHANCEMENT: Cross-Sport Parlay Support
        PHASE 15 ENHANCEMENT: 1H vs Full Game Correlation Detection
        """
        if len(legs) < 2:
            return 0.0
            
        # PHASE 15: Check for 1H vs Full Game conflicts
        first_half_conflict = self._detect_first_half_conflict(legs)
        if first_half_conflict:
            logger.warning(f"⚠️ 1H vs Full Game conflict detected: {first_half_conflict}")
            return first_half_conflict['correlation']
            
        # Check if same game
        event_ids = [leg.get("event_id") for leg in legs]
        if len(set(event_ids)) == 1:
            # Same game parlay - analyze bet type correlations
            return self._calculate_same_game_correlation(legs)
            
        # Different games - check if cross-sport
        sports = [leg.get("sport_key", "unknown") for leg in legs]
        unique_sports = set(sports)
        
        if len(unique_sports) > 1:
            # CROSS-SPORT PARLAY: Generally independent
            return self._calculate_cross_sport_correlation(legs, sports)
        
        # Same sport, different games
        return self._calculate_cross_game_correlation(legs)
    
    def _detect_first_half_conflict(self, legs: List[Dict[str, Any]]) -> Dict[str, Any] | None:
        """
        PHASE 15: Detect contradictory 1H vs Full Game picks
        
        Conflict Examples:
        - 1H Under + Full Game Over = NEGATIVE CORRELATION (second half must be huge)
        - 1H Over + Full Game Over = HIGH CORRELATION (both need high scoring)
        
        Returns:
            Dict with conflict details if found, None otherwise
        """
        # Group legs by event_id and period
        event_periods = {}
        for leg in legs:
            event_id = leg.get("event_id")
            period = leg.get("period", "full")  # "1H", "2H", "full"
            bet_type = leg.get("bet_type")
            side = leg.get("side")  # "over", "under", "home", "away"
            
            if event_id not in event_periods:
                event_periods[event_id] = []
            
            event_periods[event_id].append({
                "period": period,
                "bet_type": bet_type,
                "side": side
            })
        
        # Check for conflicts within same event
        for event_id, periods_data in event_periods.items():
            first_half_picks = [p for p in periods_data if p['period'] == '1H']
            full_game_picks = [p for p in periods_data if p['period'] == 'full']
            
            if first_half_picks and full_game_picks:
                # Analyze total conflicts
                for fh_pick in first_half_picks:
                    for fg_pick in full_game_picks:
                        if fh_pick['bet_type'] == 'total' and fg_pick['bet_type'] == 'total':
                            # 1H Under + Full Game Over = NEGATIVE CORRELATION
                            if fh_pick['side'] == 'under' and fg_pick['side'] == 'over':
                                return {
                                    "type": "1H_FG_CONFLICT",
                                    "event_id": event_id,
                                    "correlation": -0.3,  # Negative correlation (hedging)
                                    "message": "⚠️ 1H Under + Full Game Over = Negative Correlation",
                                    "explanation": "This requires a low-scoring 1H followed by a high-scoring 2H"
                                }
                            
                            # 1H Over + Full Game Over = HIGH CORRELATION
                            elif fh_pick['side'] == 'over' and fg_pick['side'] == 'over':
                                return {
                                    "type": "1H_FG_SUPPORT",
                                    "event_id": event_id,
                                    "correlation": 0.75,  # High positive correlation
                                    "message": "✅ 1H Over + Full Game Over = High Correlation",
                                    "explanation": "Both require sustained high scoring throughout game"
                                }
                            
                            # 1H Over + Full Game Under = CONFLICT
                            elif fh_pick['side'] == 'over' and fg_pick['side'] == 'under':
                                return {
                                    "type": "1H_FG_CONFLICT",
                                    "event_id": event_id,
                                    "correlation": -0.4,  # Strong negative correlation
                                    "message": "🔴 1H Over + Full Game Under = Major Conflict",
                                    "explanation": "This requires high 1H scoring but low total (mathematically unlikely)"
                                }
        
        return None
        
    def _calculate_cross_sport_correlation(
        self, 
        legs: List[Dict[str, Any]], 
        sports: List[str]
    ) -> float:
        """
        Calculate correlation for cross-sport parlays
        
        PHASE 7 LOGIC:
        - Default: 0.0 (independent)
        - Exception 1: City-based bias (e.g., Boston Celtics + Boston Bruins = 0.1)
        - Exception 2: Time overlap (simultaneous games in same city = 0.05)
        
        Args:
            legs: List of parlay legs with team/event info
            sports: List of sport_keys for each leg
        
        Returns:
            Correlation score (0.0-0.2 for cross-sport)
        """
        correlation = 0.0
        
        # Check for city-based correlation
        cities = []
        for leg in legs:
            # Extract city from team name (simplified - production would use team database)
            team = leg.get("team", "")
            for city in ["Boston", "New York", "Los Angeles", "Chicago", 
                        "Philadelphia", "Toronto", "Miami", "Dallas"]:
                if city in team:
                    cities.append(city)
                    break
        
        # If multiple legs from same city across sports
        if len(cities) >= 2 and len(set(cities)) < len(cities):
            correlation = 0.10  # "Boston Super Parlay" effect
            logger.info(f"🏙️ City-based correlation detected: {set(cities)}")
        
        # Check for time overlap (would need game start times)
        # For now, assume games are independent if different sports
        
        return correlation

        
    def _calculate_same_game_correlation(self, legs: List[Dict[str, Any]]) -> float:
        """
        Calculate correlation for same-game parlay
        Examples:
        - Team spread + over total = 0.6 (if team expected to win big)
        - Both team spreads = 0.95 (nearly impossible)
        """
        bet_types = [leg.get("bet_type") for leg in legs]
        
        # Both spreads in same game = very high correlation
        if bet_types.count("spread") >= 2:
            return 0.95
            
        # Spread + total = moderate-high correlation
        if "spread" in bet_types and "total" in bet_types:
            return 0.65
            
        # Moneyline + spread = high correlation
        if "moneyline" in bet_types and "spread" in bet_types:
            return 0.85
            
        return 0.7  # Default same-game correlation
        
    def _calculate_cross_game_correlation(self, legs: List[Dict[str, Any]]) -> float:
        """
        Calculate correlation across different games (same sport)
        Lower correlation than same-game, higher than cross-sport
        """
        # Same sport, different games typically have low but non-zero correlation
        # (e.g., weather affects multiple outdoor games, league-wide scoring trends)
        return 0.15  # Different games, same sport
        
    async def _calculate_combined_probability(
        self, 
        legs: List[Dict[str, Any]], 
        correlation: float
    ) -> float:
        """
        Calculate true combined probability adjusting for correlation
        
        Formula:
        - Independent: P(A and B) = P(A) * P(B)
        - Correlated: Adjusted using correlation factor
        """
        if not legs:
            return 0.0
            
        # Get individual probabilities
        probs = [leg.get("true_probability", 0.5) for leg in legs]
        
        # Start with independent multiplication
        independent_prob = math.prod(probs)
        
        # Adjust for correlation (higher correlation = higher combined prob)
        # When correlation = 0: use independent prob
        # When correlation = 1: use minimum of individual probs
        min_prob = min(probs)
        
        adjusted_prob = (independent_prob * (1 - correlation)) + (min_prob * correlation)
        
        return max(0.0, min(1.0, adjusted_prob))
        
    async def _calculate_risk_score(self, legs: List[Dict[str, Any]], correlation: float) -> str:
        """
        Calculate risk score: LOW, MEDIUM, HIGH, EXTREME
        Based on:
        - Number of legs
        - Correlation
        - Individual leg confidence
        """
        num_legs = len(legs)
        
        # More legs = higher risk
        if num_legs >= 5:
            return "EXTREME"
        elif num_legs >= 4:
            return "HIGH"
            
        # High correlation in parlays = higher risk
        if correlation > 0.8:
            return "HIGH"
            
        # Check if any legs have low confidence
        low_confidence_legs = [leg for leg in legs if leg.get("expected_value", 0) < 0]
        if len(low_confidence_legs) > 0:
            return "HIGH"
            
        if num_legs >= 3:
            return "MEDIUM"
            
        return "LOW"
        
    def _calculate_parlay_odds(self, legs: List[Dict[str, Any]]) -> float:
        """Calculate decimal parlay odds"""
        decimal_odds = [self._odds_to_decimal(leg.get("odds", -110)) for leg in legs]
        return math.prod(decimal_odds)
        
    def _odds_to_probability(self, american_odds: int) -> float:
        """Convert American odds to implied probability"""
        if american_odds > 0:
            return 100 / (american_odds + 100)
        else:
            return abs(american_odds) / (abs(american_odds) + 100)
            
    def _odds_to_decimal(self, american_odds: int) -> float:
        """Convert American odds to decimal odds"""
        if american_odds > 0:
            return (american_odds / 100) + 1
        else:
            return (100 / abs(american_odds)) + 1
            
    def _get_recommendation(self, ev: float, risk_score: str) -> str:
        """Generate recommendation based on EV and risk"""
        if ev < -0.05:
            return "AVOID - Negative expected value"
        elif ev < 0.02:
            return "PASS - Minimal edge"
        elif ev >= 0.10 and risk_score in ["LOW", "MEDIUM"]:
            return "STRONG PLAY - High EV with manageable risk"
        elif ev >= 0.05:
            return "CONSIDER - Positive EV"
        else:
            return "PASS - Risk outweighs reward"
            
    async def _respond_error(self, user_id: Optional[str], error: str):
        """Publish error response"""
        await self.bus.publish("parlay.responses", {
            "type": "error",
            "user_id": user_id,
            "error": error,
            "timestamp": datetime.utcnow().isoformat()
        })
