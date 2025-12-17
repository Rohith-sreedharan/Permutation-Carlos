"""
Truth Mode Enforcement Middleware
==================================

Enforces zero-lies principle across all pick-serving endpoints
"""
from typing import Dict, List, Any, Optional
from core.truth_mode import truth_mode_validator, BlockReason
from db.mongo import db


def enforce_truth_mode_on_pick(
    event_id: str,
    bet_type: str = "moneyline",
    rcl_decision: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Enforce Truth Mode on a single pick
    Returns validated pick or NO_PLAY response
    """
    # Get event data
    event = db.events.find_one({"event_id": event_id})
    if not event:
        return {
            "status": "NO_PLAY",
            "blocked": True,
            "block_reasons": ["event_not_found"],
            "message": "Event not found in database"
        }
    
    # Get simulation data
    simulation = db.monte_carlo_simulations.find_one(
        {"event_id": event_id},
        sort=[("created_at", -1)]
    )
    
    # Validate through Truth Mode
    validation = truth_mode_validator.validate_pick(
        event=event,
        simulation=simulation,
        bet_type=bet_type,
        rcl_decision=rcl_decision
    )
    
    if not validation.is_valid:
        return truth_mode_validator.create_no_play_response(
            event=event,
            block_reasons=validation.block_reasons,
            details=validation.details
        )
    
    # Pick passed - return validated pick data
    return {
        "status": "VALID",
        "event_id": event_id,
        "event": event,
        "simulation": simulation,
        "bet_type": bet_type,
        "confidence_score": validation.confidence_score,
        "truth_mode_validated": True,
        "validation_details": validation.details
    }


def filter_picks_with_truth_mode(
    picks: List[Dict[str, Any]],
    include_blocked: bool = False
) -> Dict[str, Any]:
    """
    Filter a list of picks through Truth Mode
    
    Args:
        picks: List of picks to validate
        include_blocked: If True, include blocked picks with NO_PLAY status
    
    Returns:
        Dict with valid_picks and optionally blocked_picks
    """
    valid_picks = []
    blocked_picks = []
    
    for pick in picks:
        event_id = pick.get("event_id")
        bet_type = pick.get("bet_type", "moneyline")
        
        result = enforce_truth_mode_on_pick(
            event_id=event_id,
            bet_type=bet_type,
            rcl_decision=pick.get("rcl_decision")
        )
        
        if result["status"] == "VALID":
            # Merge validation data with original pick
            pick.update({
                "truth_mode_validated": True,
                "confidence_score": result["confidence_score"],
                "validation_details": result.get("validation_details", {})
            })
            valid_picks.append(pick)
        else:
            # Pick was blocked
            blocked_pick = {
                **pick,
                "status": "NO_PLAY",
                "blocked": True,
                "block_reasons": result.get("block_reasons", []),
                "block_message": result.get("message", ""),
                "block_details": result.get("details", {})
            }
            blocked_picks.append(blocked_pick)
    
    response = {
        "valid_picks": valid_picks,
        "valid_count": len(valid_picks),
        "blocked_count": len(blocked_picks)
    }
    
    if include_blocked:
        response["blocked_picks"] = blocked_picks
    
    return response


def validate_parlay_with_truth_mode(
    legs: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Validate parlay legs through Truth Mode
    
    Returns:
        Dict with status, valid_legs, and blocked_legs
    """
    valid_legs = []
    blocked_legs = []
    
    for leg in legs:
        event_id = leg.get("event_id")
        bet_type = leg.get("bet_type", "moneyline")
        
        result = enforce_truth_mode_on_pick(
            event_id=event_id,
            bet_type=bet_type,
            rcl_decision=leg.get("rcl_decision")
        )
        
        if result["status"] == "VALID":
            leg["truth_mode_validated"] = True
            leg["confidence_score"] = result["confidence_score"]
            valid_legs.append(leg)
        else:
            leg["status"] = "NO_PLAY"
            leg["blocked"] = True
            leg["block_reasons"] = result.get("block_reasons", [])
            leg["block_message"] = result.get("message", "")
            blocked_legs.append(leg)
    
    # Parlay is only valid if ALL legs pass Truth Mode
    parlay_valid = len(blocked_legs) == 0
    
    return {
        "status": "VALID" if parlay_valid else "BLOCKED",
        "valid_legs": valid_legs,
        "blocked_legs": blocked_legs,
        "total_legs": len(legs),
        "valid_count": len(valid_legs),
        "blocked_count": len(blocked_legs),
        "message": "All legs passed Truth Mode" if parlay_valid else f"{len(blocked_legs)} leg(s) blocked by Truth Mode"
    }
