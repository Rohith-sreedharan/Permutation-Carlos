"""
NCAAF (NCAA Football) Calibration & Edge Logic

Spread-first sport with potential blowouts.
Compression factor: 0.80 (same as NCAAB)
QB confirmation required.
Weather-sensitive.
"""
from typing import Dict, Optional, Tuple
from dataclasses import dataclass
from .sport_configs import (
    NCAAF_CONFIG, EdgeState, MarketType, DistributionFlag, VolatilityLevel
)


@dataclass
class NCAAFMarketEvaluation:
    """Result of evaluating a specific NCAAF market"""
    market_type: MarketType
    edge_state: EdgeState
    raw_edge: float
    compressed_edge: float
    distribution_flag: DistributionFlag
    volatility: VolatilityLevel
    eligible: bool
    blocking_reason: Optional[str] = None
    
    # NCAAF-specific
    spread_size: Optional[float] = None
    is_large_spread: bool = False
    qb_confirmed: bool = False
    weather_clear: bool = True


def compress_probability(raw_prob: float, compression_factor: float = 0.80) -> float:
    """
    Apply compression to raw simulation win probability
    
    Formula: compressed = 0.5 + (raw - 0.5) * compression_factor
    """
    return 0.5 + (raw_prob - 0.5) * compression_factor


def calculate_spread_edge(
    sim_cover_prob: float,
    spread: float,
    spread_odds: int,
    compression_factor: float = 0.80
) -> Tuple[float, float]:
    """
    Calculate edge for spread market
    
    Args:
        sim_cover_prob: Simulated probability of covering the spread
        spread: Point spread (negative for favorite)
        spread_odds: American odds (typically -110)
    
    Returns: (raw_edge, compressed_edge)
    """
    compressed_prob = compress_probability(sim_cover_prob, compression_factor)
    
    # Calculate implied probability from odds
    if spread_odds < 0:
        implied_prob = abs(spread_odds) / (abs(spread_odds) + 100)
    else:
        implied_prob = 100 / (spread_odds + 100)
    
    raw_edge = sim_cover_prob - implied_prob
    compressed_edge = compressed_prob - implied_prob
    
    return raw_edge, compressed_edge


def calculate_total_edge(
    sim_over_prob: float,
    over_odds: int,
    under_odds: int,
    compression_factor: float = 0.80
) -> Tuple[str, float, float]:
    """
    Calculate edge for totals market
    
    Returns: (side, raw_edge, compressed_edge)
    """
    compressed_over_prob = compress_probability(sim_over_prob, compression_factor)
    compressed_under_prob = 1.0 - compressed_over_prob
    
    # Calculate implied probabilities
    if over_odds < 0:
        over_implied = abs(over_odds) / (abs(over_odds) + 100)
    else:
        over_implied = 100 / (over_odds + 100)
    
    if under_odds < 0:
        under_implied = abs(under_odds) / (abs(under_odds) + 100)
    else:
        under_implied = 100 / (under_odds + 100)
    
    over_edge = compressed_over_prob - over_implied
    under_edge = compressed_under_prob - under_implied
    
    if over_edge > under_edge:
        return "OVER", sim_over_prob - over_implied, over_edge
    else:
        return "UNDER", (1.0 - sim_over_prob) - under_implied, under_edge


def classify_edge_state(
    compressed_edge: float,
    market_type: MarketType,
    is_large_spread: bool = False
) -> EdgeState:
    """
    Classify edge into EDGE/LEAN/NO_PLAY
    
    Large spreads require higher edge threshold
    """
    config = NCAAF_CONFIG
    
    if market_type == MarketType.SPREAD:
        # Large spread requires higher edge
        if is_large_spread:
            required_edge = config.large_spread_edge_requirement or 0.0
            if compressed_edge >= required_edge:
                return EdgeState.EDGE
            else:
                return EdgeState.NO_PLAY
        
        # Normal spread classification
        if compressed_edge >= config.spread_edge_threshold:
            return EdgeState.EDGE
        elif compressed_edge >= config.spread_lean_min:
            return EdgeState.LEAN
        else:
            return EdgeState.NO_PLAY
    
    elif market_type == MarketType.TOTAL:
        if compressed_edge >= config.total_edge_threshold:
            return EdgeState.EDGE
        elif compressed_edge >= config.total_lean_min:
            return EdgeState.LEAN
        else:
            return EdgeState.NO_PLAY
    
    else:
        return EdgeState.NO_PLAY


def check_spread_size_guardrails(spread: float, is_favorite: bool) -> Tuple[bool, bool, Optional[str]]:
    """
    Check if spread falls within acceptable limits
    
    NCAAF allows larger spreads than NFL due to mismatch games
    
    Args:
        spread: Point spread (absolute value)
        is_favorite: True if betting the favorite
    
    Returns: (is_large_spread, eligible, blocking_reason)
    """
    config = NCAAF_CONFIG
    abs_spread = abs(spread)
    
    # Different limits for favorites vs underdogs
    if is_favorite:
        max_spread = config.max_favorite_spread or 0.0  # 21.0
    else:
        max_spread = config.max_dog_spread or 0.0  # 24.0
    
    # Check if spread is too large
    if abs_spread > max_spread:
        return True, False, f"SPREAD_TOO_LARGE_{abs_spread}"
    
    # Flag as large spread if above threshold (14 points)
    is_large_spread = abs_spread > 14.0
    
    return is_large_spread, True, None


def assess_distribution_volatility(
    simulation_results: Dict,
    market_type: MarketType
) -> Tuple[DistributionFlag, VolatilityLevel]:
    """
    Assess simulation distribution stability
    
    NCAAF has moderate volatility
    """
    if market_type == MarketType.SPREAD:
        std = simulation_results.get('cover_prob_std', 0)
    else:
        std = simulation_results.get('total_std', 0)
    
    # Volatility classification
    if std < 0.025:
        volatility = VolatilityLevel.LOW
    elif std < 0.045:
        volatility = VolatilityLevel.MEDIUM
    elif std < 0.065:
        volatility = VolatilityLevel.HIGH
    else:
        volatility = VolatilityLevel.EXTREME
    
    # Distribution flag
    convergence = simulation_results.get('convergence_rate', 1.0)
    
    if volatility in [VolatilityLevel.LOW, VolatilityLevel.MEDIUM] and convergence > 0.94:
        flag = DistributionFlag.STABLE
    elif volatility == VolatilityLevel.EXTREME:
        flag = DistributionFlag.UNSTABLE_EXTREME
    else:
        flag = DistributionFlag.UNSTABLE
    
    return flag, volatility


def check_eligibility_gates(
    compressed_edge: float,
    market_type: MarketType,
    distribution_flag: DistributionFlag,
    qb_confirmed: bool,
    weather_clear: bool,
    spread: Optional[float] = None,
    is_favorite: Optional[bool] = None
) -> Tuple[bool, Optional[str]]:
    """
    Check if market passes all eligibility gates
    
    Returns: (eligible, blocking_reason)
    """
    config = NCAAF_CONFIG
    
    # QB confirmation required
    if not qb_confirmed:
        return False, "QB_NOT_CONFIRMED"
    
    # Weather check
    if not weather_clear:
        return False, "WEATHER_UNCERTAIN"
    
    # Distribution stability
    if distribution_flag == DistributionFlag.UNSTABLE_EXTREME:
        return False, "DISTRIBUTION_UNSTABLE_EXTREME"
    
    # Minimum edge threshold
    if market_type == MarketType.SPREAD:
        if compressed_edge < config.spread_eligibility_min:
            return False, "EDGE_BELOW_MINIMUM"
        
        # Check spread size guardrails
        if spread is not None and is_favorite is not None:
            _, eligible, reason = check_spread_size_guardrails(spread, is_favorite)
            if not eligible:
                return False, reason
    
    elif market_type == MarketType.TOTAL:
        if compressed_edge < config.total_eligibility_min:
            return False, "EDGE_BELOW_MINIMUM"
    
    return True, None


def evaluate_ncaaf_market(
    market_type: MarketType,
    sim_cover_prob: Optional[float] = None,
    sim_over_prob: Optional[float] = None,
    spread: Optional[float] = None,
    spread_odds: Optional[int] = None,
    over_odds: Optional[int] = None,
    under_odds: Optional[int] = None,
    simulation_results: Optional[Dict] = None,
    qb_confirmed: bool = False,
    weather_clear: bool = True,
    is_favorite: Optional[bool] = None
) -> NCAAFMarketEvaluation:
    """
    Complete evaluation of an NCAAF market
    
    Args:
        market_type: SPREAD or TOTAL
        sim_cover_prob: Simulated probability of covering spread
        sim_over_prob: Simulated over probability
        spread: Point spread (negative for favorite)
        spread_odds: American odds for spread
        over_odds, under_odds: For totals
        simulation_results: Distribution metrics
        qb_confirmed: Confirmed starting QB
        weather_clear: Weather conditions acceptable
        is_favorite: True if betting the favorite
    
    Returns: NCAAFMarketEvaluation
    """
    simulation_results = simulation_results or {}
    
    # Check spread size guardrails first
    is_large_spread = False
    spread_size = None
    
    if market_type == MarketType.SPREAD and spread is not None and is_favorite is not None:
        spread_size = abs(spread)
        is_large_spread, spread_eligible, spread_block_reason = check_spread_size_guardrails(
            spread, is_favorite
        )
        
        if not spread_eligible:
            return NCAAFMarketEvaluation(
                market_type=market_type,
                edge_state=EdgeState.NO_PLAY,
                raw_edge=0.0,
                compressed_edge=0.0,
                distribution_flag=DistributionFlag.STABLE,
                volatility=VolatilityLevel.LOW,
                eligible=False,
                blocking_reason=spread_block_reason,
                spread_size=spread_size,
                is_large_spread=is_large_spread,
                qb_confirmed=qb_confirmed,
                weather_clear=weather_clear
            )
    
    # Validate required parameters and calculate edge
    if market_type == MarketType.SPREAD:
        if sim_cover_prob is None or spread is None or spread_odds is None:
            return NCAAFMarketEvaluation(
                market_type=market_type,
                edge_state=EdgeState.NO_PLAY,
                raw_edge=0.0,
                compressed_edge=0.0,
                distribution_flag=DistributionFlag.STABLE,
                volatility=VolatilityLevel.LOW,
                eligible=False,
                blocking_reason="MISSING_MARKET_DATA"
            )
        raw_edge, compressed_edge = calculate_spread_edge(
            sim_cover_prob, spread, spread_odds, NCAAF_CONFIG.compression_factor
        )
    elif market_type == MarketType.TOTAL:
        if sim_over_prob is None or over_odds is None or under_odds is None:
            return NCAAFMarketEvaluation(
                market_type=market_type,
                edge_state=EdgeState.NO_PLAY,
                raw_edge=0.0,
                compressed_edge=0.0,
                distribution_flag=DistributionFlag.STABLE,
                volatility=VolatilityLevel.LOW,
                eligible=False,
                blocking_reason="MISSING_MARKET_DATA"
            )
        side, raw_edge, compressed_edge = calculate_total_edge(
            sim_over_prob, over_odds, under_odds, NCAAF_CONFIG.compression_factor
        )
    else:
        return NCAAFMarketEvaluation(
            market_type=market_type,
            edge_state=EdgeState.NO_PLAY,
            raw_edge=0.0,
            compressed_edge=0.0,
            distribution_flag=DistributionFlag.STABLE,
            volatility=VolatilityLevel.LOW,
            eligible=False,
            blocking_reason="MARKET_TYPE_NOT_SUPPORTED",
            qb_confirmed=qb_confirmed,
            weather_clear=weather_clear
        )
    
    # Classify edge state
    edge_state = classify_edge_state(compressed_edge, market_type, is_large_spread)
    
    # Assess distribution
    dist_flag, volatility = assess_distribution_volatility(simulation_results, market_type)
    
    # Check eligibility
    eligible, blocking_reason = check_eligibility_gates(
        compressed_edge,
        market_type,
        dist_flag,
        qb_confirmed,
        weather_clear,
        spread,
        is_favorite
    )
    
    # Override edge state if not eligible
    if not eligible:
        edge_state = EdgeState.NO_PLAY
    
    return NCAAFMarketEvaluation(
        market_type=market_type,
        edge_state=edge_state,
        raw_edge=raw_edge * 100,  # Convert to percentage
        compressed_edge=compressed_edge * 100,
        distribution_flag=dist_flag,
        volatility=volatility,
        eligible=eligible,
        blocking_reason=blocking_reason,
        spread_size=spread_size,
        is_large_spread=is_large_spread,
        qb_confirmed=qb_confirmed,
        weather_clear=weather_clear
    )


def grade_ncaaf_result(
    bet_side: str,
    market_type: MarketType,
    final_score_favorite: int,
    final_score_underdog: int,
    spread: Optional[float] = None,
    total_line: Optional[float] = None
) -> str:
    """
    Grade NCAAF bet result
    
    Returns: "WIN", "LOSS", or "PUSH"
    """
    if market_type == MarketType.SPREAD:
        if spread is None:
            return "UNKNOWN"
            
        # Apply spread to favorite's score
        favorite_ats = final_score_favorite + spread  # spread is negative
        
        if bet_side == "FAVORITE":
            if favorite_ats > final_score_underdog:
                return "WIN"
            elif favorite_ats == final_score_underdog:
                return "PUSH"
            else:
                return "LOSS"
        else:  # UNDERDOG
            if final_score_underdog > favorite_ats:
                return "WIN"
            elif final_score_underdog == favorite_ats:
                return "PUSH"
            else:
                return "LOSS"
    
    elif market_type == MarketType.TOTAL:
        if total_line is None:
            return "UNKNOWN"
            
        total_points = final_score_favorite + final_score_underdog
        
        if bet_side == "OVER":
            if total_points > total_line:
                return "WIN"
            elif total_points == total_line:
                return "PUSH"
            else:
                return "LOSS"
        else:  # UNDER
            if total_points < total_line:
                return "WIN"
            elif total_points == total_line:
                return "PUSH"
            else:
                return "LOSS"
    
    return "UNKNOWN"
