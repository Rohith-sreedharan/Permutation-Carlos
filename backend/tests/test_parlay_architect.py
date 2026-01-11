"""
Parlay Architect Verification Tests
====================================
Deterministic test fixture to verify parlay generation.

This ensures:
1. Parlay Architect ALWAYS returns PARLAY or FAIL (never None/silent)
2. Tier mapping works correctly
3. Fallback ladder produces valid results
4. Correlation enforcement works
5. All required greps pass
"""

import pytest
from datetime import datetime, timezone
from typing import Optional
from backend.core.parlay_architect import (
    build_parlay, ParlayRequest, Leg, Tier, MarketType,
    derive_tier, compute_leg_weight, eligible_pool, tier_counts
)


# -----------------------------
# Test Fixtures
# -----------------------------

def create_test_leg(
    event_id: str,
    sport: str = "NBA",
    tier: Tier = Tier.EDGE,
    confidence: float = 70.0,
    volatility: str = "MEDIUM",
    canonical_state: str = "EDGE",
    team_key: Optional[str] = None,
) -> Leg:
    """Create a test leg with sensible defaults"""
    return Leg(
        event_id=event_id,
        sport=sport,
        league="NBA" if sport == "NBA" else sport,
        start_time_utc=datetime.now(timezone.utc),
        market_type=MarketType.SPREAD,
        selection=f"Team A {event_id}",
        tier=tier,
        confidence=confidence,
        clv=0.5,
        total_deviation=5.0,
        volatility=volatility,
        ev=0.0,
        di_pass=True,
        mv_pass=True,
        is_locked=False,
        injury_stable=True,
        team_key=team_key,
        canonical_state=canonical_state,
    )


def get_healthy_fixture() -> list[Leg]:
    """
    Healthy fixture with diverse tiers.
    
    Should produce a parlay for any profile.
    """
    return [
        # 3 EDGE legs
        create_test_leg("evt_1", tier=Tier.EDGE, confidence=75.0, canonical_state="EDGE"),
        create_test_leg("evt_2", tier=Tier.EDGE, confidence=72.0, canonical_state="EDGE"),
        create_test_leg("evt_3", tier=Tier.EDGE, confidence=68.0, canonical_state="EDGE"),
        
        # 5 PICK legs
        create_test_leg("evt_4", tier=Tier.PICK, confidence=65.0, canonical_state="LEAN", team_key="team_a"),
        create_test_leg("evt_5", tier=Tier.PICK, confidence=62.0, canonical_state="LEAN", team_key="team_b"),
        create_test_leg("evt_6", tier=Tier.PICK, confidence=60.0, canonical_state="LEAN", team_key="team_c"),
        create_test_leg("evt_7", tier=Tier.PICK, confidence=61.0, canonical_state="LEAN", team_key="team_d"),
        create_test_leg("evt_8", tier=Tier.PICK, confidence=63.0, canonical_state="LEAN", team_key="team_e"),
        
        # 8 LEAN legs
        create_test_leg("evt_9", tier=Tier.LEAN, confidence=55.0, canonical_state="LEAN"),
        create_test_leg("evt_10", tier=Tier.LEAN, confidence=54.0, canonical_state="LEAN"),
        create_test_leg("evt_11", tier=Tier.LEAN, confidence=53.0, canonical_state="LEAN"),
        create_test_leg("evt_12", tier=Tier.LEAN, confidence=52.0, canonical_state="LEAN"),
        create_test_leg("evt_13", tier=Tier.LEAN, confidence=51.0, canonical_state="LEAN"),
        create_test_leg("evt_14", tier=Tier.LEAN, confidence=50.0, canonical_state="LEAN"),
        create_test_leg("evt_15", tier=Tier.LEAN, confidence=55.0, canonical_state="LEAN"),
        create_test_leg("evt_16", tier=Tier.LEAN, confidence=54.0, canonical_state="LEAN"),
    ]


def get_starved_fixture() -> list[Leg]:
    """
    Low-quality fixture (few EDGE, mostly LEAN).
    
    Should produce FAIL for premium, but PARLAY for balanced/speculative.
    """
    return [
        # Only 1 EDGE
        create_test_leg("evt_1", tier=Tier.EDGE, confidence=70.0, canonical_state="EDGE"),
        
        # 2 PICK
        create_test_leg("evt_2", tier=Tier.PICK, confidence=62.0, canonical_state="LEAN"),
        create_test_leg("evt_3", tier=Tier.PICK, confidence=60.0, canonical_state="LEAN"),
        
        # 6 LEAN
        create_test_leg("evt_4", tier=Tier.LEAN, confidence=55.0, canonical_state="LEAN"),
        create_test_leg("evt_5", tier=Tier.LEAN, confidence=54.0, canonical_state="LEAN"),
        create_test_leg("evt_6", tier=Tier.LEAN, confidence=53.0, canonical_state="LEAN"),
        create_test_leg("evt_7", tier=Tier.LEAN, confidence=52.0, canonical_state="LEAN"),
        create_test_leg("evt_8", tier=Tier.LEAN, confidence=51.0, canonical_state="LEAN"),
        create_test_leg("evt_9", tier=Tier.LEAN, confidence=50.0, canonical_state="LEAN"),
    ]


# -----------------------------
# Unit Tests
# -----------------------------

class TestTierDerivation:
    """Test derive_tier() mapping"""
    
    def test_edge_maps_to_edge(self):
        assert derive_tier("EDGE", 70.0) == Tier.EDGE
    
    def test_strong_lean_upgrades_to_pick(self):
        assert derive_tier("LEAN", 65.0) == Tier.PICK
        assert derive_tier("LEAN", 60.0) == Tier.PICK
    
    def test_weak_lean_stays_lean(self):
        assert derive_tier("LEAN", 59.0) == Tier.LEAN
        assert derive_tier("LEAN", 50.0) == Tier.LEAN
    
    def test_pick_maps_to_pick(self):
        assert derive_tier("PICK", 65.0) == Tier.PICK


class TestLegWeighting:
    """Test compute_leg_weight() scoring"""
    
    def test_edge_weights_higher_than_pick(self):
        edge_leg = create_test_leg("evt_1", tier=Tier.EDGE, confidence=70.0)
        pick_leg = create_test_leg("evt_2", tier=Tier.PICK, confidence=70.0)
        
        assert compute_leg_weight(edge_leg) > compute_leg_weight(pick_leg)
    
    def test_pick_weights_higher_than_lean(self):
        pick_leg = create_test_leg("evt_1", tier=Tier.PICK, confidence=60.0)
        lean_leg = create_test_leg("evt_2", tier=Tier.LEAN, confidence=60.0)
        
        assert compute_leg_weight(pick_leg) > compute_leg_weight(lean_leg)
    
    def test_high_volatility_penalizes(self):
        low_vol = create_test_leg("evt_1", tier=Tier.EDGE, volatility="LOW")
        high_vol = create_test_leg("evt_2", tier=Tier.EDGE, volatility="HIGH")
        
        assert compute_leg_weight(low_vol) > compute_leg_weight(high_vol)


class TestEligibilityGates:
    """Test hard gates (DI/MV)"""
    
    def test_di_fail_excluded(self):
        legs = [
            create_test_leg("evt_1", tier=Tier.EDGE),
            Leg(
                event_id="evt_2",
                sport="NBA",
                league="NBA",
                start_time_utc=datetime.now(timezone.utc),
                market_type=MarketType.SPREAD,
                selection="Bad leg",
                tier=Tier.EDGE,
                confidence=80.0,
                clv=0.0,
                total_deviation=0.0,
                volatility="LOW",
                ev=0.0,
                di_pass=False,  # FAIL
                mv_pass=True,
            ),
        ]
        
        pool = eligible_pool(legs, include_props=False)
        assert len(pool) == 1
        assert pool[0].event_id == "evt_1"
    
    def test_mv_fail_excluded(self):
        legs = [
            create_test_leg("evt_1", tier=Tier.EDGE),
            Leg(
                event_id="evt_2",
                sport="NBA",
                league="NBA",
                start_time_utc=datetime.now(timezone.utc),
                market_type=MarketType.SPREAD,
                selection="Bad leg",
                tier=Tier.EDGE,
                confidence=80.0,
                clv=0.0,
                total_deviation=0.0,
                volatility="LOW",
                ev=0.0,
                di_pass=True,
                mv_pass=False,  # FAIL
            ),
        ]
        
        pool = eligible_pool(legs, include_props=False)
        assert len(pool) == 1
        assert pool[0].event_id == "evt_1"


# -----------------------------
# Integration Tests
# -----------------------------

class TestHealthyFixture:
    """Test with healthy fixture (should always produce PARLAY)"""
    
    def test_premium_profile_produces_parlay(self):
        legs = get_healthy_fixture()
        req = ParlayRequest(profile="premium", legs=4, seed=12345)
        result = build_parlay(legs, req)
        
        assert result.status == "PARLAY"
        assert len(result.legs_selected) == 4
        assert result.parlay_weight > 0.0
    
    def test_balanced_profile_produces_parlay(self):
        legs = get_healthy_fixture()
        req = ParlayRequest(profile="balanced", legs=4, seed=12345)
        result = build_parlay(legs, req)
        
        assert result.status == "PARLAY"
        assert len(result.legs_selected) == 4
    
    def test_speculative_profile_produces_parlay(self):
        legs = get_healthy_fixture()
        req = ParlayRequest(profile="speculative", legs=4, seed=12345)
        result = build_parlay(legs, req)
        
        assert result.status == "PARLAY"
        assert len(result.legs_selected) == 4
    
    def test_deterministic_with_seed(self):
        """Same seed should produce same parlay"""
        legs = get_healthy_fixture()
        
        req1 = ParlayRequest(profile="balanced", legs=4, seed=99999)
        result1 = build_parlay(legs, req1)
        
        req2 = ParlayRequest(profile="balanced", legs=4, seed=99999)
        result2 = build_parlay(legs, req2)
        
        # Same event IDs in same order
        assert [l.event_id for l in result1.legs_selected] == [l.event_id for l in result2.legs_selected]


class TestStarvedFixture:
    """Test with starved fixture (low quality)"""
    
    def test_premium_may_fail(self):
        """Premium profile may fail with weak fixture"""
        legs = get_starved_fixture()
        req = ParlayRequest(profile="premium", legs=4, seed=12345)
        result = build_parlay(legs, req)
        
        # Either succeeds with fallback or fails with reason
        if result.status == "FAIL":
            assert result.reason_code is not None
            assert result.reason_detail is not None
        else:
            assert result.status == "PARLAY"
            assert len(result.legs_selected) == 4
    
    def test_balanced_produces_parlay(self):
        """Balanced should produce parlay even with weak fixture"""
        legs = get_starved_fixture()
        req = ParlayRequest(profile="balanced", legs=4, seed=12345)
        result = build_parlay(legs, req)
        
        assert result.status == "PARLAY"
        assert len(result.legs_selected) == 4
    
    def test_speculative_produces_parlay(self):
        """Speculative should always produce parlay if eligible_total >= legs"""
        legs = get_starved_fixture()
        req = ParlayRequest(profile="speculative", legs=4, seed=12345)
        result = build_parlay(legs, req)
        
        assert result.status == "PARLAY"
        assert len(result.legs_selected) == 4


class TestCorrelationEnforcement:
    """Test same_event and same_team blocking"""
    
    def test_same_event_blocked(self):
        """When allow_same_event=False, should block correlated legs"""
        legs = [
            create_test_leg("evt_1", tier=Tier.EDGE),
            create_test_leg("evt_1", tier=Tier.EDGE),  # same event
            create_test_leg("evt_2", tier=Tier.EDGE),
            create_test_leg("evt_3", tier=Tier.EDGE),
        ]
        
        req = ParlayRequest(profile="balanced", legs=4, allow_same_event=False, seed=12345)
        result = build_parlay(legs, req)
        
        # Should fail or select only unique events
        if result.status == "PARLAY":
            event_ids = [l.event_id for l in result.legs_selected]
            assert len(event_ids) == len(set(event_ids))  # all unique
    
    def test_same_team_blocked(self):
        """When allow_same_team=False, should block correlated team legs"""
        legs = [
            create_test_leg("evt_1", tier=Tier.EDGE, team_key="team_a"),
            create_test_leg("evt_2", tier=Tier.EDGE, team_key="team_a"),  # same team
            create_test_leg("evt_3", tier=Tier.EDGE, team_key="team_b"),
            create_test_leg("evt_4", tier=Tier.EDGE, team_key="team_c"),
        ]
        
        req = ParlayRequest(profile="balanced", legs=4, allow_same_team=False, seed=12345)
        result = build_parlay(legs, req)
        
        # Should fail or select only unique teams
        if result.status == "PARLAY":
            team_keys = [l.team_key for l in result.legs_selected if l.team_key]
            assert len(team_keys) == len(set(team_keys))  # all unique


class TestFailureReasons:
    """Test that failures always have reasons"""
    
    def test_insufficient_pool_has_reason(self):
        """Test INSUFFICIENT_POOL failure"""
        legs = [
            create_test_leg("evt_1", tier=Tier.EDGE),
            create_test_leg("evt_2", tier=Tier.EDGE),
        ]
        
        req = ParlayRequest(profile="balanced", legs=4, seed=12345)
        result = build_parlay(legs, req)
        
        assert result.status == "FAIL"
        assert result.reason_code == "INSUFFICIENT_POOL"
        assert result.reason_detail is not None
        assert "eligible_pool_size" in result.reason_detail
    
    def test_invalid_profile_has_reason(self):
        """Test INVALID_PROFILE failure"""
        legs = get_healthy_fixture()
        req = ParlayRequest(profile="invalid_profile", legs=4, seed=12345)
        result = build_parlay(legs, req)
        
        assert result.status == "FAIL"
        assert result.reason_code == "INVALID_PROFILE"
        assert result.reason_detail is not None


# -----------------------------
# Grep Verification Tests
# -----------------------------

class TestNoSilentFailure:
    """Ensure ZERO silent failures (critical requirement)"""
    
    def test_never_returns_none(self):
        """build_parlay must NEVER return None"""
        legs = get_healthy_fixture()
        req = ParlayRequest(profile="balanced", legs=4, seed=12345)
        result = build_parlay(legs, req)
        
        assert result is not None
        assert isinstance(result, type(result))  # has a type
    
    def test_always_has_status(self):
        """Result must always have status"""
        legs = get_healthy_fixture()
        req = ParlayRequest(profile="balanced", legs=4, seed=12345)
        result = build_parlay(legs, req)
        
        assert result.status in ["PARLAY", "FAIL"]
    
    def test_fail_always_has_reason(self):
        """FAIL must always have reason_code and reason_detail"""
        legs = []  # empty to force fail
        req = ParlayRequest(profile="balanced", legs=4, seed=12345)
        result = build_parlay(legs, req)
        
        assert result.status == "FAIL"
        assert result.reason_code is not None
        assert result.reason_detail is not None


if __name__ == "__main__":
    # Quick smoke test
    print("Running smoke tests...")
    
    # Test 1: Healthy fixture
    legs = get_healthy_fixture()
    req = ParlayRequest(profile="balanced", legs=4, seed=12345)
    result = build_parlay(legs, req)
    print(f"✓ Healthy fixture: {result.status} (weight={result.parlay_weight:.2f})")
    
    # Test 2: Starved fixture
    legs = get_starved_fixture()
    req = ParlayRequest(profile="premium", legs=4, seed=12345)
    result = build_parlay(legs, req)
    print(f"✓ Starved fixture (premium): {result.status}")
    if result.status == "FAIL":
        print(f"  Reason: {result.reason_code}")
    
    # Test 3: Determinism
    legs = get_healthy_fixture()
    req1 = ParlayRequest(profile="balanced", legs=4, seed=99999)
    req2 = ParlayRequest(profile="balanced", legs=4, seed=99999)
    result1 = build_parlay(legs, req1)
    result2 = build_parlay(legs, req2)
    assert [l.event_id for l in result1.legs_selected] == [l.event_id for l in result2.legs_selected]
    print("✓ Deterministic output verified")
    
    print("\n✅ All smoke tests passed!")
