"""
AI Parlay Architect Service
Generates optimized 3-6 leg parlays using Monte Carlo simulation data
TRUTH MODE ENFORCED: All legs validated through zero-lies gates
"""
import random
from typing import Dict, List, Any, Optional
from datetime import datetime, timezone, timedelta
from db.mongo import db
from core.monte_carlo_engine import monte_carlo_engine
from core.truth_mode import truth_mode_validator
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
        user_tier: str = "free",
        multi_sport: bool = False
    ) -> Dict[str, Any]:
        """
        Generate AI-optimized parlay with CROSS-SPORT support
        
        CROSS-SPORT COMPOSITION:
        Supports combining legs from NFL, NBA, NHL, MLB, NCAAF, NCAAB in single parlay.
        Cross-sport legs are treated as independent (0.0 correlation).
        
        Args:
            sport_key: Primary sport (or 'all' for multi-sport)
            leg_count: Number of legs (3-6)
            risk_profile: 'high_confidence' | 'balanced' | 'high_volatility'
            user_tier: User's subscription tier
            multi_sport: If True, include games from ALL 6 supported sports (same day only)
        
        Returns:
            Parlay with legs, odds, EV, confidence, correlation analysis
            
        Governance:
            All legs validated through Truth Mode (PICK/LEAN/NO_PLAY enforcement)
            Cross-sport correlation = 0.0 (independent events)
        """
        
        # Step 1: Get all available games (SAME DAY ONLY for parlays)
        now = datetime.now(timezone.utc)
        
        # Get events grouped by calendar day
        events_by_day = self._get_events_by_day(sport_key, multi_sport)
        
        if not events_by_day:
            raise ValueError(
                f"No games available in the next 7 days for {sport_key}. "
                f"Try a different sport or check back later."
            )
        
        # Find the first day with enough games
        selected_day = None
        events = []
        
        for day_date, day_events in sorted(events_by_day.items()):
            if len(day_events) >= leg_count:
                selected_day = day_date
                events = day_events
                print(f"📅 [Parlay Architect] Using games from {day_date}: {len(events)} available")
                break
        
        if not events or len(events) < leg_count:
            # Show what's available each day
            day_breakdown = "\n".join([
                f"   • {date}: {len(evts)} games"
                for date, evts in sorted(events_by_day.items())[:5]
            ])
            raise ValueError(
                f"Insufficient games on any single day for {sport_key}. "
                f"Need {leg_count} legs, but no day has enough games.\n\n"
                f"📊 Games by day:\n{day_breakdown}\n\n"
                f"💡 Options:\n"
                f"   • Reduce leg count to 2\n"
                f"   • Enable multi-sport parlays\n"
                f"   • Try a different sport"
            )
        
        if len(events) < leg_count:
            # Check other sports to suggest alternatives
            available_sports = self._get_available_sports_count(now, extended_end if len(events) < leg_count else today_end)
            
            suggestions = []
            for sport, count in available_sports.items():
                if count >= leg_count and sport != sport_key:
                    sport_name = sport.replace('_', ' ').replace('basketball', 'Basketball').replace('americanfootball', 'Football').replace('baseball', 'Baseball').replace('icehockey', 'Hockey')
                    suggestions.append(f"   • {sport_name}: {count} games available")
            
            suggestion_text = "\n\n💡 Available alternatives:\n" + "\n".join(suggestions) if suggestions else ""
            
            raise ValueError(
                f"Insufficient games available for {sport_key}. "
                f"Found {len(events)} games in next 72 hours, need {leg_count} for parlay. "
                f"\n\n📊 Options:\n"
                f"   • Reduce leg count to {len(events)} or fewer\n"
                f"   • Try a different sport{suggestion_text}"
            )
        
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
        
        # Step 3.5: TRUTH MODE VALIDATION - Enforce zero-lies principle
        print(f"🛡️ [Truth Mode] Validating {len(selected_legs['legs'])} legs through zero-lies gates...")
        valid_legs, blocked_legs = truth_mode_validator.validate_parlay_legs(selected_legs["legs"])
        
        if blocked_legs:
            print(f"⚠️ [Truth Mode] {len(blocked_legs)} leg(s) blocked:")
            for leg in blocked_legs:
                print(f"   ❌ {leg.get('event', 'Unknown')}: {leg.get('block_reasons', [])}")
        
        print(f"✅ [Truth Mode] {len(valid_legs)} leg(s) validated and approved")
        
        # Use only Truth Mode validated legs
        if len(valid_legs) < 2:
            # BLOCKED STATE - Return structured blocked response with next-best actions
            best_single = self._find_best_single(scored_legs)
            
            # Calculate next refresh time (simulations update every 5-10 minutes)
            next_refresh_seconds = 300  # 5 minutes
            
            blocked_response = {
                "status": "BLOCKED",
                "message": "No Valid Parlay Available",
                "reason": "Current games do not meet Truth Mode standards for safe parlay construction.",
                "passed_count": len(valid_legs),
                "failed_count": len(blocked_legs),
                "minimum_required": 2,
                "failed": [
                    {
                        "game": leg.get('event', 'Unknown'),
                        "reason": ', '.join(leg.get('block_reasons', []))
                    }
                    for leg in blocked_legs[:5]
                ],
                "best_single": best_single,
                "next_best_actions": {
                    "market_filters": [
                        {"option": "totals_only", "label": "Re-run with Totals Only"},
                        {"option": "spreads_only", "label": "Re-run with Spreads Only"},
                        {"option": "all_sports", "label": "Try ALL SPORTS (Multi-Sport)"}
                    ],
                    "risk_profiles": [
                        {"profile": "balanced", "label": "Switch to Balanced Risk"},
                        {"profile": "high_volatility", "label": "Switch to High Volatility"}
                    ]
                },
                "next_refresh_seconds": next_refresh_seconds,
                "next_refresh_eta": (datetime.now(timezone.utc) + timedelta(seconds=next_refresh_seconds)).isoformat()
            }
            
            # Raise ValueError with the structured response
            # The API route will catch this and return the proper response
            raise ValueError(blocked_response)
        
        final_legs = valid_legs
        transparency_message = selected_legs.get("transparency_message")
        
        # Add Truth Mode badge to transparency message
        if transparency_message:
            transparency_message += " | Truth Mode: All legs validated ✓"
        else:
            transparency_message = "Truth Mode: All legs validated through zero-lies gates ✓"
        
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
        
        CROSS-SPORT SUPPORT:
        - Same game = high correlation (bad) → 0.8
        - Same sport, different games = low correlation → 0.1
        - Different sports = ZERO correlation (independent) → 0.0
        
        This enables cross-sport parlays (NFL + NBA + NHL in single parlay)
        """
        max_correlation = 0.0
        
        for leg in existing_legs:
            if leg["event_id"] == new_leg["event_id"]:
                # Same game - very high correlation (blocks same-game parlays)
                correlation = 0.8
            elif leg["sport"] == new_leg["sport"]:
                # Same sport, different games - low correlation
                correlation = 0.1
            else:
                # Different sports - ZERO correlation (fully independent)
                # This allows cross-sport composition: NFL + NBA + NHL
                correlation = 0.0
            
            max_correlation = max(max_correlation, correlation)
        
        return max_correlation
    
    def _calculate_correlation(self, legs: List[Dict[str, Any]]) -> float:
        """
        Calculate overall correlation score for parlay
        
        Cross-sport legs are treated as fully independent (0.0 correlation)
        Same-sport legs have minimal correlation (0.1)
        Same-game legs have high correlation and are rejected (0.8)
        
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
    
    def _get_events_by_day(
        self, 
        sport_key: str, 
        multi_sport: bool = False
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Get events grouped by calendar day (UTC)
        All parlay legs MUST be on the same day
        
        Returns:
            Dict mapping date string (YYYY-MM-DD) to list of events
        """
        now = datetime.now(timezone.utc)
        week_end = now + timedelta(days=7)
        
        # Build query
        query = {
            "commence_time": {
                "$gt": now.isoformat(),
                "$lt": week_end.isoformat()
            }
        }
        
        # Single sport or multi-sport
        if not multi_sport and sport_key != "all":
            query["sport_key"] = sport_key
        
        events = list(db.events.find(query).limit(200))
        
        # Group by calendar day (UTC date)
        events_by_day = {}
        for event in events:
            try:
                # Parse commence_time and get date
                commence = datetime.fromisoformat(event["commence_time"].replace("Z", "+00:00"))
                date_key = commence.strftime("%Y-%m-%d")
                
                if date_key not in events_by_day:
                    events_by_day[date_key] = []
                
                events_by_day[date_key].append(event)
            except Exception as e:
                print(f"⚠️ Error parsing date for event {event.get('event_id')}: {e}")
                continue
        
        # Log what we found
        if multi_sport:
            total = sum(len(evts) for evts in events_by_day.values())
            print(f"🌐 [Multi-Sport] Found {total} games across all sports in next 7 days")
        else:
            total = sum(len(evts) for evts in events_by_day.values())
            print(f"📅 [Same-Day Filter] Found {total} {sport_key} games grouped by day")
        
        return events_by_day
    
    def _get_available_sports_count(self, start_time: datetime, end_time: datetime) -> Dict[str, int]:
        """
        Get count of available games for each sport in the time window
        """
        sports = [
            "basketball_nba",
            "basketball_ncaab", 
            "americanfootball_nfl",
            "americanfootball_ncaaf",
            "baseball_mlb",
            "icehockey_nhl"
        ]
        
        sport_counts = {}
        for sport in sports:
            count = db.events.count_documents({
                "sport_key": sport,
                "commence_time": {
                    "$gt": start_time.isoformat(),
                    "$lt": end_time.isoformat()
                }
            })
            if count > 0:
                sport_counts[sport] = count
        
        return sport_counts
    
    def _find_best_single(self, scored_legs: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """
        Find the single best Truth-Mode-approved pick
        Used when parlay generation is blocked
        
        Returns:
            Best single pick with full details, or None if no valid picks
        """
        if not scored_legs:
            return None
        
        # Validate each leg through Truth Mode
        valid_singles = []
        for leg in scored_legs:
            # Create a single-item list for validation
            valid_legs, blocked_legs = truth_mode_validator.validate_parlay_legs([leg])
            if valid_legs:
                valid_singles.append(leg)
        
        if not valid_singles:
            return None
        
        # Sort by score (confidence * 60 + EV * 40)
        valid_singles.sort(key=lambda x: x['score'], reverse=True)
        best = valid_singles[0]
        
        # Format for response
        return {
            "sport": best['sport'],
            "event": best['event'],
            "market": best['market_type'],
            "pick": best['pick'],
            "confidence": round(best['confidence'] * 100, 1),
            "expected_value": round(best['ev'], 2),
            "volatility": best['volatility'],
            "edge_description": self._get_edge_description(best),
            "american_odds": best['american_odds'],
            "pricing": {
                "single_unlock": 399  # $3.99 in cents
            }
        }
    
    def _get_edge_description(self, leg: Dict[str, Any]) -> str:
        """
        Generate human-readable edge description
        """
        confidence_pct = leg['confidence'] * 100
        ev_pct = leg['ev']
        
        if confidence_pct >= 60 and ev_pct >= 5:
            return f"Premium edge: {confidence_pct:.0f}% confidence, {ev_pct:+.1f}% EV"
        elif confidence_pct >= 52 and ev_pct >= 1:
            return f"Solid edge: {confidence_pct:.0f}% confidence, {ev_pct:+.1f}% EV"
        else:
            return f"Value play: {confidence_pct:.0f}% confidence, {ev_pct:+.1f}% EV"


# Singleton instance
parlay_architect_service = ParlayArchitectService()
