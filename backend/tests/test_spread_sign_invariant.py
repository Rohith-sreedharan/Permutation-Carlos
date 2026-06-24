"""
REGRESSION TEST: Spread Sign Invariant Enforcement

This test suite ensures the backend NEVER allows same-signed spread values for
opposing teams (the exact bug class reported on 2026-06-18).

INVARIANT:
  For any spread market on any event, home and away sides must ALWAYS have
  opposite-signed values. Model Preference must inherit the canonical binding.
  
  If the binding is missing, ambiguous, or contradictory:
  - The system MUST fail closed (no_edge, no_play)
  - It MUST NEVER render two same-signed values for opposing sides

TEST CASES:
  1. Correct binding: has_edge=True + matching sharp_team/selection + model pref refs
  2. Missing binding: has_edge=True but sharp_team=None → FAIL CLOSED
  3. MARKET_ALIGNED + has_edge: Contradictory edge_class → FAIL CLOSED
  4. Same-sign rendering prevention: Verify no two same-signed renders possible
"""

import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone
from core.canonical_contract_enforcer import (
    enforce_canonical_contract,
    _normalize_spread_contract,
)


class TestSpreadSignInvariant:
    """Ensure spread sign contradictions are prevented at the backend layer."""

    def test_normalize_spread_contract_missing_binding_blocks_edge(self):
        """
        BUG CLASS: has_edge=True but sharp_team=None
        
        This was the EXACT failure pattern on event a75cee44d2cbdcedb356612df99cd692:
        - Model had directional probabilities (p_cover_home > p_cover_away)
        - sharp_selection was set to "PLAY"
        - BUT sharp_team was None (binding missing)
        - Model Preference was set to a team despite binding being incomplete
        - Result: Two same-signed values rendered to the UI
        
        Expected: Fail closed - block rendering, set edge_class=INVALID
        """
        # Create the EXACT failure shape from production
        simulation = {
            "event_id": "a75cee44d2cbdcedb356612df99cd692",
            "team_a": "Los Angeles Dodgers",
            "team_b": "Tampa Bay Rays",
            "sharp_analysis": {
                "spread": {
                    "has_edge": True,  # ← Claims edge exists
                    "sharp_team": None,  # ← But binding missing
                    "sharp_selection": "PLAY",
                    "sharp_side": "UNKNOWN",
                    "market_spread_home": 1.5,
                    "edge_direction": "DOG",
                }
            },
            "market_views": {
                "spread": {
                    "model_preference_selection_id": "a75cee44_spread_home",  # ← Render mismatch
                    "model_direction_selection_id": "a75cee44_spread_home",
                    "edge_class": "MARKET_ALIGNED",
                    "selections": [
                        {
                            "selection_id": "a75cee44_spread_home",
                            "team_name": "Los Angeles Dodgers",
                            "line": 1.5,
                            "side": "home",
                        },
                        {
                            "selection_id": "a75cee44_spread_away",
                            "team_name": "Tampa Bay Rays",
                            "line": -1.5,
                            "side": "away",
                        },
                    ],
                }
            },
        }

        # Apply the normalizer
        _normalize_spread_contract(simulation)

        # Assert it failed closed
        spread_view = simulation["market_views"]["spread"]
        spread_analysis = simulation["sharp_analysis"]["spread"]

        assert spread_view["edge_class"] == "INVALID", "Should block contradictory edge"
        assert (
            spread_view["model_preference_selection_id"] == "NO_EDGE"
        ), "Should clear preference on block"
        assert spread_analysis["has_edge"] is False, "Should disable edge"
        assert spread_analysis["sharp_selection"] == "NO PLAY", "Should block play"
        assert (
            "SPREAD_CANONICAL_BINDING_MISSING"
            in spread_view["integrity_status"]["errors"]
        ), "Should record binding error"

    def test_market_aligned_with_has_edge_fails_closed(self):
        """
        BUG VARIANT: edge_class=MARKET_ALIGNED + has_edge=True
        
        This is contradictory: MARKET_ALIGNED means "market line only, no edge",
        but has_edge=True means "we have an edge". These cannot both be true.
        
        Expected: Fail closed
        """
        simulation = {
            "event_id": "test_event",
            "team_a": "Team A",
            "team_b": "Team B",
            "sharp_analysis": {
                "spread": {
                    "has_edge": True,
                    "sharp_team": "Team A",
                    "sharp_selection": "PLAY",
                    "sharp_side": "Team A +1.5",
                }
            },
            "market_views": {
                "spread": {
                    "model_preference_selection_id": "selection_1",
                    "model_direction_selection_id": "selection_1",
                    "edge_class": "MARKET_ALIGNED",  # ← Contradicts has_edge=True
                    "ui_render_mode": "FULL",
                }
            },
        }

        _normalize_spread_contract(simulation)

        assert (
            simulation["market_views"]["spread"]["edge_class"] == "INVALID"
        ), "MARKET_ALIGNED + has_edge must fail closed"
        assert (
            simulation["sharp_analysis"]["spread"]["has_edge"] is False
        ), "Must disable edge on block"

    def test_correct_binding_passes_through(self):
        """
        VALID STATE: Binding complete and consistent
        
        - has_edge=True
        - sharp_team set to actual team
        - sharp_selection set to valid action (not NO PLAY)
        - model_pref/model_dir point to correct selection
        - edge_class not MARKET_ALIGNED
        
        Expected: Passes through unchanged
        """
        simulation = {
            "event_id": "valid_event",
            "team_a": "Team A",
            "team_b": "Team B",
            "sharp_analysis": {
                "spread": {
                    "has_edge": True,
                    "sharp_team": "Team A",
                    "sharp_selection": "PLAY",
                    "sharp_side": "Team A +1.5",
                    "recommended_bet": "PLAY",
                }
            },
            "market_views": {
                "spread": {
                    "model_preference_selection_id": "selection_1",
                    "model_direction_selection_id": "selection_1",
                    "edge_class": "SHARP_SIDE",
                    "ui_render_mode": "FULL",
                }
            },
        }

        _normalize_spread_contract(simulation)

        # Should remain unchanged
        assert simulation["sharp_analysis"]["spread"]["has_edge"] is True
        assert simulation["sharp_analysis"]["spread"]["sharp_team"] == "Team A"
        assert (
            simulation["market_views"]["spread"]["edge_class"] == "SHARP_SIDE"
        )

    def test_no_edge_state_passes_through(self):
        """
        VALID STATE: no edge detected
        
        - has_edge=False
        - sharp_selection=NO PLAY
        - model_pref=NO_EDGE
        
        Expected: No changes needed, passes through
        """
        simulation = {
            "event_id": "no_edge_event",
            "team_a": "Team A",
            "team_b": "Team B",
            "sharp_analysis": {
                "spread": {
                    "has_edge": False,
                    "sharp_team": None,
                    "sharp_selection": "NO PLAY",
                }
            },
            "market_views": {
                "spread": {
                    "model_preference_selection_id": "NO_EDGE",
                    "model_direction_selection_id": "NO_EDGE",
                    "edge_class": "NO_EDGE",
                }
            },
        }

        _normalize_spread_contract(simulation)

        # Should remain unchanged
        assert simulation["sharp_analysis"]["spread"]["has_edge"] is False
        assert simulation["sharp_analysis"]["spread"]["sharp_selection"] == "NO PLAY"
        assert (
            simulation["market_views"]["spread"]["model_preference_selection_id"]
            == "NO_EDGE"
        )

    def test_enforce_canonical_contract_calls_spread_normalizer(self):
        """
        INTEGRATION: Verify enforce_canonical_contract calls _normalize_spread_contract
        
        This ensures the fix is integrated into the main response pipeline.
        """
        # Create a record with the bug pattern
        simulation = {
            "event_id": "integration_test",
            "team_a": "Team A",
            "team_b": "Team B",
            "sharp_analysis": {
                "spread": {
                    "has_edge": True,
                    "sharp_team": None,  # ← Missing binding
                    "sharp_selection": "PLAY",
                }
            },
            "market_views": {
                "spread": {
                    "model_preference_selection_id": "team_a_pref",
                    "edge_class": "MARKET_ALIGNED",
                }
            },
        }

        # Call the main enforcer
        result = enforce_canonical_contract(simulation)

        # Verify the spread contract was normalized
        assert (
            result["market_views"]["spread"]["edge_class"] == "INVALID"
        ), "enforce_canonical_contract must apply spread normalization"
        assert (
            "SPREAD_CANONICAL_BINDING_MISSING"
            in result["integrity_warnings"]
        ), "Must record the integrity warning"

    def test_same_sign_rendering_impossible_after_fix(self):
        """
        BEHAVIORAL: Ensure the fix prevents the exact bug:
        Two same-signed values rendered for opposing teams.
        
        Even if data somehow reaches the UI layer with this bug,
        the canonical contract enforcer should have blocked it before serialization.
        """
        # This is the exact scenario from the user's report:
        # Market: "Tampa Bay Rays +1.5"
        # Model: "Los Angeles Dodgers +1.5"
        # (same sign, opposite teams = IMPOSSIBLE after fix)

        buggy_simulation = {
            "event_id": "a75cee44d2cbdcedb356612df99cd692",
            "team_a": "Los Angeles Dodgers",
            "team_b": "Tampa Bay Rays",
            "sharp_analysis": {
                "spread": {
                    "has_edge": True,
                    "sharp_team": None,
                    "sharp_selection": "PLAY",
                    "market_spread_home": 1.5,  # LA +1.5
                }
            },
            "market_views": {
                "spread": {
                    "model_preference_selection_id": "dodgers_pref",
                    "edge_class": "MARKET_ALIGNED",
                }
            },
        }

        # Apply the fix
        _normalize_spread_contract(buggy_simulation)

        # Extract what the UI would render
        spread_view = buggy_simulation["market_views"]["spread"]
        spread_analysis = buggy_simulation["sharp_analysis"]["spread"]

        # If edge_class is INVALID, UI should not render market preference
        # (it's blocked)
        if spread_view["edge_class"] == "INVALID":
            # Verify the blocking flags are set
            assert (
                spread_view["ui_render_mode"] == "SAFE"
            ), "Blocked state must use SAFE render mode"
            assert (
                spread_view["model_preference_selection_id"] == "NO_EDGE"
            ), "Preference must be cleared"
            assert (
                spread_analysis["sharp_selection"] == "NO PLAY"
            ), "Selection must be blocked"

            # In this state, the UI cannot render same-signed values
            # because the model_preference_selection_id is "NO_EDGE"
            # which means "do not render model preference"
            render_is_safe = True
        else:
            # If not blocked, binding must be complete
            assert (
                spread_analysis["sharp_team"] is not None
            ), "has_edge=True requires sharp_team"
            assert (
                spread_view["model_preference_selection_id"] != "NO_EDGE"
            ), "Valid binding requires valid preference"
            render_is_safe = True

        assert render_is_safe, "After fix, same-sign rendering impossible"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
