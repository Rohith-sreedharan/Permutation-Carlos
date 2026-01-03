"""
MLB Calibration & Edge Logic

Moneyline-first sport with totals secondary.
Probabilities compressed at 0.82 factor.
Pitcher confirmation required.
"""
from typing import Dict, Optional, Tuple
from dataclasses import dataclass
from .sport_configs import (
    MLB_CONFIG, EdgeState, MarketType, DistributionFlag, VolatilityLevel
)


@dataclass
class MLBMarketEvaluation:
    """Result of evaluating a specific MLB market"""
    market_type: MarketType
    edge_state: EdgeState
    raw_edge: float
    compressed_edge: float
    distribution_flag: DistributionFlag
    volatility: VolatilityLevel
    eligible: bool
    blocking_reason: Optional[str] = None
    
    # MLB-specific
    pitcher_confirmed: bool = False
    weather_clear: bool = True


def compress_probability(raw_prob: float, compression_factor: float = 0.82) -> float:
    """
    Apply compression to raw simulation win probability
    
    Formula: compressed = 0.5 + (raw - 0.5) * compression_factor
    
    Examples:
    - 60% raw → 58.2% compressed (0.5 + 0.1 * 0.82)
    - 55% raw → 54.1% compressed (0.5 + 0.05 * 0.82)
    """
    return 0.5 + (raw_prob - 0.5) * compression_factor


def calculate_implied_probability(american_odds: int) -> float:
    """
    Convert American odds to implied probability
    
    Examples:
    - -150 → 60.0%
    - +130 → 43.48%
    """
    if american_odds < 0:
        return abs(american_odds) / (abs(american_odds) + 100)
    else:
        return 100 / (american_odds + 100)


def calculate_moneyline_edge(
    sim_win_prob: float,
    odds: int,
    compression_factor: float = 0.82
) -> Tuple[float, float]:
    """
    Calculate edge for moneyline market
    
    Returns: (raw_edge, compressed_edge)
    """
    compressed_prob = compress_probability(sim_win_prob, compression_factor)
    implied_prob = calculate_implied_probability(odds)
    
    raw_edge = sim_win_prob - implied_prob
    compressed_edge = compressed_prob - implied_prob
    
    return raw_edge, compressed_edge


def calculate_total_edge(
    sim_over_prob: float,
    over_odds: int,
    under_odds: int,
    compression_factor: float = 0.82
) -> Tuple[str, float, float]:
    """
    Calculate edge for totals market
    
    Returns: (side, raw_edge, compressed_edge)
    """
    compressed_over_prob = compress_probability(sim_over_prob, compression_factor)
    compressed_under_prob = 1.0 - compressed_over_prob
    
    over_implied = calculate_implied_probability(over_odds)
    under_implied = calculate_implied_probability(under_odds)
    
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
    """
    config = MLB_CONFIG
    
    if market_type == MarketType.MONEYLINE:
        # MLB always has ML thresholds
        ml_edge = config.ml_edge_threshold or 0.0
        ml_lean = config.ml_lean_min or 0.0
        if compressed_edge >= ml_edge:
            return EdgeState.EDGE
        elif compressed_edge >= ml_lean:
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


def assess_distribution_volatility(
    simulation_results: Dict,
    market_type: MarketType
) -> Tuple[DistributionFlag, VolatilityLevel]:
    """
    Assess simulation distribution stability
    
    Args:
        simulation_results: {
            'win_prob_std': float,  # Standard deviation across simulation batches
            'total_std': float,  # For totals
            'convergence_rate': float,  # How quickly sims converged
        }
    
    Returns: (distribution_flag, volatility_level)
    """
    if market_type == MarketType.MONEYLINE:
        std = simulation_results.get('win_prob_std', 0)
    else:
        std = simulation_results.get('total_std', 0)
    
    # Volatility classification
    if std < 0.02:
        volatility = VolatilityLevel.LOW
    elif std < 0.04:
        volatility = VolatilityLevel.MEDIUM
    elif std < 0.06:
        volatility = VolatilityLevel.HIGH
    else:
        volatility = VolatilityLevel.EXTREME
    
    # Distribution flag
    convergence = simulation_results.get('convergence_rate', 1.0)
    
    if volatility in [VolatilityLevel.LOW, VolatilityLevel.MEDIUM] and convergence > 0.95:
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
    pitcher_confirmed: bool,
    weather_clear: bool
) -> Tuple[bool, Optional[str]]:
    """
    Check if market passes all eligibility gates
    
    Returns: (eligible, blocking_reason)
    """
    config = MLB_CONFIG
    
    # Pitcher confirmation required
    if not pitcher_confirmed:
        return False, "PITCHER_NOT_CONFIRMED"
    
    # Weather check
    if not weather_clear:
        return False, "WEATHER_UNCERTAIN"
    
    # Distribution stability
    if distribution_flag == DistributionFlag.UNSTABLE_EXTREME:
        return False, "DISTRIBUTION_UNSTABLE_EXTREME"
    
    # Minimum edge threshold
    if market_type == MarketType.MONEYLINE:
        ml_min = config.ml_win_prob_edge_min or 0.0
        if compressed_edge < ml_min:
            return False, "EDGE_BELOW_MINIMUM"
    elif market_type == MarketType.TOTAL:
        if compressed_edge < config.total_eligibility_min:
            return False, "EDGE_BELOW_MINIMUM"
    
    return True, None


def evaluate_mlb_market(
    market_type: MarketType,
    sim_win_prob: Optional[float] = None,
    sim_over_prob: Optional[float] = None,
    odds: Optional[int] = None,
    over_odds: Optional[int] = None,
    under_odds: Optional[int] = None,
    simulation_results: Optional[Dict] = None,
    pitcher_confirmed: bool = False,
    weather_clear: bool = True
) -> MLBMarketEvaluation:
    """
    Complete evaluation of an MLB market
    
    Args:
        market_type: MONEYLINE or TOTAL
        sim_win_prob: Simulated win probability (for moneyline)
        sim_over_prob: Simulated over probability (for totals)
        odds: American odds (for moneyline)
        over_odds, under_odds: For totals
        simulation_results: Distribution metrics
        pitcher_confirmed: Confirmed starting pitcher
        weather_clear: Weather conditions acceptable
    
    Returns: MLBMarketEvaluation
    """
    simulation_results = simulation_results or {}
    
    # Validate required parameters based on market type
    if market_type == MarketType.MONEYLINE:
        if sim_win_prob is None or odds is None:
            return MLBMarketEvaluation(
                market_type=market_type,
                edge_state=EdgeState.NO_PLAY,
                raw_edge=0.0,
                compressed_edge=0.0,
                distribution_flag=DistributionFlag.STABLE,
                volatility=VolatilityLevel.LOW,
                eligible=False,
                blocking_reason="MISSING_MARKET_DATA",
                pitcher_confirmed=pitcher_confirmed,
                weather_clear=weather_clear
            )
        raw_edge, compressed_edge = calculate_moneyline_edge(
            sim_win_prob, odds, MLB_CONFIG.compression_factor
        )
    elif market_type == MarketType.TOTAL:
        if sim_over_prob is None or over_odds is None or under_odds is None:
            return MLBMarketEvaluation(
                market_type=market_type,
                edge_state=EdgeState.NO_PLAY,
                raw_edge=0.0,
                compressed_edge=0.0,
                distribution_flag=DistributionFlag.STABLE,
                volatility=VolatilityLevel.LOW,
                eligible=False,
                blocking_reason="MISSING_MARKET_DATA",
                pitcher_confirmed=pitcher_confirmed,
                weather_clear=weather_clear
            )
        side, raw_edge, compressed_edge = calculate_total_edge(
            sim_over_prob, over_odds, under_odds, MLB_CONFIG.compression_factor
        )
    else:
        return MLBMarketEvaluation(
            market_type=market_type,
            edge_state=EdgeState.NO_PLAY,
            raw_edge=0.0,
            compressed_edge=0.0,
            distribution_flag=DistributionFlag.STABLE,
            volatility=VolatilityLevel.LOW,
            eligible=False,
            blocking_reason="MARKET_TYPE_NOT_SUPPORTED",
            pitcher_confirmed=pitcher_confirmed,
            weather_clear=weather_clear
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
        pitcher_confirmed,
        weather_clear
    )
    
    # Override edge state if not eligible
    if not eligible:
        edge_state = EdgeState.NO_PLAY
    
    return MLBMarketEvaluation(
        market_type=market_type,
        edge_state=edge_state,
        raw_edge=raw_edge * 100,  # Convert to percentage
        compressed_edge=compressed_edge * 100,
        distribution_flag=dist_flag,
        volatility=volatility,
        eligible=eligible,
        blocking_reason=blocking_reason,
        pitcher_confirmed=pitcher_confirmed,
        weather_clear=weather_clear
    )


def grade_mlb_result(
    bet_side: str,
    market_type: MarketType,
    final_score_home: int,
    final_score_away: int,
    total_line: Optional[float] = None
) -> str:
    """
    Grade MLB bet result
    
    Returns: "WIN", "LOSS", or "PUSH"
    """
    if market_type == MarketType.MONEYLINE:
        if bet_side == "HOME":
            return "WIN" if final_score_home > final_score_away else "LOSS"
        else:
            return "WIN" if final_score_away > final_score_home else "LOSS"
    
    elif market_type == MarketType.TOTAL:
        if total_line is None:
            return "UNKNOWN"
            
        total_runs = final_score_home + final_score_away
        
        if bet_side == "OVER":
            if total_runs > total_line:
                return "WIN"
            elif total_runs == total_line:
                return "PUSH"
            else:
                return "LOSS"
        else:  # UNDER
            if total_runs < total_line:
                return "WIN"
            elif total_runs == total_line:
                return "PUSH"
            else:
                return "LOSS"
    
    return "UNKNOWN"
