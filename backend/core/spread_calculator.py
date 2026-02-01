"""
core/spread_calculator.py
Canonical spread cover logic with half-point integer arithmetic.

vFinal.1 Multi-Sport Patch Implementation
"""
from typing import Dict
from .sport_config import get_sport_config, MarketSettlement


# ============================================================================
# HALF-POINT INTEGER ARITHMETIC (SAFE)
# ============================================================================

def to_half_points(line: float) -> int:
    """Convert decimal line to half-point integer."""
    return int(line * 2)


def from_half_points(hp: int) -> float:
    """Convert half-point integer to decimal line."""
    return hp / 2.0


def is_half_point_line(hp: int) -> bool:
    """Check if line is half-point (push impossible)."""
    return hp % 2 != 0  # Odd = half-point


# ============================================================================
# SPREAD COVER LOGIC (PROVEN CORRECT)
# ============================================================================

def check_spread_cover(margin: int, vegas_spread_hp: int) -> dict:
    """
    CANONICAL SPREAD COVER LOGIC
    
    Args:
        margin: home_score - away_score (integer)
        vegas_spread_hp: spread in half-point units (e.g., -7.5 => -15)
    
    Returns:
        {'home_covers': bool, 'away_covers': bool, 'push': bool}
    
    Logic:
        home_result = (margin * 2) + vegas_spread_hp
        
        If half-point line (vegas_spread_hp is odd):
            Push is IMPOSSIBLE (never occurs)
        If integer line (vegas_spread_hp is even):
            Push occurs when home_result == 0 exactly
    
    This uses integer arithmetic ONLY - no float tolerance needed.
    """
    # Convert margin to half-points for comparison
    margin_hp = margin * 2
    home_result = margin_hp + vegas_spread_hp
    
    # Check if line allows pushes
    if is_half_point_line(vegas_spread_hp):
        # Half-point line: push impossible
        if home_result > 0:
            return {'home_covers': True, 'away_covers': False, 'push': False}
        else:
            return {'home_covers': False, 'away_covers': True, 'push': False}
    else:
        # Integer line: push possible
        if home_result == 0:
            return {'home_covers': False, 'away_covers': False, 'push': True}
        elif home_result > 0:
            return {'home_covers': True, 'away_covers': False, 'push': False}
        else:
            return {'home_covers': False, 'away_covers': True, 'push': False}


class SpreadCalculator:
    """Spread calculator with multi-sport support."""
    
    def validate_spread_market(
        self,
        sport_code: str,
        market_settlement: MarketSettlement
    ) -> None:
        """
        Validate spread market configuration.
        Spreads are typically FULL_GAME but can be REGULATION for NHL.
        """
        config = get_sport_config(sport_code)
        
        if market_settlement == MarketSettlement.REGULATION:
            if sport_code not in ['NHL', 'NFL']:
                raise ValueError(
                    f"{sport_code} does not support REGULATION spreads. "
                    f"Use FULL_GAME settlement."
                )
    
    def _check_cover(self, margin: int, vegas_spread_hp: int) -> dict:
        """Wrapper for canonical check_spread_cover function."""
        return check_spread_cover(margin, vegas_spread_hp)
    
    def _compute_sharp_side(
        self,
        home_ev: float,
        away_ev: float,
        home_probability: float,
        away_probability: float,
        edge_gap_points: float = 0.0
    ) -> dict:
        """
        Determine sharp side and classification.
        
        Selection Logic (in priority order):
        1. Choose max(EV) if odds available
        2. If odds missing (max_ev = 0): use probability + edge_gap fallback
        3. If EVs within tolerance: choose higher probability (tie-breaker)
        
        Classification (based on max EV or fallback):
        EDGE: EV >= 3.0% OR (edge_gap >= 3.0 AND win_prob >= 55%)
        LEAN: 0.5% <= EV < 3.0% OR (edge_gap >= 2.0 AND win_prob >= 52%)
        NEUTRAL: 0% <= EV < 0.5%
        NO_PLAY: EV < 0%
        """
        EDGE_THRESHOLD = 3.0
        LEAN_THRESHOLD = 0.5
        EV_TIE_TOLERANCE = 0.1
        
        # Fallback thresholds when odds missing
        EDGE_GAP_MIN = 3.0
        LEAN_GAP_MIN = 2.0
        EDGE_PROB_MIN = 55.0
        LEAN_PROB_MIN = 52.0
        
        ev_diff = abs(home_ev - away_ev)
        
        # Check if odds are missing (both EVs are 0)
        odds_missing = (home_ev == 0.0 and away_ev == 0.0)
        
        if odds_missing:
            # CHANGE 1: Fallback classification using win_prob + edge_gap_points
            sharp_side = 'home' if home_probability >= away_probability else 'away'
            max_prob = max(home_probability, away_probability)
            selection_method = 'gap_probability_fallback'
            
            # Classify based on gap + probability
            if edge_gap_points >= EDGE_GAP_MIN and max_prob >= EDGE_PROB_MIN:
                classification = 'EDGE'
                max_ev = 0.0  # No EV available, but classified as EDGE
            elif edge_gap_points >= LEAN_GAP_MIN and max_prob >= LEAN_PROB_MIN:
                classification = 'LEAN'
                max_ev = 0.0
            else:
                classification = 'NEUTRAL'
                max_ev = 0.0
        elif ev_diff < EV_TIE_TOLERANCE:
            # EV tie: use probability as tie-breaker
            sharp_side = 'home' if home_probability >= away_probability else 'away'
            max_ev = max(home_ev, away_ev)
            selection_method = 'ev_tie_probability'
            
            # Determine classification based on EV
            if max_ev >= EDGE_THRESHOLD:
                classification = 'EDGE'
            elif max_ev >= LEAN_THRESHOLD:
                classification = 'LEAN'
            elif max_ev >= 0:
                classification = 'NEUTRAL'
            else:
                classification = 'NO_PLAY'
        else:
            # Clear EV winner
            sharp_side = 'home' if home_ev > away_ev else 'away'
            max_ev = max(home_ev, away_ev)
            selection_method = 'ev'
            
            # Determine classification
            if max_ev >= EDGE_THRESHOLD:
                classification = 'EDGE'
            elif max_ev >= LEAN_THRESHOLD:
                classification = 'LEAN'
            elif max_ev >= 0:
                classification = 'NEUTRAL'
            else:
                classification = 'NO_PLAY'
        
        # CHANGE 2: Only null sharp_side for NO_PLAY, not NEUTRAL
        if classification == 'NO_PLAY':
            sharp_side = None
        
        return {
            'sharp_side': sharp_side,
            'classification': classification,
            'selection_method': selection_method,
            'max_ev': round(max_ev, 2)
        }


# ============================================================================
# VERIFICATION TESTS (MUST PASS)
# ============================================================================

if __name__ == "__main__":
    # Test 1: Home favorite covers
    result = check_spread_cover(8, to_half_points(-7.5))
    assert result['home_covers'] and not result['away_covers'] and not result['push'], \
        f"Test 1 failed: {result}"
    
    # Test 2: Home favorite doesn't cover
    result = check_spread_cover(7, to_half_points(-7.5))
    assert not result['home_covers'] and result['away_covers'] and not result['push'], \
        f"Test 2 failed: {result}"
    
    # Test 3: Home dog covers
    result = check_spread_cover(-7, to_half_points(7.5))
    assert result['home_covers'] and not result['away_covers'] and not result['push'], \
        f"Test 3 failed: {result}"
    
    # Test 4: Away favorite covers
    result = check_spread_cover(-8, to_half_points(7.5))
    assert result['away_covers'] and not result['home_covers'] and not result['push'], \
        f"Test 4 failed: {result}"
    
    # Test 5: Integer line push
    result = check_spread_cover(7, to_half_points(-7.0))
    assert result['push'] and not result['home_covers'] and not result['away_covers'], \
        f"Test 5 failed: {result}"
    
    print("✓ All spread calculator verification tests passed")
