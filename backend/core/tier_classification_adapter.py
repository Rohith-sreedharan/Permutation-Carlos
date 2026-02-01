"""
Tier Classification Adapter
============================
Adapter layer between Monte Carlo simulations and Universal Tier Classifier.

Extracts data from simulation outputs and market snapshots, feeds them to
the universal classifier, and returns classification results.

Usage:
    from core.tier_classification_adapter import classify_simulation
    
    result = classify_simulation(
        simulation=monte_carlo_output,
        market_data=current_market_snapshot,
        market_type="SPREAD"
    )
    
    if result.tier == Tier.EDGE:
        post_to_telegram(result)
"""

from typing import Optional, Dict, Any, List
from datetime import datetime, timezone
import logging

from core.universal_tier_classifier import (
    SelectionInput,
    ClassificationResult,
    build_classification_result,
    Tier,
    format_telegram_card,
    choose_top,
    decide_post,
    PostDecision,
    PostingPolicy
)

logger = logging.getLogger(__name__)


def classify_simulation(
    simulation: Dict[str, Any],
    market_data: Dict[str, Any],
    market_type: str,
    now_unix: Optional[int] = None
) -> Optional[ClassificationResult]:
    """
    Classify a single simulation + market snapshot.
    
    Args:
        simulation: Monte Carlo output containing:
            - sport: str
            - sim_count: int
            - home_win_probability: float (for spread/moneyline)
            - away_win_probability: float (for spread/moneyline)
            - over_probability: float (for totals)
            - under_probability: float (for totals)
            - timestamp: datetime
        
        market_data: Current market snapshot containing:
            - spread_home_price: int (American odds)
            - spread_away_price: int (American odds)
            - total_over_price: int
            - total_under_price: int
            - moneyline_home_price: int
            - moneyline_away_price: int
            - spread_line: float
            - total_line: float
        
        market_type: "SPREAD" | "TOTAL" | "MONEYLINE"
        now_unix: Current unix timestamp (optional, defaults to now)
    
    Returns:
        ClassificationResult or None if extraction failed
    """
    if now_unix is None:
        now_unix = int(datetime.now(timezone.utc).timestamp())
    
    try:
        # Extract timestamp from simulation
        sim_timestamp = simulation.get('timestamp')
        if isinstance(sim_timestamp, datetime):
            timestamp_unix = int(sim_timestamp.timestamp())
        elif isinstance(sim_timestamp, int):
            timestamp_unix = sim_timestamp
        else:
            timestamp_unix = now_unix
        
        # Extract based on market type
        if market_type == "SPREAD":
            # Determine which side has the edge
            home_prob = simulation.get('home_win_probability', 0.5)
            away_prob = simulation.get('away_win_probability', 0.5)
            
            # Use the side with higher probability
            if home_prob > away_prob:
                p_model = home_prob
                price = market_data.get('spread_home_price', -110)
                opp_price = market_data.get('spread_away_price', -110)
                spread_line = market_data.get('spread_line', 0)
                selection_text = f"{simulation.get('home_team', 'Home')} {spread_line:+.1f}"
            else:
                p_model = away_prob
                price = market_data.get('spread_away_price', -110)
                opp_price = market_data.get('spread_home_price', -110)
                spread_line = market_data.get('spread_line', 0)
                selection_text = f"{simulation.get('away_team', 'Away')} {-spread_line:+.1f}"
        
        elif market_type == "TOTAL":
            # Determine Over or Under
            over_prob = simulation.get('over_probability', 0.5)
            under_prob = simulation.get('under_probability', 0.5)
            
            total_line = market_data.get('total_line', 0)
            
            if over_prob > under_prob:
                p_model = over_prob
                price = market_data.get('total_over_price', -110)
                opp_price = market_data.get('total_under_price', -110)
                selection_text = f"Over {total_line:.1f}"
            else:
                p_model = under_prob
                price = market_data.get('total_under_price', -110)
                opp_price = market_data.get('total_over_price', -110)
                selection_text = f"Under {total_line:.1f}"
        
        elif market_type == "MONEYLINE":
            home_prob = simulation.get('home_win_probability', 0.5)
            away_prob = simulation.get('away_win_probability', 0.5)
            
            if home_prob > away_prob:
                p_model = home_prob
                price = market_data.get('moneyline_home_price', -110)
                opp_price = market_data.get('moneyline_away_price', -110)
                selection_text = f"{simulation.get('home_team', 'Home')} ML"
            else:
                p_model = away_prob
                price = market_data.get('moneyline_away_price', -110)
                opp_price = market_data.get('moneyline_home_price', -110)
                selection_text = f"{simulation.get('away_team', 'Away')} ML"
        
        else:
            logger.error(f"Unknown market_type: {market_type}")
            return None
        
        # Build SelectionInput
        selection = SelectionInput(
            sport=simulation.get('sport', 'UNKNOWN'),
            market_type=market_type,
            selection_id=f"{simulation.get('game_id', 'unknown')}_{market_type.lower()}",
            selection_text=selection_text,
            timestamp_unix=timestamp_unix,
            sims_n=simulation.get('sim_count', 0),
            p_model=p_model,
            price_american=price,
            opp_price_american=opp_price
        )
        
        # Classify
        result = build_classification_result(selection, now_unix)
        return result
    
    except Exception as e:
        logger.error(f"Error classifying simulation: {e}")
        return None


def classify_all_markets(
    simulation: Dict[str, Any],
    market_data: Dict[str, Any],
    now_unix: Optional[int] = None
) -> Dict[str, Optional[ClassificationResult]]:
    """
    Classify all three markets (SPREAD, TOTAL, MONEYLINE) for a game.
    
    Args:
        simulation: Monte Carlo output
        market_data: Current market snapshot
        now_unix: Current unix timestamp (optional)
    
    Returns:
        {
            "SPREAD": ClassificationResult or None,
            "TOTAL": ClassificationResult or None,
            "MONEYLINE": ClassificationResult or None
        }
    """
    results = {}
    
    for market_type in ["SPREAD", "TOTAL", "MONEYLINE"]:
        results[market_type] = classify_simulation(
            simulation=simulation,
            market_data=market_data,
            market_type=market_type,
            now_unix=now_unix
        )
    
    return results


def get_best_pick(
    simulations: List[Dict[str, Any]],
    market_data_list: List[Dict[str, Any]],
    max_picks: int = 2,
    policy: PostingPolicy = PostingPolicy()
) -> List[ClassificationResult]:
    """
    Get top N picks across multiple games.
    
    Filters to EDGE/LEAN only, ranks by prob_edge + EV, returns top N.
    
    Args:
        simulations: List of Monte Carlo outputs
        market_data_list: List of market snapshots (same order as simulations)
        max_picks: Maximum number of picks to return
        policy: Posting policy (default: post EDGE and LEAN)
    
    Returns:
        List of top N ClassificationResults
    """
    all_results = []
    now_unix = int(datetime.now(timezone.utc).timestamp())
    
    for sim, market in zip(simulations, market_data_list):
        # Classify all markets for this game
        game_results = classify_all_markets(sim, market, now_unix)
        
        # Add valid results
        for market_type, result in game_results.items():
            if result is not None:
                all_results.append(result)
    
    # Use choose_top from universal_tier_classifier
    return choose_top(all_results, max_posts=max_picks)


def is_telegram_eligible(tier: Tier) -> bool:
    """
    Check if tier is eligible for Telegram posting.
    
    Only EDGE and LEAN are posted to Telegram.
    MARKET_ALIGNED and BLOCKED are not posted.
    
    Args:
        tier: Classification tier
    
    Returns:
        True if should be posted to Telegram
    """
    return tier in {Tier.EDGE, Tier.LEAN}


def is_war_room_visible(tier: Tier) -> bool:
    """
    Check if tier should be visible in War Room.
    
    EDGE, LEAN, and MARKET_ALIGNED are shown (for transparency).
    BLOCKED is hidden (data integrity failure).
    
    Args:
        tier: Classification tier
    
    Returns:
        True if should be shown in War Room
    """
    return tier != Tier.BLOCKED


def is_parlay_eligible(tier: Tier) -> bool:
    """
    Check if tier is eligible for parlay construction.
    
    Only EDGE selections should be used in parlays.
    LEAN can be considered but with caution.
    
    Args:
        tier: Classification tier
    
    Returns:
        True if can be used in parlays
    """
    return tier in {Tier.EDGE, Tier.LEAN}


def tier_to_edge_state(tier: Tier) -> str:
    """
    Convert new Tier to old EdgeState string for backward compatibility.
    
    Args:
        tier: Classification tier
    
    Returns:
        "EDGE" | "LEAN" | "NO_PLAY"
    """
    tier_map = {
        Tier.EDGE: "EDGE",
        Tier.LEAN: "LEAN",
        Tier.MARKET_ALIGNED: "NO_PLAY",
        Tier.BLOCKED: "NO_PLAY"
    }
    return tier_map.get(tier, "NO_PLAY")


def format_for_telegram(result: ClassificationResult) -> str:
    """
    Format classification result for Telegram posting.
    
    Wrapper around format_telegram_card with error handling.
    
    Args:
        result: Classification result
    
    Returns:
        Formatted telegram message
    
    Raises:
        ValueError: If result is not EDGE or LEAN
    """
    return format_telegram_card(result)


# ============================================================================
# INTEGRATION TESTS
# ============================================================================

def _run_adapter_tests():
    """Test adapter extraction and classification"""
    print("=== ADAPTER INTEGRATION TESTS ===\n")
    
    # Mock simulation output
    simulation = {
        'sport': 'NBA',
        'game_id': 'nba_lal_gsw_2026',
        'home_team': 'Lakers',
        'away_team': 'Warriors',
        'sim_count': 50000,
        'home_win_probability': 0.60,
        'away_win_probability': 0.40,
        'over_probability': 0.55,
        'under_probability': 0.45,
        'timestamp': datetime.now(timezone.utc)
    }
    
    # Mock market data
    market_data = {
        'spread_line': -3.5,
        'spread_home_price': -110,
        'spread_away_price': -110,
        'total_line': 225.5,
        'total_over_price': -110,
        'total_under_price': -110,
        'moneyline_home_price': -180,
        'moneyline_away_price': +150
    }
    
    # Test SPREAD classification
    print("[1] Testing SPREAD classification")
    result_spread = classify_simulation(simulation, market_data, "SPREAD")
    if result_spread:
        print(f"   ✓ Tier: {result_spread.tier.value}")
        print(f"   ✓ Selection: {result_spread.selection_text}")
        if result_spread.prob_edge is not None:
            print(f"   ✓ Prob Edge: {result_spread.prob_edge*100:.1f}%")
        if result_spread.ev is not None:
            print(f"   ✓ EV: {result_spread.ev*100:.1f}%")
    else:
        print("   ✗ FAILED: No result returned")
    
    # Test TOTAL classification
    print("\n[2] Testing TOTAL classification")
    result_total = classify_simulation(simulation, market_data, "TOTAL")
    if result_total:
        print(f"   ✓ Tier: {result_total.tier.value}")
        print(f"   ✓ Selection: {result_total.selection_text}")
        if result_total.prob_edge is not None:
            print(f"   ✓ Prob Edge: {result_total.prob_edge*100:.1f}%")
    else:
        print("   ✗ FAILED: No result returned")
    
    # Test all markets
    print("\n[3] Testing classify_all_markets")
    all_results = classify_all_markets(simulation, market_data)
    for market_type, result in all_results.items():
        if result:
            print(f"   ✓ {market_type}: {result.tier.value}")
        else:
            print(f"   ✗ {market_type}: Failed")
    
    # Test Telegram eligibility
    print("\n[4] Testing Telegram eligibility")
    if result_spread:
        eligible = is_telegram_eligible(result_spread.tier)
        print(f"   ✓ SPREAD tier {result_spread.tier.value} eligible: {eligible}")
    
    # Test Telegram formatting
    if result_spread and result_spread.tier in {Tier.EDGE, Tier.LEAN}:
        print("\n[5] Testing Telegram card formatting")
        try:
            card = format_for_telegram(result_spread)
            print("   ✓ Card formatted successfully:")
            print("\n" + card + "\n")
        except Exception as e:
            print(f"   ✗ FAILED: {e}")
    
    # Test prob_edge and EV are not None
    if result_spread and result_spread.prob_edge is not None:
        print(f"\n[6] Metrics validation")
        print(f"   ✓ Prob Edge: {result_spread.prob_edge * 100:.1f}%")
        if result_spread.ev is not None:
            print(f"   ✓ EV: {result_spread.ev * 100:.1f}%")
    
    print("=== ADAPTER TESTS COMPLETE ===\n")


if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO)
    _run_adapter_tests()
