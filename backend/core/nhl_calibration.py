"""
NHL Calibration & Edge Logic

Totals/puckline focused sport.
Compression factor: 0.60 (most aggressive)
Goalie confirmation required.
Very tight edge thresholds.
"""
from typing import Dict, Optional, Tuple
from dataclasses import dataclass
from .sport_configs import (
    NHL_CONFIG, EdgeState, MarketType, DistributionFlag, VolatilityLevel
)


@dataclass
class NHLMarketEvaluation:
    """Result of evaluating a specific NHL market"""
    market_type: MarketType
    edge_state: EdgeState
    raw_edge: float
    compressed_edge: float
    distribution_flag: DistributionFlag
    volatility: VolatilityLevel
    eligible: bool
    blocking_reason: Optional[str] = None
    
    # NHL-specific
    puckline_size: Optional[float] = None
    goalie_confirmed: bool = False


def compress_probability(raw_prob: float, compression_factor: float = 0.60) -> float:
    """
    Apply compression to raw simulation win probability
    
    NHL uses MOST aggressive compression (0.60) due to high variance nature
    
    Formula: compressed = 0.5 + (raw - 0.5) * compression_factor
    
    Examples:
    - 60% raw → 56.0% compressed (0.5 + 0.1 * 0.60)
    - 55% raw → 53.0% compressed (0.5 + 0.05 * 0.60)
    """
    return 0.5 + (raw_prob - 0.5) * compression_factor


def calculate_puckline_edge(
    sim_cover_prob: float,
    puckline: float,
    puckline_odds: int,
    compression_factor: float = 0.60
) -> Tuple[float, float]:
    """
    Calculate edge for puckline market
    
    Args:
        sim_cover_prob: Simulated probability of covering the puckline
        puckline: Puckline (typically ±1.5)
        puckline_odds: American odds
    
    Returns: (raw_edge, compressed_edge)
    """
    compressed_prob = compress_probability(sim_cover_prob, compression_factor)
    
    # Calculate implied probability from odds
    if puckline_odds < 0:
        implied_prob = abs(puckline_odds) / (abs(puckline_odds) + 100)
    else:
        implied_prob = 100 / (puckline_odds + 100)
    
    raw_edge = sim_cover_prob - implied_prob
    compressed_edge = compressed_prob - implied_prob
    
    return raw_edge, compressed_edge


def calculate_total_edge(
    sim_over_prob: float,
    over_odds: int,
    under_odds: int,
    compression_factor: float = 0.60
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
    market_type: MarketType
) -> EdgeState:
    """
    Classify edge into EDGE/LEAN/NO_PLAY
    
    NHL has very tight thresholds
    """
    config = NHL_CONFIG
    
    if market_type == MarketType.PUCKLINE:
        if compressed_edge >= config.spread_edge_threshold:  # 1.5%
            return EdgeState.EDGE
        elif compressed_edge >= config.spread_lean_min:  # 1.0%
            return EdgeState.LEAN
        else:
            return EdgeState.NO_PLAY
    
    elif market_type == MarketType.TOTAL:
        if compressed_edge >= config.total_edge_threshold:  # 2.5%
            return EdgeState.EDGE
        elif compressed_edge >= config.total_lean_min:  # 1.5%
            return EdgeState.LEAN
        else:
            return EdgeState.NO_PLAY
    
    else:
        return EdgeState.NO_PLAY


def check_puckline_size_guardrails(puckline: float) -> Tuple[bool, Optional[str]]:
    """
    Check if puckline falls within acceptable limits
    
    NHL pucklines are almost always ±1.5, but check for outliers
    
    Returns: (eligible, blocking_reason)
    """
    config = NHL_CONFIG
    abs_puckline = abs(puckline)
    
    # Puckline should be ±1.5 in vast majority of cases
    max_favorite_spread = config.max_favorite_spread or 0.0
    if abs_puckline > max_favorite_spread:  # 2.5
        return False, f"PUCKLINE_TOO_LARGE_{abs_puckline}"
    
    return True, None


def assess_distribution_volatility(
    simulation_results: Dict,
    market_type: MarketType
) -> Tuple[DistributionFlag, VolatilityLevel]:
    """
    Assess simulation distribution stability
    
    NHL has high baseline volatility due to goalie/variance
    """
    if market_type == MarketType.PUCKLINE:
        std = simulation_results.get('cover_prob_std', 0)
    else:
        std = simulation_results.get('total_std', 0)
    
    # Volatility classification (wider bands for NHL)
    if std < 0.03:
        volatility = VolatilityLevel.LOW
    elif std < 0.05:
        volatility = VolatilityLevel.MEDIUM
    elif std < 0.07:
        volatility = VolatilityLevel.HIGH
    else:
        volatility = VolatilityLevel.EXTREME
    
    # Distribution flag
    convergence = simulation_results.get('convergence_rate', 1.0)
    
    if volatility in [VolatilityLevel.LOW, VolatilityLevel.MEDIUM] and convergence > 0.93:
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
    goalie_confirmed: bool,
    puckline: Optional[float] = None
) -> Tuple[bool, Optional[str]]:
    """
    Check if market passes all eligibility gates
    
    Returns: (eligible, blocking_reason)
    """
    config = NHL_CONFIG
    
    # Goalie confirmation required
    if not goalie_confirmed:
        return False, "GOALIE_NOT_CONFIRMED"
    
    # Distribution stability
    if distribution_flag == DistributionFlag.UNSTABLE_EXTREME:
        return False, "DISTRIBUTION_UNSTABLE_EXTREME"
    
    # Minimum edge threshold
    if market_type == MarketType.PUCKLINE:
        if compressed_edge < config.spread_eligibility_min:
            return False, "EDGE_BELOW_MINIMUM"
        
        # Check puckline size guardrails
        if puckline is not None:
            eligible, reason = check_puckline_size_guardrails(puckline)
            if not eligible:
                return False, reason
    
    elif market_type == MarketType.TOTAL:
        if compressed_edge < config.total_eligibility_min:
            return False, "EDGE_BELOW_MINIMUM"
    
    return True, None


def evaluate_nhl_market(
    market_type: MarketType,
    sim_cover_prob: Optional[float] = None,
    sim_over_prob: Optional[float] = None,
    puckline: Optional[float] = None,
    puckline_odds: Optional[int] = None,
    over_odds: Optional[int] = None,
    under_odds: Optional[int] = None,
    simulation_results: Optional[Dict] = None,
    goalie_confirmed: bool = False
) -> NHLMarketEvaluation:
    """
    Complete evaluation of an NHL market
    
    Args:
        market_type: PUCKLINE or TOTAL
        sim_cover_prob: Simulated probability of covering puckline
        sim_over_prob: Simulated over probability
        puckline: Puckline (typically ±1.5)
        puckline_odds: American odds for puckline
        over_odds, under_odds: For totals
        simulation_results: Distribution metrics
        goalie_confirmed: Confirmed starting goalie
    
    Returns: NHLMarketEvaluation
    """
    simulation_results = simulation_results or {}
    
    # Check puckline size guardrails first
    puckline_size = None
    
    if market_type == MarketType.PUCKLINE and puckline is not None:
        puckline_size = abs(puckline)
        eligible, block_reason = check_puckline_size_guardrails(puckline)
        
        if not eligible:
            return NHLMarketEvaluation(
                market_type=market_type,
                edge_state=EdgeState.NO_PLAY,
                raw_edge=0.0,
                compressed_edge=0.0,
                distribution_flag=DistributionFlag.STABLE,
                volatility=VolatilityLevel.LOW,
                eligible=False,
                blocking_reason=block_reason,
                puckline_size=puckline_size,
                goalie_confirmed=goalie_confirmed
            )
    
    # Validate required parameters and calculate edge
    if market_type == MarketType.PUCKLINE:
        if sim_cover_prob is None or puckline is None or puckline_odds is None:
            return NHLMarketEvaluation(
                market_type=market_type,
                edge_state=EdgeState.NO_PLAY,
                raw_edge=0.0,
                compressed_edge=0.0,
                distribution_flag=DistributionFlag.STABLE,
                volatility=VolatilityLevel.LOW,
                eligible=False,
                blocking_reason="MISSING_MARKET_DATA"
            )
        raw_edge, compressed_edge = calculate_puckline_edge(
            sim_cover_prob, puckline, puckline_odds, NHL_CONFIG.compression_factor
        )
    elif market_type == MarketType.TOTAL:
        if sim_over_prob is None or over_odds is None or under_odds is None:
            return NHLMarketEvaluation(
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
            sim_over_prob, over_odds, under_odds, NHL_CONFIG.compression_factor
        )
    else:
        return NHLMarketEvaluation(
            market_type=market_type,
            edge_state=EdgeState.NO_PLAY,
            raw_edge=0.0,
            compressed_edge=0.0,
            distribution_flag=DistributionFlag.STABLE,
            volatility=VolatilityLevel.LOW,
            eligible=False,
            blocking_reason="MARKET_TYPE_NOT_SUPPORTED",
            goalie_confirmed=goalie_confirmed
        )
    
    # Classify edge state
    edge_state = classify_edge_state(compressed_edge, market_type)
    
    # Assess distribution
    dist_flag, volatility = assess_distribution_volatility(simulation_results, market_type)
    
    # Check eligibility
    eligible, blocking_reason = check_eligibility_gates(
        compressed_edge,
        market_type,
        dist_flag,
        goalie_confirmed,
        puckline
    )
    
    # Override edge state if not eligible
    if not eligible:
        edge_state = EdgeState.NO_PLAY
    
    return NHLMarketEvaluation(
        market_type=market_type,
        edge_state=edge_state,
        raw_edge=raw_edge * 100,  # Convert to percentage
        compressed_edge=compressed_edge * 100,
        distribution_flag=dist_flag,
        volatility=volatility,
        eligible=eligible,
        blocking_reason=blocking_reason,
        puckline_size=puckline_size,
        goalie_confirmed=goalie_confirmed
    )


def grade_nhl_result(
    bet_side: str,
    market_type: MarketType,
    final_score_favorite: int,
    final_score_underdog: int,
    puckline: Optional[float] = None,
    total_line: Optional[float] = None
) -> str:
    """
    Grade NHL bet result
    
    Returns: "WIN", "LOSS", or "PUSH"
    """
    if market_type == MarketType.PUCKLINE:
        if puckline is None:
            return "UNKNOWN"
            
        # Apply puckline to favorite's score
        favorite_apl = final_score_favorite + puckline  # puckline is negative (usually -1.5)
        
        if bet_side == "FAVORITE":
            if favorite_apl > final_score_underdog:
                return "WIN"
            elif favorite_apl == final_score_underdog:
                return "PUSH"
            else:
                return "LOSS"
        else:  # UNDERDOG
            if final_score_underdog > favorite_apl:
                return "WIN"
            elif final_score_underdog == favorite_apl:
                return "PUSH"
            else:
                return "LOSS"
    
    elif market_type == MarketType.TOTAL:
        if total_line is None:
            return "UNKNOWN"
            
        total_goals = final_score_favorite + final_score_underdog
        
        if bet_side == "OVER":
            if total_goals > total_line:
                return "WIN"
            elif total_goals == total_line:
                return "PUSH"
            else:
                return "LOSS"
        else:  # UNDER
            if total_goals < total_line:
                return "WIN"
            elif total_goals == total_line:
                return "PUSH"
            else:
                return "LOSS"
    
    return "UNKNOWN"
