"""
Parlay Architect Integrity Gates
=================================

Hard-block enforcement for parlay leg eligibility.

Rules:
- Blocked picks (integrity violations) → NEVER eligible
- Missing selection IDs → NEVER eligible  
- Probability mismatch → NEVER eligible
- recommended_action = NO_PLAY → NEVER eligible
- Insufficient valid candidates → Return "No valid parlay" (no filler legs)

Author: System
Date: 2026-02-02
Version: v1.0.0 (Hard-Lock Patch)
"""

from typing import List, Dict, Any, Optional
from datetime import datetime
from services.pick_integrity_validator import (
    PickIntegrityValidator,
    CanonicalActionPayload,
    RecommendedAction,
    TierLevel
)


class ParlayEligibilityGate:
    """
    Enforces hard rules for parlay leg eligibility.
    
    NO soft filtering. NO filler legs. Fail deterministically.
    """
    
    def __init__(self, db, validator: PickIntegrityValidator):
        self.db = db
        self.validator = validator
    
    def filter_eligible_legs(
        self,
        candidate_picks: List[Dict[str, Any]],
        min_required: int = 2
    ) -> Dict[str, Any]:
        """
        Filter picks for parlay eligibility using hard integrity gates.
        
        Args:
            candidate_picks: List of pick documents
            min_required: Minimum valid legs needed for parlay
        
        Returns:
            {
                "eligible": [...],  # List of valid picks
                "blocked": [...],   # List of blocked picks with reasons
                "has_minimum": bool,  # True if enough eligible legs
                "block_reasons": {...}  # Aggregated block reasons
            }
        """
        eligible = []
        blocked = []
        block_reasons = {}
        
        for pick in candidate_picks:
            # Run integrity validation
            event_id = pick.get("event_id")
            market_id = pick.get("market_snapshot_id")
            if not event_id or not market_id:
                return {"allowed": False, "reason": "Missing event_id or market_snapshot_id"}
            event = self._fetch_event(event_id)
            market = self._fetch_market(market_id)
            
            violations = self.validator.validate_pick_integrity(pick, event, market)
            
            # Hard gate 1: Integrity violations block
            if violations:
                block_reason = f"Integrity violations: {len(violations)}"
                blocked.append({
                    "pick_id": pick.get("pick_id"),
                    "game": pick.get("event_label", "Unknown"),
                    "reason": block_reason,
                    "violations": [v.violation_type for v in violations]
                })
                block_reasons[pick["pick_id"]] = block_reason
                continue
            
            # Hard gate 2: NO_PLAY action blocks
            recommended_action = pick.get("recommended_action")
            if recommended_action == "NO_PLAY" or recommended_action == RecommendedAction.NO_PLAY:
                block_reason = "No actionable edge"
                blocked.append({
                    "pick_id": pick.get("pick_id"),
                    "game": pick.get("event_label", "Unknown"),
                    "reason": block_reason
                })
                block_reasons[pick["pick_id"]] = block_reason
                continue
            
            # Hard gate 3: BLOCKED tier blocks
            tier = pick.get("tier")
            if tier == "BLOCKED" or tier == TierLevel.BLOCKED:
                block_reason = "Pick tier BLOCKED"
                blocked.append({
                    "pick_id": pick.get("pick_id"),
                    "game": pick.get("event_label", "Unknown"),
                    "reason": block_reason
                })
                block_reasons[pick["pick_id"]] = block_reason
                continue
            
            # Hard gate 4: Validity state (if exists)
            validity_state = pick.get("validity_state")
            if validity_state and validity_state != "VALID":
                block_reason = f"Invalid state: {validity_state}"
                blocked.append({
                    "pick_id": pick.get("pick_id"),
                    "game": pick.get("event_label", "Unknown"),
                    "reason": block_reason
                })
                block_reasons[pick["pick_id"]] = block_reason
                continue
            
            # Passed all gates - eligible
            eligible.append(pick)
        
        return {
            "eligible": eligible,
            "blocked": blocked,
            "has_minimum": len(eligible) >= min_required,
            "block_reasons": block_reasons,
            "eligible_count": len(eligible),
            "blocked_count": len(blocked)
        }
    
    def create_no_valid_parlay_response(
        self,
        blocked_legs: List[Dict[str, Any]],
        min_required: int,
        eligible_count: int
    ) -> Dict[str, Any]:
        """
        Deterministic "No valid parlay available" response.
        
        NO filler legs. NO partial parlay. Return diagnostic info only.
        """
        return {
            "status": "NO_VALID_PARLAY",
            "message": f"Insufficient valid candidates ({eligible_count}/{min_required} required)",
            "reason": "Integrity gates blocked most candidates",
            "passed_count": eligible_count,
            "failed_count": len(blocked_legs),
            "minimum_required": min_required,
            "failed": blocked_legs[:10],  # Top 10 blocked legs for diagnostics
            "next_actions": {
                "wait_for_refresh": "Market data refreshes every 15 minutes",
                "adjust_filters": "Try different sport/market filters",
                "check_integrity": "Review blocked legs for common issues"
            },
            "next_refresh_eta": self._estimate_next_refresh()
        }
    
    def validate_parlay_before_publish(
        self,
        parlay_legs: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Final validation before parlay publish.
        
        Ensures ALL legs pass integrity checks.
        Returns validation result.
        """
        eligibility = self.filter_eligible_legs(parlay_legs, min_required=len(parlay_legs))
        
        if not eligibility["has_minimum"]:
            return {
                "valid": False,
                "reason": "One or more legs failed integrity validation",
                "blocked_legs": eligibility["blocked"]
            }
        
        # Lock per-leg metadata
        locked_legs = []
        for leg in eligibility["eligible"]:
            locked_legs.append({
                "pick_id": leg["pick_id"],
                "market_type": leg["market_type"],
                "line": leg.get("line"),
                "odds": leg.get("odds"),
                "book": leg.get("book", "UNKNOWN"),
                "snapshot_timestamp": leg.get("snapshot_timestamp"),
                "snapshot_id": leg.get("market_snapshot_id"),
                "recommended_action": leg.get("recommended_action")
            })
        
        return {
            "valid": True,
            "locked_legs": locked_legs
        }
    
    def _fetch_event(self, event_id: str) -> Dict[str, Any]:
        """Fetch event document"""
        if not event_id:
            return {}
        event = self.db["events"].find_one({"event_id": event_id})
        return event or {}
    
    def _fetch_market(self, market_snapshot_id: str) -> Dict[str, Any]:
        """Fetch market snapshot"""
        if not market_snapshot_id:
            return {}
        market = self.db["market_snapshots"].find_one({"market_snapshot_id": market_snapshot_id})
        return market or {}
    
    def _estimate_next_refresh(self) -> str:
        """Estimate when next market refresh happens"""
        # Placeholder - actual implementation depends on refresh schedule
        return "Next refresh in ~15 minutes"


# Backend route integration example
"""
@app.post("/api/parlay/generate")
async def generate_parlay(
    sport: str,
    leg_count: int,
    risk_profile: str,
    current_user=Depends(get_current_user)
):
    db = get_db()
    validator = PickIntegrityValidator(db)
    gate = ParlayEligibilityGate(db, validator)
    
    # Fetch candidate picks
    candidates = db["picks"].find({
        "sport": sport,
        "status": "PUBLISHED"
    }).limit(50)
    
    # Filter for eligibility
    result = gate.filter_eligible_legs(list(candidates), min_required=leg_count)
    
    if not result["has_minimum"]:
        # Return NO_VALID_PARLAY response
        return gate.create_no_valid_parlay_response(
            result["blocked"],
            leg_count,
            result["eligible_count"]
        )
    
    # Build parlay from eligible legs only
    parlay_legs = result["eligible"][:leg_count]
    
    # Final validation before publish
    validation = gate.validate_parlay_before_publish(parlay_legs)
    
    if not validation["valid"]:
        raise HTTPException(
            status_code=400,
            detail=validation["reason"]
        )
    
    # Safe to publish
    parlay_id = create_parlay(validation["locked_legs"], risk_profile)
    
    return {
        "parlay_id": parlay_id,
        "legs": validation["locked_legs"],
        "status": "PUBLISHED"
    }
"""
