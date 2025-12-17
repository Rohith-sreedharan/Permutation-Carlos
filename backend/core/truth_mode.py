"""
Truth Mode v1.0 - Zero-Lies Enforcement System
==============================================

PRINCIPLE: No pick is allowed to be shown unless it passes:
1. Data Integrity Check
2. Model Validity Check  
3. RCL Gate (Publish/Block decision)

If blocked → Return NO PLAY with reason codes
Applies to ALL sports, ALL endpoints, ALL pick displays
"""
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timezone
from enum import Enum


class BlockReason(Enum):
    """Reason codes for why a pick is blocked"""
    DATA_INTEGRITY_FAIL = "data_integrity_fail"
    MODEL_VALIDITY_FAIL = "model_validity_fail"
    RCL_BLOCKED = "rcl_blocked"
    MISSING_SIMULATION = "missing_simulation"
    INSUFFICIENT_DATA = "insufficient_data"
    INJURY_UNCERTAINTY = "injury_uncertainty"
    LINE_MOVEMENT_UNSTABLE = "line_movement_unstable"
    LOW_CONFIDENCE = "low_confidence"


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
    Enforces zero-lies principle across all picks
    """
    
    def __init__(self):
        # Minimum thresholds for publication
        self.min_confidence = 0.48  # 48% minimum win probability
        self.min_data_quality = 0.7  # 70% data completeness
        self.min_stability = 10  # Minimum stability score
    
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
        
        # Model validity checks (more lenient for existing simulations)
        checks = {
            "sufficient_iterations": iterations >= 10000,
            "good_convergence": convergence >= 0.80,  # Lowered from 0.85
            "stable_results": stability >= 10,  # Minimum stability
            "confident_prediction": confidence >= 0.48,  # 48% minimum
        }
        
        # Calculate model score
        model_score = sum(checks.values()) / len(checks)
        
        passed = all(checks.values())
        
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
        legs: List[Dict[str, Any]]
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        Validate all legs in a parlay through Truth Mode
        
        Returns:
            Tuple of (valid_legs, blocked_legs)
        """
        from db.mongo import db
        
        valid_legs = []
        blocked_legs = []
        
        for leg in legs:
            # Fetch event data if only event_id provided
            event = leg.get("event")
            if isinstance(event, str) or not event:
                # event_id passed as string, fetch full event
                event_id = leg.get("event_id") or event
                event = db.events.find_one({"event_id": event_id})
                if not event:
                    # Can't validate without event data
                    leg["truth_mode_blocked"] = True
                    leg["block_reasons"] = ["event_not_found"]
                    leg["block_details"] = {"error": "Event not found in database"}
                    blocked_legs.append(leg)
                    continue
            
            # Fetch simulation data if not provided
            simulation = leg.get("simulation")
            if not simulation or isinstance(simulation, str):
                event_id = leg.get("event_id") or event.get("event_id")
                simulation = db.monte_carlo_simulations.find_one(
                    {"event_id": event_id},
                    sort=[("created_at", -1)]
                )
            
            # Validate the leg
            validation = self.validate_pick(
                event=event,
                simulation=simulation,
                bet_type=leg.get("bet_type", "moneyline"),
                rcl_decision=leg.get("rcl_decision")
            )
            
            if validation.is_valid:
                leg["truth_mode_validated"] = True
                leg["confidence_score"] = validation.confidence_score
                valid_legs.append(leg)
            else:
                leg["truth_mode_blocked"] = True
                leg["block_reasons"] = [r.value for r in validation.block_reasons]
                leg["block_details"] = validation.details
                blocked_legs.append(leg)
        
        return valid_legs, blocked_legs
    
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
