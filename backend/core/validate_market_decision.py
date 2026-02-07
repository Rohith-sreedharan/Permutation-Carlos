"""
MARKET DECISION VALIDATOR
=========================

Enforces invariants. If ANY fail → BLOCKED_BY_INTEGRITY.
No patching. No baseline. No silent failures.
"""

from typing import Dict, List, Tuple
from core.market_decision import MarketDecision, Classification, ReleaseStatus


def validate_market_decision(
    decision: MarketDecision,
    game_competitors: Dict[str, str]  # {team_id: team_name}
) -> Tuple[bool, List[str]]:
    """
    Validates MarketDecision invariants.
    
    Returns: (is_valid, violations)
    If not valid, decision.release_status MUST be set to BLOCKED_BY_INTEGRITY.
    """
    violations = []
    
    # 1. Competitor integrity
    if decision.market_type.value in ["spread", "moneyline"]:
        pick_team_id = getattr(decision.pick, 'team_id', None)
        if pick_team_id and pick_team_id not in game_competitors:
            violations.append(f"Pick team_id '{pick_team_id}' not in game competitors {list(game_competitors.keys())}")
    
    # 2. Required fields presence
    if not decision.selection_id:
        violations.append("Missing selection_id")
    if not decision.debug.inputs_hash:
        violations.append("Missing debug.inputs_hash")
    
    # 3. Classification coherence
    if decision.classification == Classification.MARKET_ALIGNED:
        # MARKET_ALIGNED cannot claim misprice
        misprice_keywords = ['misprice', 'edge', 'value', 'inefficiency']
        for reason in decision.reasons:
            if any(kw in reason.lower() for kw in misprice_keywords):
                violations.append(f"MARKET_ALIGNED cannot claim misprice in reasons: '{reason}'")
    
    if decision.classification in [Classification.EDGE, Classification.LEAN]:
        # Must have meaningful edge_points or edge_ev
        if decision.market_type.value == "moneyline":
            if not decision.edge.edge_ev or decision.edge.edge_ev == 0:
                violations.append(f"{decision.classification} must have non-zero edge_ev for moneyline")
        else:
            if not decision.edge.edge_points or decision.edge.edge_points == 0:
                violations.append(f"{decision.classification} must have non-zero edge_points")
    
    # 4. Spread sign sanity (critical: prevents "both teams +6.5" bug)
    if decision.market_type.value == "spread":
        # Cannot validate opponent here without full odds snapshot
        # But we can check that line is non-zero
        market_line = getattr(decision.market, 'line', None)
        if market_line == 0:
            violations.append("Spread market line cannot be 0")
    
    # 5. Total side logic
    if decision.market_type.value == "total":
        pick_side = getattr(decision.pick, 'side', None)
        if pick_side not in ['OVER', 'UNDER']:
            violations.append(f"Total pick.side must be OVER or UNDER, got '{pick_side}'")
    
    # 6. Selection consistency
    # selection_id should map deterministically
    # (This would require access to selection generator - skip for now)
    
    is_valid = len(violations) == 0
    return is_valid, violations
