"""
Daily Best Cards Service
Automatically selects the 6 best cards across all sports and bet types
"""
from typing import Dict, List, Any, Optional
from datetime import datetime, timezone, timedelta
from db.mongo import db
from services.parlay_architect import parlay_architect_service
from utils.mongo_helpers import sanitize_mongo_doc


class DailyCardsService:
    """
    Curates the 6 flagship cards for daily content:
    1. Best Game Overall
    2. Top NBA Game
    3. Top NCAAB Game
    4. Top NCAAF Game
    5. Top Prop Mispricing
    6. Parlay Architect Preview
    """
    
    def __init__(self):
        self.min_win_probability = 0.52  # Minimum 52% to be considered
        self.min_confidence = 0.50  # Medium-high confidence required
    
    def generate_daily_cards(self) -> Dict[str, Any]:
        """
        Generate all 6 daily best cards
        
        Returns:
            Dict with 6 card types and metadata
        """
        today = datetime.now(timezone.utc)
        tomorrow = today + timedelta(days=1)
        
        # Get all events happening today/tomorrow
        events = list(db.events.find({
            "commence_time": {
                "$gte": today.isoformat(),
                "$lt": tomorrow.isoformat()
            }
        }))
        
        if len(events) == 0:
            print("⚠️ No events found for today/tomorrow")
            # Return empty cards structure
            return {
                "best_game_overall": None,
                "top_nba_game": None,
                "top_ncaab_game": None,
                "top_ncaaf_game": None,
                "top_prop_mispricing": None,
                "parlay_preview": None,
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "expires_at": tomorrow.isoformat(),
                "message": "No games available for today's slate. Check back later."
            }
        
        # Get simulations for all events
        event_ids = [e["event_id"] for e in events]
        simulations = list(db.monte_carlo_simulations.find({
            "event_id": {"$in": event_ids}
        }))
        
        if len(simulations) == 0:
            print(f"⚠️ No simulations found for {len(events)} events")
            print(f"📌 Generating preview cards from {len(events)} available events")
            
            # Generate actual game cards from events (no simulation required)
            cards_from_events = self._generate_cards_from_events(events)
            
            # Still try to generate parlay preview from events
            try:
                parlay_preview = self._generate_parlay_preview_fallback(events)
            except Exception as e:
                print(f"Error generating parlay preview: {e}")
                parlay_preview = {
                    "card_type": "AI Parlay Preview",
                    "status": "processing",
                    "message": f"🎯 {len(events)} games queued for simulation",
                    "leg_count": 0,
                    "parlay_odds": 0,
                    "expected_value": 0.0,
                    "confidence_rating": "PENDING"
                }
            
            cards_from_events["parlay_preview"] = parlay_preview
            cards_from_events["generated_at"] = datetime.now(timezone.utc).isoformat()
            cards_from_events["expires_at"] = tomorrow.isoformat()
            
            return cards_from_events
        
        # Build simulation lookup
        sim_lookup = {s["event_id"]: s for s in simulations}
        
        # Enrich events with simulation data
        enriched_events = []
        for event in events:
            sim = sim_lookup.get(event["event_id"])
            if sim:
                enriched_events.append({
                    "event": event,
                    "simulation": sim,
                    "sport_key": event["sport_key"]
                })
        
        # Generate each card
        cards = {
            "best_game_overall": self._select_best_game_overall(enriched_events),
            "top_nba_game": self._select_top_sport_game(enriched_events, "basketball_nba"),
            "top_ncaab_game": self._select_top_sport_game(enriched_events, "basketball_ncaab"),
            "top_ncaaf_game": self._select_top_sport_game(enriched_events, "americanfootball_ncaaf"),
            "top_prop_mispricing": self._select_top_prop(),
            "parlay_preview": self._generate_parlay_preview(),
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "expires_at": tomorrow.isoformat()
        }
        
        # Sanitize to remove MongoDB ObjectIds
        cards = sanitize_mongo_doc(cards)
        
        # Store in database for caching
        db.daily_best_cards.delete_many({})  # Clear old cards
        db.daily_best_cards.insert_one(cards.copy())  # Copy to avoid _id injection
        
        return cards
    
    def _select_best_game_overall(self, enriched_events: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """
        Select the absolute best game of the day
        
        Criteria:
        - Highest win probability (>58%)
        - High confidence
        - Clean injury data
        - Low/medium volatility
        - Strong EV
        """
        candidates = []
        
        for item in enriched_events:
            event = item["event"]
            sim = item["simulation"]
            
            # Extract metrics
            win_prob = sim.get("team_a_win_probability", 0.5)
            confidence = sim.get("outcome", {}).get("confidence", sim.get("confidence_score", 0.5))
            volatility = sim.get("volatility", "MODERATE")
            
            # Calculate score
            if win_prob < 0.58 or confidence < 0.60:
                continue  # Skip low quality
            
            if volatility == "HIGH":
                continue  # Skip volatile games
            
            # Check injury impact is reasonable
            injury_impact = sim.get("injury_impact", [])
            total_injury_points = sum(abs(inj.get("impact_points", 0)) for inj in injury_impact)
            
            if total_injury_points > 15:  # Too much injury chaos
                continue
            
            # Calculate composite score
            score = (
                win_prob * 100 +  # Win probability (58-70 = 58-70 points)
                confidence * 50 +  # Confidence (0.6-0.8 = 30-40 points)
                (1 if volatility == "LOW" else 0.5) * 20  # Volatility bonus
            )
            
            candidates.append({
                "event_id": event["event_id"],
                "matchup": f"{event['away_team']} @ {event['home_team']}",
                "sport": event["sport_key"],
                "commence_time": event["commence_time"],
                "win_probability": round(win_prob, 4),
                "confidence": round(confidence, 4),
                "volatility": volatility,
                "recommended_bet": sim.get("outcome", {}).get("recommended_bet", "N/A"),
                "odds": sim.get("outcome", {}).get("odds", 0),
                "injury_count": len(injury_impact),
                "total_injury_impact": round(total_injury_points, 1),
                "score": score,
                "card_type": "FLAGSHIP - Best Game of the Day",
                "reasoning": self._generate_flagship_reasoning(sim, event)
            })
        
        if not candidates:
            return None
        
        # Sort by score and return top
        candidates.sort(key=lambda x: x["score"], reverse=True)
        return candidates[0]
    
    def _select_top_sport_game(
        self,
        enriched_events: List[Dict[str, Any]],
        sport_key: str
    ) -> Optional[Dict[str, Any]]:
        """
        Select top game for specific sport
        
        Criteria:
        - Strong win probability (>55%)
        - Injury impact that makes sense
        - Good O/U projection if available
        - Solid confidence
        """
        candidates = []
        
        for item in enriched_events:
            event = item["event"]
            sim = item["simulation"]
            
            if event["sport_key"] != sport_key:
                continue
            
            win_prob = sim.get("team_a_win_probability", 0.5)
            confidence = sim.get("outcome", {}).get("confidence", sim.get("confidence_score", 0.5))
            over_prob = sim.get("over_probability", 0.5)
            
            if win_prob < 0.55 or confidence < 0.52:
                continue
            
            # Calculate score
            score = (
                win_prob * 80 +
                confidence * 40 +
                abs(over_prob - 0.5) * 30  # O/U edge bonus
            )
            
            candidates.append({
                "event_id": event["event_id"],
                "matchup": f"{event['away_team']} @ {event['home_team']}",
                "sport": event["sport_key"],
                "commence_time": event["commence_time"],
                "win_probability": round(win_prob, 4),
                "over_probability": round(over_prob, 4),
                "confidence": round(confidence, 4),
                "recommended_bet": sim.get("outcome", {}).get("recommended_bet", "N/A"),
                "odds": sim.get("outcome", {}).get("odds", 0),
                "avg_total": sim.get("avg_total_score", 0),
                "injury_impact": sim.get("injury_impact", []),
                "score": score,
                "card_type": f"Top {sport_key.replace('_', ' ').title()} Game",
                "reasoning": self._generate_sport_reasoning(sim, event, sport_key)
            })
        
        if not candidates:
            return None
        
        candidates.sort(key=lambda x: x["score"], reverse=True)
        return candidates[0]
    
    def _select_top_prop(self) -> Optional[Dict[str, Any]]:
        """
        Select best prop mispricing of the day
        
        Criteria:
        - Highest EV%
        - Solid win probability (>55%)
        - Clean mispricing explanation
        - Yellow/Green tier
        """
        # Get all props from recent simulations
        today = datetime.now(timezone.utc)
        simulations = list(db.monte_carlo_simulations.find({
            "created_at": {"$gte": (today - timedelta(hours=6)).isoformat()},
            "high_value_props": {"$exists": True, "$ne": []}
        }))
        
        all_props = []
        for sim in simulations:
            props = sim.get("high_value_props", [])
            for prop in props:
                # Only include props with good EV
                ev = prop.get("expected_value", 0)
                prob = prop.get("probability", 0)
                
                if ev < 3.0 or prob < 0.55:
                    continue
                
                all_props.append({
                    "event_id": sim.get("event_id"),
                    "player_name": prop.get("player_name", "Unknown"),
                    "prop_type": prop.get("prop_type", "Unknown"),
                    "line": prop.get("line", 0),
                    "over_under": prop.get("over_under", "OVER"),
                    "probability": round(prob, 4),
                    "expected_value": round(ev, 2),
                    "recent_avg": prop.get("recent_avg", 0),
                    "season_avg": prop.get("season_avg", 0),
                    "mispricing_explanation": prop.get("mispricing_explanation", ""),
                    "confidence_level": prop.get("confidence_level", "MEDIUM"),
                    "card_type": "Top Prop Mispricing"
                })
        
        if not all_props:
            return None
        
        # Sort by EV and return top
        all_props.sort(key=lambda x: x["expected_value"], reverse=True)
        return all_props[0]
    
    def _generate_parlay_preview(self) -> Optional[Dict[str, Any]]:
        """
        Generate parlay architect preview
        
        Even if generation fails, still create preview card
        """
        try:
            # Try to generate 4-leg balanced parlay
            parlay = parlay_architect_service.generate_optimal_parlay(
                sport_key="basketball_nba",
                leg_count=4,
                risk_profile="balanced",
                user_tier="preview"
            )
            
            return {
                "parlay_id": parlay["parlay_id"],
                "leg_count": parlay["leg_count"],
                "parlay_odds": parlay["parlay_odds"],
                "expected_value": parlay["expected_value"],
                "confidence_rating": parlay["confidence_rating"],
                "parlay_probability": parlay["parlay_probability"],
                "risk_profile": parlay["risk_profile"],
                "legs_preview": [
                    {
                        "matchup": leg["event"],
                        "bet_type": leg["bet_type"],
                        "line": leg["line"],
                        "confidence": f"{leg['confidence']*100:.1f}%"
                    }
                    for leg in parlay["legs"][:4]
                ],
                "card_type": "AI Parlay Preview",
                "status": "success"
            }
        except Exception as e:
            # If generation fails, return preview structure anyway
            return {
                "card_type": "AI Parlay Preview",
                "status": "failed",
                "message": "Generating optimal parlay structure...",
                "error": str(e),
                "fallback_preview": {
                    "leg_count": 4,
                    "risk_profile": "balanced",
                    "estimated_odds": "+350 to +500",
                    "note": "Today's slate is being analyzed. Check back in 10 minutes."
                }
            }
    
    def _generate_flagship_reasoning(self, sim: Dict[str, Any], event: Dict[str, Any]) -> str:
        """
        Generate flagship reasoning for best game card
        """
        win_prob = sim.get("team_a_win_probability", 0.5)
        confidence = sim.get("outcome", {}).get("confidence", 0.5)
        volatility = sim.get("volatility", "MODERATE")
        
        reasoning_parts = []
        
        # Win probability
        if win_prob >= 0.65:
            reasoning_parts.append(f"Strong model agreement ({win_prob*100:.1f}% win probability)")
        else:
            reasoning_parts.append(f"Solid win probability ({win_prob*100:.1f}%)")
        
        # Confidence
        if confidence >= 0.70:
            reasoning_parts.append("High stability simulation")
        else:
            reasoning_parts.append("Medium-high confidence")
        
        # Volatility
        if volatility == "LOW":
            reasoning_parts.append("Low variance expected")
        
        # Injuries
        injury_impact = sim.get("injury_impact", [])
        if len(injury_impact) == 0:
            reasoning_parts.append("Clean injury table")
        elif len(injury_impact) <= 2:
            reasoning_parts.append(f"{len(injury_impact)} injury factors accounted for")
        
        return " • ".join(reasoning_parts)
    
    def _generate_sport_reasoning(
        self,
        sim: Dict[str, Any],
        event: Dict[str, Any],
        sport_key: str
    ) -> str:
        """
        Generate sport-specific reasoning
        """
        win_prob = sim.get("team_a_win_probability", 0.5)
        over_prob = sim.get("over_probability", 0.5)
        
        reasoning_parts = []
        
        reasoning_parts.append(f"{win_prob*100:.1f}% model projection")
        
        # O/U analysis
        if over_prob >= 0.60:
            reasoning_parts.append("Strong OVER tendency")
        elif over_prob <= 0.40:
            reasoning_parts.append("Strong UNDER tendency")
        
        # Injuries
        injury_count = len(sim.get("injury_impact", []))
        if injury_count > 0:
            reasoning_parts.append(f"{injury_count} injury arbitrage factors")
        
        return " • ".join(reasoning_parts)
    
    def _placeholder_card(
        self,
        sport_name: str,
        events: List[Dict[str, Any]],
        sport_key: str
    ) -> Dict[str, Any]:
        """
        Generate placeholder card when simulations are processing
        """
        sport_events = [e for e in events if e.get("sport_key") == sport_key]
        
        if not sport_events:
            return {
                "card_type": f"Top {sport_name} Game",
                "status": "no_games",
                "message": f"No {sport_name} games today"
            }
        
        # Show first game as placeholder
        event = sport_events[0]
        return {
            "card_type": f"Top {sport_name} Game",
            "status": "processing",
            "matchup": f"{event['away_team']} @ {event['home_team']}",
            "commence_time": event["commence_time"],
            "message": "🔄 Simulation in progress",
            "event_count": len(sport_events)
        }
    
    def _generate_parlay_preview_fallback(
        self,
        events: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Generate parlay preview even without simulations (for content posting)
        """
        import random
        
        # Pick 4 random upcoming games
        sample_events = random.sample(events, min(4, len(events)))
        
        legs_preview = []
        for event in sample_events:
            legs_preview.append({
                "matchup": f"{event['away_team']} @ {event['home_team']}",
                "bet_type": "processing",
                "line": "Analyzing...",
                "confidence": "TBD"
            })
        
        return {
            "parlay_id": f"preview_pending_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
            "leg_count": len(legs_preview),
            "parlay_odds": 0,
            "expected_value": 0.0,
            "confidence_rating": "PROCESSING",
            "risk_profile": "balanced",
            "legs_preview": legs_preview,
            "card_type": "AI Parlay Preview",
            "status": "processing",
            "message": f"🔄 Building optimal {len(legs_preview)}-leg parlay"
        }
    
    def _generate_cards_from_events(self, events: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Generate game cards directly from events (without simulations)
        Shows upcoming games to provide content even before simulations run
        """
        # Sort events by commence_time (soonest first)
        sorted_events = sorted(events, key=lambda e: e.get("commence_time", ""))
        
        # Helper to create card from event
        def event_to_card(event: Dict[str, Any], card_type: str) -> Dict[str, Any]:
            # Get bookmaker odds if available
            home_odds = None
            away_odds = None
            spread = None
            total = None
            
            if "bookmakers" in event and event["bookmakers"]:
                bookmaker = event["bookmakers"][0]  # Use first bookmaker
                for market in bookmaker.get("markets", []):
                    if market["key"] == "h2h":
                        outcomes = market.get("outcomes", [])
                        for outcome in outcomes:
                            if outcome["name"] == event["home_team"]:
                                home_odds = outcome.get("price")
                            elif outcome["name"] == event["away_team"]:
                                away_odds = outcome.get("price")
                    elif market["key"] == "spreads":
                        outcomes = market.get("outcomes", [])
                        for outcome in outcomes:
                            if outcome["name"] == event["home_team"]:
                                spread = outcome.get("point")
                    elif market["key"] == "totals":
                        outcomes = market.get("outcomes", [])
                        if outcomes:
                            total = outcomes[0].get("point")
            
            return {
                "card_type": card_type,
                "event_id": event["event_id"],
                "matchup": f"{event['away_team']} @ {event['home_team']}",
                "sport": event["sport_key"],
                "commence_time": event["commence_time"],
                "home_odds": home_odds,
                "away_odds": away_odds,
                "spread": spread,
                "total": total,
                "status": "preview",
                "message": "📊 Click to run full Monte Carlo simulation"
            }
        
        # Filter by sport
        nba_events = [e for e in sorted_events if e.get("sport_key") == "basketball_nba"]
        ncaab_events = [e for e in sorted_events if e.get("sport_key") == "basketball_ncaab"]
        ncaaf_events = [e for e in sorted_events if e.get("sport_key") == "americanfootball_ncaaf"]
        nfl_events = [e for e in sorted_events if e.get("sport_key") == "americanfootball_nfl"]
        
        # Generate cards
        return {
            "best_game_overall": event_to_card(sorted_events[0], "FLAGSHIP - Next Game") if sorted_events else None,
            "top_nba_game": event_to_card(nba_events[0], "Top NBA Game") if nba_events else None,
            "top_ncaab_game": event_to_card(ncaab_events[0], "Top NCAAB Game") if ncaab_events else None,
            "top_ncaaf_game": event_to_card(ncaaf_events[0], "Top NCAAF Game") if ncaaf_events else None,
            "top_prop_mispricing": {
                "card_type": "Top Prop Mispricing",
                "status": "processing",
                "message": "📊 Props require simulation data"
            },
        }
    
    def get_cached_daily_cards(self) -> Optional[Dict[str, Any]]:
        """
        Get cached daily cards (if still valid)
        """
        cached = db.daily_best_cards.find_one()
        
        if not cached:
            return None
        
        # Check if expired
        expires_at = datetime.fromisoformat(cached.get("expires_at", ""))
        if datetime.now(timezone.utc) >= expires_at:
            return None
        
        # Sanitize to remove MongoDB _id and ObjectId fields
        return sanitize_mongo_doc(cached)


# Singleton instance
daily_cards_service = DailyCardsService()
