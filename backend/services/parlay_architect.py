"""
AI Parlay Architect Service
Generates optimized 3-6 leg parlays using Monte Carlo simulation data
"""
import random
from typing import Dict, List, Any, Optional
from datetime import datetime, timezone
from db.mongo import db
from core.monte_carlo_engine import monte_carlo_engine
from utils.mongo_helpers import sanitize_mongo_doc


class ParlayArchitectService:
    """
    AI-driven parlay generation engine
    
    Scans all available games, runs simulations, evaluates EV and correlation,
    then chains together the optimal 3-6 leg parlay based on user preferences.
    """
    
    def __init__(self):
        self.max_correlation = 0.3  # Reject parlays with >30% negative correlation
        
        # Tiered leg quality thresholds
        self.tier_thresholds = {
            "A": {  # Premium Confidence
                "confidence": 0.60,
                "ev": 5.0,
                "stability": 40
            },
            "B": {  # Medium Confidence
                "confidence": 0.52,
                "ev": 1.0,
                "stability": 20
            },
            "C": {  # Value Edge (Speculative)
                "confidence": 0.48,
                "ev": 0.0,
                "stability": 10
            }
        }
    
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
                from integrations.odds_api import extract_market_lines
                team_a = get_team_data_with_roster(event["home_team"], sport_key, True)
                team_b = get_team_data_with_roster(event["away_team"], sport_key, False)
                
                # Extract real market lines from bookmakers
                market_context = extract_market_lines(event)
                
                simulation = monte_carlo_engine.run_simulation(
                    event_id=event["event_id"],
                    team_a=team_a,
                    team_b=team_b,
                    market_context=market_context,
                    iterations=10000
                )
            
            # Calculate EV for each bet type
            win_prob = simulation.get("team_a_win_probability", 0.5)
            spread_edge = abs(win_prob - 0.5)
            over_prob = simulation.get("over_probability", 0.5)
            total_edge = abs(over_prob - 0.5)
            
            # Extract confidence from outcome or root level, with fallback
            outcome = simulation.get("outcome", {})
            raw_confidence = outcome.get("confidence", simulation.get("confidence_score", 0.65))
            
            # Normalize confidence to usable range
            if raw_confidence < 0.30:
                confidence = 0.40 + (raw_confidence / 0.30) * 0.15  # Map 0-0.30 to 0.40-0.55
            else:
                confidence = raw_confidence
            
            volatility = simulation.get("volatility", simulation.get("volatility_index", "MODERATE"))
            stability = confidence * 100  # Convert to stability score
            
            # Determine best bet type FIRST to get probability
            if spread_edge > total_edge:
                bet_type = "spread"
                probability = win_prob
                line = f"{event['home_team']} -5.5" if win_prob > 0.5 else f"{event['away_team']} +5.5"
            else:
                bet_type = "total"
                probability = over_prob
                avg_total = simulation.get("avg_total_score", 220)
                line = f"Over {avg_total:.1f}" if over_prob > 0.5 else f"Under {avg_total:.1f}"
            
            # Calculate EV percentage
            ev = (probability - 0.5) * 100
            
            # Classify leg into quality tier
            tier = self._classify_leg_tier(confidence, ev, stability)
            
            scored_legs.append({
                "event_id": event["event_id"],
                "event": f"{event['away_team']} @ {event['home_team']}",
                "sport": event["sport_key"],
                "commence_time": event["commence_time"],
                "bet_type": bet_type,
                "line": line,
                "probability": probability,
                "confidence": confidence,
                "ev": ev,
                "stability": stability,
                "tier": tier,
                "score": confidence * 60 + ev * 40,  # Combined scoring
                "volatility": volatility
            })
        
        # Step 3: Use tiered fallback system to select legs
        selected_legs = self._select_legs_with_tiered_fallback(
            scored_legs=scored_legs,
            leg_count=leg_count,
            risk_profile=risk_profile
        )
        
        # Check if we have enough legs (minimum 2 for any parlay)
        if len(selected_legs["legs"]) < 2:
            raise ValueError(
                f"⚠️ Unable to generate parlay - insufficient quality legs.\n\n"
                f"📊 Results:\n"
                f"   • Total events scanned: {len(events)}\n"
                f"   • Tier A (Premium): {len([l for l in scored_legs if l['tier'] == 'A'])}\n"
                f"   • Tier B (Medium): {len([l for l in scored_legs if l['tier'] == 'B'])}\n"
                f"   • Tier C (Value): {len([l for l in scored_legs if l['tier'] == 'C'])}\n\n"
                f"💡 Try:\n"
                f"   • Switch to 'balanced' or 'high_volatility' risk profile\n"
                f"   • Try a different sport\n"
                f"   • Check back in 5-10 minutes for new simulations"
            )
        
        final_legs = selected_legs["legs"]
        transparency_message = selected_legs.get("transparency_message")
        
        # Step 5: Calculate parlay metrics
        parlay_probability = 1.0
        for leg in final_legs:
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
        correlation_score = self._calculate_correlation(final_legs)
        
        parlay_id = f"parlay_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}_{random.randint(1000, 9999)}"
        
        parlay_data = {
            "parlay_id": parlay_id,
            "sport": sport_key,
            "leg_count": len(final_legs),
            "risk_profile": risk_profile,
            "legs": final_legs,
            "parlay_odds": american_odds,
            "parlay_probability": round(parlay_probability, 4),
            "expected_value": round(ev_percent, 2),
            "correlation_score": correlation_score,
            "correlation_impact": self._interpret_correlation(correlation_score),
            "confidence_rating": self._calculate_parlay_confidence(final_legs),
            "transparency_message": transparency_message,  # User notification about tier fallback
            "created_at": datetime.now(timezone.utc).isoformat(),
            "user_tier": user_tier
        }
        
        # Sanitize to remove any MongoDB ObjectId fields before storing/returning
        parlay_data = sanitize_mongo_doc(parlay_data)
        
        # Store in database
        db.parlay_architect_generations.insert_one(parlay_data.copy())  # Copy to avoid _id injection
        
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
    
    def _classify_leg_tier(self, confidence: float, ev: float, stability: float) -> str:
        """
        Classify leg into quality tier (A, B, or C)
        
        Args:
            confidence: Confidence score (0-1)
            ev: Expected value percentage
            stability: Stability score (0-100)
        
        Returns:
            Tier classification: 'A', 'B', or 'C'
        """
        # Check Tier A (Premium Confidence)
        if (confidence >= self.tier_thresholds["A"]["confidence"] and
            ev >= self.tier_thresholds["A"]["ev"] and
            stability >= self.tier_thresholds["A"]["stability"]):
            return "A"
        
        # Check Tier B (Medium Confidence)
        if (confidence >= self.tier_thresholds["B"]["confidence"] and
            ev >= self.tier_thresholds["B"]["ev"] and
            stability >= self.tier_thresholds["B"]["stability"]):
            return "B"
        
        # Check Tier C (Value Edge)
        if (confidence >= self.tier_thresholds["C"]["confidence"] and
            ev >= self.tier_thresholds["C"]["ev"] and
            stability >= self.tier_thresholds["C"]["stability"]):
            return "C"
        
        # Below all thresholds - still classify as C but flag it
        return "C"
    
    def _select_legs_with_tiered_fallback(
        self,
        scored_legs: List[Dict[str, Any]],
        leg_count: int,
        risk_profile: str
    ) -> Dict[str, Any]:
        """
        Select legs using tiered fallback system
        
        Strategy:
        1. Try to fill with Tier A legs first
        2. If not enough, add Tier B legs
        3. If still not enough (and high_volatility profile), add Tier C legs
        4. If still not enough, reduce leg count
        
        Args:
            scored_legs: All available legs with tier classifications
            leg_count: Requested number of legs
            risk_profile: User's risk profile
        
        Returns:
            Dict with 'legs' and optional 'transparency_message'
        """
        # Separate legs by tier
        tier_a_legs = [leg for leg in scored_legs if leg["tier"] == "A"]
        tier_b_legs = [leg for leg in scored_legs if leg["tier"] == "B"]
        tier_c_legs = [leg for leg in scored_legs if leg["tier"] == "C"]
        
        # Sort each tier by score
        tier_a_legs.sort(key=lambda x: x["score"], reverse=True)
        tier_b_legs.sort(key=lambda x: x["score"], reverse=True)
        tier_c_legs.sort(key=lambda x: x["score"], reverse=True)
        
        selected = []
        used_events = set()
        transparency_message = None
        tiers_used = {"A": 0, "B": 0, "C": 0}
        
        # Step 1: Fill with Tier A legs
        for leg in tier_a_legs:
            if len(selected) >= leg_count:
                break
            if leg["event_id"] not in used_events:
                # Check correlation
                if not selected or self._check_leg_correlation(leg, selected) <= self.max_correlation:
                    selected.append(leg)
                    used_events.add(leg["event_id"])
                    tiers_used["A"] += 1
        
        # Step 2: If not enough, add Tier B legs (allowed for balanced and high_volatility)
        if len(selected) < leg_count and risk_profile in ["balanced", "high_volatility"]:
            for leg in tier_b_legs:
                if len(selected) >= leg_count:
                    break
                if leg["event_id"] not in used_events:
                    if not selected or self._check_leg_correlation(leg, selected) <= self.max_correlation:
                        selected.append(leg)
                        used_events.add(leg["event_id"])
                        tiers_used["B"] += 1
        
        # Step 3: If STILL not enough, add Tier C legs (only for high_volatility, or as emergency fallback)
        if len(selected) < leg_count:
            # Allow Tier C for high_volatility OR as emergency fallback for other profiles
            allow_tier_c = risk_profile == "high_volatility" or (len(selected) < 2 and len(tier_a_legs) == 0 and len(tier_b_legs) == 0)
            
            if allow_tier_c:
                for leg in tier_c_legs:
                    if len(selected) >= leg_count:
                        break
                    if leg["event_id"] not in used_events:
                        if not selected or self._check_leg_correlation(leg, selected) <= self.max_correlation:
                            selected.append(leg)
                            used_events.add(leg["event_id"])
                            tiers_used["C"] += 1
        
        # Step 4: Generate transparency message
        if len(selected) < leg_count and len(selected) >= 2:
            # Auto-reduce leg count
            transparency_message = (
                f"⚠️ Only {len(selected)} quality legs available today. "
                f"Generated a {len(selected)}-leg parlay instead of {leg_count}-leg."
            )
        elif tiers_used["B"] > 0 or tiers_used["C"] > 0:
            # Used fallback tiers
            tier_breakdown = []
            if tiers_used["A"] > 0:
                tier_breakdown.append(f"{tiers_used['A']} Premium")
            if tiers_used["B"] > 0:
                tier_breakdown.append(f"{tiers_used['B']} Medium")
            if tiers_used["C"] > 0:
                tier_breakdown.append(f"{tiers_used['C']} Speculative")
            
            if risk_profile == "high_confidence" and tiers_used["C"] > 0:
                # Special message for high_confidence using Tier C (emergency fallback)
                transparency_message = (
                    f"⚠️ No premium legs available. Emergency fallback activated. "
                    f"Parlay includes: {', '.join(tier_breakdown)}. "
                    f"💡 Recommend switching to 'balanced' or 'high_volatility' risk profile for better results."
                )
            else:
                transparency_message = (
                    f"⚠️ Not enough premium legs available. "
                    f"Parlay includes: {', '.join(tier_breakdown)}."
                )
        
        return {
            "legs": selected,
            "transparency_message": transparency_message,
            "tier_breakdown": tiers_used
        }


# Singleton instance
parlay_architect_service = ParlayArchitectService()
