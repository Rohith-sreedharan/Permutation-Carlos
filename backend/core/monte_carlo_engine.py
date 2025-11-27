"""
Monte Carlo Simulation Engine
Performs 10,000-100,000 iterations per game using granular inputs
NOW WITH MULTI-SPORT SUPPORT (NBA/NFL/MLB/NHL)
"""
import random
import numpy as np
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from db.mongo import db
from services.logger import log_stage
from core.sport_strategies import SportStrategyFactory


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
    
    def __init__(self):
        self.default_iterations = 50000
        self.min_iterations = 10000
        self.max_iterations = 100000
        self.strategy_factory = SportStrategyFactory()
    
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
        
        # Generate spread distribution as array
        spread_dist_array = []
        margin_counts = {}
        for m in margins_array:
            rounded = round(m)
            margin_counts[rounded] = margin_counts.get(rounded, 0) + 1
        
        for margin in sorted(margin_counts.keys()):
            spread_dist_array.append({
                "margin": float(margin),
                "probability": margin_counts[margin] / iterations
            })
        
        # Extract real injury data from team rosters
        injury_impact = []
        for team, team_data in [(team_a, team_a), (team_b, team_b)]:
            players = team_data.get("players", [])
            for player in players:
                status = player.get("status", "active").upper()
                if status in ["OUT", "DOUBTFUL", "QUESTIONABLE"]:
                    per = player.get("per", 15.0)
                    minutes = player.get("avg_minutes", 0)
                    usage = player.get("usage_rate", 0.2)
                    impact = (per - 15.0) * (minutes / 48.0) * usage
                    injury_impact.append({
                        "player": player.get("name", "Unknown Player"),
                        "team": team_data.get("name", "Unknown Team"),
                        "status": status,
                        "impact_points": round(impact, 1)
                    })
        
        # Calculate top props from actual player stats
        top_props = []
        all_players = []
        
        # Collect all active players from both teams
        for team_data in [team_a, team_b]:
            players = team_data.get("players", [])
            for player in players:
                if player.get("status", "active").lower() == "active":
                    all_players.append({
                        "player": player,
                        "team": team_data.get("name", "Unknown Team")
                    })
        
        # Sort by PER and get top 3 players
        all_players.sort(key=lambda x: x["player"].get("per", 0), reverse=True)
        
        for player_data in all_players[:3]:
            player = player_data["player"]
            ppg = player.get("ppg", 0)
            apg = player.get("apg", 0)
            rpg = player.get("rpg", 0)
            per = player.get("per", 15.0)
            
            # Determine primary prop type based on stats
            if ppg > apg and ppg > rpg:
                prop_type = "Points"
                line = ppg
                base_prob = 0.5 + (per - 15.0) / 50.0
            elif apg > rpg:
                prop_type = "Assists"
                line = apg
                base_prob = 0.5 + (per - 15.0) / 60.0
            else:
                prop_type = "Rebounds"
                line = rpg
                base_prob = 0.5 + (per - 15.0) / 55.0
            
            probability = max(0.4, min(0.7, base_prob))
            ev = (probability - 0.5) * 100
            
            top_props.append({
                "player": player.get("name", "Unknown Player"),
                "prop_type": prop_type,
                "line": round(line, 1),
                "probability": round(probability, 3),
                "ev": round(ev, 1)
            })
        
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
        
        # Calculate Over/Under probabilities for most common total line
        avg_total_score = (results["team_a_total"] + results["team_b_total"]) / iterations
        most_common_total = round(avg_total_score / 0.5) * 0.5  # Round to nearest 0.5
        overs = sum(1 for t in totals_array if t > most_common_total)
        over_probability = overs / iterations
        under_probability = 1 - over_probability
        
        simulation_result = {
            "simulation_id": f"sim_{event_id}_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
            "event_id": event_id,
            "iterations": iterations,
            "mode": mode,
            "team_a": team_a.get("name"),
            "team_b": team_b.get("name"),
            "team_a_win_probability": round(results["team_a_wins"] / iterations, 4),
            "team_b_win_probability": round(results["team_b_wins"] / iterations, 4),
            "win_probability": round(results["team_a_wins"] / iterations, 4),  # For home team
            "push_probability": round(results["pushes"] / iterations, 4),
            "upset_probability": round(upset_probability, 4),
            "avg_team_a_score": round(results["team_a_total"] / iterations, 2),
            "avg_team_b_score": round(results["team_b_total"] / iterations, 2),
            "avg_total": round(avg_total_score, 2),
            "avg_total_score": round(avg_total_score, 2),  # Alias for TypeScript compatibility
            "over_probability": round(over_probability, 4),
            "under_probability": round(under_probability, 4),
            "total_line": most_common_total,
            "avg_margin": round(avg_margin / iterations, 2),
            "distribution_curve": spread_dist_array,  # For graphing score margins
            "spread_distribution": spread_dist_array,  # Array format for charts (legacy)
            "total_distribution": self._calculate_total_distribution(results["totals"]),
            "variance": round(margin_std ** 2, 2),
            "volatility_index": volatility_label,
            "volatility_score": volatility_score,  # High/Medium/Low
            "pace_factor": team_a.get("pace_factor", 1.0),
            "injury_impact_weighted": sum(inj.get("impact_points", 0) for inj in injury_impact),
            "confidence_score": self._calculate_confidence_score(results, iterations),
            "confidence_intervals": {
                "ci_68": [round(ci_68[0], 2), round(ci_68[1], 2)],
                "ci_95": [round(ci_95[0], 2), round(ci_95[1], 2)],
                "ci_99": [round(ci_99[0], 2), round(ci_99[1], 2)]
            },
            "injury_impact": injury_impact,
            "top_props": top_props,
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        
        # Store simulation in database
        db["monte_carlo_simulations"].insert_one(simulation_result)
        
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
    
    def _apply_adjustments(self, team: Dict[str, Any], context: Dict[str, Any]) -> float:
        """
        Apply adjustments for injuries, fatigue, location
        """
        adjustment = 0.0
        
        # Injury impact
        injured_players = [p for p in team.get("players", []) if p.get("status") in ["out", "doubtful"]]
        for player in injured_players:
            impact = player.get("per", 15.0) - 15.0
            minutes = player.get("avg_minutes", 0)
            adjustment -= impact * (minutes / 48.0) * 0.8  # 80% of their normal impact
        
        # Fatigue (back-to-back games, travel)
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
        Calculate confidence score (0-1) based on simulation consistency
        
        Higher confidence = lower volatility in outcomes
        """
        win_prob = max(results["team_a_wins"], results["team_b_wins"]) / iterations
        margin_std = np.std(results["margins"])
        
        # Normalize confidence
        # Strong edge + low volatility = high confidence
        edge_factor = abs(win_prob - 0.5) * 2  # 0 to 1
        volatility_factor = max(0, 1 - (margin_std / 20.0))  # Lower std = higher confidence
        
        confidence = (edge_factor * 0.6 + volatility_factor * 0.4)
        return round(min(1.0, confidence), 3)
    
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
