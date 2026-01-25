"""
core/moneyline_calculator.py
Multi-sport moneyline grading with settlement modes.

vFinal.1 Multi-Sport Patch Implementation
"""
from .sport_config import get_sport_config, MarketSettlement, MarketType


def check_moneyline_winner(
    home_score: int,
    away_score: int,
    sport_code: str,
    market_settlement: MarketSettlement = MarketSettlement.FULL_GAME
) -> str:
    """
    Determine moneyline winner with sport-specific rules.
    
    Sport-Specific Behavior:
    
    NBA (FULL_GAME):
    - Ties IMPOSSIBLE (unlimited OT)
    - Tie in simulation = SIMULATION BUG (raise ValueError)
    
    NCAAB/NCAAF (FULL_GAME):
    - Ties IMPOSSIBLE (unlimited OT)
    - Tie in simulation = SIMULATION BUG
    
    NFL (FULL_GAME):
    - Ties POSSIBLE in regular season (10-min OT, then tie)
    - Tie result = 'TIE' (treated as PUSH on 2-way ML)
    
    NHL (FULL_GAME):
    - Ties IMPOSSIBLE (5-min OT + shootout)
    - Tie in simulation = SIMULATION BUG
    
    NHL (REGULATION):
    - Ties POSSIBLE (60-minute regulation only)
    - Tie result = 'TIE'
    - Used for regulation moneyline markets (3-way or 2-way with push)
    
    MLB (FULL_GAME):
    - Ties IMPOSSIBLE (unlimited extra innings)
    - Tie in simulation = SIMULATION BUG
    
    Args:
        home_score: Final home score (includes OT if FULL_GAME)
        away_score: Final away score
        sport_code: 'NBA' | 'NFL' | 'NHL' | 'NCAAB' | 'NCAAF' | 'MLB'
        market_settlement: FULL_GAME (default) or REGULATION
    
    Returns:
        'HOME' | 'AWAY' | 'TIE'
    
    Raises:
        ValueError: If tie occurs when sport/settlement prohibits it
    """
    config = get_sport_config(sport_code)
    
    # Determine if tie is possible
    if market_settlement == MarketSettlement.FULL_GAME:
        tie_possible = config.can_tie_final
    else:  # REGULATION
        tie_possible = config.can_tie_regulation
    
    # Check result
    if home_score > away_score:
        return 'HOME'
    elif away_score > home_score:
        return 'AWAY'
    else:
        # Tie
        if not tie_possible:
            raise ValueError(
                f"{sport_code} simulation produced tie with {market_settlement.value} settlement. "
                f"This is a SIMULATION BUG. Sport config: can_tie_final={config.can_tie_final}, "
                f"can_tie_regulation={config.can_tie_regulation}. "
                f"Scores: {home_score}-{away_score}"
            )
        return 'TIE'


def validate_moneyline_market(
    sport_code: str,
    market_type: MarketType,
    market_settlement: MarketSettlement
) -> None:
    """
    Validate moneyline market configuration.
    Called before simulation to catch config errors early.
    """
    from .sport_config import validate_market_contract
    validate_market_contract(sport_code, market_type, market_settlement)


def get_moneyline_market_type(
    sport_code: str,
    market_settlement: MarketSettlement = MarketSettlement.FULL_GAME
) -> MarketType:
    """
    Determine moneyline market type.
    
    Returns MONEYLINE_2WAY or MONEYLINE_3WAY based on sport + settlement.
    
    Rules:
    - If sport can tie in chosen settlement → 2-way (tie = push) OR 3-way (tie = loss)
    - If sport cannot tie → always 2-way
    
    Default: All sports use 2-way ML (tie = push when possible)
    3-way ML reserved for soccer/draw markets (not implemented in v2)
    """
    config = get_sport_config(sport_code)
    
    if market_settlement == MarketSettlement.FULL_GAME:
        return config.default_ml_type
    else:
        # REGULATION markets can use 2-way or 3-way
        return config.default_ml_type


class MoneylineCalculator:
    """Moneyline calculator with multi-sport support."""
    
    def check_winner(
        self,
        home_score: int,
        away_score: int,
        sport_code: str,
        market_settlement: MarketSettlement = MarketSettlement.FULL_GAME
    ) -> str:
        """Wrapper for canonical check_moneyline_winner function."""
        return check_moneyline_winner(home_score, away_score, sport_code, market_settlement)
    
    def validate_market(
        self,
        sport_code: str,
        market_type: MarketType,
        market_settlement: MarketSettlement
    ) -> None:
        """Validate moneyline market configuration."""
        validate_moneyline_market(sport_code, market_type, market_settlement)


# ============================================================================
# VERIFICATION TESTS (MUST PASS)
# ============================================================================

if __name__ == "__main__":
    # Test: NBA tie raises error (FULL_GAME)
    try:
        result = check_moneyline_winner(100, 100, 'NBA', MarketSettlement.FULL_GAME)
        assert False, "NBA FULL_GAME tie should raise ValueError"
    except ValueError as e:
        assert "SIMULATION BUG" in str(e), f"Wrong error message: {e}"
    
    # Test: NFL tie is valid (FULL_GAME)
    result = check_moneyline_winner(24, 24, 'NFL', MarketSettlement.FULL_GAME)
    assert result == 'TIE', f"Expected TIE, got {result}"
    
    # Test: NHL FULL_GAME tie raises error (OT/SO decides)
    try:
        result = check_moneyline_winner(3, 3, 'NHL', MarketSettlement.FULL_GAME)
        assert False, "NHL FULL_GAME tie should raise ValueError"
    except ValueError as e:
        assert "SIMULATION BUG" in str(e), f"Wrong error message: {e}"
    
    # Test: NHL REGULATION tie is valid
    result = check_moneyline_winner(2, 2, 'NHL', MarketSettlement.REGULATION)
    assert result == 'TIE', f"Expected TIE, got {result}"
    
    # Test: MLB tie raises error
    try:
        result = check_moneyline_winner(5, 5, 'MLB', MarketSettlement.FULL_GAME)
        assert False, "MLB FULL_GAME tie should raise ValueError"
    except ValueError as e:
        assert "SIMULATION BUG" in str(e), f"Wrong error message: {e}"
    
    print("✓ All moneyline calculator verification tests passed")
