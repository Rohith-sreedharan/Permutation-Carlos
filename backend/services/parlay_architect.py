"""
AI Parlay Architect Service
Generates optimized 3-6 leg parlays using Monte Carlo simulation data
"""
import random
from typing import Dict, List, Any, Optional
from datetime import datetime, timezone
from db.mongo import db
from core.monte_carlo_engine import monte_carlo_engine


class ParlayArchitectService:
    """
    AI-driven parlay generation engine
    
    Scans all available games, runs simulations, evaluates EV and correlation,
    then chains together the optimal 3-6 leg parlay based on user preferences.
    """
    
    def __init__(self):
        self.min_confidence = 0.55
        self.max_correlation = 0.3  # Reject parlays with >30% negative correlation
    
    def generate_optimal_parlay(
        self,
        sport_key: str,
        leg_count: int,
        risk_profile: str,
        user_tier: str = "free"
    ) -> Dict[str, Any]:
        """
        Generate AI-optimized parlay
        
        Args:
            sport_key: Sport to focus on (basketball_nba, americanfootball_nfl, etc)
            leg_count: Number of legs (3-6)
            risk_profile: 'high_confidence' | 'balanced' | 'high_volatility'
            user_tier: User's subscription tier
        
        Returns:
            Parlay with legs, odds, EV, confidence, correlation analysis
        """
        
        # Step 1: Get all available games for the sport
        events = list(db.events.find({
            "sport_key": sport_key,
            "commence_time": {"$gt": datetime.now(timezone.utc).isoformat()}
        }).limit(50))
        
        if len(events) < leg_count:
            raise ValueError(f"Insufficient games available. Found {len(events)}, need {leg_count}")
        
        # Step 2: Score all potential legs using simulations
        scored_legs = []
        for event in events:
            # Get or generate simulation
            simulation = db.monte_carlo_simulations.find_one(
                {"event_id": event["event_id"]},
                sort=[("created_at", -1)]
            )
            
            if not simulation:
                # Auto-generate simulation if missing
                from integrations.player_api import get_team_data_with_roster
                team_a = get_team_data_with_roster(event["home_team"], sport_key, True)
                team_b = get_team_data_with_roster(event["away_team"], sport_key, False)
                
                simulation = monte_carlo_engine.run_simulation(
                    event_id=event["event_id"],
                    team_a=team_a,
                    team_b=team_b,
                    market_context={
                        "current_spread": 0,
                        "total_line": 220,
                        "public_betting_pct": 0.5,
                        "sport_key": sport_key
                    },
                    iterations=10000
                )
            
            # Calculate EV for each bet type
            win_prob = simulation.get("team_a_win_probability", 0.5)
            spread_edge = abs(win_prob - 0.5)
            over_prob = simulation.get("over_probability", 0.5)
            total_edge = abs(over_prob - 0.5)
            confidence = simulation.get("confidence_score", 0.5)
            volatility = simulation.get("volatility_index", "MODERATE")
            
            # Score based on risk profile
            if risk_profile == "high_confidence":
                score = confidence * 100 + spread_edge * 50
                min_conf = 0.65
            elif risk_profile == "high_volatility":
                score = spread_edge * 100 + (1.0 if volatility == "HIGH" else 0.5) * 30
                min_conf = 0.45
            else:  # balanced
                score = confidence * 60 + spread_edge * 40
                min_conf = 0.55
            
            # Only include legs that meet minimum confidence
            if confidence >= min_conf:
                # Determine best bet type
                if spread_edge > total_edge:
                    bet_type = "spread"
                    probability = win_prob
                    line = f"{event['home_team']} -5.5" if win_prob > 0.5 else f"{event['away_team']} +5.5"
                else:
                    bet_type = "total"
                    probability = over_prob
                    avg_total = simulation.get("avg_total_score", 220)
                    line = f"Over {avg_total:.1f}" if over_prob > 0.5 else f"Under {avg_total:.1f}"
                
                scored_legs.append({
                    "event_id": event["event_id"],
                    "event": f"{event['away_team']} @ {event['home_team']}",
                    "sport": event["sport_key"],
                    "commence_time": event["commence_time"],
                    "bet_type": bet_type,
                    "line": line,
                    "probability": probability,
                    "confidence": confidence,
                    "ev": (probability - 0.5) * 100,
                    "score": score,
                    "volatility": volatility
                })
        
        # Step 3: Sort by score and select top candidates
        scored_legs.sort(key=lambda x: x["score"], reverse=True)
        candidates = scored_legs[:leg_count * 3]  # Get 3x more than needed for diversity
        
        if len(candidates) < leg_count:
            raise ValueError(f"Insufficient high-quality legs. Found {len(candidates)}, need {leg_count}")
        
        # Step 4: Build optimal chain with correlation check
        selected_legs = self._build_correlated_chain(candidates, leg_count, risk_profile)
        
        # Step 5: Calculate parlay metrics
        parlay_probability = 1.0
        for leg in selected_legs:
            parlay_probability *= leg["probability"]
        
        # Calculate American odds from probability
        if parlay_probability > 0.5:
            american_odds = int(-(parlay_probability / (1 - parlay_probability)) * 100)
        else:
            american_odds = int(((1 - parlay_probability) / parlay_probability) * 100)
        
        # Calculate EV
        implied_odds_decimal = self._american_to_decimal(american_odds)
        fair_odds_decimal = 1 / parlay_probability
        ev_percent = ((fair_odds_decimal / implied_odds_decimal) - 1) * 100
        
        # Correlation analysis
        correlation_score = self._calculate_correlation(selected_legs)
        
        parlay_id = f"parlay_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}_{random.randint(1000, 9999)}"
        
        parlay_data = {
            "parlay_id": parlay_id,
            "sport": sport_key,
            "leg_count": leg_count,
            "risk_profile": risk_profile,
            "legs": selected_legs,
            "parlay_odds": american_odds,
            "parlay_probability": round(parlay_probability, 4),
            "expected_value": round(ev_percent, 2),
            "correlation_score": correlation_score,
            "correlation_impact": self._interpret_correlation(correlation_score),
            "confidence_rating": self._calculate_parlay_confidence(selected_legs),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "user_tier": user_tier
        }
        
        # Store in database
        db.parlay_architect_generations.insert_one(parlay_data)
        
        return parlay_data
    
    def _build_correlated_chain(
        self,
        candidates: List[Dict[str, Any]],
        leg_count: int,
        risk_profile: str
    ) -> List[Dict[str, Any]]:
        """
        Build optimal leg chain considering correlation
        
        Avoid same-game parlays (negative correlation)
        Prefer diversified games (positive correlation through independence)
        """
        selected = []
        used_events = set()
        
        for candidate in candidates:
            if len(selected) >= leg_count:
                break
            
            # Skip if event already used
            if candidate["event_id"] in used_events:
                continue
            
            # Check correlation with existing legs
            if selected:
                correlation = self._check_leg_correlation(candidate, selected)
                if correlation > self.max_correlation:
                    continue  # Skip highly correlated legs
            
            selected.append(candidate)
            used_events.add(candidate["event_id"])
        
        return selected
    
    def _check_leg_correlation(
        self,
        new_leg: Dict[str, Any],
        existing_legs: List[Dict[str, Any]]
    ) -> float:
        """
        Calculate correlation between new leg and existing legs
        
        Same game = high correlation (bad)
        Same sport, different games = low correlation (good)
        """
        max_correlation = 0.0
        
        for leg in existing_legs:
            if leg["event_id"] == new_leg["event_id"]:
                # Same game - very high correlation
                correlation = 0.8
            elif leg["sport"] == new_leg["sport"]:
                # Same sport - low correlation
                correlation = 0.1
            else:
                # Different sports - no correlation
                correlation = 0.0
            
            max_correlation = max(max_correlation, correlation)
        
        return max_correlation
    
    def _calculate_correlation(self, legs: List[Dict[str, Any]]) -> float:
        """
        Calculate overall correlation score for parlay
        
        Lower is better (more independent legs)
        """
        if len(legs) <= 1:
            return 0.0
        
        total_correlation = 0.0
        comparisons = 0
        
        for i in range(len(legs)):
            for j in range(i + 1, len(legs)):
                correlation = self._check_leg_correlation(legs[i], [legs[j]])
                total_correlation += correlation
                comparisons += 1
        
        return round(total_correlation / comparisons, 3) if comparisons > 0 else 0.0
    
    def _interpret_correlation(self, correlation_score: float) -> str:
        """
        Interpret correlation score for user display
        """
        if correlation_score < 0.15:
            return "EXCELLENT - Highly independent legs"
        elif correlation_score < 0.3:
            return "GOOD - Low correlation detected"
        elif correlation_score < 0.5:
            return "MODERATE - Some correlation present"
        else:
            return "HIGH - Consider alternative legs"
    
    def _calculate_parlay_confidence(self, legs: List[Dict[str, Any]]) -> str:
        """
        Calculate overall confidence rating
        """
        avg_confidence = sum(leg["confidence"] for leg in legs) / len(legs)
        
        if avg_confidence >= 0.7:
            return "HIGH"
        elif avg_confidence >= 0.6:
            return "MEDIUM-HIGH"
        elif avg_confidence >= 0.55:
            return "MEDIUM"
        else:
            return "SPECULATIVE"
    
    def _american_to_decimal(self, american_odds: int) -> float:
        """
        Convert American odds to decimal odds
        """
        if american_odds > 0:
            return (american_odds / 100) + 1
        else:
            return (100 / abs(american_odds)) + 1


# Singleton instance
parlay_architect_service = ParlayArchitectService()
