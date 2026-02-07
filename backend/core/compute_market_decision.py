"""
COMPUTE MARKET DECISION - SINGLE SOURCE OF TRUTH
=================================================

THIS IS THE ONLY FUNCTION ALLOWED TO COMPUTE MARKET OUTPUT.
All other paths (baseline, sharp_analysis, etc.) MUST BE DELETED.

NO UI-SIDE RECOMPUTATION ALLOWED.
"""

import hashlib
from datetime import datetime
from typing import Dict, Optional, List
from backend.core.market_decision import (
    MarketDecision, MarketType, Classification, ReleaseStatus,
    PickSpread, PickTotal, MarketSpread, MarketTotal, MarketMoneyline,
    ModelSpread, ModelTotal, ModelMoneyline, Probabilities, Edge, Risk, Debug
)
from backend.core.validate_market_decision import validate_market_decision


class MarketDecisionComputer:
    """
    SINGLE CANONICAL COMPUTE PATH.
    
    NO OTHER CODE PATH MAY COMPUTE:
    - direction
    - preference  
    - status
    - reasons
    - classification
    """
    
    def __init__(self, league: str, game_id: str, odds_event_id: str):
        self.league = league
        self.game_id = game_id
        self.odds_event_id = odds_event_id
        self.decision_version_counter = 0
    
    def compute_spread(
        self,
        odds_snapshot: Dict,
        sim_result: Dict,
        config: Dict,
        game_competitors: Dict[str, str]  # {team_id: team_name}
    ) -> MarketDecision:
        """
        Compute SPREAD market decision.
        
        Deterministic mapping:
        - pick.team_id determines which line to use
        - market.line = sportsbook line for that team_id (SIGNED)
        - model.fair_line = fair spread for SAME team_id (SIGNED)
        - edge_points = market.line - model.fair_line
        """
        
        # 1. Extract normalized odds (team_id -> line mapping)
        # This MUST come from league-agnostic normalization layer
        spread_lines = odds_snapshot.get('spread_lines', {})  # {team_id: {line, odds}}
        
        # 2. Get simulation output
        sim_spread_home = sim_result.get('model_spread_home_perspective', 0)
        home_cover_prob = sim_result.get('home_cover_probability', 0.5)
        away_cover_prob = 1 - home_cover_prob
        
        # 3. Determine pick (highest cover probability)
        home_team_id = list(game_competitors.keys())[0]
        away_team_id = list(game_competitors.keys())[1]
        
        if home_cover_prob > away_cover_prob:
            pick_team_id = home_team_id
            pick_team_name = game_competitors[home_team_id]
            model_prob = home_cover_prob
            market_line = spread_lines.get(home_team_id, {}).get('line', 0)
            model_fair_line = sim_spread_home
        else:
            pick_team_id = away_team_id
            pick_team_name = game_competitors[away_team_id]
            model_prob = away_cover_prob
            market_line = spread_lines.get(away_team_id, {}).get('line', 0)
            model_fair_line = -sim_spread_home  # Flip sign for away perspective
        
        # 4. Calculate edge
        edge_points = abs(market_line - model_fair_line)
        
        # 5. Classify
        classification = self._classify_spread(edge_points, model_prob, config)
        
        # 6. Generate reasons
        reasons = self._generate_reasons_spread(classification, edge_points, model_prob)
        
        # 7. Risk assessment
        volatility = sim_result.get('volatility', 'MODERATE')
        injury_impact = sim_result.get('total_injury_impact', 0)
        
        risk = Risk(
            volatility_flag=volatility,
            injury_impact=injury_impact,
            clv_forecast=None,
            blocked_reason=None
        )
        
        # 8. Release status (default OFFICIAL if classification is EDGE)
        release_status = self._determine_release_status(classification, risk)
        
        # 9. Build decision
        inputs_hash = self._compute_inputs_hash(odds_snapshot, sim_result, config)
        
        decision = MarketDecision(
            league=self.league,
            game_id=self.game_id,
            odds_event_id=self.odds_event_id,
            market_type=MarketType.SPREAD,
            selection_id=f"{self.game_id}_spread_{pick_team_id}",
            pick=PickSpread(team_id=pick_team_id, team_name=pick_team_name, side=None),
            market=MarketSpread(line=market_line, odds=spread_lines.get(pick_team_id, {}).get('odds')),
            model=ModelSpread(fair_line=model_fair_line),
            probabilities=Probabilities(
                model_prob=model_prob,
                market_implied_prob=self._get_implied_prob(spread_lines.get(pick_team_id, {}).get('odds', -110))
            ),
            edge=Edge(edge_points=edge_points, edge_ev=None, edge_grade=self._grade_edge(edge_points)),
            classification=classification,
            release_status=release_status,
            reasons=reasons,
            risk=risk,
            debug=Debug(
                inputs_hash=inputs_hash,
                odds_timestamp=odds_snapshot.get('timestamp', datetime.utcnow().isoformat()),
                sim_run_id=sim_result.get('simulation_id', 'unknown'),
                config_profile=config.get('profile', 'balanced'),
                decision_version=self._next_version()
            ),
            validator_failures=[]
        )
        
        # 10. VALIDATE (block if fails)
        is_valid, violations = validate_market_decision(decision, game_competitors)
        if not is_valid:
            decision.release_status = ReleaseStatus.BLOCKED_BY_INTEGRITY
            decision.validator_failures = violations
        
        return decision
    
    def compute_total(
        self,
        odds_snapshot: Dict,
        sim_result: Dict,
        config: Dict,
        game_competitors: Dict[str, str]
    ) -> MarketDecision:
        """Compute TOTAL market decision"""
        
        total_lines = odds_snapshot.get('total_lines', {})
        market_total = total_lines.get('line', 220)
        
        model_fair_total = sim_result.get('rcl_total', market_total)
        over_prob = sim_result.get('over_probability', 0.5)
        under_prob = 1 - over_prob
        
        # Determine side
        if model_fair_total > market_total:
            pick_side = "OVER"
            model_prob = over_prob
        else:
            pick_side = "UNDER"
            model_prob = under_prob
        
        edge_points = abs(model_fair_total - market_total)
        classification = self._classify_total(edge_points, model_prob, config)
        reasons = self._generate_reasons_total(classification, edge_points, pick_side)
        
        risk = Risk(
            volatility_flag=sim_result.get('volatility', 'MODERATE'),
            injury_impact=sim_result.get('total_injury_impact', 0),
            clv_forecast=None,
            blocked_reason=None
        )
        
        release_status = self._determine_release_status(classification, risk)
        inputs_hash = self._compute_inputs_hash(odds_snapshot, sim_result, config)
        
        decision = MarketDecision(
            league=self.league,
            game_id=self.game_id,
            odds_event_id=self.odds_event_id,
            market_type=MarketType.TOTAL,
            selection_id=f"{self.game_id}_total_{pick_side.lower()}",
            pick=PickTotal(side=pick_side),
            market=MarketTotal(line=market_total, odds=total_lines.get('odds')),
            model=ModelTotal(fair_total=model_fair_total),
            probabilities=Probabilities(
                model_prob=model_prob,
                market_implied_prob=self._get_implied_prob(total_lines.get('odds', -110))
            ),
            edge=Edge(edge_points=edge_points, edge_ev=None, edge_grade=self._grade_edge(edge_points)),
            classification=classification,
            release_status=release_status,
            reasons=reasons,
            risk=risk,
            debug=Debug(
                inputs_hash=inputs_hash,
                odds_timestamp=odds_snapshot.get('timestamp', datetime.utcnow().isoformat()),
                sim_run_id=sim_result.get('simulation_id', 'unknown'),
                config_profile=config.get('profile', 'balanced'),
                decision_version=self._next_version()
            ),
            validator_failures=[]
        )
        
        is_valid, violations = validate_market_decision(decision, game_competitors)
        if not is_valid:
            decision.release_status = ReleaseStatus.BLOCKED_BY_INTEGRITY
            decision.validator_failures = violations
        
        return decision
    
    def _classify_spread(self, edge_points: float, model_prob: float, config: Dict) -> Classification:
        """Classify spread decision"""
        edge_threshold = config.get('edge_threshold', 2.0)
        lean_threshold = config.get('lean_threshold', 1.0)
        prob_threshold = config.get('prob_threshold', 0.55)
        
        if edge_points >= edge_threshold and model_prob >= prob_threshold:
            return Classification.EDGE
        elif edge_points >= lean_threshold:
            return Classification.LEAN
        else:
            return Classification.MARKET_ALIGNED
    
    def _classify_total(self, edge_points: float, model_prob: float, config: Dict) -> Classification:
        """Classify total decision"""
        return self._classify_spread(edge_points, model_prob, config)
    
    def _generate_reasons_spread(self, classification: Classification, edge_points: float, model_prob: float) -> List[str]:
        """Generate pre-computed reasons for spread"""
        if classification == Classification.MARKET_ALIGNED:
            return ["Model and market consensus detected", "No quantitative edge identified"]
        
        reasons = []
        if edge_points >= 2:
            reasons.append(f"Spread misprice detected: {edge_points:.1f} point edge")
        if model_prob >= 0.6:
            reasons.append(f"High cover probability: {model_prob*100:.1f}%")
        
        return reasons or ["Moderate edge identified"]
    
    def _generate_reasons_total(self, classification: Classification, edge_points: float, side: str) -> List[str]:
        """Generate pre-computed reasons for total"""
        if classification == Classification.MARKET_ALIGNED:
            return ["Model and market consensus on total", "No directional edge"]
        
        reasons = []
        if edge_points >= 2:
            reasons.append(f"Total misprice: {edge_points:.1f} points favoring {side}")
        
        return reasons or [f"{side} shows value"]
    
    def _determine_release_status(self, classification: Classification, risk: Risk) -> ReleaseStatus:
        """Determine if pick is official or info-only"""
        if classification == Classification.MARKET_ALIGNED or classification == Classification.NO_ACTION:
            return ReleaseStatus.INFO_ONLY
        
        if risk.volatility_flag == "HIGH":
            return ReleaseStatus.BLOCKED_BY_RISK
        
        return ReleaseStatus.OFFICIAL if classification == Classification.EDGE else ReleaseStatus.INFO_ONLY
    
    def _grade_edge(self, edge_points: float) -> Optional[str]:
        """Assign grade to edge"""
        if edge_points >= 5:
            return "S"
        elif edge_points >= 3:
            return "A"
        elif edge_points >= 2:
            return "B"
        elif edge_points >= 1:
            return "C"
        return "D"
    
    def _get_implied_prob(self, american_odds: Optional[int]) -> float:
        """Convert American odds to implied probability"""
        if not american_odds:
            return 0.5
        
        if american_odds > 0:
            return 100 / (american_odds + 100)
        else:
            return abs(american_odds) / (abs(american_odds) + 100)
    
    def _compute_inputs_hash(self, odds_snapshot: Dict, sim_result: Dict, config: Dict) -> str:
        """Compute deterministic hash of inputs"""
        hash_input = f"{odds_snapshot.get('timestamp')}{sim_result.get('simulation_id')}{config.get('profile')}"
        return hashlib.md5(hash_input.encode()).hexdigest()
    
    def _next_version(self) -> int:
        """Monotonic version counter"""
        self.decision_version_counter += 1
        return self.decision_version_counter
