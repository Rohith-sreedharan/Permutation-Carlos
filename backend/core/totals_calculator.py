"""
core/totals_calculator.py
Canonical totals (over/under) logic with half-point integer arithmetic.

vFinal.1 Multi-Sport Patch Implementation
"""
from .sport_config import get_sport_config, MarketSettlement
from .spread_calculator import to_half_points, from_half_points, is_half_point_line


def check_totals_outcome(
    total_points: int,
    vegas_total_hp: int
) -> dict:
    """
    Check totals (over/under) outcome.
    
    Args:
        total_points: home_score + away_score
        vegas_total_hp: total line in half-points (e.g., 215.5 => 431)
    
    Returns:
        {'over_hits': bool, 'under_hits': bool, 'push': bool}
    """
    total_points_hp = total_points * 2
    
    if is_half_point_line(vegas_total_hp):
        # Half-point total: push impossible
        if total_points_hp > vegas_total_hp:
            return {'over_hits': True, 'under_hits': False, 'push': False}
        else:
            return {'over_hits': False, 'under_hits': True, 'push': False}
    else:
        # Integer total: push possible
        if total_points_hp == vegas_total_hp:
            return {'over_hits': False, 'under_hits': False, 'push': True}
        elif total_points_hp > vegas_total_hp:
            return {'over_hits': True, 'under_hits': False, 'push': False}
        else:
            return {'over_hits': False, 'under_hits': True, 'push': False}


class TotalsCalculator:
    """Totals calculator with multi-sport support."""
    
    def validate_totals_market(
        self,
        sport_code: str,
        market_settlement: MarketSettlement
    ) -> None:
        """
        Validate totals market configuration.
        Totals are typically FULL_GAME but can be REGULATION for NHL.
        """
        config = get_sport_config(sport_code)
        
        if market_settlement == MarketSettlement.REGULATION:
            if sport_code not in ['NHL', 'NFL']:
                raise ValueError(
                    f"{sport_code} does not support REGULATION totals. "
                    f"Use FULL_GAME settlement."
                )
    
    def _check_outcome(self, total_points: int, vegas_total_hp: int) -> dict:
        """Wrapper for canonical check_totals_outcome function."""
        return check_totals_outcome(total_points, vegas_total_hp)


# ============================================================================
# VERIFICATION TESTS (MUST PASS)
# ============================================================================

if __name__ == "__main__":
    # Test: Over hits
    result = check_totals_outcome(220, to_half_points(215.5))
    assert result['over_hits'] and not result['under_hits'] and not result['push'], \
        f"Test failed: {result}"
    
    # Test: Under hits
    result = check_totals_outcome(210, to_half_points(215.5))
    assert not result['over_hits'] and result['under_hits'] and not result['push'], \
        f"Test failed: {result}"
    
    # Test: Push on integer line
    result = check_totals_outcome(216, to_half_points(216.0))
    assert not result['over_hits'] and not result['under_hits'] and result['push'], \
        f"Test failed: {result}"
    
    # Test: No push on half-point line
    result = check_totals_outcome(216, to_half_points(215.5))
    assert result['over_hits'] and not result['push'], \
        f"Test failed: {result}"
    
    print("✓ All totals calculator verification tests passed")
