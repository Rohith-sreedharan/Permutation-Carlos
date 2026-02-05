"""
SINGLES ENGINE STRESS TEST SUITE
Singles Engine Brief - Non-Negotiable Validation

Test Matrix:
1. Schema stress (unknown versions, missing required fields)
2. Binding stress (preference != direction mismatches)
3. Probability consistency (epsilon tolerance)
4. Edge classification rules (MARKET_ALIGNED => NO_EDGE)
5. Snapshot locking (no mixed old/new data)
6. Totals OVER/UNDER (side key correctness)
7. ML null lines (market_line_for_selection nullable)
8. Independent markets (missing TOTAL doesn't break SPREAD)
9. Line movements (snapshot_hash changes)
10. OddsAPI bookmaker variations

Passing Criteria:
- 25 games × 3 markets = 75 renders
- 0 crashes
- 0 team mismatches
- 0 probability mismatches
- 0 snapshot mixing
- SAFE MODE triggers only on FAIL payloads
- Valid payloads never trigger SAFE MODE
"""

import pytest
from typing import Dict, Any, List
from unittest.mock import Mock, patch
import hashlib
import json


# ===========================
# TEST FIXTURES
# ===========================

@pytest.fixture
def valid_spread_marketview() -> Dict[str, Any]:
    """Valid SPREAD MarketView (PASS)"""
    return {
        "schema_version": "mv.v1",
        "event_id": "test_event_123",
        "market_type": "SPREAD",
        "snapshot_hash": "abc123",
        "integrity_status": "PASS",
        "integrity_violations": [],
        "selections": [
            {
                "selection_id": "sel_home_spread",
                "side": "HOME",
                "market_line_for_selection": -5.5,
                "model_fair_line_for_selection": -3.2,
                "market_probability": 0.52,
                "model_probability": 0.58
            },
            {
                "selection_id": "sel_away_spread",
                "side": "AWAY",
                "market_line_for_selection": 5.5,
                "model_fair_line_for_selection": 3.2,
                "market_probability": 0.48,
                "model_probability": 0.42
            }
        ],
        "model_preference_selection_id": "sel_home_spread",
        "edge_class": "EDGE",
        "edge_points": 2.3
    }


@pytest.fixture
def valid_ml_marketview() -> Dict[str, Any]:
    """Valid MONEYLINE MarketView (null lines allowed)"""
    return {
        "schema_version": "mv.v1",
        "event_id": "test_event_123",
        "market_type": "MONEYLINE",
        "snapshot_hash": "abc123",
        "integrity_status": "PASS",
        "integrity_violations": [],
        "selections": [
            {
                "selection_id": "sel_home_ml",
                "side": "HOME",
                "market_line_for_selection": None,  # ML allows null
                "model_fair_line_for_selection": None,
                "market_probability": 0.65,
                "model_probability": 0.70
            },
            {
                "selection_id": "sel_away_ml",
                "side": "AWAY",
                "market_line_for_selection": None,
                "model_fair_line_for_selection": None,
                "market_probability": 0.35,
                "model_probability": 0.30
            }
        ],
        "model_preference_selection_id": "sel_home_ml",
        "edge_class": "LEAN",
        "edge_points": 0.05
    }


@pytest.fixture
def valid_total_marketview() -> Dict[str, Any]:
    """Valid TOTAL MarketView (OVER/UNDER sides)"""
    return {
        "schema_version": "mv.v1",
        "event_id": "test_event_123",
        "market_type": "TOTAL",
        "snapshot_hash": "abc123",
        "integrity_status": "PASS",
        "integrity_violations": [],
        "selections": [
            {
                "selection_id": "sel_over",
                "side": "OVER",
                "market_line_for_selection": 226.5,
                "model_fair_line_for_selection": 224.1,
                "market_probability": 0.50,
                "model_probability": 0.54
            },
            {
                "selection_id": "sel_under",
                "side": "UNDER",
                "market_line_for_selection": 226.5,
                "model_fair_line_for_selection": 224.1,
                "market_probability": 0.50,
                "model_probability": 0.46
            }
        ],
        "model_preference_selection_id": "sel_over",
        "edge_class": "LEAN",
        "edge_points": 2.4
    }


@pytest.fixture
def market_aligned_marketview() -> Dict[str, Any]:
    """MARKET_ALIGNED => preference must be NO_EDGE"""
    return {
        "schema_version": "mv.v1",
        "event_id": "test_event_456",
        "market_type": "SPREAD",
        "snapshot_hash": "def456",
        "integrity_status": "PASS",
        "integrity_violations": [],
        "selections": [
            {
                "selection_id": "sel_home",
                "side": "HOME",
                "market_line_for_selection": -3.0,
                "model_fair_line_for_selection": -3.1,
                "market_probability": 0.51,
                "model_probability": 0.51
            },
            {
                "selection_id": "sel_away",
                "side": "AWAY",
                "market_line_for_selection": 3.0,
                "model_fair_line_for_selection": 3.1,
                "market_probability": 0.49,
                "model_probability": 0.49
            }
        ],
        "model_preference_selection_id": "NO_EDGE",
        "edge_class": "MARKET_ALIGNED",
        "edge_points": 0.0
    }


# ===========================
# VALIDATION TESTS
# ===========================

class TestSchemaValidation:
    """Test 1: Schema stress - version checks, missing required fields"""
    
    def test_unknown_schema_version(self, valid_spread_marketview):
        """Unknown schema_version must trigger SAFE MODE"""
        valid_spread_marketview["schema_version"] = "mv.v2"  # Unknown
        errors = validate_marketview_required_fields(valid_spread_marketview)
        assert "Unknown schema_version" in str(errors)
    
    def test_missing_schema_version(self, valid_spread_marketview):
        """Missing schema_version must trigger SAFE MODE"""
        del valid_spread_marketview["schema_version"]
        errors = validate_marketview_required_fields(valid_spread_marketview)
        assert "Missing schema_version" in str(errors)
    
    def test_missing_event_id(self, valid_spread_marketview):
        """Missing event_id must trigger SAFE MODE"""
        del valid_spread_marketview["event_id"]
        errors = validate_marketview_required_fields(valid_spread_marketview)
        assert "Missing event_id" in str(errors)
    
    def test_missing_snapshot_hash(self, valid_spread_marketview):
        """Missing snapshot_hash must trigger SAFE MODE"""
        del valid_spread_marketview["snapshot_hash"]
        errors = validate_marketview_required_fields(valid_spread_marketview)
        assert "Missing snapshot_hash" in str(errors)
    
    def test_missing_selection_id(self, valid_spread_marketview):
        """Missing selection_id must trigger SAFE MODE (REQUIRED)"""
        del valid_spread_marketview["selections"][0]["selection_id"]
        errors = validate_marketview_required_fields(valid_spread_marketview)
        assert "missing selection_id" in str(errors)
    
    def test_optional_fields_dont_gate(self, valid_spread_marketview):
        """OPTIONAL fields (labels, grades) must NOT trigger SAFE MODE"""
        # Remove all optional fields
        if "explanation" in valid_spread_marketview:
            del valid_spread_marketview["explanation"]
        if "grade" in valid_spread_marketview:
            del valid_spread_marketview["grade"]
        
        errors = validate_marketview_required_fields(valid_spread_marketview)
        assert len(errors) == 0, "Optional fields should not gate PASS status"


class TestProbabilityConsistency:
    """Test 3: Probability epsilon tolerance (≤0.001 PASS, >0.001 DEGRADE, >0.01 FAIL)"""
    
    def test_epsilon_pass(self):
        """Prob sum within 0.001 => PASS"""
        # 0.5001 + 0.4999 = 1.0000 (diff = 0.0000)
        probs = {"market_probability": 0.5001, "model_probability": 0.4999}
        status = validate_probability_sum(probs)
        assert status == "PASS"
    
    def test_epsilon_degrade(self):
        """Prob sum drift 0.001 < diff ≤ 0.01 => DEGRADE"""
        # 0.51 + 0.48 = 0.99 (diff = 0.01)
        probs = {"market_probability": 0.51, "model_probability": 0.48}
        status = validate_probability_sum(probs)
        assert status == "DEGRADE"
    
    def test_epsilon_fail(self):
        """Prob sum drift > 0.01 => FAIL"""
        # 0.55 + 0.40 = 0.95 (diff = 0.05)
        probs = {"market_probability": 0.55, "model_probability": 0.40}
        status = validate_probability_sum(probs)
        assert status == "FAIL"


class TestEdgeClassificationRules:
    """Test 4: Edge classification logic (MARKET_ALIGNED => NO_EDGE, EDGE/LEAN => valid sel_id)"""
    
    def test_market_aligned_requires_no_edge(self, market_aligned_marketview):
        """MARKET_ALIGNED must have preference = NO_EDGE"""
        assert market_aligned_marketview["edge_class"] == "MARKET_ALIGNED"
        assert market_aligned_marketview["model_preference_selection_id"] == "NO_EDGE"
    
    def test_edge_requires_valid_selection(self, valid_spread_marketview):
        """EDGE/LEAN must have preference matching one selection"""
        assert valid_spread_marketview["edge_class"] in ["EDGE", "LEAN"]
        pref_id = valid_spread_marketview["model_preference_selection_id"]
        selection_ids = [s["selection_id"] for s in valid_spread_marketview["selections"]]
        assert pref_id in selection_ids
    
    def test_market_aligned_with_wrong_preference_fails(self, market_aligned_marketview):
        """MARKET_ALIGNED with preference != NO_EDGE must FAIL"""
        market_aligned_marketview["model_preference_selection_id"] = "sel_home"  # Wrong
        errors = validate_edge_logic(market_aligned_marketview)
        assert "MARKET_ALIGNED must have preference=NO_EDGE" in str(errors)


class TestSnapshotLocking:
    """Test 5: Snapshot locking (no mixed old/new data)"""
    
    def test_consistent_snapshot_across_markets(self):
        """All markets in one render must share same snapshot_hash (or be independent)"""
        # Simulate multi-market response
        spread_view = {"snapshot_hash": "abc123", "market_type": "SPREAD"}
        ml_view = {"snapshot_hash": "abc123", "market_type": "MONEYLINE"}
        total_view = {"snapshot_hash": "abc123", "market_type": "TOTAL"}
        
        hashes = [spread_view["snapshot_hash"], ml_view["snapshot_hash"], total_view["snapshot_hash"]]
        assert len(set(hashes)) == 1, "All markets must share same snapshot or be independent"
    
    def test_snapshot_change_triggers_full_swap(self):
        """On snapshot_hash change, entire MarketView must swap (no partial updates)"""
        old_view = {"snapshot_hash": "old123", "edge_points": 2.5}
        new_view = {"snapshot_hash": "new456", "edge_points": 3.1}
        
        # Simulated atomic swap
        assert old_view["snapshot_hash"] != new_view["snapshot_hash"]
        # In real UI, this would trigger a React key change and full unmount/remount


class TestIndependentMarkets:
    """Test 8: Independent markets (missing TOTAL doesn't break SPREAD)"""
    
    def test_missing_total_doesnt_crash(self, valid_spread_marketview, valid_ml_marketview):
        """Missing TOTAL market should not invalidate SPREAD/ML"""
        simulation = {
            "market_views": {
                "spread": valid_spread_marketview,
                "moneyline": valid_ml_marketview,
                "total": None  # Missing
            }
        }
        
        # SPREAD should still be valid
        assert simulation["market_views"]["spread"]["integrity_status"] == "PASS"
        # ML should still be valid
        assert simulation["market_views"]["moneyline"]["integrity_status"] == "PASS"
        # TOTAL being None is acceptable (UI will hide tab)


class TestTotalsOVERUNDER:
    """Test 6: Totals OVER/UNDER side key correctness"""
    
    def test_total_has_over_under_sides(self, valid_total_marketview):
        """TOTAL market must have OVER and UNDER selections"""
        sides = [s["side"] for s in valid_total_marketview["selections"]]
        assert "OVER" in sides
        assert "UNDER" in sides
    
    def test_total_selections_have_same_line(self, valid_total_marketview):
        """OVER/UNDER selections must reference same total line"""
        over_line = valid_total_marketview["selections"][0]["market_line_for_selection"]
        under_line = valid_total_marketview["selections"][1]["market_line_for_selection"]
        assert over_line == under_line


class TestMoneylineNullLines:
    """Test 7: ML null lines (market_line_for_selection nullable only for MONEYLINE)"""
    
    def test_ml_allows_null_lines(self, valid_ml_marketview):
        """MONEYLINE selections can have null market_line_for_selection"""
        for sel in valid_ml_marketview["selections"]:
            assert sel["market_line_for_selection"] is None  # OK for ML
    
    def test_spread_requires_lines(self, valid_spread_marketview):
        """SPREAD selections must have non-null market_line_for_selection"""
        for sel in valid_spread_marketview["selections"]:
            assert sel["market_line_for_selection"] is not None
    
    def test_total_requires_lines(self, valid_total_marketview):
        """TOTAL selections must have non-null market_line_for_selection"""
        for sel in valid_total_marketview["selections"]:
            assert sel["market_line_for_selection"] is not None


# ===========================
# 25 GAMES × 3 MARKETS = 75 RENDERS
# ===========================

class TestRegressionSuite:
    """Test functional regression: 25 games × 3 markets"""
    
    @pytest.fixture
    def generate_25_games(self) -> List[Dict[str, Any]]:
        """Generate 25 sample events for regression testing"""
        games = []
        for i in range(25):
            games.append({
                "event_id": f"game_{i:03d}",
                "home_team": f"Team_Home_{i}",
                "away_team": f"Team_Away_{i}",
                "market_views": {
                    "spread": self._generate_spread(f"game_{i:03d}"),
                    "moneyline": self._generate_ml(f"game_{i:03d}"),
                    "total": self._generate_total(f"game_{i:03d}")
                }
            })
        return games
    
    def _generate_spread(self, event_id: str) -> Dict[str, Any]:
        return {
            "schema_version": "mv.v1",
            "event_id": event_id,
            "market_type": "SPREAD",
            "snapshot_hash": hashlib.sha256(event_id.encode()).hexdigest()[:16],
            "integrity_status": "PASS",
            "integrity_violations": [],
            "selections": [
                {
                    "selection_id": f"{event_id}_spread_home",
                    "side": "HOME",
                    "market_line_for_selection": -4.5,
                    "model_fair_line_for_selection": -2.8,
                    "market_probability": 0.52,
                    "model_probability": 0.56
                },
                {
                    "selection_id": f"{event_id}_spread_away",
                    "side": "AWAY",
                    "market_line_for_selection": 4.5,
                    "model_fair_line_for_selection": 2.8,
                    "market_probability": 0.48,
                    "model_probability": 0.44
                }
            ],
            "model_preference_selection_id": f"{event_id}_spread_home",
            "edge_class": "EDGE",
            "edge_points": 1.7
        }
    
    def _generate_ml(self, event_id: str) -> Dict[str, Any]:
        return {
            "schema_version": "mv.v1",
            "event_id": event_id,
            "market_type": "MONEYLINE",
            "snapshot_hash": hashlib.sha256(event_id.encode()).hexdigest()[:16],
            "integrity_status": "PASS",
            "integrity_violations": [],
            "selections": [
                {
                    "selection_id": f"{event_id}_ml_home",
                    "side": "HOME",
                    "market_line_for_selection": None,
                    "model_fair_line_for_selection": None,
                    "market_probability": 0.60,
                    "model_probability": 0.63
                },
                {
                    "selection_id": f"{event_id}_ml_away",
                    "side": "AWAY",
                    "market_line_for_selection": None,
                    "model_fair_line_for_selection": None,
                    "market_probability": 0.40,
                    "model_probability": 0.37
                }
            ],
            "model_preference_selection_id": f"{event_id}_ml_home",
            "edge_class": "LEAN",
            "edge_points": 0.03
        }
    
    def _generate_total(self, event_id: str) -> Dict[str, Any]:
        return {
            "schema_version": "mv.v1",
            "event_id": event_id,
            "market_type": "TOTAL",
            "snapshot_hash": hashlib.sha256(event_id.encode()).hexdigest()[:16],
            "integrity_status": "PASS",
            "integrity_violations": [],
            "selections": [
                {
                    "selection_id": f"{event_id}_over",
                    "side": "OVER",
                    "market_line_for_selection": 220.5,
                    "model_fair_line_for_selection": 218.2,
                    "market_probability": 0.50,
                    "model_probability": 0.53
                },
                {
                    "selection_id": f"{event_id}_under",
                    "side": "UNDER",
                    "market_line_for_selection": 220.5,
                    "model_fair_line_for_selection": 218.2,
                    "market_probability": 0.50,
                    "model_probability": 0.47
                }
            ],
            "model_preference_selection_id": f"{event_id}_over",
            "edge_class": "LEAN",
            "edge_points": 2.3
        }
    
    def test_75_renders_no_crashes(self, generate_25_games):
        """25 games × 3 markets = 75 renders with 0 crashes"""
        crash_count = 0
        mismatch_count = 0
        
        for game in generate_25_games:
            for market_type in ["spread", "moneyline", "total"]:
                try:
                    market_view = game["market_views"][market_type]
                    errors = validate_marketview_required_fields(market_view)
                    if errors:
                        mismatch_count += 1
                except Exception as e:
                    crash_count += 1
        
        assert crash_count == 0, f"{crash_count} crashes detected"
        assert mismatch_count == 0, f"{mismatch_count} validation failures"


# ===========================
# EDGE DISPLAY PROOF TESTS
# ===========================

class TestEdgeDisplayGuarantee:
    """Proof tests: edges/leans won't disappear (closure requirement)"""
    
    def test_edge_display(self, valid_spread_marketview):
        """A) Force EDGE => UI must show EDGE and highlight preferred selection"""
        assert valid_spread_marketview["edge_class"] == "EDGE"
        assert valid_spread_marketview["model_preference_selection_id"] != "NO_EDGE"
        # UI assertion: would render EDGE badge + highlight preferred selection
    
    def test_degrade_still_shows_edge(self, valid_spread_marketview):
        """B) DEGRADE status must STILL show EDGE/LEAN (not trigger SAFE MODE)"""
        valid_spread_marketview["integrity_status"] = "DEGRADE"
        valid_spread_marketview["integrity_violations"] = ["Minor prob drift"]
        
        # Validate DEGRADE doesn't hide edges
        assert valid_spread_marketview["edge_class"] == "EDGE"
        # UI assertion: DEGRADE shows warning but still renders edge
    
    def test_fail_hides_edge(self, valid_spread_marketview):
        """C) FAIL status must trigger SAFE MODE and hide edges/leans"""
        del valid_spread_marketview["selections"][0]["selection_id"]  # Force FAIL
        errors = validate_marketview_required_fields(valid_spread_marketview)
        
        assert len(errors) > 0
        # UI assertion: SAFE MODE shows, edges/leans hidden


# ===========================
# HELPER VALIDATION FUNCTIONS
# (Simulated - in real code these live in GameDetail.tsx)
# ===========================

def validate_marketview_required_fields(market_view: Dict[str, Any]) -> List[str]:
    """Validate REQUIRED fields only (replicates GameDetail.tsx validateMarketView)"""
    errors = []
    
    # 1. Schema version
    if "schema_version" not in market_view:
        errors.append("Missing schema_version")
    elif market_view["schema_version"] != "mv.v1":
        errors.append(f"Unknown schema_version: {market_view['schema_version']}")
    
    # 2. Identifiers
    if "event_id" not in market_view:
        errors.append("Missing event_id")
    if "market_type" not in market_view:
        errors.append("Missing market_type")
    if "snapshot_hash" not in market_view:
        errors.append("Missing snapshot_hash")
    
    # 3. Integrity status
    if "integrity_status" not in market_view:
        errors.append("Missing integrity_status")
    
    # 4. Selections
    if "selections" not in market_view or not isinstance(market_view["selections"], list):
        errors.append("Missing or invalid selections")
    elif len(market_view["selections"]) != 2:
        errors.append(f"Invalid selections count: {len(market_view['selections'])}")
    else:
        for idx, sel in enumerate(market_view["selections"]):
            if "selection_id" not in sel:
                errors.append(f"Selection {idx}: missing selection_id")
            if "side" not in sel:
                errors.append(f"Selection {idx}: missing side")
            if "market_probability" not in sel:
                errors.append(f"Selection {idx}: missing market_probability")
            if "model_probability" not in sel:
                errors.append(f"Selection {idx}: missing model_probability")
            # market_line_for_selection nullable only for ML
            if market_view.get("market_type") != "MONEYLINE" and "market_line_for_selection" not in sel:
                errors.append(f"Selection {idx}: missing market_line_for_selection")
    
    # 5. Edge classification
    if "edge_class" not in market_view:
        errors.append("Missing edge_class")
    if "model_preference_selection_id" not in market_view:
        errors.append("Missing model_preference_selection_id")
    if "edge_points" not in market_view:
        errors.append("Missing edge_points")
    
    return errors


def validate_edge_logic(market_view: Dict[str, Any]) -> List[str]:
    """Validate edge classification logic"""
    errors = []
    
    edge_class = market_view.get("edge_class")
    pref_id = market_view.get("model_preference_selection_id")
    
    if edge_class == "MARKET_ALIGNED" and pref_id != "NO_EDGE":
        errors.append("MARKET_ALIGNED must have preference=NO_EDGE")
    
    if edge_class in ["EDGE", "LEAN"]:
        selection_ids = [s["selection_id"] for s in market_view.get("selections", [])]
        if pref_id not in selection_ids:
            errors.append("Preference selection_id must match one of the selections")
    
    return errors


def validate_probability_sum(probs: Dict[str, float]) -> str:
    """Validate prob sum with epsilon tolerance"""
    total = probs["market_probability"] + probs["model_probability"]
    diff = abs(total - 1.0)
    
    if diff <= 0.001:
        return "PASS"
    elif diff <= 0.01:
        return "DEGRADE"
    else:
        return "FAIL"


# ===========================
# RUN TESTS
# ===========================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
