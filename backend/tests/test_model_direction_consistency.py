"""
Model Direction Consistency — Stress Test Suite
===============================================

Version: 1.0
Generated: 2026-02-02

These tests are DETERMINISTIC and SPORT-UNIVERSAL.
They validate sign handling, side matching, and copy correctness.

A failure means the implementation is WRONG.

🚨 MUST PASS BEFORE DEPLOY
"""

import pytest
from backend.core.model_direction_canonical import (
    calculate_model_direction,
    build_sides,
    choose_preference,
    compute_edge_pts,
    assert_direction_matches_preference,
    validate_text_copy,
    DirectionLabel,
    format_display_line
)


class TestEdgePointsCalculation:
    """Test canonical edge_pts formula"""
    
    def test_underdog_generous_utah_example(self):
        """
        Test Input: Utah +10.5 market, Utah +6.4 fair
        Expected: edge_pts = +4.1 (good for Utah +10.5)
        """
        market_line = 10.5
        fair_line = 6.4
        edge = compute_edge_pts(market_line, fair_line)
        
        assert abs(edge - 4.1) < 0.01, f"Expected +4.1, got {edge}"
    
    def test_favorite_discounted(self):
        """
        Test Input: A:-4.5 market, A:-7.0 fair
        Expected: edge_pts = +2.5 (good for A -4.5)
        """
        market_line = -4.5
        fair_line = -7.0
        edge = compute_edge_pts(market_line, fair_line)
        
        assert abs(edge - 2.5) < 0.01, f"Expected +2.5, got {edge}"
    
    def test_underdog_overpriced(self):
        """
        Test Input: A:+10.5 market, A:+12.0 fair
        Expected: edge_pts = -1.5 (bad for A +10.5)
        """
        market_line = 10.5
        fair_line = 12.0
        edge = compute_edge_pts(market_line, fair_line)
        
        assert abs(edge - (-1.5)) < 0.01, f"Expected -1.5, got {edge}"
    
    def test_exact_tie(self):
        """
        Test Input: A:+5.0 market, A:+5.0 fair
        Expected: edge_pts = 0.0
        """
        market_line = 5.0
        fair_line = 5.0
        edge = compute_edge_pts(market_line, fair_line)
        
        assert abs(edge) < 0.01, f"Expected 0.0, got {edge}"


class TestSideNegation:
    """Test that opposite side is always negation"""
    
    def test_opp_side_auto_negation(self):
        """
        Test Input: A:+3.0 market, A:+3.4 fair
        Expected: B -3.0 market, B -3.4 fair
        Expected: B has edge_pts = +0.4
        """
        team_a = "Team A"
        team_b = "Team B"
        
        sides = build_sides(
            team_a_id=team_a,
            team_a_market_line=3.0,
            team_a_fair_line=3.4,
            team_b_id=team_b
        )
        
        # Check Team A
        assert sides[0].team_id == team_a
        assert abs(sides[0].market_line - 3.0) < 0.01
        assert abs(sides[0].fair_line - 3.4) < 0.01
        
        # Check Team B (must be negation)
        assert sides[1].team_id == team_b
        assert abs(sides[1].market_line - (-3.0)) < 0.01, "B market_line must be -3.0"
        assert abs(sides[1].fair_line - (-3.4)) < 0.01, "B fair_line must be -3.4"
        
        # Check B has better edge
        edge_b = compute_edge_pts(sides[1].market_line, sides[1].fair_line)
        assert abs(edge_b - 0.4) < 0.01, f"Expected B edge = +0.4, got {edge_b}"


class TestPreferenceSelection:
    """Test that preference always selects max edge_pts"""
    
    def test_underdog_generous_selects_dog(self):
        """
        Utah +10.5 market, +6.4 fair → edge +4.1
        Toronto -10.5 market, -6.4 fair → edge -4.1
        Expected: Select Utah +10.5 (TAKE_DOG)
        """
        sides = build_sides(
            team_a_id="Utah Jazz",
            team_a_market_line=10.5,
            team_a_fair_line=6.4,
            team_b_id="Toronto Raptors"
        )
        
        result = choose_preference(sides)
        
        assert result.preferred_team_id == "Utah Jazz"
        assert abs(result.preferred_market_line - 10.5) < 0.01
        assert abs(result.edge_pts - 4.1) < 0.01
        assert result.direction_label == DirectionLabel.TAKE_DOG
    
    def test_favorite_discounted_selects_fav(self):
        """
        Team A -4.5 market, -7.0 fair → edge +2.5
        Team B +4.5 market, +7.0 fair → edge -2.5
        Expected: Select Team A -4.5 (LAY_FAV)
        """
        sides = build_sides(
            team_a_id="Team A",
            team_a_market_line=-4.5,
            team_a_fair_line=-7.0,
            team_b_id="Team B"
        )
        
        result = choose_preference(sides)
        
        assert result.preferred_team_id == "Team A"
        assert abs(result.preferred_market_line - (-4.5)) < 0.01
        assert abs(result.edge_pts - 2.5) < 0.01
        assert result.direction_label == DirectionLabel.LAY_FAV
    
    def test_exact_tie_consistent(self):
        """
        A:+5.0 market, +5.0 fair → edge 0.0
        B:-5.0 market, -5.0 fair → edge 0.0
        Expected: Either side OK, but MUST be consistent
        """
        sides = build_sides(
            team_a_id="Team A",
            team_a_market_line=5.0,
            team_a_fair_line=5.0,
            team_b_id="Team B"
        )
        
        result = choose_preference(sides)
        
        # Edge must be 0.0 for both
        assert abs(result.edge_pts) < 0.01
        
        # Must pick one side consistently (first one in implementation)
        assert result.preferred_team_id in ["Team A", "Team B"]


class TestIntegrationFullFlow:
    """Test full calculate_model_direction function"""
    
    def test_utah_example_full(self):
        """
        Full integration test: Utah Jazz underdog example
        
        Game: Toronto Raptors vs Utah Jazz
        Market: Toronto -10.5, Utah +10.5
        Fair: Toronto -6.4, Utah +6.4
        
        Expected:
        - Preferred: Utah Jazz +10.5
        - Edge: +4.1 pts
        - Label: TAKE_DOG
        """
        result = calculate_model_direction(
            home_team="Toronto Raptors",
            away_team="Utah Jazz",
            market_spread_home=-10.5,
            fair_spread_home=-6.4
        )
        
        assert result.preferred_team_id == "Utah Jazz"
        assert abs(result.preferred_market_line - 10.5) < 0.01
        assert abs(result.preferred_fair_line - 6.4) < 0.01
        assert abs(result.edge_pts - 4.1) < 0.01
        assert result.direction_label == DirectionLabel.TAKE_DOG
        assert "Utah Jazz" in result.direction_text
        assert "Take the points" in result.direction_text
    
    def test_favorite_example_full(self):
        """
        Full integration test: Favorite undervalued
        
        Game: Lakers vs Celtics
        Market: Lakers -3.0, Celtics +3.0
        Fair: Lakers -5.5, Celtics +5.5
        
        Expected:
        - Preferred: Lakers -3.0
        - Edge: +2.5 pts
        - Label: LAY_FAV
        """
        result = calculate_model_direction(
            home_team="Lakers",
            away_team="Celtics",
            market_spread_home=-3.0,
            fair_spread_home=-5.5
        )
        
        assert result.preferred_team_id == "Lakers"
        assert abs(result.preferred_market_line - (-3.0)) < 0.01
        assert abs(result.preferred_fair_line - (-5.5)) < 0.01
        assert abs(result.edge_pts - 2.5) < 0.01
        assert result.direction_label == DirectionLabel.LAY_FAV
        assert "Lakers" in result.direction_text
        assert "Lay the points" in result.direction_text
    
    def test_away_favorite_example(self):
        """
        Full integration test: Away team favored
        
        Game: Warriors (home) vs Bucks (away)
        Market: Warriors +2.5, Bucks -2.5
        Fair: Warriors +4.0, Bucks -4.0
        
        Expected:
        - Preferred: Bucks -2.5
        - Edge: +1.5 pts
        - Label: LAY_FAV
        """
        result = calculate_model_direction(
            home_team="Warriors",
            away_team="Bucks",
            market_spread_home=2.5,
            fair_spread_home=4.0
        )
        
        assert result.preferred_team_id == "Bucks"
        assert abs(result.preferred_market_line - (-2.5)) < 0.01
        assert abs(result.edge_pts - 1.5) < 0.01
        assert result.direction_label == DirectionLabel.LAY_FAV


class TestUIAssertion:
    """Test that Model Direction MUST match Model Preference"""
    
    def test_direction_matches_preference_valid(self):
        """Test assertion passes when direction matches preference"""
        result = calculate_model_direction(
            home_team="Team A",
            away_team="Team B",
            market_spread_home=-5.0,
            fair_spread_home=-7.0
        )
        
        # Should not raise
        assert_direction_matches_preference(
            direction=result,
            preference_team_id=result.preferred_team_id,
            preference_market_line=result.preferred_market_line
        )
    
    def test_direction_mismatch_team_fails(self):
        """Test assertion fails when team doesn't match"""
        result = calculate_model_direction(
            home_team="Team A",
            away_team="Team B",
            market_spread_home=-5.0,
            fair_spread_home=-7.0
        )
        
        with pytest.raises(AssertionError, match="Direction team .* != Preference team"):
            assert_direction_matches_preference(
                direction=result,
                preference_team_id="Wrong Team",
                preference_market_line=result.preferred_market_line
            )
    
    def test_direction_mismatch_line_fails(self):
        """Test assertion fails when line doesn't match"""
        result = calculate_model_direction(
            home_team="Team A",
            away_team="Team B",
            market_spread_home=-5.0,
            fair_spread_home=-7.0
        )
        
        with pytest.raises(AssertionError, match="Direction line .* != Preference line"):
            assert_direction_matches_preference(
                direction=result,
                preference_team_id=result.preferred_team_id,
                preference_market_line=999.0  # Wrong line
            )


class TestTextCopyValidation:
    """Test that text copy cannot contradict direction label"""
    
    def test_take_dog_cannot_say_fade_dog(self):
        """TAKE_DOG label cannot use 'fade the dog' text"""
        result = calculate_model_direction(
            home_team="Team A",
            away_team="Team B",
            market_spread_home=-10.0,
            fair_spread_home=-6.0
        )
        
        # result should be TAKE_DOG (Team B +10.0)
        assert result.direction_label == DirectionLabel.TAKE_DOG
        
        # Validate against invalid text
        is_valid, error = validate_text_copy(result, "Fade the dog - underdog overvalued")
        assert not is_valid
        assert error and "fade the dog" in error.lower()
    
    def test_lay_fav_cannot_say_take_dog(self):
        """LAY_FAV label cannot use 'take the dog' text"""
        result = calculate_model_direction(
            home_team="Team A",
            away_team="Team B",
            market_spread_home=-3.0,
            fair_spread_home=-5.5
        )
        
        # result should be LAY_FAV (Team A -3.0)
        assert result.direction_label == DirectionLabel.LAY_FAV
        
        # Validate against invalid text
        is_valid, error = validate_text_copy(result, "Take the dog here - good value")
        assert not is_valid
        assert error and ("take the dog" in error.lower() or "take the points" in error.lower())
    
    def test_valid_copy_passes(self):
        """Valid copy should pass validation"""
        result = calculate_model_direction(
            home_team="Team A",
            away_team="Team B",
            market_spread_home=-10.0,
            fair_spread_home=-6.0
        )
        
        # Should be TAKE_DOG
        assert result.direction_label == DirectionLabel.TAKE_DOG
        
        # Validate against valid text
        is_valid, error = validate_text_copy(result, "Take the points - market giving extra value")
        assert is_valid
        assert error is None


class TestDisplayFormatting:
    """Test display string formatting"""
    
    def test_format_underdog_line(self):
        """Underdog line should format with +"""
        display = format_display_line("Utah Jazz", 10.5)
        assert display == "Utah Jazz +10.5"
    
    def test_format_favorite_line(self):
        """Favorite line should format with -"""
        display = format_display_line("Toronto Raptors", -10.5)
        assert display == "Toronto Raptors -10.5"
    
    def test_format_pickem_line(self):
        """Pick'em (0) should format with +"""
        display = format_display_line("Team A", 0.0)
        assert display == "Team A +0.0"


# ==============================================================================
# STRESS TEST MATRIX (from spec)
# ==============================================================================

class TestStressMatrix:
    """
    Deterministic stress tests from spec (Table in Section 7)
    """
    
    @pytest.mark.parametrize("team_a_market,team_a_fair,expected_team,expected_edge", [
        (10.5, 6.4, "Team A", 4.1),      # Underdog generous (A is underdog, edge +4.1)
        (-4.5, -7.0, "Team A", 2.5),     # Favorite discounted (A is favorite, edge +2.5)
        (3.0, 3.4, "Team B", 0.4),       # Opp side auto-negation check (B has edge +0.4)
        (5.0, 5.0, None, 0.0),           # Exact tie (either side, edge 0.0)
    ])
    def test_stress_matrix(self, team_a_market, team_a_fair, expected_team, expected_edge):
        """
        Stress test matrix from spec Section 7
        
        Note: For tie case (expected_team=None), we accept either team as long as edge=0.0
        """
        result = calculate_model_direction(
            home_team="Team A",
            away_team="Team B",
            market_spread_home=team_a_market,
            fair_spread_home=team_a_fair
        )
        
        # Check edge
        assert abs(result.edge_pts - expected_edge) < 0.01, \
            f"Expected edge={expected_edge}, got {result.edge_pts}"
        
        # Check team (skip for tie case)
        if expected_team is not None:
            assert result.preferred_team_id == expected_team, \
                f"Expected team={expected_team}, got {result.preferred_team_id}"
        
        # Verify label matches sign
        if result.preferred_market_line > 0:
            assert result.direction_label == DirectionLabel.TAKE_DOG
        elif result.preferred_market_line < 0:
            assert result.direction_label == DirectionLabel.LAY_FAV


# ==============================================================================
# RUN TESTS
# ==============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
