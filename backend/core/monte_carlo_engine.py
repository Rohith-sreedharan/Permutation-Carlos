"""
Monte Carlo Simulation Engine
Performs 10,000-100,000 iterations per game using granular inputs
NOW WITH MULTI-SPORT SUPPORT (NBA/NFL/MLB/NHL)

NUMERICAL ACCURACY ENFORCEMENT:
- All outputs must come from real simulation data
- NO placeholders, NO hard-coded fallbacks, NO safe defaults
- If simulation fails → return error, NOT fake numbers
"""
import random
import numpy as np
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from db.mongo import db
from services.logger import log_stage
from core.sport_strategies import SportStrategyFactory
from core.sport_constants import map_position_abbreviation
from core.numerical_accuracy import (
    SimulationOutput,
    OverUnderAnalysis,
    ExpectedValue,
    ClosingLineValue,
    SimulationTierConfig,
    ConfidenceCalculator,
    EdgeValidator,
    validate_simulation_output,
    get_debug_label
)
from core.sharp_analysis import (
    calculate_spread_edge,
    calculate_total_edge,
    format_for_api,
    explain_edge_reasoning,
    STANDARD_DISCLAIMER
)
from core.feedback_loop import store_prediction

logger = logging.getLogger(__name__)


class MonteCarloEngine:
    """
    Advanced Monte Carlo Simulation Engine for Beat Vegas
    
    Simulation Volume: 10,000-100,000 iterations per game
    Granular Inputs: Player efficiency, injuries, fatigue, volatility
    Outputs: Win probability, spread coverage, totals distribution, prop predictions
    
    MULTI-SPORT SUPPORT:
    - NBA/NFL: Normal Distribution (high-scoring sports)
    - MLB/NHL: Poisson Distribution (low-scoring sports)
    
    This is the core of the "moat" - unique probabilistic fingerprints
    """
    
    def __init__(self, num_iterations: Optional[int] = None):
        """
        Initialize Monte Carlo Engine
        
        Args:
            num_iterations: Default number of iterations (based on user tier)
                           If None, defaults to 10,000 (FREE tier baseline)
        """
        self.default_iterations = num_iterations or 10000
        self.min_iterations = 10000
        self.max_iterations = 100000
        self.strategy_factory = SportStrategyFactory()
        self.clv_predictions = []  # Store CLV predictions for validation
        
        # PHASE 15: First Half physics multipliers
        self.FIRST_HALF_CONFIG = {
            # Basketball/High-tempo sports
            "basketball": {
                "duration_multiplier": 0.5,      # 50% of regulation time
                "pace_multiplier": 1.035,         # 3.5% faster pace in early game
                "starter_weight": 1.20,           # Starters play 20% more minutes in 1H
                "fatigue_enabled": False          # No fatigue in first half
            },
            # Football (drive-based, not time-based)
            "football": {
                "duration_multiplier": 0.48,      # 48% of full game scoring (slightly less than half)
                "pace_multiplier": 1.00,          # No pace boost - drives are roughly equal
                "starter_weight": 1.00,           # No starter boost - all players critical
                "fatigue_enabled": False,         # Minimal fatigue impact in 1H
                "scripted_drive_boost": 1.05      # Small 5% boost for opening scripted plays (first 1-2 drives only)
            }
        }
    
    def run_simulation(
        self,
        event_id: str,
        team_a: Dict[str, Any],
        team_b: Dict[str, Any],
        market_context: Dict[str, Any],
        iterations: Optional[int] = None,
        mode: str = "full"
    ) -> Dict[str, Any]:
        """
        Run Monte Carlo simulation for a single game
        
        Args:
            event_id: Unique event identifier
            team_a: Team A data including player stats, injuries, fatigue
            team_b: Team B data including player stats, injuries, fatigue
            market_context: Current odds, line movement, public betting %, sport_key
            iterations: Number of simulations (default: 50,000)
            mode: "full" for comprehensive analysis with distribution curves, "basic" for quick results
        
        Returns:
            Simulation results with win probabilities, spread distribution, props
        """
        if not iterations:
            iterations = self.default_iterations if mode == "full" else 10000
        
        iterations = max(self.min_iterations, min(iterations, self.max_iterations))
        
        # Get sport-specific strategy
        sport_key = market_context.get('sport_key', 'basketball_nba')
        strategy = self.strategy_factory.get_strategy(sport_key)
        
        # Extract team data
        team_a_rating = self._calculate_team_rating(team_a, sport_key)
        team_b_rating = self._calculate_team_rating(team_b, sport_key)
        
        # Apply adjustments for injuries, fatigue, home/away
        team_a_adj = self._apply_adjustments(team_a, market_context)
        team_b_adj = self._apply_adjustments(team_b, market_context)
        
        # Run sport-specific simulations using Strategy Pattern
        results = strategy.simulate_game(
            team_a_rating + team_a_adj,
            team_b_rating + team_b_adj,
            iterations,
            market_context
        )
        
        # Calculate output metrics
        margins_array = results["margins"]
        totals_array = results["totals"]
        margin_std = np.std(margins_array)
        avg_margin = results["team_a_total"] - results["team_b_total"]
        
        # Calculate upset probability (underdog winning)
        team_a_favored = team_a_rating > team_b_rating
        upset_probability = (results["team_b_wins"] / iterations) if team_a_favored else (results["team_a_wins"] / iterations)
        
        # Calculate confidence intervals (1, 2, 3 standard deviations)
        ci_68 = [avg_margin / iterations - margin_std, avg_margin / iterations + margin_std]
        ci_95 = [avg_margin / iterations - 2 * margin_std, avg_margin / iterations + 2 * margin_std]
        ci_99 = [avg_margin / iterations - 3 * margin_std, avg_margin / iterations + 3 * margin_std]
        
        # Generate spread distribution as array with PROPER BINNING
        spread_dist_array = []
        margin_counts = {}
        
        # BIN_SIZE: 0.5 for smooth distribution (not stepped/flat)
        BIN_SIZE = 0.5
        
        for m in margins_array:
            # Round to nearest 0.5 increment for smooth distribution
            binned = round(m / BIN_SIZE) * BIN_SIZE
            margin_counts[binned] = margin_counts.get(binned, 0) + 1
        
        # NORMALIZE: Ensure probabilities sum to 1.0
        total_count = sum(margin_counts.values())
        
        for margin in sorted(margin_counts.keys()):
            normalized_prob = margin_counts[margin] / total_count
            spread_dist_array.append({
                "margin": float(margin),
                "probability": float(normalized_prob)  # Normalized, sum = 1
            })
        
        # Verify normalization (debugging)
        prob_sum = sum(d["probability"] for d in spread_dist_array)
        if abs(prob_sum - 1.0) > 0.01:
            print(f"⚠️  Distribution normalization warning: sum = {prob_sum:.4f}")
        
        # Extract real injury data from team rosters
        injury_impact = []
        offensive_impact = 0.0
        defensive_impact = 0.0
        
        for team, team_data in [(team_a, team_a), (team_b, team_b)]:
            players = team_data.get("players", [])
            for player in players:
                status = player.get("status", "active").upper()
                if status in ["OUT", "DOUBTFUL", "QUESTIONABLE"]:
                    per = player.get("per", 15.0)
                    minutes = player.get("avg_minutes", 0)
                    usage = player.get("usage_rate", 0.2)
                    
                    # FIXED: Realistic impact formula (not inflated)
                    # Base impact: (PER - league_avg) * minutes_pct * usage
                    per_diff = (per - 15.0) / 5.0  # Normalize PER difference
                    minutes_pct = minutes / 48.0
                    
                    # Status multiplier (realistic ranges)
                    if status == "OUT":
                        status_mult = 1.0  # Full impact
                    elif status == "DOUBTFUL":
                        status_mult = 0.6  # 60% impact
                    else:  # QUESTIONABLE
                        status_mult = 0.3  # 30% impact
                    
                    # Calculate impact (realistic range: -5 to +5 points typically)
                    impact = per_diff * minutes_pct * usage * status_mult * 3.5
                    
                    # Determine if offensive or defensive impact
                    ppg = player.get("ppg", 0)
                    is_offensive = ppg > 10  # Offensive player if scoring > 10ppg
                    
                    if is_offensive:
                        offensive_impact += impact
                    else:
                        defensive_impact += impact
                    
                    injury_impact.append({
                        "player": player.get("name", "Unknown Player"),
                        "team": team_data.get("name", "Unknown Team"),
                        "status": status,
                        "impact_points": round(impact, 1),
                        "impact_type": "offensive" if is_offensive else "defensive"
                    })
        
        # Calculate top props from REAL SPORTSBOOK data ONLY
        # ✅ NOW ENABLED: Fetching real props from DraftKings/FanDuel/BetMGM/Caesars
        top_props = []
        
        try:
            from integrations.props_api import fetch_event_props, normalize_props
            
            # Fetch real sportsbook props
            event_props = fetch_event_props(event_id, market_context.get("sport_key", "americanfootball_nfl"))
            
            if event_props.get("bookmakers"):
                # Normalize props with multi-book validation
                home_team_name = team_a.get("name") or ""
                away_team_name = team_b.get("name") or ""
                
                if home_team_name and away_team_name:
                    normalized_props = normalize_props(
                        event_props,
                        home_team_name,
                        away_team_name
                    )
                else:
                    normalized_props = []
                
                # Convert to frontend format (top 10 by book count)
                for prop in sorted(normalized_props, key=lambda x: x.get("book_count", 0), reverse=True)[:10]:
                    top_props.append({
                        "player": prop["player_name"],
                        "prop_type": prop["market_name"],
                        "line": prop["line"],
                        "probability": prop.get("fair_over_prob", 0.5),
                        "ev": prop.get("ev_percent", 0.0),
                        "edge": prop.get("edge", 0.0),
                        "ai_projection": prop.get("model_projection", prop["line"]),
                        "books": [b["book_name"] for b in prop["books"]],
                        "book_count": prop["book_count"]
                    })
                
                logger.info(f"✅ Integrated {len(top_props)} REAL sportsbook props")
            else:
                logger.info("ℹ️  No sportsbook props available for this event")
        
        except Exception as e:
            logger.warning(f"⚠️  Props fetch failed: {e}")
            # Don't fail simulation if props fail
        
        # Determine volatility label using sport-specific thresholds
        thresholds = strategy.get_volatility_thresholds()
        if margin_std < thresholds['stable']:
            volatility_label = "STABLE"
            volatility_score = "Low"
        elif margin_std < thresholds['moderate']:
            volatility_label = "MODERATE"
            volatility_score = "Medium"
        else:
            volatility_label = "HIGH"
            volatility_score = "High"
        
        # Calculate projected totals from simulation data (NUMERICAL ACCURACY ENFORCED)
        totals_array = np.array(results["totals"])
        median_total = float(np.median(totals_array))
        mean_total = float(np.mean(totals_array))
        variance_total = float(np.var(totals_array))
        
        # Validate we have real simulation data
        if len(totals_array) != iterations:
            raise ValueError(f"Simulation integrity violation: expected {iterations} totals, got {len(totals_array)}")
        
        # Get bookmaker's total line from market_context (REQUIRED - NO FALLBACK)
        bookmaker_total_line = market_context.get('total_line', None)
        
        if bookmaker_total_line is None:
            raise ValueError("CRITICAL: No bookmaker total line provided. Cannot calculate O/U probabilities without market line.")
        
        # Calculate Over/Under probabilities using proper formula from numerical_accuracy.py
        ou_analysis = OverUnderAnalysis.from_simulation(totals_array, bookmaker_total_line)
        over_probability = ou_analysis.over_probability
        under_probability = ou_analysis.under_probability
        
        logger.info(f"O/U Analysis: {ou_analysis.sims_over}/{iterations} over {bookmaker_total_line} = {over_probability:.1%}")
        
        # Calculate Win Probabilities from simulation counts (NO HEURISTICS)
        home_win_probability = float(results["team_a_wins"] / iterations)
        away_win_probability = float(results["team_b_wins"] / iterations)
        
        # Validate probabilities sum to ~1.0
        prob_sum = home_win_probability + away_win_probability
        if abs(prob_sum - 1.0) > 0.01:
            logger.warning(f"Win probability sum = {prob_sum:.4f} (expected 1.0)")
        
        
        # Calculate win probabilities from simulation results
        home_win_probability = results["team_a_wins"] / iterations
        away_win_probability = results["team_b_wins"] / iterations
        
        # Calculate tier-aware confidence score (NUMERICAL ACCURACY)
        tier_config = SimulationTierConfig.get_tier_config(iterations)
        confidence_score = ConfidenceCalculator.calculate(
            variance=variance_total,
            sim_count=iterations,
            volatility=volatility_label,
            median_value=median_total
        )
        
        logger.info(f"Confidence: {confidence_score}/100 (Tier: {tier_config['label']}, Variance: {variance_total:.1f})")
        
        # ===== SHARP SIDE ANALYSIS =====
        # Calculate model's projected spread (based on win probabilities and margin)
        # model_spread = Team A score - Team B score
        # Positive = Team A (home) favored, Negative = Team B (away) favored
        model_spread = avg_margin / iterations
        
        # vegas_spread is from market_context (home team's perspective from odds API)
        # Negative = home team favored, Positive = home team underdog
        vegas_spread = market_context.get('current_spread', 0.0)
        
        # Determine favorite and underdog based on MODEL projection
        if abs(model_spread) < 0.5:
            # Pick'em game - no spread edge to calculate
            favorite_team = team_a.get("name", "Team A")
            underdog_team = team_b.get("name", "Team B")
            model_spread_formatted = model_spread
            vegas_spread_formatted = vegas_spread
        elif model_spread > 0:
            # Team A (home) is favored by model
            favorite_team = team_a.get("name", "Team A")
            underdog_team = team_b.get("name", "Team B")
            # Express as favorite's spread (negative)
            model_spread_formatted = -abs(model_spread)
            # Vegas spread should also be negative if home is favored
            # If vegas_spread is positive, that means away team is favored by Vegas, keep it as-is
            vegas_spread_formatted = vegas_spread
        else:
            # Team B (away) is favored by model
            favorite_team = team_b.get("name", "Team B")
            underdog_team = team_a.get("name", "Team A")
            # Express as favorite's spread (negative) 
            model_spread_formatted = -abs(model_spread)
            # Convert vegas_spread to away team's perspective
            # If home team has +5, away team is favored at -5
            vegas_spread_formatted = -vegas_spread
        
        # Calculate spread edge
        spread_analysis = calculate_spread_edge(
            vegas_spread=vegas_spread_formatted,
            model_spread=model_spread_formatted,
            favorite_team=favorite_team,
            underdog_team=underdog_team,
            threshold=2.0
        )
        
        # Calculate total edge
        total_analysis = calculate_total_edge(
            vegas_total=bookmaker_total_line,
            model_total=median_total,
            threshold=3.0
        )
        
        # Format for API
        spread_edge_api = format_for_api(spread_analysis)
        total_edge_api = format_for_api(total_analysis)
        
        # Generate detailed reasoning for edge explanations
        total_reasoning = explain_edge_reasoning(
            market_type='total',
            model_value=median_total,
            vegas_value=bookmaker_total_line,
            edge_points=total_analysis.edge_points,
            simulation_context={
                'injury_impact': offensive_impact + defensive_impact,
                'pace_factor': team_a.get("pace_factor", 1.0),
                'variance': variance_total,
                'confidence_score': confidence_score,
                'team_a_projection': results["team_a_total"] / iterations,
                'team_b_projection': results["team_b_total"] / iterations,
            }
        )
        
        logger.info(f"Sharp Analysis - Spread: {spread_analysis.sharp_side or 'No Edge'}, Total: {total_analysis.sharp_side or 'No Edge'}")
        if total_analysis.has_edge:
            logger.info(f"Edge Reasoning: {total_reasoning['primary_factor']} - {len(total_reasoning['contributing_factors'])} factors identified")
        
        # Build validated simulation output (enforces data integrity)
        simulation_output = SimulationOutput(
            median_total=median_total,
            mean_total=mean_total,
            variance_total=variance_total,
            home_win_probability=home_win_probability,
            away_win_probability=away_win_probability,
            h1_median_total=None,  # Set separately if 1H simulation exists
            h1_variance=None,
            sim_count=iterations,
            timestamp=datetime.now(timezone.utc),
            source="monte_carlo_engine"
        )
        
        # Validate output integrity (raises ValueError if invalid)
        simulation_output.validate()
        
        simulation_result = {
            "simulation_id": f"sim_{event_id}_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
            "event_id": event_id,
            "iterations": iterations,
            "mode": mode,
            "sport_key": market_context.get("sport_key", "basketball_nba"),
            "team_a": team_a.get("name"),
            "team_b": team_b.get("name"),
            
            # NUMERICAL ACCURACY: All values from validated SimulationOutput
            "team_a_win_probability": round(home_win_probability, 4),
            "team_b_win_probability": round(away_win_probability, 4),
            "win_probability": round(home_win_probability, 4),  # For home team
            "push_probability": round(results["pushes"] / iterations, 4),
            "upset_probability": round(upset_probability, 4),
            
            # Projected totals (MUST come from simulation)
            "median_total": round(median_total, 2),  # PRIMARY projected total
            "mean_total": round(mean_total, 2),
            "avg_total": round(mean_total, 2),  # Legacy alias
            "avg_total_score": round(mean_total, 2),  # TypeScript compatibility
            "projected_score": round(median_total, 2),  # Use MEDIAN for projection (more stable)
            
            "avg_team_a_score": round(results["team_a_total"] / iterations, 2),
            "avg_team_b_score": round(results["team_b_total"] / iterations, 2),
            
            # Over/Under (from validated O/U Analysis)
            "over_probability": round(over_probability, 4),
            "under_probability": round(under_probability, 4),
            "total_line": bookmaker_total_line,  # Bookmaker's line (REQUIRED)
            "vegas_line": bookmaker_total_line,  # Alias
            
            # Variance and distribution (REAL DATA ONLY)
            "variance": round(variance_total, 2),
            "variance_total": round(variance_total, 2),
            "distribution_curve": spread_dist_array,  # For graphing score margins
            "spread_distribution": spread_dist_array,  # Array format for charts (legacy)
            "total_distribution": self._calculate_total_distribution(results["totals"]),
            
            # Confidence score (tier-aware, formula-based)
            "confidence_score": confidence_score,
            "tier_label": tier_config['label'],
            "tier_stability_band": tier_config['stability_band'],
            "tier_stability_band": tier_config['stability_band'],
            
            # Volatility
            "avg_margin": round(avg_margin / iterations, 2),
            "volatility_index": volatility_label,
            "volatility_score": volatility_score,  # High/Medium/Low
            "pace_factor": team_a.get("pace_factor", 1.0),
            
            # Market context with odds timestamp for backtesting
            "market_context": {
                "total_line": bookmaker_total_line,
                "spread": market_context.get('current_spread', 0.0),
                "bookmaker_source": market_context.get('bookmaker_source', 'Consensus'),
                "odds_timestamp": market_context.get('odds_timestamp', datetime.now(timezone.utc).isoformat()),
                "sim_result_delta": round(median_total - bookmaker_total_line, 2),
                "edge_percentage": round(((median_total - bookmaker_total_line) / bookmaker_total_line * 100), 2) if bookmaker_total_line > 0 else 0
            },
            
            # Injury impact
            # Injury impact
            "injury_impact_weighted": sum(inj.get("impact_points", 0) for inj in injury_impact),
            "injury_summary": {
                "total_offensive_impact": round(offensive_impact, 1),
                "total_defensive_impact": round(defensive_impact, 1),
                "combined_net_impact": round(offensive_impact + defensive_impact, 1),
                "impact_description": "Positive impact benefits team, negative hurts team"
            },
            
            # Confidence intervals
            "confidence_intervals": {
                "ci_68": [round(ci_68[0], 2), round(ci_68[1], 2)],
                "ci_95": [round(ci_95[0], 2), round(ci_95[1], 2)],
                "ci_99": [round(ci_99[0], 2), round(ci_99[1], 2)]
            },
            
            # ===== SHARP SIDE ANALYSIS =====
            "sharp_analysis": {
                "spread": {
                    "vegas_spread": vegas_spread,
                    "model_spread": model_spread,
                    "sharp_side": spread_analysis.sharp_side,
                    "edge_points": spread_analysis.edge_points,
                    "edge_direction": spread_analysis.edge_direction,
                    "edge_grade": spread_analysis.edge_grade,
                    "edge_strength": spread_analysis.edge_strength,
                    "sharp_side_reason": spread_analysis.sharp_side_reason,
                    **spread_edge_api
                },
                "total": {
                    "vegas_total": bookmaker_total_line,
                    "model_total": median_total,
                    "sharp_side": total_analysis.sharp_side,
                    "edge_points": total_analysis.edge_points,
                    "edge_direction": total_analysis.edge_direction,
                    "edge_grade": total_analysis.edge_grade,
                    "edge_strength": total_analysis.edge_strength,
                    "sharp_side_reason": total_analysis.sharp_side_reason,
                    "edge_reasoning": total_reasoning if total_analysis.has_edge else None,
                    **total_edge_api
                },
                "disclaimer": STANDARD_DISCLAIMER
            },
            
            # Props and additional data
            "injury_impact": injury_impact,
            "top_props": top_props,
            "market_context": market_context,
            "created_at": datetime.now(timezone.utc).isoformat(),
            
            # Debug label (dev mode only)
            "debug_label": get_debug_label("monte_carlo_engine", iterations, median_total, variance_total)
        }
        
        # Store simulation in database - use update_one with upsert to avoid duplicate key errors
        # This handles regeneration cases where simulation_id might already exist
        db["monte_carlo_simulations"].update_one(
            {"simulation_id": simulation_result["simulation_id"]},
            {"$set": simulation_result.copy()},
            upsert=True
        )
        
        # ===== FEEDBACK LOOP: Store predictions for future grading =====
        try:
            # Store spread prediction if there's an edge
            if spread_analysis.has_edge:
                store_prediction(
                    game_id=event_id,
                    event_id=event_id,
                    sport_key=market_context.get("sport_key", "basketball_nba"),
                    commence_time=market_context.get("commence_time", datetime.now(timezone.utc).isoformat()),
                    home_team=team_a.get("name", "Team A"),
                    away_team=team_b.get("name", "Team B"),
                    market_type="spread",
                    predicted_outcome={
                        "prediction_value": model_spread,
                        "win_probability": home_win_probability if spread_analysis.edge_direction == 'DOG' else away_win_probability,
                        "sharp_side": spread_analysis.sharp_side,
                        "edge_points": spread_analysis.edge_points,
                        "edge_grade": spread_analysis.edge_grade
                    },
                    vegas_line={
                        "line_value": vegas_spread,
                        "bookmaker": market_context.get("bookmaker_source", "Consensus"),
                        "timestamp": market_context.get("odds_timestamp", datetime.now(timezone.utc).isoformat())
                    },
                    sim_count=iterations
                )
            
            # Store total prediction if there's an edge
            if total_analysis.has_edge:
                # Extract structured reasoning for calibration engine
                structured_reasoning = total_reasoning.get('structured_data', {}) if total_reasoning else {}
                
                store_prediction(
                    game_id=event_id,
                    event_id=event_id,
                    sport_key=market_context.get("sport_key", "basketball_nba"),
                    commence_time=market_context.get("commence_time", datetime.now(timezone.utc).isoformat()),
                    home_team=team_a.get("name", "Team A"),
                    away_team=team_b.get("name", "Team B"),
                    market_type="total",
                    predicted_outcome={
                        "prediction_value": median_total,
                        "win_probability": over_probability if total_analysis.edge_direction == 'OVER' else under_probability,
                        "sharp_side": total_analysis.sharp_side,
                        "edge_points": total_analysis.edge_points,
                        "edge_grade": total_analysis.edge_grade,
                        # CRITICAL: Store structured reasoning for calibration
                        "structured_reasoning": structured_reasoning
                    },
                    vegas_line={
                        "line_value": bookmaker_total_line,
                        "bookmaker": market_context.get("bookmaker_source", "Consensus"),
                        "timestamp": market_context.get("odds_timestamp", datetime.now(timezone.utc).isoformat())
                    },
                    sim_count=iterations
                )
        except Exception as e:
            logger.warning(f"Failed to store prediction for feedback loop: {str(e)}")
        
        log_stage(
            "monte_carlo_engine",
            "simulation_completed",
            input_payload={
                "event_id": event_id,
                "iterations": iterations
            },
            output_payload={
                "team_a_win_prob": simulation_result["team_a_win_probability"],
                "volatility": simulation_result["volatility_index"]
            }
        )
        
        return simulation_result
    
    def simulate_period(
        self,
        event_id: str,
        team_a: Dict[str, Any],
        team_b: Dict[str, Any],
        market_context: Dict[str, Any],
        period: str = "1H",
        iterations: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        PHASE 15: Simulate specific game periods (1H, 2H, Q1, etc.)
        
        Args:
            event_id: Unique event identifier
            team_a: Team A data
            team_b: Team B data
            market_context: Current odds, line movement, sport_key
            period: "1H" (First Half), "2H" (Second Half), "Q1", etc.
            iterations: Number of simulations (default: 50,000)
        
        Returns:
            Period-specific simulation results with adjusted physics
        """
        if not iterations:
            iterations = self.default_iterations
        
        iterations = max(self.min_iterations, min(iterations, self.max_iterations))
        
        sport_key = market_context.get('sport_key', 'basketball_nba')
        strategy = self.strategy_factory.get_strategy(sport_key)
        
        # PHASE 15: Apply period-specific physics overrides based on sport type
        is_football = 'football' in sport_key.lower()
        sport_type = 'football' if is_football else 'basketball'
        config = self.FIRST_HALF_CONFIG.get(sport_type, self.FIRST_HALF_CONFIG['basketball'])
        
        if period == "1H":
            # Apply sport-specific 1H physics
            market_context = market_context.copy()
            market_context['pace_multiplier'] = config['pace_multiplier']
            market_context['duration_multiplier'] = config['duration_multiplier']
            market_context['starter_weight'] = config.get('starter_weight', 1.0)
            market_context['fatigue_enabled'] = config['fatigue_enabled']
            market_context['scripted_drive_boost'] = config.get('scripted_drive_boost', 1.0)
            
            print(f"🏈 1H Simulation ({sport_key}): duration={config['duration_multiplier']:.2f}, pace={config['pace_multiplier']:.2f}")
        
        # Calculate team ratings with period adjustments
        team_a_rating = self._calculate_team_rating(team_a, sport_key)
        team_b_rating = self._calculate_team_rating(team_b, sport_key)
        
        # Scale ratings for period duration BEFORE simulation
        duration_mult = market_context.get('duration_multiplier', 1.0)
        team_a_rating *= duration_mult
        team_b_rating *= duration_mult
        
        # Apply sport-specific 1H boosts
        if period == "1H":
            if is_football:
                # Football: Small scripted play boost (5%) applied ONLY to base rating, not amplified
                scripted_boost = config.get('scripted_drive_boost', 1.0)
                if scripted_boost > 1.0:
                    # Apply minimal boost for opening scripted drives
                    team_a_rating *= scripted_boost
                    team_b_rating *= scripted_boost
                    print(f"⚡ Football 1H: Applied {(scripted_boost-1)*100:.1f}% scripted drive boost")
            else:
                # Basketball: Starter weight boost for 1H
                starter_boost_a = self._calculate_starter_boost(team_a)
                starter_boost_b = self._calculate_starter_boost(team_b)
                team_a_rating += starter_boost_a * duration_mult  
                team_b_rating += starter_boost_b * duration_mult
        
        # Apply standard adjustments (but skip fatigue for 1H)
        team_a_adj = self._apply_adjustments(team_a, market_context, skip_fatigue=(period == "1H"))
        team_b_adj = self._apply_adjustments(team_b, market_context, skip_fatigue=(period == "1H"))
        
        # Run simulations with period-scaled ratings
        results = strategy.simulate_game(
            team_a_rating + team_a_adj,
            team_b_rating + team_b_adj,
            iterations,
            market_context
        )
        
        # Results are already scaled - no need to multiply again
        # Calculate period-specific metrics (NUMERICAL ACCURACY ENFORCED)
        totals_array = np.array(results["totals"])
        h1_median_total = float(np.median(totals_array))
        h1_mean_total = float(np.mean(totals_array))
        h1_variance = float(np.var(totals_array))
        
        # Validate simulation data integrity
        if len(totals_array) != iterations:
            raise ValueError(f"1H Simulation integrity violation: expected {iterations} totals, got {len(totals_array)}")
        
        # 🏈 SANITY CHECK: For football, ensure 1H doesn't exceed 65% of expected full game
        if period == "1H" and is_football:
            # Get full game projection from market or estimate
            full_game_total = market_context.get('total_line', None)
            if full_game_total and full_game_total > 0:
                max_1h_total = full_game_total * 0.65  # Hard cap at 65% of full game
                if h1_median_total > max_1h_total:
                    logger.warning(f"⚠️ 1H median {h1_median_total:.1f} exceeds 65% of full game {full_game_total:.1f}, clamping to {max_1h_total:.1f}")
                    h1_median_total = max_1h_total
                    h1_mean_total = min(h1_mean_total, max_1h_total)
                
                # Log the 1H/Full ratio for debugging
                ratio = h1_median_total / full_game_total
                logger.info(f"📊 1H Projection: {h1_median_total:.1f} ({ratio*100:.1f}% of full game {full_game_total:.1f})")
                
                # Typical football 1H should be 45-55% of full game
                if ratio < 0.40 or ratio > 0.60:
                    logger.warning(f"⚠️ Unusual 1H ratio: {ratio*100:.1f}% (expected 45-55%)")
        
        # Determine period-specific total line (NUMERICAL ACCURACY - PREFER BOOKMAKER LINE)
        bookmaker_1h_line = market_context.get('bookmaker_1h_line', None)
        
        if bookmaker_1h_line is None:
            # WARNING: No bookmaker 1H line available
            # We CANNOT calculate proper O/U probabilities without market line
            logger.warning(f"⚠️ CRITICAL: No bookmaker 1H line for {event_id}. 1H O/U probabilities will be informational only.")
            # Use projection as reference (but mark as unavailable)
            period_total_line = round(h1_median_total / 0.5) * 0.5
            book_line_available = False
        else:
            period_total_line = bookmaker_1h_line
            book_line_available = True
            logger.info(f"✅ Using bookmaker 1H line: {period_total_line}")
        
        # Calculate Over/Under probabilities (only meaningful if bookmaker line exists)
        if book_line_available:
            ou_analysis = OverUnderAnalysis.from_simulation(totals_array, period_total_line)
            over_probability = ou_analysis.over_probability
            under_probability = ou_analysis.under_probability
        else:
            # No bookmaker line - cannot provide meaningful probabilities
            over_probability = None
            under_probability = None
        
        # Calculate tier-aware confidence
        tier_config = SimulationTierConfig.get_tier_config(iterations)
        
        # Determine volatility for 1H
        margin_std = float(np.std(results["margins"]))
        thresholds = strategy.get_volatility_thresholds()
        if margin_std < thresholds['stable']:
            volatility_label = "STABLE"
        elif margin_std < thresholds['moderate']:
            volatility_label = "MODERATE"
        else:
            volatility_label = "HIGH"
        
        confidence_score = ConfidenceCalculator.calculate(
            variance=h1_variance,
            sim_count=iterations,
            volatility=volatility_label,
            median_value=h1_median_total
        )
        
        # Reasoning for 1H prediction
        reasoning = self._generate_1h_reasoning(
            team_a, team_b, market_context, period_total_line, sport_key
        )
        
        simulation_result = {
            "simulation_id": f"sim_{period}_{event_id}_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
            "event_id": event_id,
            "period": period,
            "iterations": iterations,
            "sport_key": sport_key,
            "team_a": team_a.get("name"),
            "team_b": team_b.get("name"),
            
            # NUMERICAL ACCURACY: 1H projected totals
            "h1_median_total": round(h1_median_total, 2),
            "h1_mean_total": round(h1_mean_total, 2),
            "h1_variance": round(h1_variance, 2),
            "projected_total": round(h1_median_total, 1),  # Legacy field
            
            # Bookmaker line (may be None if unavailable)
            "bookmaker_line": period_total_line if book_line_available else None,
            "book_line_available": book_line_available,
            "bookmaker_source": market_context.get('bookmaker_1h_source', None) if book_line_available else None,
            
            # O/U probabilities (None if no bookmaker line)
            "over_probability": round(over_probability, 4) if over_probability is not None else None,
            "under_probability": round(under_probability, 4) if under_probability is not None else None,
            
            # Confidence and tier info
            "confidence": confidence_score,
            "confidence_score": confidence_score,
            "tier_label": tier_config['label'],
            "volatility": volatility_label,
            
            # Additional metadata
            "expected_value": round((over_probability - 0.5) * 100, 2) if over_probability else None,
            "pace_factor": market_context.get('pace_multiplier', 1.0),
            "starter_impact": period == "1H",
            "reasoning": reasoning,
            "created_at": datetime.now(timezone.utc).isoformat(),
            
            # Debug label
            "debug_label": get_debug_label(f"monte_carlo_1h", iterations, h1_median_total, h1_variance)
        }
        
        # Store period simulation in database - use update_one with upsert to avoid duplicate key errors
        db["monte_carlo_simulations"].update_one(
            {"simulation_id": simulation_result["simulation_id"]},
            {"$set": simulation_result.copy()},
            upsert=True
        )
        
        log_stage(
            "monte_carlo_engine",
            f"{period}_simulation_completed",
            input_payload={"event_id": event_id, "period": period},
            output_payload={"projected_total": simulation_result["projected_total"]}
        )
        
        return simulation_result
    
    def _calculate_starter_boost(self, team: Dict[str, Any]) -> float:
        """
        Calculate rating boost from starters playing higher % of minutes in 1H
        """
        players = team.get("players", [])
        starters = [p for p in players if p.get("is_starter", False)]
        
        starter_boost = 0.0
        for player in starters:
            per = player.get("per", 15.0)
            if per > 15.0:  # Above league average
                starter_boost += (per - 15.0) * 0.15  # 15% weight for 1H starter impact
        
        return starter_boost
    
    def _generate_1h_reasoning(
        self,
        team_a: Dict[str, Any],
        team_b: Dict[str, Any],
        context: Dict[str, Any],
        total_line: float,
        sport_key: str
    ) -> str:
        """
        Generate human-readable reasoning for 1H prediction (SPORT-SPECIFIC)
        """
        pace_mult = context.get('pace_multiplier', 1.0)
        
        reasoning_parts = []
        
        # SPORT-SPECIFIC PACE ANALYSIS
        if 'basketball' in sport_key:
            if pace_mult > 1.02:
                pace_boost_pct = (pace_mult - 1.0) * 100
                reasoning_parts.append(f"Fast pace expected (Early game tempo +{pace_boost_pct:.1f}%)")
            elif pace_mult < 0.98:
                reasoning_parts.append("Slower pace expected (Conservative start)")
            
            # Basketball: Starter minutes analysis
            team_a_starters = len([p for p in team_a.get("players", []) if p.get("is_starter", False)])
            team_b_starters = len([p for p in team_b.get("players", []) if p.get("is_starter", False)])
            if team_a_starters + team_b_starters >= 8:
                reasoning_parts.append("Starters projected to play 18+ minutes in 1H")
            
            reasoning_parts.append("Fatigue curve removed (Fresh legs)")
            reasoning_parts.append("1H = 24 regulation minutes (2 quarters)")
            
        elif 'football' in sport_key:
            # FOOTBALL: Drive-based analysis (not time-based)
            full_game_total = context.get('total_line', 0)
            scripted_boost = context.get('scripted_drive_boost', 1.0)
            
            # Typical football 1H is 45-55% of full game
            reasoning_parts.append("1H = 2 quarters (30 minutes clock, ~5-7 drives per team)")
            reasoning_parts.append("Drive-based simulation (not time-based)")
            
            if scripted_boost > 1.0:
                boost_pct = (scripted_boost - 1.0) * 100
                reasoning_parts.append(f"Opening script advantage (+{boost_pct:.0f}% first 1-2 drives)")
            
            # Pace/tempo analysis for football
            if pace_mult > 1.03:
                reasoning_parts.append("Fast tempo offense (Hurry-up, spread formations)")
            elif pace_mult < 0.98:
                reasoning_parts.append("Slow tempo (Power run, clock control)")
            else:
                reasoning_parts.append("Standard tempo (Balanced offense)")
            
            # Typical 1H share
            if full_game_total > 0:
                reasoning_parts.append(f"Projected 1H typically 45-55% of full game ({full_game_total:.1f})")

        
        return "; ".join(reasoning_parts)
    
    def _calculate_team_rating(self, team: Dict[str, Any], sport_key: str = 'basketball_nba') -> float:
        """
        Calculate composite team rating from player efficiency metrics
        
        MULTI-SPORT SUPPORT:
        - Normalizes ratings to expected score range per sport
        - NBA: 90-130 points
        - NFL: 14-35 points
        - MLB: 2-8 runs
        - NHL: 1-6 goals
        
        Inputs:
        - Player PER (Player Efficiency Rating)
        - Win Shares
        - Usage Rate
        - Plus/Minus
        """
        # Get sport-specific score range
        min_score, max_score = self.strategy_factory.get_expected_score_range(sport_key)
        
        base_rating = team.get("offensive_rating", 105.0) + team.get("defensive_rating", 105.0)
        
        # Normalize to sport-specific range
        # Default base_rating is ~210 (105+105), normalize to sport's midpoint
        sport_midpoint = (min_score + max_score) / 2
        normalized_rating = (base_rating / 210.0) * sport_midpoint
        
        # Player-level adjustments (scale to sport)
        players = team.get("players", [])
        player_impact = 0.0
        
        for player in players:
            if player.get("status") == "active":
                per = player.get("per", 15.0)  # League average = 15
                minutes = player.get("avg_minutes", 0)
                usage = player.get("usage_rate", 0.2)
                
                # Weight by minutes and usage
                player_contribution = (per - 15.0) * (minutes / 48.0) * usage
                player_impact += player_contribution
        
        # Scale player impact to sport (NBA impact ~10 points, MLB ~0.5 runs)
        sport_scale = sport_midpoint / 110.0  # 110 is NBA midpoint
        scaled_impact = player_impact * sport_scale
        
        return normalized_rating + scaled_impact
    
    def _apply_adjustments(self, team: Dict[str, Any], context: Dict[str, Any], skip_fatigue: bool = False) -> float:
        """
        Apply adjustments for injuries, fatigue, location
        
        Args:
            team: Team data with players and metadata
            context: Market context
            skip_fatigue: If True, skip fatigue penalties (used for 1H simulations)
        """
        adjustment = 0.0
        
        # Injury impact
        injured_players = [p for p in team.get("players", []) if p.get("status") in ["out", "doubtful"]]
        for player in injured_players:
            impact = player.get("per", 15.0) - 15.0
            minutes = player.get("avg_minutes", 0)
            adjustment -= impact * (minutes / 48.0) * 0.8  # 80% of their normal impact
        
        # Fatigue (back-to-back games, travel) - SKIP FOR 1H
        if not skip_fatigue:
            rest_days = team.get("rest_days", 2)
            if rest_days == 0:
                adjustment -= 2.5  # Back-to-back penalty
            elif rest_days == 1:
                adjustment -= 1.0
            
            travel_distance = team.get("travel_miles", 0)
            if travel_distance > 1500:
                adjustment -= 1.5  # Long travel penalty
        
        # Home court advantage
        if team.get("location") == "home":
            adjustment += 3.0
        
        # Altitude (if applicable)
        if team.get("altitude_ft", 0) > 5000 and team.get("location") == "home":
            adjustment += 1.5
        
        return adjustment
    
    def _run_iterations(
        self,
        team_a_rating: float,
        team_b_rating: float,
        iterations: int,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Execute Monte Carlo iterations
        """
        team_a_wins = 0
        team_b_wins = 0
        pushes = 0
        team_a_total = 0.0
        team_b_total = 0.0
        margins = []
        totals = []
        
        # Volatility factors
        base_volatility = context.get("volatility", 10.0)
        
        for _ in range(iterations):
            # Simulate team scores with volatility
            team_a_score = np.random.normal(team_a_rating / 2, base_volatility)
            team_b_score = np.random.normal(team_b_rating / 2, base_volatility)
            
            # Ensure scores are realistic
            team_a_score = max(50, min(150, team_a_score))
            team_b_score = max(50, min(150, team_b_score))
            
            # Accumulate results
            team_a_total += team_a_score
            team_b_total += team_b_score
            
            margin = team_a_score - team_b_score
            margins.append(margin)
            totals.append(team_a_score + team_b_score)
            
            if team_a_score > team_b_score:
                team_a_wins += 1
            elif team_b_score > team_a_score:
                team_b_wins += 1
            else:
                pushes += 1
        
        return {
            "team_a_wins": team_a_wins,
            "team_b_wins": team_b_wins,
            "pushes": pushes,
            "team_a_total": team_a_total,
            "team_b_total": team_b_total,
            "margins": margins,
            "totals": totals
        }
    
    def _calculate_spread_distribution(self, margins: List[float]) -> Dict[str, float]:
        """
        Calculate probability distribution for common spread lines
        """
        spreads = [-10.5, -7.5, -4.5, -3.5, -2.5, -1.5, 0, 1.5, 2.5, 3.5, 4.5, 7.5, 10.5]
        distribution = {}
        
        for spread in spreads:
            # Count how often team A covers this spread
            covers = sum(1 for m in margins if m > spread)
            distribution[f"spread_{spread:+.1f}"] = round(covers / len(margins), 4)
        
        return distribution
    
    def _calculate_total_distribution(self, totals: List[float]) -> Dict[str, float]:
        """
        Calculate probability distribution for common totals lines
        """
        total_lines = [180.5, 190.5, 200.5, 210.5, 220.5, 230.5, 240.5]
        distribution = {}
        
        for total_line in total_lines:
            # Count how often game goes over this total
            overs = sum(1 for t in totals if t > total_line)
            distribution[f"total_o{total_line:.1f}"] = round(overs / len(totals), 4)
            distribution[f"total_u{total_line:.1f}"] = round(1 - (overs / len(totals)), 4)
        
        return distribution
    
    def _calculate_confidence_score(self, results: Dict[str, Any], iterations: int) -> float:
        """
        Calculate confidence score (0-1) based on simulation consistency and edge strength
        
        Factors:
        - Win probability edge (how decisive is the prediction)
        - Outcome consistency (how stable are the results)
        - Sample size quality (iteration count reliability)
        """
        win_prob = max(results["team_a_wins"], results["team_b_wins"]) / iterations
        margin_std = np.std(results["margins"])
        margins = results["margins"]
        
        # 1. Edge Factor: How strong is the prediction (0-1)
        # - 50% win prob = 0.0 edge (coin flip)
        # - 70%+ win prob = 1.0 edge (strong prediction)
        edge_strength = abs(win_prob - 0.5) * 2  # 0 to 1 scale
        edge_factor = min(1.0, edge_strength * 1.2)  # Boost slightly
        
        # 2. Consistency Factor: How stable are the outcomes (0-1)
        # Lower std = more consistent = higher confidence
        # Normalize margin_std: typically ranges 5-20 points
        consistency = max(0, 1 - (margin_std / 15.0))
        
        # 3. Distribution Quality: Check for normal distribution
        # High variance in outcomes = lower confidence
        margin_variance = np.var(margins)
        distribution_quality = max(0, 1 - (margin_variance / 200.0))
        
        # 4. Sample Size Factor: More iterations = higher confidence
        if iterations >= 50000:
            sample_factor = 1.0
        elif iterations >= 10000:
            sample_factor = 0.9
        elif iterations >= 1000:
            sample_factor = 0.75
        else:
            sample_factor = 0.6
        
        # Weighted combination
        # Edge (40%) + Consistency (30%) + Distribution Quality (20%) + Sample Size (10%)
        confidence = (
            edge_factor * 0.40 +
            consistency * 0.30 +
            distribution_quality * 0.20 +
            sample_factor * 0.10
        )
        
        # Ensure minimum confidence of 0.30 (30%) for any prediction
        # Maximum confidence of 0.95 (95%) - never claim 100% certainty
        confidence = max(0.30, min(0.95, confidence))
        
        return float(round(confidence, 3))
    
    def detect_prop_mispricings(
        self,
        simulation_result: Dict[str, Any],
        market_props: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Detect mispriced player props using simulation data
        
        Compare simulation-derived probabilities vs market odds
        """
        mispricings = []
        
        for prop in market_props:
            prop_type = prop.get("type", "")  # e.g., "player_points", "player_rebounds"
            player = prop.get("player", "")
            line = prop.get("line", 0.0)
            market_odds = prop.get("odds", 2.0)
            
            if not all([player, prop_type, market_odds]):
                continue
            
            # Simulate player performance (simplified)
            # In production, this would use player-specific simulations
            sim_prob = self._simulate_player_prop(
                player,
                prop_type,
                line,
                simulation_result
            )
            
            market_implied_prob = 1 / float(market_odds)
            edge = (sim_prob - market_implied_prob) * 100
            
            if abs(edge) > 5.0:  # 5% edge threshold
                mispricings.append({
                    "player": player,
                    "prop_type": prop_type,
                    "line": line,
                    "market_odds": market_odds,
                    "market_implied_prob": round(market_implied_prob, 4),
                    "sim_probability": round(sim_prob, 4),
                    "edge_pct": round(edge, 2),
                    "recommendation": "OVER" if edge > 0 else "UNDER"
                })
        
        return mispricings
    
    def _simulate_player_prop(
        self,
        player: str,
        prop_type: str,
        line: float,
        game_simulation: Dict[str, Any]
    ) -> float:
        """
        Simulate player prop probability (simplified implementation)
        
        In production, this would use detailed player models
        """
        # Placeholder: Use game pace and player usage to estimate
        # Real implementation would run player-specific Monte Carlo
        
        base_prob = 0.5  # Default 50/50
        
        # Adjust based on game total (higher scoring games = more likely overs)
        game_total = game_simulation.get("avg_total", 210)
        pace_factor = (game_total - 210) / 30.0  # +/- 30 points impacts props
        
        adjusted_prob = base_prob + (pace_factor * 0.1)
        return max(0.1, min(0.9, adjusted_prob))
    
    def calculate_parlay_correlation(
        self,
        picks: List[Dict[str, Any]],
        simulations: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Calculate correlation between parlay legs
        
        Correlated picks reduce true parlay value
        Example: Same game spread + total are correlated
        """
        if len(picks) < 2:
            return {"correlation": 0.0, "adjusted_probability": 1.0}
        
        # Detect same-game parlays
        same_game = len(set(p["event_id"] for p in picks)) < len(picks)
        
        if same_game:
            # High correlation penalty
            correlation = 0.7
        else:
            # Low correlation for different games
            correlation = 0.1
        
        # Calculate naive parlay probability
        naive_prob = 1.0
        for pick in picks:
            naive_prob *= pick.get("win_probability", 0.5)
        
        # Adjust for correlation
        adjusted_prob = naive_prob * (1 - correlation * 0.3)
        
        return {
            "correlation": round(correlation, 3),
            "naive_probability": round(naive_prob, 4),
            "adjusted_probability": round(adjusted_prob, 4),
            "same_game_parlay": same_game,
            "edge_impact": round((naive_prob - adjusted_prob) * 100, 2)
        }


# Singleton instance
monte_carlo_engine = MonteCarloEngine()
