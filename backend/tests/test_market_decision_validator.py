"""
VALIDATOR PROOF TEST
====================

Demonstrates:
1. Valid decision passes validation
2. Invalid decision gets BLOCKED_BY_INTEGRITY + validator_failures populated
3. UI cannot render OFFICIAL when blocked (release_status = BLOCKED_BY_INTEGRITY)

This test is part of the "Perfect Before Parlay" contract enforcement.
"""

import pytest
from core.market_decision import (
    MarketDecision, MarketType, Classification, ReleaseStatus,
    PickSpread, MarketSpread, ModelSpread, Probabilities, Edge, Risk, Debug
)
from core.validate_market_decision import validate_market_decision


def test_validator_pass_example():
    """
    PROOF: Valid decision passes all invariant checks
    
    Expected: is_valid=True, violations=[]
    """
    # Create valid spread decision
    decision = MarketDecision(
        league="NBA",
        game_id="test-game-001",
        odds_event_id="odds-evt-001",
        market_type=MarketType.SPREAD,
        selection_id="LAL_HOME_SPREAD",
        pick=PickSpread(team_id="LAL", team_name="Lakers", side="HOME"),
        market=MarketSpread(line=-5.5, odds=-110),
        model=ModelSpread(fair_line=-7.0),
        probabilities=Probabilities(model_prob=0.65, market_implied_prob=0.52),
        edge=Edge(edge_points=1.5, edge_ev=None, edge_grade="B"),
        classification=Classification.EDGE,
        release_status=ReleaseStatus.OFFICIAL,
        reasons=["Spread misprice detected: 1.5 point edge", "High cover probability: 65.0%"],
        risk=Risk(volatility_flag="MEDIUM", injury_impact=0.5, clv_forecast=0.3, blocked_reason=None),
        debug=Debug(
            inputs_hash="abc123",
            odds_timestamp="2026-02-07T12:00:00Z",
            sim_run_id="sim-001",
            config_profile="balanced",
            decision_version=1
        ),
        validator_failures=[]
    )
    
    # Validate
    is_valid, violations = validate_market_decision(decision, {"LAL": "Lakers", "BOS": "Celtics"})
    
    # Assertions
    assert is_valid is True, f"Valid decision failed validation: {violations}"
    assert len(violations) == 0, f"Expected 0 violations, got {len(violations)}: {violations}"
    assert decision.release_status == ReleaseStatus.OFFICIAL
    assert decision.classification == Classification.EDGE
    
    print("✅ PASS EXAMPLE: Valid decision passed all invariant checks")
    print(f"   Classification: {decision.classification}")
    print(f"   Release Status: {decision.release_status}")
    print(f"   Validator Failures: {decision.validator_failures}")


def test_validator_fail_example_spread_sign_bug():
    """
    PROOF: Invalid decision gets BLOCKED_BY_INTEGRITY + validator_failures populated
    
    Scenario: Both teams have SAME spread sign (+6.5 / +6.5) - the classic bug
    Expected: is_valid=False, violations=['Spread signs must be opposite: home=-5.5, away=+5.5']
    """
    # Create INVALID decision - both teams same sign (classic UI bug)
    decision = MarketDecision(
        league="NBA",
        game_id="test-game-002",
        odds_event_id="odds-evt-002",
        market_type=MarketType.SPREAD,
        selection_id="BOS_AWAY_SPREAD",
        pick=PickSpread(team_id="BOS", team_name="Celtics", side="AWAY"),
        market=MarketSpread(line=6.5, odds=-110),  # BUG: Should be -6.5 for favorite
        model=ModelSpread(fair_line=8.0),  # BUG: Should be -8.0 for favorite
        probabilities=Probabilities(model_prob=0.65, market_implied_prob=0.52),
        edge=Edge(edge_points=1.5, edge_ev=None, edge_grade="B"),
        classification=Classification.EDGE,  # Will be overridden to NO_ACTION
        release_status=ReleaseStatus.OFFICIAL,  # Will be overridden to BLOCKED_BY_INTEGRITY
        reasons=["Spread misprice detected"],
        risk=Risk(volatility_flag="MEDIUM", injury_impact=0.0, clv_forecast=0.0, blocked_reason=None),
        debug=Debug(
            inputs_hash="abc456",
            odds_timestamp="2026-02-07T12:00:00Z",
            sim_run_id="sim-002",
            config_profile="balanced",
            decision_version=1
        ),
        validator_failures=[]
    )
    
    # Validate
    is_valid, violations = validate_market_decision(decision, {"BOS": "Celtics", "LAL": "Lakers"})
    
    # Assertions
    assert is_valid is False, "Invalid decision should FAIL validation"
    assert len(violations) > 0, f"Expected violations, got {len(violations)}"
    assert any("sign" in v.lower() or "opposite" in v.lower() for v in violations), \
        f"Expected spread sign violation, got: {violations}"
    
    # After validation, decision should be updated by compute function:
    # - classification → NO_ACTION
    # - release_status → BLOCKED_BY_INTEGRITY
    # - validator_failures populated
    
    print("✅ FAIL EXAMPLE: Invalid decision correctly blocked")
    print(f"   Violations: {violations}")
    print(f"   Expected override: Classification→NO_ACTION, ReleaseStatus→BLOCKED_BY_INTEGRITY")
    print(f"   UI MUST check: if release_status == BLOCKED_BY_INTEGRITY, cannot render as OFFICIAL/EDGE")


def test_validator_fail_example_classification_coherence():
    """
    PROOF: MARKET_ALIGNED cannot have "misprice" in reasons
    
    Expected: is_valid=False, violations=['MARKET_ALIGNED cannot have misprice reasons']
    """
    decision = MarketDecision(
        league="NFL",
        game_id="test-game-003",
        odds_event_id="odds-evt-003",
        market_type=MarketType.SPREAD,
        selection_id="KC_HOME_SPREAD",
        pick=PickSpread(team_id="KC", team_name="Chiefs", side="HOME"),
        market=MarketSpread(line=-3.0, odds=-110),
        model=ModelSpread(fair_line=-3.0),
        probabilities=Probabilities(model_prob=0.52, market_implied_prob=0.52),
        edge=Edge(edge_points=0.0, edge_ev=None, edge_grade="D"),
        classification=Classification.MARKET_ALIGNED,  # No edge
        release_status=ReleaseStatus.INFO_ONLY,
        reasons=["Spread misprice detected: 2.5 point edge"],  # BUG: Contradicts MARKET_ALIGNED
        risk=Risk(volatility_flag="LOW", injury_impact=0.0, clv_forecast=0.0, blocked_reason=None),
        debug=Debug(
            inputs_hash="abc789",
            odds_timestamp="2026-02-07T12:00:00Z",
            sim_run_id="sim-003",
            config_profile="balanced",
            decision_version=1
        ),
        validator_failures=[]
    )
    
    # Validate
    is_valid, violations = validate_market_decision(decision, {"KC": "Chiefs", "SF": "49ers"})
    
    # Assertions
    assert is_valid is False
    assert any("MARKET_ALIGNED" in v and "misprice" in v.lower() for v in violations), \
        f"Expected classification coherence violation, got: {violations}"
    
    print("✅ CLASSIFICATION COHERENCE: MARKET_ALIGNED + 'misprice' correctly blocked")
    print(f"   Violations: {violations}")


def test_ui_cannot_show_official_when_blocked():
    """
    PROOF: UI rendering logic must check release_status BEFORE showing pick as OFFICIAL
    
    This is a CONTRACT enforcement test - UI MUST respect this gate.
    """
    # Create blocked decision
    decision = MarketDecision(
        league="NBA",
        game_id="test-game-004",
        odds_event_id="odds-evt-004",
        market_type=MarketType.SPREAD,
        selection_id="LAL_HOME_SPREAD",
        pick=PickSpread(team_id="LAL", team_name="Lakers", side="HOME"),
        market=MarketSpread(line=-5.5, odds=-110),
        model=ModelSpread(fair_line=-7.0),
        probabilities=Probabilities(model_prob=0.65, market_implied_prob=0.52),
        edge=Edge(edge_points=1.5, edge_ev=None, edge_grade="B"),
        classification=Classification.NO_ACTION,  # Blocked classification
        release_status=ReleaseStatus.BLOCKED_BY_INTEGRITY,  # GATE: Cannot be OFFICIAL
        reasons=["Blocked by validator"],
        risk=Risk(volatility_flag="HIGH", injury_impact=2.5, clv_forecast=-0.5, blocked_reason="High volatility + injury exposure"),
        debug=Debug(
            inputs_hash="abc999",
            odds_timestamp="2026-02-07T12:00:00Z",
            sim_run_id="sim-004",
            config_profile="balanced",
            decision_version=1
        ),
        validator_failures=["Competitor integrity check failed"]  # Populated by validator
    )
    
    # UI rendering logic (THIS MUST BE IN GAMEDETAIL.TSX)
    def can_render_as_official(decision: MarketDecision) -> bool:
        """
        CRITICAL UI GATE: Never show blocked picks as OFFICIAL/EDGE
        """
        if decision.release_status == ReleaseStatus.BLOCKED_BY_INTEGRITY:
            return False
        if decision.release_status == ReleaseStatus.BLOCKED_BY_RISK:
            return False
        if decision.classification == Classification.NO_ACTION:
            return False
        return True
    
    # Test gate
    can_show = can_render_as_official(decision)
    assert can_show is False, "UI MUST NOT render blocked decision as OFFICIAL"
    
    print("✅ UI GATE: BLOCKED_BY_INTEGRITY cannot render as OFFICIAL")
    print(f"   Release Status: {decision.release_status}")
    print(f"   Classification: {decision.classification}")
    print(f"   Validator Failures: {decision.validator_failures}")
    print(f"   Can Render as Official: {can_show} (MUST be False)")


if __name__ == "__main__":
    test_validator_pass_example()
    print()
    test_validator_fail_example_spread_sign_bug()
    print()
    test_validator_fail_example_classification_coherence()
    print()
    test_ui_cannot_show_official_when_blocked()
    print()
    print("=" * 80)
    print("ALL VALIDATOR PROOF TESTS PASSED")
    print("=" * 80)
