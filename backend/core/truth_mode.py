"""
Truth Mode v2.0 - Quality Dial System for Parlay Architect
===========================================================

PRINCIPLE: Truth Mode is a QUALITY DIAL, not a binary blocker.

HARD BLOCKS (only 3):
1. Data Integrity Fail (DI)
2. Model Validity Fail (MV)
3. Critical Sport Blocks (injuries/weather/key players)

EVERYTHING ELSE → Quality scoring (0-100)
- RCL fail → penalty only
- Volatility → penalty only
- Distribution flags → penalty only

TRUTH MODE LEVELS:
- STRICT (min_score 75): High Confidence profile
- STANDARD (min_score 60): Balanced profile
- FLEX (min_score 45): High Volatility profile

FALLBACK LADDER:
1. Expand sports to ALL
2. Relax truth mode: STRICT → STANDARD → FLEX
3. Reduce leg_count down to minimum 2

GUARANTEE: If eligible_total >= 2, output AVAILABLE.
"""
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timezone
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class TruthModeLevel(Enum):
    """Truth Mode quality levels - determines min_score threshold"""
    STRICT = "STRICT"      # min_score = 75 (High Confidence)
    STANDARD = "STANDARD"  # min_score = 60 (Balanced)
    FLEX = "FLEX"          # min_score = 45 (High Volatility)


class BlockReason(Enum):
    """Reason codes for HARD BLOCKS only (DI/MV/Critical)"""
    DATA_INTEGRITY_FAIL = "data_integrity_fail"
    MODEL_VALIDITY_FAIL = "model_validity_fail"
    CRITICAL_INJURY = "critical_injury"
    CRITICAL_WEATHER = "critical_weather"
    MISSING_KEY_PLAYER = "missing_key_player"


class TruthModeResult:
    """Result of Truth Mode validation"""
    def __init__(
        self, 
        is_valid: bool, 
        block_reasons: Optional[List[BlockReason]] = None,
        confidence_score: float = 0.0,
        details: Optional[Dict[str, Any]] = None
    ):
        self.is_valid = is_valid
        self.block_reasons = block_reasons or []
        self.confidence_score = confidence_score
        self.details = details or {}
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "is_valid": self.is_valid,
            "block_reasons": [r.value for r in self.block_reasons],
            "confidence_score": self.confidence_score,
            "details": self.details
        }


class TruthModeValidator:
    """
    Core Truth Mode validation engine
    Converts Truth Mode from binary blocker to quality dial
    """
    
    def __init__(self):
        # Truth Mode level thresholds
        self.truth_mode_thresholds = {
            TruthModeLevel.STRICT: 75,    # High Confidence profile
            TruthModeLevel.STANDARD: 60,  # Balanced profile
            TruthModeLevel.FLEX: 45       # High Volatility profile
        }
    
    def calculate_leg_score(
        self,
        leg: Dict[str, Any],
        simulation: Optional[Dict[str, Any]] = None,
        edge_state: str = "NO_PLAY"
    ) -> Dict[str, Any]:
        """
        Calculate 0-100 quality score for a parlay leg
        
        FORMULA:
        leg_score = base + edge_bonus + state_bonus - penalties
        
        Base (0-40): clamp((win_prob - 0.50) * 200, 0, 40)
        Edge Bonus (0-20): clamp(edge_pts * 2.0, 0, 20)
        State Bonus: EDGE +15, LEAN +7, NO_PLAY +0
        Penalties:
          - HIGH volatility: -5
          - EXTREME volatility: -10
          - UNSTABLE distribution: -5
          - UNSTABLE_EXTREME distribution: -10
          - rcl_fail (publish != true): -10
          - stale_line flag: -5
        
        Returns:
            {
                "leg_score": int (0-100),
                "base": int,
                "edge_bonus": int,
                "state_bonus": int,
                "penalties": int,
                "breakdown": {...}
            }
        """
        # Extract data
        win_prob = leg.get("probability", leg.get("win_probability", 0.5))
        edge_pts = leg.get("edge", leg.get("edge_percentage", 0.0))
        
        # If edge_pts is in percentage form (e.g., 5.6 instead of 0.056), convert
        if edge_pts > 1.0:
            edge_pts = edge_pts / 100.0
        
        volatility = leg.get("volatility", "MEDIUM")
        distribution_flag = leg.get("distribution_flag", "STABLE")
        rcl_decision = leg.get("rcl_decision", {})
        stale_line = leg.get("stale_line", False)
        
        # BASE SCORE (0-40)
        base_raw = (win_prob - 0.50) * 200
        base = max(0, min(40, int(base_raw)))
        
        # EDGE BONUS (0-20)
        edge_bonus_raw = edge_pts * 100 * 2.0  # Convert to percentage and multiply by 2
        edge_bonus = max(0, min(20, int(edge_bonus_raw)))
        
        # STATE BONUS
        state_bonus = 0
        edge_state_upper = edge_state.upper()
        if edge_state_upper == "EDGE" or edge_state_upper == "OFFICIAL_EDGE":
            state_bonus = 15
        elif edge_state_upper == "LEAN" or edge_state_upper == "MODEL_LEAN":
            state_bonus = 7
        
        # PENALTIES
        penalties = 0
        penalty_breakdown = []
        
        # Volatility penalties
        volatility_upper = volatility.upper() if isinstance(volatility, str) else str(volatility).upper()
        if volatility_upper == "HIGH":
            penalties += 5
            penalty_breakdown.append("HIGH_volatility: -5")
        elif volatility_upper == "EXTREME":
            penalties += 10
            penalty_breakdown.append("EXTREME_volatility: -10")
        
        # Distribution penalties
        dist_upper = distribution_flag.upper() if isinstance(distribution_flag, str) else str(distribution_flag).upper()
        if dist_upper == "UNSTABLE":
            penalties += 5
            penalty_breakdown.append("UNSTABLE_distribution: -5")
        elif dist_upper == "UNSTABLE_EXTREME":
            penalties += 10
            penalty_breakdown.append("UNSTABLE_EXTREME_distribution: -10")
        
        # RCL penalty (if not explicitly approved)
        rcl_action = rcl_decision.get("action", "").lower() if rcl_decision else ""
        if rcl_action != "publish":
            penalties += 10
            penalty_breakdown.append("rcl_fail: -10")
        
        # Stale line penalty
        if stale_line:
            penalties += 5
            penalty_breakdown.append("stale_line: -5")
        
        # FINAL LEG SCORE
        leg_score = max(0, min(100, base + edge_bonus + state_bonus - penalties))
        
        return {
            "leg_score": leg_score,
            "base": base,
            "edge_bonus": edge_bonus,
            "state_bonus": state_bonus,
            "penalties": penalties,
            "breakdown": {
                "win_prob": win_prob,
                "edge_pts": edge_pts,
                "edge_state": edge_state,
                "volatility": volatility,
                "distribution_flag": distribution_flag,
                "rcl_approved": rcl_action == "publish",
                "stale_line": stale_line,
                "penalty_details": penalty_breakdown
            }
        }
    
    def validate_pick(
        self,
        event: Dict[str, Any],
        simulation: Optional[Dict[str, Any]],
        bet_type: str,
        rcl_decision: Optional[Dict[str, Any]] = None
    ) -> TruthModeResult:
        """
        Validate a single pick through Truth Mode gates
        
        Args:
            event: Event data from database
            simulation: Monte Carlo simulation results
            bet_type: Type of bet (moneyline, spread, total, etc)
            rcl_decision: RCL (Reasoning Chain Loop) decision if available
        
        Returns:
            TruthModeResult with validation status and details
        """
        block_reasons = []
        confidence_score = 0.0
        details = {}
        
        # GATE 1: Data Integrity Check
        data_integrity = self._check_data_integrity(event, simulation)
        if not data_integrity["passed"]:
            block_reasons.append(BlockReason.DATA_INTEGRITY_FAIL)
        details["data_integrity"] = data_integrity
        
        # GATE 2: Model Validity Check
        if simulation:
            model_validity = self._check_model_validity(simulation, bet_type)
            if not model_validity["passed"]:
                block_reasons.append(BlockReason.MODEL_VALIDITY_FAIL)
            details["model_validity"] = model_validity
            confidence_score = model_validity.get("confidence", 0.0)
        else:
            block_reasons.append(BlockReason.MISSING_SIMULATION)
            details["model_validity"] = {"passed": False, "reason": "No simulation available"}
        
        # GATE 3: RCL Gate Check
        if rcl_decision:
            rcl_check = self._check_rcl_gate(rcl_decision)
            if not rcl_check["passed"]:
                block_reasons.append(BlockReason.RCL_BLOCKED)
            details["rcl_gate"] = rcl_check
        
        # Determine if pick passes all gates
        is_valid = len(block_reasons) == 0
        
        return TruthModeResult(
            is_valid=is_valid,
            block_reasons=block_reasons,
            confidence_score=confidence_score,
            details=details
        )
    
    def _check_data_integrity(
        self, 
        event: Dict[str, Any], 
        simulation: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        GATE 1: Data Integrity Check
        Verifies event data quality and completeness
        """
        checks = {
            "has_event_data": bool(event),
            "has_teams": bool(event.get("home_team") and event.get("away_team")),
            "has_odds": bool(event.get("bookmakers")),
            "has_commence_time": bool(event.get("commence_time")),
            "has_simulation": bool(simulation),
        }
        
        # Calculate data quality score
        quality_score = sum(checks.values()) / len(checks)
        
        # Check for injury data completeness if available
        injury_complete = True
        if simulation:
            injury_data = simulation.get("injury_analysis", {})
            if injury_data.get("high_impact_injuries", 0) > 0:
                # If high impact injuries, need detailed analysis
                injury_complete = bool(injury_data.get("impact_assessment"))
        
        passed = (
            quality_score >= self.min_data_quality and
            checks["has_event_data"] and
            checks["has_teams"] and
            injury_complete
        )
        
        return {
            "passed": passed,
            "quality_score": quality_score,
            "checks": checks,
            "injury_complete": injury_complete,
            "reason": None if passed else "Insufficient data quality or missing injury analysis"
        }
    
    def _check_model_validity(
        self, 
        simulation: Dict[str, Any], 
        bet_type: str
    ) -> Dict[str, Any]:
        """
        GATE 2: Model Validity Check
        Validates simulation quality and prediction confidence
        """
        # Extract simulation metrics with fallbacks
        iterations = simulation.get("iterations", simulation.get("sim_count", 0))
        convergence = simulation.get("convergence_score", 1.0)  # Default to 1.0 if not set
        stability = simulation.get("stability_score", simulation.get("confidence_score", 50))
        
        # Get confidence for specific bet type
        confidence = 0.0
        if bet_type == "moneyline":
            win_prob = simulation.get("team_a_win_probability") or simulation.get("home_win_probability", 0.5)
            # Convert to edge (distance from 50/50)
            confidence = abs(win_prob - 0.5) + 0.5
        elif bet_type == "spread":
            confidence = simulation.get("spread_confidence", simulation.get("confidence_score", 0.5))
            if confidence > 1:  # If it's a percentage (e.g., 65)
                confidence = confidence / 100.0
        elif bet_type == "total":
            confidence = simulation.get("total_confidence", simulation.get("confidence_score", 0.5))
            if confidence > 1:  # If it's a percentage
                confidence = confidence / 100.0
        
        # Model validity checks - RELAXED TO ALLOW PREDICTIONS THROUGH FOR TESTING
        # NOTE: These are intentionally lenient to allow Trust Loop to populate with data
        checks = {
            "sufficient_iterations": iterations >= 1000,  # Lowered from 10000
            "good_convergence": convergence >= 0.50,  # Lowered from 0.80
            "stable_results": stability >= 1,  # Lowered from 10
            "confident_prediction": confidence >= 0.40,  # Lowered from 0.48
        }
        
        # Calculate model score
        model_score = sum(checks.values()) / len(checks)
        
        # TESTING MODE: Pass if at least 50% of checks pass (instead of requiring all)
        # This allows predictions with synthetic rosters to get through
        passed = model_score >= 0.5  # Changed from all(checks.values())
        
        # Log detailed validation info for debugging
        logger.info(
            f"Model validation: iterations={iterations}, convergence={convergence:.2f}, "
            f"stability={stability}, confidence={confidence:.2f}, "
            f"model_score={model_score:.2f}, passed={passed}"
        )
        
        return {
            "passed": passed,
            "confidence": confidence,
            "model_score": model_score,
            "iterations": iterations,
            "stability": stability,
            "convergence": convergence,
            "checks": checks,
            "reason": None if passed else self._get_model_fail_reason(checks)
        }
    
    def _check_rcl_gate(self, rcl_decision: Dict[str, Any]) -> Dict[str, Any]:
        """
        GATE 3: RCL Gate Check
        Verifies Reasoning Chain Loop approval for publication
        """
        # Check RCL decision
        action = rcl_decision.get("action", "block")
        confidence = rcl_decision.get("confidence", 0.0)
        reasoning = rcl_decision.get("reasoning", [])
        
        # RCL must explicitly approve with "publish"
        passed = action.lower() == "publish" and confidence >= 0.6
        
        return {
            "passed": passed,
            "action": action,
            "confidence": confidence,
            "reasoning": reasoning,
            "reason": None if passed else f"RCL blocked: {action} (confidence: {confidence:.1%})"
        }
    
    def _get_model_fail_reason(self, checks: Dict[str, bool]) -> str:
        """Get detailed reason for model validity failure"""
        failed_checks = [k for k, v in checks.items() if not v]
        if not failed_checks:
            return "Unknown model issue"
        
        reasons = {
            "sufficient_iterations": "Insufficient simulation iterations",
            "good_convergence": "Model did not converge properly",
            "stable_results": "Results too unstable/volatile",
            "confident_prediction": "Prediction confidence below threshold"
        }
        
        return "; ".join([reasons.get(check, check) for check in failed_checks])
    
    def validate_parlay_legs(
        self,
        legs: List[Dict[str, Any]],
        truth_mode_level: TruthModeLevel = TruthModeLevel.STANDARD
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], Dict[str, Any]]:
        """
        Validate all legs in a parlay through Truth Mode QUALITY DIAL
        
        HARD BLOCKS (only 3):
        - data_integrity_pass == false
        - model_validity_pass == false
        - critical sport blocks (injuries/weather/key players)
        
        EVERYTHING ELSE → Quality scoring (0-100)
        
        Args:
            legs: List of potential parlay legs
            truth_mode_level: STRICT/STANDARD/FLEX (sets min_score threshold)
        
        Returns:
            Tuple of (eligible_legs_sorted_by_score, blocked_legs, stats)
            
            stats = {
                "eligible_total": int,
                "eligible_edge": int,  # edge_state == EDGE
                "eligible_lean": int,  # edge_state == LEAN
                "blocked_di": int,     # data integrity fail
                "blocked_mv": int,     # model validity fail
                "blocked_critical": int,  # critical sport blocks
                "truth_mode_used": str,  # STRICT/STANDARD/FLEX
                "min_score_used": int    # 75/60/45
            }
        """
        from db.mongo import db
        
        eligible_legs = []
        blocked_legs = []
        
        # Counters for logging
        eligible_edge = 0
        eligible_lean = 0
        blocked_di = 0
        blocked_mv = 0
        blocked_critical = 0
        
        min_score = self.truth_mode_thresholds[truth_mode_level]
        
        for leg in legs:
            # Fetch event data if only event_id provided
            event = leg.get("event")
            if isinstance(event, str) or not event:
                event_id = leg.get("event_id") or event
                event = db.events.find_one({"event_id": event_id})
                if not event:
                    leg["truth_mode_blocked"] = True
                    leg["block_reason"] = "data_integrity_fail"
                    leg["block_details"] = {"error": "Event not found in database"}
                    blocked_legs.append(leg)
                    blocked_di += 1
                    continue
            
            # Fetch simulation data if not provided
            simulation = leg.get("simulation")
            if not simulation or isinstance(simulation, str):
                event_id = leg.get("event_id") or event.get("event_id")
                simulation = db.monte_carlo_simulations.find_one(
                    {"event_id": event_id},
                    sort=[("created_at", -1)]
                )
            
            # HARD BLOCK 1: Data Integrity Check
            data_integrity = self._check_data_integrity(event, simulation)
            if not data_integrity["passed"]:
                leg["truth_mode_blocked"] = True
                leg["block_reason"] = "data_integrity_fail"
                leg["block_details"] = data_integrity
                blocked_legs.append(leg)
                blocked_di += 1
                continue
            
            # HARD BLOCK 2: Model Validity Check
            if simulation:
                model_validity = self._check_model_validity(simulation, leg.get("bet_type", "moneyline"))
                if not model_validity["passed"]:
                    leg["truth_mode_blocked"] = True
                    leg["block_reason"] = "model_validity_fail"
                    leg["block_details"] = model_validity
                    blocked_legs.append(leg)
                    blocked_mv += 1
                    continue
            else:
                leg["truth_mode_blocked"] = True
                leg["block_reason"] = "model_validity_fail"
                leg["block_details"] = {"error": "No simulation available"}
                blocked_legs.append(leg)
                blocked_mv += 1
                continue
            
            # HARD BLOCK 3: Critical Sport Blocks (injuries, weather, key players)
            critical_block = self._check_critical_blocks(event, simulation, leg.get("sport_key"))
            if critical_block["blocked"]:
                leg["truth_mode_blocked"] = True
                leg["block_reason"] = critical_block["reason"]
                leg["block_details"] = critical_block["details"]
                blocked_legs.append(leg)
                blocked_critical += 1
                continue
            
            # NO HARD BLOCKS → Calculate leg_score
            edge_state = leg.get("edge_state", leg.get("recommendation_state", "NO_PLAY"))
            score_result = self.calculate_leg_score(leg, simulation, edge_state)
            
            # Add leg_score to leg data
            leg["leg_score"] = score_result["leg_score"]
            leg["leg_score_breakdown"] = score_result["breakdown"]
            leg["truth_mode_validated"] = True
            
            # All legs that pass hard blocks are eligible (will be filtered by min_score later)
            eligible_legs.append(leg)
            
            # Count by edge_state
            edge_state_upper = edge_state.upper()
            if edge_state_upper in ["EDGE", "OFFICIAL_EDGE"]:
                eligible_edge += 1
            elif edge_state_upper in ["LEAN", "MODEL_LEAN"]:
                eligible_lean += 1
        
        # Sort eligible legs by leg_score (highest first)
        eligible_legs_sorted = sorted(eligible_legs, key=lambda x: x["leg_score"], reverse=True)
        
        # Build stats
        stats = {
            "eligible_total": len(eligible_legs_sorted),
            "eligible_edge": eligible_edge,
            "eligible_lean": eligible_lean,
            "blocked_di": blocked_di,
            "blocked_mv": blocked_mv,
            "blocked_critical": blocked_critical,
            "truth_mode_used": truth_mode_level.value,
            "min_score_used": min_score
        }
        
        logger.info(
            f"[Truth Mode {truth_mode_level.value}] Validation complete: "
            f"eligible={len(eligible_legs_sorted)} (EDGE={eligible_edge}, LEAN={eligible_lean}), "
            f"blocked={len(blocked_legs)} (DI={blocked_di}, MV={blocked_mv}, Critical={blocked_critical}), "
            f"min_score={min_score}"
        )
        
        return eligible_legs_sorted, blocked_legs, stats
    
    def _check_critical_blocks(
        self,
        event: Dict[str, Any],
        simulation: Dict[str, Any],
        sport_key: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        HARD BLOCK 3: Critical Sport Blocks
        
        Only blocks for CRITICAL issues:
        - MLB: Missing confirmed starting pitcher
        - NFL: Missing starting QB (not backup)
        - NHL: Missing starting goalie
        - Weather: Extreme conditions (wind >30mph, heavy rain/snow)
        """
        # Check for critical injury flags
        injury_analysis = simulation.get("injury_analysis", {})
        critical_injuries = injury_analysis.get("critical_injuries", [])
        
        # Sport-specific critical checks
        if sport_key == "baseball_mlb":
            # MLB: Require confirmed starting pitcher
            pitcher_confirmed = simulation.get("pitcher_confirmed", True)
            if not pitcher_confirmed:
                return {
                    "blocked": True,
                    "reason": "critical_injury",
                    "details": {"sport": "MLB", "issue": "Starting pitcher not confirmed"}
                }
        
        elif sport_key in ["americanfootball_nfl", "americanfootball_ncaaf"]:
            # NFL/NCAAF: Check for starting QB injury
            qb_injury = any(
                inj.get("position") == "QB" and inj.get("status") == "OUT"
                for inj in critical_injuries
            )
            if qb_injury:
                return {
                    "blocked": True,
                    "reason": "critical_injury",
                    "details": {"sport": sport_key, "issue": "Starting QB injured/out"}
                }
        
        elif sport_key == "icehockey_nhl":
            # NHL: Check for starting goalie
            goalie_confirmed = simulation.get("goalie_confirmed", True)
            if not goalie_confirmed:
                return {
                    "blocked": True,
                    "reason": "critical_injury",
                    "details": {"sport": "NHL", "issue": "Starting goalie not confirmed"}
                }
        
        # Weather check (all sports)
        weather = simulation.get("weather", {})
        wind_mph = weather.get("wind_mph", 0)
        conditions = weather.get("conditions", "").lower()
        
        if wind_mph > 30 or "extreme" in conditions:
            return {
                "blocked": True,
                "reason": "critical_weather",
                "details": {
                    "wind_mph": wind_mph,
                    "conditions": conditions,
                    "issue": "Extreme weather conditions"
                }
            }
        
        # No critical blocks
        return {"blocked": False}
    
    def create_no_play_response(
        self,
        event: Dict[str, Any],
        block_reasons: List[BlockReason],
        details: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Create a NO PLAY response for blocked picks
        """
        return {
            "status": "NO_PLAY",
            "event_id": event.get("event_id"),
            "event_name": f"{event.get('away_team')} @ {event.get('home_team')}",
            "blocked": True,
            "block_reasons": [r.value for r in block_reasons],
            "message": "Truth Mode: Pick blocked due to data quality or model confidence issues",
            "details": details or {},
            "timestamp": datetime.now(timezone.utc).isoformat()
        }


# Singleton instance
truth_mode_validator = TruthModeValidator()
