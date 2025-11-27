"""
Multi-Agent System for BeatVegas
Implements 4 specialized agents that communicate via Event Bus

Agents:
1. Parlay Agent - Detects correlated outcomes
2. Market Agent - Compares simulations vs market odds
3. Risk Agent - Validates bankroll and bet sizing
4. AI Coach Orchestrator - Aggregates agent responses
"""
import asyncio
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
from core.event_bus import in_memory_bus
from core.monte_carlo_engine import monte_carlo_engine

logger = logging.getLogger(__name__)


class ParlayAgent:
    """
    Detects correlation between parlay legs
    
    Positive Correlation: Star player Over + Team Win (helps each other)
    Negative Correlation: Player Under + Team Win (hurts EV)
    """
    
    def __init__(self):
        self.name = "ParlayAgent"
        in_memory_bus.subscribe("parlay.request", self.handle_parlay_request)
        logger.info(f"✅ {self.name} initialized")
        
    async def handle_parlay_request(self, message: Dict[str, Any]):
        """
        Analyze parlay correlation
        Args:
            message: {
                "data": {
                    "request_id": str,
                    "legs": [{"event_id": str, "pick_type": str, "player": str, ...}]
                }
            }
        """
        data = message.get("data", {})
        legs = data.get("legs", [])
        request_id = data.get("request_id", "unknown")
        
        logger.info(f"🔗 {self.name} analyzing {len(legs)} legs for request {request_id}")
        
        # Correlation analysis
        correlation_result = self._analyze_correlation(legs)
        
        # Publish response
        await in_memory_bus.publish("parlay.response", {
            "request_id": request_id,
            "agent": self.name,
            "correlation_grade": correlation_result["grade"],
            "correlation_score": correlation_result["score"],
            "ev_warning": correlation_result["ev_warning"],
            "analysis": correlation_result["analysis"],
            "adjusted_probability": correlation_result["adjusted_prob"],
            "timestamp": datetime.utcnow().isoformat()
        })
        
    def _analyze_correlation(self, legs: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Analyze correlation between legs
        Returns: {grade, score, ev_warning, analysis, adjusted_prob}
        """
        if len(legs) < 2:
            return {
                "grade": "N/A",
                "score": 0.0,
                "ev_warning": False,
                "analysis": "Single leg, no correlation",
                "adjusted_prob": legs[0].get("win_probability", 0.5) if legs else 0.5
            }
        
        # Check if same game parlay
        event_ids = [leg.get("event_id") for leg in legs]
        unique_events = set(event_ids)
        same_game = len(unique_events) < len(legs)
        
        if same_game:
            # HIGH correlation - same game parlay
            correlation_score = 0.75
            ev_warning = False
            
            # Check for positive vs negative correlation
            pick_types = [leg.get("pick_type", "") for leg in legs]
            
            # Detect specific patterns
            has_team_pick = any("moneyline" in pt or "spread" in pt for pt in pick_types)
            has_player_pick = any("prop" in pt or "player" in pt for pt in pick_types)
            
            if has_team_pick and has_player_pick:
                # Star player Over + Team Win = POSITIVE correlation
                correlation_score = 0.80
                analysis = "🔴 HIGH: Same-game parlay with team + player correlation"
                ev_warning = False
            else:
                correlation_score = 0.70
                analysis = "🔴 HIGH: Same-game parlay correlation detected"
                ev_warning = False
                
        elif len(unique_events) == len(legs):
            # Different games - LOW correlation
            # Check for conference matchups
            teams = []
            for leg in legs:
                teams.extend([leg.get("team_a", ""), leg.get("team_b", "")])
            
            # Simple heuristic: if many teams overlap, medium correlation
            if len(set(teams)) < len(teams) * 0.8:
                correlation_score = 0.50
                analysis = "🟡 MEDIUM: Related conference games"
                ev_warning = False
            else:
                correlation_score = 0.20
                analysis = "🟢 LOW: Independent games"
                ev_warning = False
        else:
            # Some overlap - MEDIUM correlation
            correlation_score = 0.50
            analysis = "🟡 MEDIUM: Some game overlap detected"
            ev_warning = False
        
        # Calculate naive probability
        naive_prob = 1.0
        for leg in legs:
            naive_prob *= leg.get("win_probability", 0.5)
        
        # Adjust for correlation (higher correlation = lower true probability)
        correlation_penalty = correlation_score * 0.25
        adjusted_prob = naive_prob * (1 - correlation_penalty)
        
        # Determine grade
        if correlation_score >= 0.70:
            grade = "HIGH"
        elif correlation_score >= 0.40:
            grade = "MEDIUM"
        elif correlation_score >= 0.20:
            grade = "LOW"
        else:
            grade = "NEGATIVE"
            ev_warning = True
            analysis += " ⚠️ Anti-correlated legs reduce EV"
        
        return {
            "grade": grade,
            "score": round(correlation_score, 2),
            "ev_warning": ev_warning,
            "analysis": analysis,
            "adjusted_prob": round(adjusted_prob, 4),
            "naive_prob": round(naive_prob, 4),
            "same_game_parlay": same_game
        }


class MarketAgent:
    """
    Compares simulation probabilities vs market odds
    Detects value bets and closing line value (CLV)
    """
    
    def __init__(self):
        self.name = "MarketAgent"
        in_memory_bus.subscribe("simulation.completed", self.handle_simulation)
        logger.info(f"✅ {self.name} initialized")
        
    async def handle_simulation(self, message: Dict[str, Any]):
        """
        Compare simulation results vs market odds
        """
        data = message.get("data", {})
        event_id = data.get("event_id")
        simulation = data.get("simulation")
        market_odds = data.get("market_odds", {})
        
        if not simulation or not market_odds:
            return
        
        logger.info(f"📊 {self.name} analyzing market for event {event_id}")
        
        # Compare probabilities
        sim_win_prob = simulation.get("win_probability", 0.5)
        market_ml = market_odds.get("moneyline_home", 2.0)
        market_implied = 1 / market_ml if market_ml > 0 else 0.5
        
        edge = (sim_win_prob - market_implied) * 100
        
        # Publish market analysis
        await in_memory_bus.publish("market.analysis", {
            "event_id": event_id,
            "agent": self.name,
            "sim_probability": sim_win_prob,
            "market_implied": market_implied,
            "edge_percent": round(edge, 2),
            "value_bet": abs(edge) > 5.0,
            "recommendation": "BET" if edge > 5.0 else "PASS",
            "timestamp": datetime.utcnow().isoformat()
        })


class RiskAgent:
    """
    Validates bankroll health and bet sizing
    Implements Kelly Criterion
    """
    
    def __init__(self):
        self.name = "RiskAgent"
        in_memory_bus.subscribe("user.bet_attempt", self.handle_bet_attempt)
        logger.info(f"✅ {self.name} initialized")
        
    async def handle_bet_attempt(self, message: Dict[str, Any]):
        """
        Validate bet sizing and bankroll
        """
        data = message.get("data", {})
        user_id = data.get("user_id")
        bankroll = data.get("bankroll", 1000.0)
        stake = data.get("stake", 0.0)
        win_prob = data.get("win_probability", 0.5)
        odds = data.get("odds", 2.0)
        
        logger.info(f"🛡️ {self.name} validating bet for user {user_id}")
        
        # Kelly Criterion
        kelly_fraction = self._calculate_kelly(win_prob, odds)
        recommended_stake = bankroll * kelly_fraction
        
        # Risk assessment
        stake_percent = (stake / bankroll) * 100
        
        risk_level = "LOW"
        warnings = []
        
        if stake_percent > 10:
            risk_level = "HIGH"
            warnings.append("⚠️ Stake exceeds 10% of bankroll")
        elif stake_percent > 5:
            risk_level = "MEDIUM"
            warnings.append("⚡ Stake exceeds 5% of bankroll")
        
        if stake > recommended_stake * 1.5:
            warnings.append(f"⚠️ Over-betting. Kelly suggests ${recommended_stake:.2f}")
        
        # Publish risk alert
        await in_memory_bus.publish("risk.alert", {
            "user_id": user_id,
            "agent": self.name,
            "risk_level": risk_level,
            "recommended_stake": round(recommended_stake, 2),
            "kelly_fraction": round(kelly_fraction, 4),
            "warnings": warnings,
            "approved": stake <= recommended_stake * 2,  # Max 2x Kelly
            "timestamp": datetime.utcnow().isoformat()
        })
        
    def _calculate_kelly(self, win_prob: float, odds: float) -> float:
        """
        Kelly Criterion: f = (bp - q) / b
        where b = odds - 1, p = win_prob, q = 1 - p
        """
        b = odds - 1
        p = win_prob
        q = 1 - p
        
        kelly = (b * p - q) / b
        
        # Fractional Kelly (25% for safety)
        return max(0, min(kelly * 0.25, 0.10))  # Cap at 10%


class AICoachOrchestrator:
    """
    Orchestrator Agent - Aggregates responses from all agents
    This is the only agent exposed to API endpoints
    """
    
    def __init__(self):
        self.name = "AICoachOrchestrator"
        self.pending_requests: Dict[str, Dict[str, Any]] = {}
        
        # Subscribe to all agent responses
        in_memory_bus.subscribe("parlay.response", self.collect_response)
        in_memory_bus.subscribe("market.analysis", self.collect_response)
        in_memory_bus.subscribe("risk.alert", self.collect_response)
        
        logger.info(f"✅ {self.name} initialized")
        
    async def request_parlay_analysis(self, request_id: str, legs: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Request parlay analysis and wait for response
        """
        # Initialize request tracking
        self.pending_requests[request_id] = {
            "status": "pending",
            "responses": {},
            "timestamp": datetime.utcnow().isoformat()
        }
        
        # Publish request
        await in_memory_bus.publish("parlay.request", {
            "request_id": request_id,
            "legs": legs
        })
        
        # Wait for response (with timeout)
        max_wait = 5.0  # seconds
        elapsed = 0.0
        interval = 0.1
        
        while elapsed < max_wait:
            if "parlay" in self.pending_requests[request_id].get("responses", {}):
                response = self.pending_requests[request_id]["responses"]["parlay"]
                del self.pending_requests[request_id]
                return response
            
            await asyncio.sleep(interval)
            elapsed += interval
        
        # Timeout
        del self.pending_requests[request_id]
        return {"error": "Timeout waiting for parlay analysis"}
        
    async def collect_response(self, message: Dict[str, Any]):
        """
        Collect agent responses
        """
        data = message.get("data", {})
        request_id = data.get("request_id")
        agent = data.get("agent", "unknown")
        
        if request_id and request_id in self.pending_requests:
            response_type = "parlay" if "Parlay" in agent else "market" if "Market" in agent else "risk"
            self.pending_requests[request_id]["responses"][response_type] = data
            logger.debug(f"📥 {self.name} collected {response_type} response for {request_id}")


# Initialize all agents
parlay_agent = ParlayAgent()
market_agent = MarketAgent()
risk_agent = RiskAgent()
ai_coach = AICoachOrchestrator()

logger.info("🤖 Multi-Agent System initialized")
