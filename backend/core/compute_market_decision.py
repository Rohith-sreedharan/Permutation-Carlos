"""
COMPUTE MARKET DECISION - SINGLE SOURCE OF TRUTH
=================================================

THIS IS THE ONLY FUNCTION ALLOWED TO COMPUTE MARKET OUTPUT.
All other paths (baseline, sharp_analysis, etc.) MUST BE DELETED.

NO UI-SIDE RECOMPUTATION ALLOWED.
"""

import hashlib
import uuid
from datetime import datetime
from typing import Dict, Optional, List, Literal
from core.market_decision import (
    MarketDecision, MarketType, Classification, ReleaseStatus,
    PickSpread, PickTotal, MarketSpread, MarketTotal, MarketMoneyline,
    ModelSpread, ModelTotal, ModelMoneyline, Probabilities, Edge, Risk, Debug
)
from core.validate_market_decision import validate_market_decision


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
        # ATOMIC: One version per compute cycle (shared across all markets)
        self.bundle_version = 1
        self.bundle_computed_at = datetime.utcnow().isoformat()
        self.bundle_trace_id = str(uuid.uuid4())
    
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
                # Compute inputs hash early (needed for BLOCKED decisions)
        inputs_hash = self._compute_inputs_hash(odds_snapshot, sim_result, config)
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
        
        # 4. VALIDATION GATES (per spec Section 2.2 - run BEFORE classification)
        
        # 4a. Directional Integrity Gate (per spec Section 3)
        if not self._validate_directional_integrity_spread(sim_spread_home, home_cover_prob):
            # Return BLOCKED decision
            return self._create_blocked_spread_decision(
                pick_team_id, pick_team_name, market_line,
                spread_lines, game_competitors, home_team_id, inputs_hash,
                blocked_reason="Directional integrity violation: spread direction conflicts with probability",
                release_status=ReleaseStatus.BLOCKED_BY_INTEGRITY
            )
        
        # 4b. Odds Alignment Gate (per spec Section 4)
        simulation_market_spread = sim_result.get('simulation_market_spread_home')
        if simulation_market_spread is not None:
            # Get current market line for home team (same perspective as simulation)
            current_market_line_home = spread_lines.get(home_team_id, {}).get('line', 0)
            
            # REQUIREMENT 1: Absolute line delta logic
            line_delta = abs(simulation_market_spread - current_market_line_home)
            
            # REQUIREMENT 2: Pick'em symmetry check
            is_pickem = abs(current_market_line_home) < 0.01  # Treat as 0
            
            if is_pickem:
                # Check implied probability delta
                home_odds = spread_lines.get(home_team_id, {}).get('odds', -110)
                away_odds = spread_lines.get(away_team_id, {}).get('odds', -110)
                
                implied_prob_home = self._get_implied_prob(home_odds)
                implied_prob_away = self._get_implied_prob(away_odds)
                prob_delta = abs(implied_prob_home - implied_prob_away)
                
                # Boundary: 0.0200 = PASS, 0.02001 = BLOCK
                if prob_delta > 0.0200:
                    return self._create_blocked_spread_decision(
                        pick_team_id, pick_team_name, market_line,
                        spread_lines, game_competitors, home_team_id, inputs_hash,
                        blocked_reason=f"Pick'em symmetry violation: prob_delta={prob_delta:.4f} > 0.0200",
                        release_status=ReleaseStatus.BLOCKED_BY_ODDS_MISMATCH
                    )
            else:
                # Boundary: 0.25 = PASS, 0.25001 = BLOCK
                if line_delta > 0.25:
                    return self._create_blocked_spread_decision(
                        pick_team_id, pick_team_name, market_line,
                        spread_lines, game_competitors, home_team_id, inputs_hash,
                        blocked_reason=f"Odds movement: line_delta={line_delta:.4f} > 0.25 (sim={simulation_market_spread}, current={current_market_line_home})",
                        release_status=ReleaseStatus.BLOCKED_BY_ODDS_MISMATCH
                    )
        
        # 4c. Freshness Gate (per spec Section 5)
        computed_at_str = sim_result.get('computed_at')
        if computed_at_str and not self._validate_freshness(computed_at_str):
            return self._create_blocked_spread_decision(
                pick_team_id, pick_team_name, market_line,
                spread_lines, game_competitors, home_team_id, inputs_hash,
                blocked_reason="Simulation data stale (> 120 minutes old)",
                release_status=ReleaseStatus.BLOCKED_BY_STALE_DATA
            )
        
        # 5. Calculate edge
        edge_points = abs(market_line - model_fair_line)
        
        # 6. Classify
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
        
        # 8. Release status (default APPROVED if validations pass)
        release_status = self._determine_release_status(classification, risk)
        
        # 9. Build decision with canonical fields (inputs_hash already computed)
        selection_id = f"{self.game_id}_spread_{pick_team_id}"
        
        # Build market_selections (both sides of the spread)
        market_selections = [
            {
                "selection_id": f"{self.game_id}_spread_{home_team_id}",
                "team_id": home_team_id,
                "team_name": game_competitors[home_team_id],
                "line": spread_lines.get(home_team_id, {}).get('line', 0),
                "odds": spread_lines.get(home_team_id, {}).get('odds', -110)
            },
            {
                "selection_id": f"{self.game_id}_spread_{away_team_id}",
                "team_id": away_team_id,
                "team_name": game_competitors[away_team_id],
                "line": spread_lines.get(away_team_id, {}).get('line', 0),
                "odds": spread_lines.get(away_team_id, {}).get('odds', -110)
            }
        ]
        
        decision = MarketDecision(
            league=self.league,
            game_id=self.game_id,
            odds_event_id=self.odds_event_id,
            market_type=MarketType.SPREAD,
            decision_id=str(uuid.uuid4()),  # ← CANONICAL: Unique ID per decision
            selection_id=selection_id,
            preferred_selection_id=selection_id,  # ← CANONICAL: Bettable anchor
            market_selections=market_selections,  # ← CANONICAL: Both sides available
            pick=PickSpread(team_id=pick_team_id, team_name=pick_team_name, side=None),
            market=MarketSpread(line=market_line, odds=spread_lines.get(pick_team_id, {}).get('odds')),
            model=ModelSpread(fair_line=model_fair_line),
            fair_selection={  # ← CANONICAL: Fair line for preferred selection
                "line": model_fair_line,
                "team_id": pick_team_id
            },
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
                trace_id=self.bundle_trace_id,  # ← CANONICAL: Audit trail
                config_profile=config.get('profile', 'balanced'),
                decision_version=self.bundle_version,  # ← ATOMIC: Same version for all markets
                computed_at=self.bundle_computed_at  # ← CANONICAL: Consistent timestamp
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
        market_total = total_lines.get('line', 0)
        
        # Get model's projected total from simulation
        # The default value should already be league-appropriate from decisions.py
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
        selection_id = f"{self.game_id}_total_{pick_side.lower()}"
        
        # Build market_selections (over/under)
        market_selections = [
            {
                "selection_id": f"{self.game_id}_total_over",
                "side": "OVER",
                "line": market_total,
                "odds": total_lines.get('odds', -110)
            },
            {
                "selection_id": f"{self.game_id}_total_under",
                "side": "UNDER",
                "line": market_total,
                "odds": total_lines.get('odds', -110)
            }
        ]
        
        decision = MarketDecision(
            league=self.league,
            game_id=self.game_id,
            odds_event_id=self.odds_event_id,
            market_type=MarketType.TOTAL,
            decision_id=str(uuid.uuid4()),  # ← CANONICAL: Unique ID per decision
            selection_id=selection_id,
            preferred_selection_id=selection_id,  # ← CANONICAL: Bettable anchor
            market_selections=market_selections,  # ← CANONICAL: Both sides available
            pick=PickTotal(side=pick_side),
            market=MarketTotal(line=market_total, odds=total_lines.get('odds')),
            model=ModelTotal(fair_total=model_fair_total),
            fair_selection={  # ← CANONICAL: Fair total for preferred side
                "total": model_fair_total,
                "side": pick_side
            },
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
                trace_id=self.bundle_trace_id,  # ← CANONICAL: Audit trail
                config_profile=config.get('profile', 'balanced'),
                decision_version=self.bundle_version,  # ← ATOMIC: Same version for all markets
                computed_at=self.bundle_computed_at  # ← CANONICAL: Consistent timestamp
            ),
            validator_failures=[]
        )
        
        is_valid, violations = validate_market_decision(decision, game_competitors)
        if not is_valid:
            decision.release_status = ReleaseStatus.BLOCKED_BY_INTEGRITY
            decision.validator_failures = violations
        
        return decision
    
    def _classify_spread(self, edge_points: float, model_prob: float, config: Dict) -> Classification:
        """Classify spread decision using magnitude-based thresholds"""
        edge_threshold = config.get('edge_threshold', 2.0)
        lean_threshold = config.get('lean_threshold', 0.5)
        prob_threshold = config.get('prob_threshold', 0.55)
        
        # Use absolute value for magnitude-based classification (direction agnostic)
        edge_magnitude = abs(edge_points)
        
        # MARKET_ALIGNED: edge < 0.5 (model and market very close)
        if edge_magnitude < lean_threshold:
            return Classification.MARKET_ALIGNED
        
        # EDGE: edge >= 2.0 AND strong directional conviction (prob >= 55% or <= 45%)
        elif edge_magnitude >= edge_threshold:
            if model_prob >= prob_threshold or model_prob <= (1 - prob_threshold):
                return Classification.EDGE
            else:
                return Classification.LEAN
        
        # LEAN: 0.5 <= edge < 2.0
        else:
            return Classification.LEAN
    
    def _classify_total(self, edge_points: float, model_prob: float, config: Dict) -> Classification:
        """Classify total decision"""
        return self._classify_spread(edge_points, model_prob, config)
    
    def _generate_reasons_spread(self, classification: Classification, edge_points: float, model_prob: float) -> List[str]:
        """Generate pre-computed reasons for spread"""
        edge_mag = abs(edge_points)
        
        if classification == Classification.MARKET_ALIGNED:
            return ["Model and market consensus detected", "No significant value detected"]
        
        elif classification == Classification.LEAN:
            # LEAN: edge exists but probability gate not met
            if edge_mag >= 10:
                return [f"Large spread disagreement ({edge_mag:.1f} pts) but cover probability insufficient for EDGE classification"]
            elif edge_mag >= 5:
                return [f"Significant spread disagreement ({edge_mag:.1f} pts) but probability gate not met"]
            else:
                return [f"Moderate edge: {edge_mag:.1f} point spread differential"]
        
        elif classification == Classification.EDGE:
            reasons = []
            reasons.append(f"Spread misprice detected: {edge_mag:.1f} point edge")
            if model_prob >= 0.6:
                reasons.append(f"High cover probability: {model_prob*100:.1f}%")
            elif model_prob <= 0.4:
                reasons.append(f"High cover probability: {(1-model_prob)*100:.1f}%")
            return reasons
        
        return ["Edge detected"]
    
    def _generate_reasons_total(self, classification: Classification, edge_points: float, side: str) -> List[str]:
        """Generate pre-computed reasons for total"""
        edge_mag = abs(edge_points)
        
        if classification == Classification.MARKET_ALIGNED:
            return ["Model and market consensus on total", "No significant value detected"]
        
        elif classification == Classification.LEAN:
            return [f"Moderate edge: {edge_mag:.1f} point total differential favoring {side}"]
        
        elif classification == Classification.EDGE:
            return [f"Total misprice: {edge_mag:.1f} points favoring {side}"]
        
        return [f"{side} shows value"]
    
    def _determine_release_status(self, classification: Classification, risk: Risk) -> ReleaseStatus:
        """
        Determine release status - per spec Section 9
        
        APPROVED if all validations pass (regardless of classification).
        BLOCKED_BY_* set by validation gates or fail-closed.
        """
        # Default to APPROVED - validation gates will override if needed
        return ReleaseStatus.APPROVED
    
    def _grade_edge(self, edge_points: float) -> Optional[Literal["S", "A", "B", "C", "D"]]:
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
    
    def _validate_directional_integrity_spread(self, sim_spread_home: float, home_cover_prob: float) -> bool:
        """
        Validate directional integrity per spec Section 3.
        
        If median_margin > 0 → home_win_prob > 0.5
        If median_margin < 0 → home_win_prob < 0.5
        If median_margin = 0 → home_win_prob ≈ 0.5 ±0.02
        """
        if sim_spread_home > 0:
            return home_cover_prob > 0.5
        elif sim_spread_home < 0:
            return home_cover_prob < 0.5
        else:  # sim_spread_home == 0
            return abs(home_cover_prob - 0.5) <= 0.02
    
    def _validate_freshness(self, computed_at_str: str, max_age_minutes: int = 120) -> bool:
        """
        Validate freshness per spec Section 5.
        
        Max age = 120 minutes
        """
        try:
            from dateutil import parser
            computed_at = parser.isoparse(computed_at_str)
            now = datetime.utcnow()
            # Make computed_at timezone-naive if it has timezone info
            if computed_at.tzinfo:
                computed_at = computed_at.replace(tzinfo=None)
            age_minutes = (now - computed_at).total_seconds() / 60
            return age_minutes <= max_age_minutes
        except:
            # If we can't parse the timestamp, fail safe and block
            return False
    
    def _create_blocked_spread_decision(
        self,
        pick_team_id: str,
        pick_team_name: str,
        market_line: float,
        spread_lines: Dict,
        game_competitors: Dict[str, str],
        home_team_id: str,
        inputs_hash: str,
        blocked_reason: str,
        release_status: ReleaseStatus
    ) -> MarketDecision:
        """
        Create a BLOCKED spread decision per spec Section 1.4.
        
        When BLOCKED:
        - classification = null
        - reasons = []
        - pick = null (but we set it for context)
        - edge = null
        - probabilities = null
        - model = null
        - fair_selection = null
        - risk.blocked_reason = explicit reason
        """
        market_odds = spread_lines.get(pick_team_id, {}).get('odds', -110)
        
        market_selections = [
            {
                "selection_id": f"{self.game_id}_spread_{home_team_id}",
                "team_id": home_team_id,
                "team_name": game_competitors[home_team_id],
                "line": spread_lines.get(home_team_id, {}).get('line', 0),
                "odds": spread_lines.get(home_team_id, {}).get('odds', -110)
            },
            {
                "selection_id": f"{self.game_id}_spread_{list(game_competitors.keys())[1]}",
                "team_id": list(game_competitors.keys())[1],
                "team_name": game_competitors[list(game_competitors.keys())[1]],
                "line": spread_lines.get(list(game_competitors.keys())[1], {}).get('line', 0),
                "odds": spread_lines.get(list(game_competitors.keys())[1], {}).get('odds', -110)
            }
        ]
        
        return MarketDecision(
            league=self.league,
            game_id=self.game_id,
            odds_event_id=self.odds_event_id,
            market_type=MarketType.SPREAD,
            decision_id=str(uuid.uuid4()),
            selection_id=f"{self.game_id}_spread_{pick_team_id}",
            preferred_selection_id=f"{self.game_id}_spread_{pick_team_id}",
            market_selections=market_selections,
            pick=None,  # null per spec
            market=MarketSpread(line=market_line, odds=market_odds),
            model=None,  # null per spec
            fair_selection=None,  # null per spec
            probabilities=None,  # null per spec
            edge=None,  # null per spec
            classification=None,  # null per spec
            release_status=release_status,
            reasons=[],  # empty per spec
            risk=Risk(
                volatility_flag=None,
                injury_impact=None,
                clv_forecast=None,
                blocked_reason=blocked_reason
            ),
            debug=Debug(
                inputs_hash=inputs_hash,
                odds_timestamp=datetime.utcnow().isoformat(),
                sim_run_id="blocked",
                trace_id=self.bundle_trace_id,
                config_profile=None,
                decision_version=self.bundle_version,
                computed_at=self.bundle_computed_at
            ),
            validator_failures=[]
        )
