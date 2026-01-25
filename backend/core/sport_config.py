"""
core/sport_config.py
Sport-specific configuration contract.
This is the SINGLE SOURCE OF TRUTH for sport rules.

vFinal.1 Multi-Sport Patch Implementation
"""
from enum import Enum
from typing import Literal


class MarketSettlement(str, Enum):
    """How market is settled (affects tie probability)."""
    FULL_GAME = "FULL_GAME"  # Includes OT/SO (default for most)
    REGULATION = "REGULATION"  # 60 min for NHL, 4 quarters for others


class MarketType(str, Enum):
    """Market type enum."""
    SPREAD = "SPREAD"
    TOTAL = "TOTAL"
    MONEYLINE_2WAY = "MONEYLINE_2WAY"
    MONEYLINE_3WAY = "MONEYLINE_3WAY"


class SportConfig:
    """
    Sport-specific configuration.
    
    CRITICAL RULES:
    1. can_tie_regulation: Can the sport tie after regulation time?
    2. can_tie_final: Can the sport tie in final result (after all OT)?
    3. default_ml_settlement: Default moneyline settlement for this sport
    4. default_ml_type: 2-way or 3-way moneyline
    """
    
    def __init__(
        self,
        sport_code: str,
        can_tie_regulation: bool,
        can_tie_final: bool,
        default_ml_settlement: MarketSettlement,
        default_ml_type: MarketType,
        has_overtime: bool,
        overtime_type: str | None = None
    ):
        self.sport_code = sport_code
        self.can_tie_regulation = can_tie_regulation
        self.can_tie_final = can_tie_final
        self.default_ml_settlement = default_ml_settlement
        self.default_ml_type = default_ml_type
        self.has_overtime = has_overtime
        self.overtime_type = overtime_type


# ============================================================================
# SPORT CONFIGS (CANONICAL)
# ============================================================================

SPORT_CONFIGS = {
    'NBA': SportConfig(
        sport_code='NBA',
        can_tie_regulation=False,  # Cannot tie at end of regulation
        can_tie_final=False,  # Cannot tie in final (unlimited OT)
        default_ml_settlement=MarketSettlement.FULL_GAME,
        default_ml_type=MarketType.MONEYLINE_2WAY,
        has_overtime=True,
        overtime_type='UNLIMITED'  # OT continues until winner
    ),
    
    'NCAAB': SportConfig(
        sport_code='NCAAB',
        can_tie_regulation=False,
        can_tie_final=False,  # Unlimited OT
        default_ml_settlement=MarketSettlement.FULL_GAME,
        default_ml_type=MarketType.MONEYLINE_2WAY,
        has_overtime=True,
        overtime_type='UNLIMITED'
    ),
    
    'NFL': SportConfig(
        sport_code='NFL',
        can_tie_regulation=True,  # Can tie after 4 quarters
        can_tie_final=True,  # Can tie after OT (regular season)
        default_ml_settlement=MarketSettlement.FULL_GAME,
        default_ml_type=MarketType.MONEYLINE_2WAY,
        has_overtime=True,
        overtime_type='LIMITED'  # 10-min OT, then tie
    ),
    
    'NCAAF': SportConfig(
        sport_code='NCAAF',
        can_tie_regulation=False,
        can_tie_final=False,  # Unlimited OT
        default_ml_settlement=MarketSettlement.FULL_GAME,
        default_ml_type=MarketType.MONEYLINE_2WAY,
        has_overtime=True,
        overtime_type='UNLIMITED'
    ),
    
    'NHL': SportConfig(
        sport_code='NHL',
        can_tie_regulation=True,  # Can tie after 60 min
        can_tie_final=False,  # Cannot tie after OT/SO
        default_ml_settlement=MarketSettlement.FULL_GAME,  # CRITICAL
        default_ml_type=MarketType.MONEYLINE_2WAY,
        has_overtime=True,
        overtime_type='OT_THEN_SHOOTOUT'
    ),
    
    'MLB': SportConfig(
        sport_code='MLB',
        can_tie_regulation=False,
        can_tie_final=False,  # Unlimited innings
        default_ml_settlement=MarketSettlement.FULL_GAME,
        default_ml_type=MarketType.MONEYLINE_2WAY,
        has_overtime=True,  # Extra innings
        overtime_type='UNLIMITED'
    ),
}


def get_sport_config(sport_code: str) -> SportConfig:
    """Get sport configuration."""
    if sport_code not in SPORT_CONFIGS:
        raise ValueError(
            f"Unsupported sport: {sport_code}. "
            f"Supported: {list(SPORT_CONFIGS.keys())}"
        )
    return SPORT_CONFIGS[sport_code]


def validate_market_contract(
    sport_code: str,
    market_type: MarketType,
    market_settlement: MarketSettlement
) -> None:
    """
    Validate that market type + settlement are compatible with sport.
    Raises ValueError if contract violated.
    """
    config = get_sport_config(sport_code)
    
    # Rule 1: If market is REGULATION, sport must support ties in regulation
    if market_settlement == MarketSettlement.REGULATION:
        if not config.can_tie_regulation:
            raise ValueError(
                f"{sport_code} does not support REGULATION settlement "
                f"(no ties possible in regulation)"
            )
    
    # Rule 2: MONEYLINE_3WAY only valid for sports that can tie
    if market_type == MarketType.MONEYLINE_3WAY:
        if market_settlement == MarketSettlement.FULL_GAME:
            if not config.can_tie_final:
                raise ValueError(
                    f"{sport_code} cannot use MONEYLINE_3WAY with FULL_GAME "
                    f"(no ties in final result)"
                )
        elif market_settlement == MarketSettlement.REGULATION:
            if not config.can_tie_regulation:
                raise ValueError(
                    f"{sport_code} cannot use MONEYLINE_3WAY with REGULATION "
                    f"(no ties in regulation)"
                )
    
    # Rule 3: Default checks
    if market_type == MarketType.MONEYLINE_2WAY:
        if market_settlement == MarketSettlement.FULL_GAME:
            if config.can_tie_final:
                # Warning: 2-way ML on tie-able sport means ties = push
                pass  # This is valid (NFL regular season)
