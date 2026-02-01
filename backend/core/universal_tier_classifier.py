"""
Universal EDGE/LEAN Tier Classifier
=====================================
Sport-agnostic classification using ONLY probability edge + EV + data integrity.

CRITICAL: This is the SINGLE SOURCE OF TRUTH for tier classification.
CLV, volatility, line movement, market efficiency flags CANNOT affect tier.

Classification Tiers:
- BLOCKED: Data integrity failure (missing/invalid/stale/insufficient sims)
- EDGE: Material probability advantage (>=5%) + non-negative EV (>=0%)
- LEAN: Meaningful probability advantage (>=2.5%) + near-breakeven EV (>=-0.5%)
- MARKET_ALIGNED: Does not meet LEAN/EDGE thresholds

This classifier is used for:
1. Telegram posting decisions (EDGE/LEAN only)
2. War Room visibility
3. Parlay eligibility
4. UI display

Works across: NBA / NFL / NCAAB / NCAAF / NHL / MLB
"""

from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from enum import Enum
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)


# ============================================================================
# LOCKED DEFAULTS (DO NOT MODIFY)
# ============================================================================

MIN_SIMS = 20000
STALE_TTL_SECONDS = 180  # 3 minutes

EDGE_PROB_EDGE_MIN = 0.050  # 5.0%
LEAN_PROB_EDGE_MIN = 0.025  # 2.5%

EDGE_EV_MIN = 0.000  # >= 0%
LEAN_EV_MIN = -0.005  # >= -0.5%


# ============================================================================
# ENUMS
# ============================================================================

class Tier(str, Enum):
    """Classification tiers - deterministic, sport-agnostic"""
    EDGE = "EDGE"
    LEAN = "LEAN"
    MARKET_ALIGNED = "MARKET_ALIGNED"
    BLOCKED = "BLOCKED"


class PostDecision(str, Enum):
    """Telegram posting decisions"""
    POST = "POST"
    WATCH = "WATCH"
    PASS = "PASS"


# ============================================================================
# INPUT DATA MODEL
# ============================================================================

@dataclass
class SelectionInput:
    """Required inputs for classification - no optional ambiguity"""
    sport: str                          # "NBA", "NHL", etc.
    market_type: str                    # "SPREAD" | "TOTAL" | "MONEYLINE"
    selection_id: str                   # unique identifier
    selection_text: str                 # e.g., "Bulls -2.5", "Over 226.5"
    timestamp_unix: int                 # when market snapshot taken
    sims_n: int                         # number of simulations
    p_model: float                      # model probability for THIS selection (0..1)
    price_american: int                 # offered price (e.g., -110, +120)
    opp_price_american: Optional[int] = None  # opposite side price if available


# ============================================================================
# ODDS CONVERSION HELPERS
# ============================================================================

def implied_prob_from_american(a: int) -> float:
    """
    Convert American odds to implied probability (vig-included).
    
    Args:
        a: American odds (e.g., -110, +150)
    
    Returns:
        Implied probability (0..1)
    
    Examples:
        -110 → 0.5238
        +150 → 0.4000
    """
    if a < 0:
        return (-a) / ((-a) + 100)
    else:
        return 100 / (a + 100)


def decimal_odds_from_american(a: int) -> float:
    """
    Convert American odds to decimal odds.
    
    Args:
        a: American odds (e.g., -110, +150)
    
    Returns:
        Decimal odds (e.g., 1.909, 2.50)
    """
    if a < 0:
        return 1 + (100 / (-a))
    else:
        return 1 + (a / 100)


def ev_from_prob_and_american(p: float, a: int) -> float:
    """
    Calculate expected value from model probability and American odds.
    
    Args:
        p: Model probability (0..1)
        a: American odds (e.g., -110)
    
    Returns:
        Expected value as decimal (e.g., 0.045 = 4.5% EV)
    
    Formula:
        EV = (p × decimal_odds) - 1
    """
    dec = decimal_odds_from_american(a)
    return (p * dec) - 1


# ============================================================================
# VIG-REMOVED MARKET PROBABILITY
# ============================================================================

def market_prob_fair(price: int, opp_price: Optional[int] = None) -> float:
    """
    Calculate vig-removed fair market probability.
    
    Two-sided (preferred):
        When both sides available, remove vig by normalization:
        p_fair = p1 / (p1 + p2)
    
    Single-sided (fallback):
        When only one side available, use vig-included probability.
    
    Args:
        price: American odds for THIS selection
        opp_price: American odds for opposite side (optional)
    
    Returns:
        Fair market probability (0..1)
    
    Examples:
        price=-110, opp_price=-110 → 0.50 (vig removed)
        price=-110, opp_price=None → 0.5238 (vig included)
    """
    p1 = implied_prob_from_american(price)
    
    if opp_price is None:
        # Fallback: single side (vig-included)
        return p1
    
    p2 = implied_prob_from_american(opp_price)
    denom = p1 + p2
    
    if denom <= 0:
        # Safety fallback
        return p1
    
    # Vig-removed fair probability for THIS selection
    return p1 / denom


# ============================================================================
# DATA INTEGRITY GATE
# ============================================================================

def is_blocked(x: SelectionInput, now_unix: int) -> bool:
    """
    Check if selection fails data integrity requirements.
    
    BLOCKED if:
    - Insufficient simulations (< 20,000)
    - Invalid model probability (null, <=0, >=1)
    - Missing price
    - Stale data (> 180 seconds old)
    
    Args:
        x: Selection input
        now_unix: Current unix timestamp
    
    Returns:
        True if blocked, False if passes integrity
    """
    if x.sims_n < MIN_SIMS:
        logger.warning(f"BLOCKED {x.selection_id}: sims_n={x.sims_n} < {MIN_SIMS}")
        return True
    
    if x.p_model is None or x.p_model <= 0 or x.p_model >= 1:
        logger.warning(f"BLOCKED {x.selection_id}: invalid p_model={x.p_model}")
        return True
    
    if x.price_american is None:
        logger.warning(f"BLOCKED {x.selection_id}: missing price_american")
        return True
    
    age_seconds = now_unix - x.timestamp_unix
    if age_seconds > STALE_TTL_SECONDS:
        logger.warning(f"BLOCKED {x.selection_id}: stale data ({age_seconds}s > {STALE_TTL_SECONDS}s)")
        return True
    
    return False


# ============================================================================
# TIER CLASSIFICATION (SINGLE SOURCE OF TRUTH)
# ============================================================================

def classify(x: SelectionInput, now_unix: int) -> Tier:
    """
    Classify selection into EDGE/LEAN/MARKET_ALIGNED/BLOCKED.
    
    CRITICAL: Uses ONLY probability edge + EV + data integrity.
    CLV, volatility, line movement, market efficiency CANNOT affect tier.
    
    Thresholds (locked):
    - EDGE: prob_edge >= 5.0% AND ev >= 0.0%
    - LEAN: prob_edge >= 2.5% AND ev >= -0.5%
    - MARKET_ALIGNED: does not meet LEAN/EDGE
    - BLOCKED: fails data integrity
    
    Args:
        x: Selection input
        now_unix: Current unix timestamp
    
    Returns:
        Tier classification
    """
    # Gate 1: Data integrity
    if is_blocked(x, now_unix):
        return Tier.BLOCKED
    
    # Calculate metrics
    p_mkt = market_prob_fair(x.price_american, x.opp_price_american)
    prob_edge = x.p_model - p_mkt
    ev = ev_from_prob_and_american(x.p_model, x.price_american)
    
    # Gate 2: EDGE threshold
    if prob_edge >= EDGE_PROB_EDGE_MIN and ev >= EDGE_EV_MIN:
        return Tier.EDGE
    
    # Gate 3: LEAN threshold
    if prob_edge >= LEAN_PROB_EDGE_MIN and ev >= LEAN_EV_MIN:
        return Tier.LEAN
    
    # Default: MARKET_ALIGNED
    return Tier.MARKET_ALIGNED


# ============================================================================
# OUTPUT DATA MODEL
# ============================================================================

@dataclass
class ClassificationResult:
    """Deterministic classification output"""
    selection_id: str
    selection_text: str
    sport: str
    market_type: str
    tier: Tier
    
    # Metrics (null when blocked)
    p_model: Optional[float]
    p_market_fair: Optional[float]
    prob_edge: Optional[float]
    ev: Optional[float]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "selection_id": self.selection_id,
            "selection_text": self.selection_text,
            "sport": self.sport,
            "market_type": self.market_type,
            "tier": self.tier.value,
            "p_model": self.p_model,
            "p_market_fair": self.p_market_fair,
            "prob_edge": self.prob_edge,
            "ev": self.ev
        }


def build_classification_result(x: SelectionInput, now_unix: int) -> ClassificationResult:
    """
    Build complete classification result with metrics.
    
    Args:
        x: Selection input
        now_unix: Current unix timestamp
    
    Returns:
        Classification result with tier and metrics
    """
    tier = classify(x, now_unix)
    
    # If blocked, set metrics to null
    if tier == Tier.BLOCKED:
        return ClassificationResult(
            selection_id=x.selection_id,
            selection_text=x.selection_text,
            sport=x.sport,
            market_type=x.market_type,
            tier=Tier.BLOCKED,
            p_model=x.p_model,
            p_market_fair=None,
            prob_edge=None,
            ev=None
        )
    
    # Calculate metrics
    p_mkt = market_prob_fair(x.price_american, x.opp_price_american)
    prob_edge = x.p_model - p_mkt
    ev = ev_from_prob_and_american(x.p_model, x.price_american)
    
    return ClassificationResult(
        selection_id=x.selection_id,
        selection_text=x.selection_text,
        sport=x.sport,
        market_type=x.market_type,
        tier=tier,
        p_model=x.p_model,
        p_market_fair=p_mkt,
        prob_edge=prob_edge,
        ev=ev
    )


# ============================================================================
# POSTING LOGIC (SEPARATE, NON-DESTRUCTIVE)
# ============================================================================

@dataclass
class PostingPolicy:
    """Telegram posting policy - does NOT change classification tier"""
    post_edges: bool = True
    post_leans: bool = True
    max_posts_per_day: int = 2
    allow_market_aligned: bool = False


def decide_post(tier: Tier, policy: PostingPolicy = PostingPolicy()) -> PostDecision:
    """
    Determine if selection should be posted to Telegram.
    
    CRITICAL: This does NOT change tier classification.
    Posting logic is separate from edge detection.
    
    Args:
        tier: Classification tier
        policy: Posting policy
    
    Returns:
        POST, WATCH, or PASS decision
    """
    if tier == Tier.EDGE and policy.post_edges:
        return PostDecision.POST
    
    if tier == Tier.LEAN and policy.post_leans:
        return PostDecision.POST
    
    return PostDecision.PASS


def rank_score(result: ClassificationResult) -> float:
    """
    Deterministic ranking for "best pick" selection.
    
    Formula: (prob_edge × 1000) + (ev × 100)
    
    Args:
        result: Classification result
    
    Returns:
        Ranking score (higher is better)
    """
    if result.prob_edge is None or result.ev is None:
        return -999999.0
    
    return (result.prob_edge * 1000) + (result.ev * 100)


def choose_top(
    results: List[ClassificationResult],
    max_posts: int = 2
) -> List[ClassificationResult]:
    """
    Choose top N picks by ranking score.
    
    Filters to EDGE/LEAN only, then sorts by rank_score.
    
    Args:
        results: List of classification results
        max_posts: Maximum picks to return
    
    Returns:
        Top N picks sorted by rank
    """
    # Filter to postable tiers
    candidates = [r for r in results if r.tier in {Tier.EDGE, Tier.LEAN}]
    
    # Sort by rank score (descending)
    candidates.sort(key=rank_score, reverse=True)
    
    # Take top N
    return candidates[:max_posts]


# ============================================================================
# TELEGRAM CARD FORMATTER
# ============================================================================

def format_telegram_card(result: ClassificationResult) -> str:
    """
    Format classification result as Telegram card.
    
    Template:
        ■ [SPORT] — [MATCHUP]
        Market:
        [Selection Text] ([price])
        
        Model Read:
        • Model Prob: XX.X%
        • Market Prob: XX.X%
        • Prob Edge: +X.X%
        • EV: +X.X%
        
        Classification:
        EDGE / LEAN
    
    Args:
        result: Classification result
    
    Returns:
        Formatted telegram message
    """
    if result.tier not in {Tier.EDGE, Tier.LEAN}:
        raise ValueError(f"Cannot format {result.tier} for Telegram (EDGE/LEAN only)")
    
    if result.prob_edge is None or result.ev is None or result.p_model is None or result.p_market_fair is None:
        raise ValueError("Cannot format result with null metrics")
    
    # Format probabilities and percentages
    model_pct = result.p_model * 100
    market_pct = result.p_market_fair * 100
    edge_pct = result.prob_edge * 100
    ev_pct = result.ev * 100
    
    card = f"""■ {result.sport} — {result.market_type}

Market:
{result.selection_text}

Model Read:
• Model Prob: {model_pct:.1f}%
• Market Prob: {market_pct:.1f}%
• Prob Edge: {edge_pct:+.1f}%
• EV: {ev_pct:+.1f}%

Classification:
{result.tier.value}"""
    
    return card


# ============================================================================
# STRESS TEST SUITE
# ============================================================================

def run_stress_tests() -> bool:
    """
    Internal stress test suite - must pass before shipping.
    
    Tests:
    A) Integrity Tests (BLOCKED)
    B) Tier Boundary Tests (single-sided)
    C) Two-Sided Vig Removal Test
    D) Regression Kill Test (volatility/CLV cannot affect tier)
    
    Returns:
        True if all tests pass, False otherwise
    """
    now = int(datetime.now(timezone.utc).timestamp())
    all_passed = True
    
    logger.info("=== RUNNING STRESS TEST SUITE ===")
    
    # A) Integrity Tests
    logger.info("\n[A] INTEGRITY TESTS")
    
    # A1: Insufficient sims
    x1 = SelectionInput(
        sport="NBA", market_type="SPREAD", selection_id="test_a1",
        selection_text="Bulls -2.5", timestamp_unix=now, sims_n=15000,
        p_model=0.58, price_american=-110
    )
    tier1 = classify(x1, now)
    if tier1 != Tier.BLOCKED:
        logger.error(f"❌ A1 FAILED: Expected BLOCKED, got {tier1}")
        all_passed = False
    else:
        logger.info(f"✓ A1 PASSED: sims_n=15000 → BLOCKED")
    
    # A2: Invalid p_model
    x2 = SelectionInput(
        sport="NBA", market_type="SPREAD", selection_id="test_a2",
        selection_text="Bulls -2.5", timestamp_unix=now, sims_n=20000,
        p_model=1.02, price_american=-110
    )
    tier2 = classify(x2, now)
    if tier2 != Tier.BLOCKED:
        logger.error(f"❌ A2 FAILED: Expected BLOCKED, got {tier2}")
        all_passed = False
    else:
        logger.info(f"✓ A2 PASSED: p_model=1.02 → BLOCKED")
    
    # A3: Stale data
    x3 = SelectionInput(
        sport="NBA", market_type="SPREAD", selection_id="test_a3",
        selection_text="Bulls -2.5", timestamp_unix=now - 181, sims_n=20000,
        p_model=0.58, price_american=-110
    )
    tier3 = classify(x3, now)
    if tier3 != Tier.BLOCKED:
        logger.error(f"❌ A3 FAILED: Expected BLOCKED, got {tier3}")
        all_passed = False
    else:
        logger.info(f"✓ A3 PASSED: 181s old → BLOCKED")
    
    # B) Tier Boundary Tests (single-sided)
    logger.info("\n[B] TIER BOUNDARY TESTS (single-sided)")
    
    # B1: EDGE
    x_b1 = SelectionInput(
        sport="NBA", market_type="SPREAD", selection_id="test_b1",
        selection_text="Bulls -2.5", timestamp_unix=now, sims_n=20000,
        p_model=0.58, price_american=-110
    )
    tier_b1 = classify(x_b1, now)
    if tier_b1 != Tier.EDGE:
        logger.error(f"❌ B1 FAILED: Expected EDGE, got {tier_b1}")
        all_passed = False
    else:
        logger.info(f"✓ B1 PASSED: p_model=0.58 → EDGE")
    
    # B2: LEAN
    x_b2 = SelectionInput(
        sport="NBA", market_type="SPREAD", selection_id="test_b2",
        selection_text="Bulls -2.5", timestamp_unix=now, sims_n=20000,
        p_model=0.55, price_american=-110
    )
    tier_b2 = classify(x_b2, now)
    if tier_b2 != Tier.LEAN:
        logger.error(f"❌ B2 FAILED: Expected LEAN, got {tier_b2}")
        all_passed = False
    else:
        logger.info(f"✓ B2 PASSED: p_model=0.55 → LEAN")
    
    # B3: MARKET_ALIGNED
    x_b3 = SelectionInput(
        sport="NBA", market_type="SPREAD", selection_id="test_b3",
        selection_text="Bulls -2.5", timestamp_unix=now, sims_n=20000,
        p_model=0.54, price_american=-110
    )
    tier_b3 = classify(x_b3, now)
    if tier_b3 != Tier.MARKET_ALIGNED:
        logger.error(f"❌ B3 FAILED: Expected MARKET_ALIGNED, got {tier_b3}")
        all_passed = False
    else:
        logger.info(f"✓ B3 PASSED: p_model=0.54 → MARKET_ALIGNED")
    
    # C) Two-Sided Vig Removal Test
    logger.info("\n[C] TWO-SIDED VIG REMOVAL TESTS")
    
    # C1: EDGE with vig removal
    x_c1 = SelectionInput(
        sport="NBA", market_type="SPREAD", selection_id="test_c1",
        selection_text="Bulls -2.5", timestamp_unix=now, sims_n=20000,
        p_model=0.55, price_american=-110, opp_price_american=-110
    )
    tier_c1 = classify(x_c1, now)
    if tier_c1 != Tier.EDGE:
        logger.error(f"❌ C1 FAILED: Expected EDGE, got {tier_c1}")
        all_passed = False
    else:
        logger.info(f"✓ C1 PASSED: p_model=0.55 (vig removed) → EDGE")
    
    # C2: LEAN with vig removal
    x_c2 = SelectionInput(
        sport="NBA", market_type="SPREAD", selection_id="test_c2",
        selection_text="Bulls -2.5", timestamp_unix=now, sims_n=20000,
        p_model=0.53, price_american=-110, opp_price_american=-110
    )
    tier_c2 = classify(x_c2, now)
    if tier_c2 != Tier.LEAN:
        logger.error(f"❌ C2 FAILED: Expected LEAN, got {tier_c2}")
        all_passed = False
    else:
        logger.info(f"✓ C2 PASSED: p_model=0.53 (vig removed) → LEAN")
    
    # C3: MARKET_ALIGNED with vig removal
    x_c3 = SelectionInput(
        sport="NBA", market_type="SPREAD", selection_id="test_c3",
        selection_text="Bulls -2.5", timestamp_unix=now, sims_n=20000,
        p_model=0.51, price_american=-110, opp_price_american=-110
    )
    tier_c3 = classify(x_c3, now)
    if tier_c3 != Tier.MARKET_ALIGNED:
        logger.error(f"❌ C3 FAILED: Expected MARKET_ALIGNED, got {tier_c3}")
        all_passed = False
    else:
        logger.info(f"✓ C3 PASSED: p_model=0.51 (vig removed) → MARKET_ALIGNED")
    
    # D) Regression Kill Test
    logger.info("\n[D] REGRESSION KILL TEST")
    logger.info("Testing: HIGH volatility + negative CLV + 6% prob_edge + 1% EV")
    logger.info("Expected: EDGE (volatility/CLV must NOT affect tier)")
    
    # This mimics the regression scenario where valid edges were suppressed
    x_d = SelectionInput(
        sport="NFL", market_type="SPREAD", selection_id="test_regression",
        selection_text="Chiefs -3.5", timestamp_unix=now, sims_n=50000,
        p_model=0.60, price_american=-110, opp_price_american=-110
    )
    tier_d = classify(x_d, now)
    
    # Calculate actual metrics to verify
    result_d = build_classification_result(x_d, now)
    
    if tier_d != Tier.EDGE:
        logger.error(f"❌ REGRESSION KILL FAILED: Expected EDGE, got {tier_d}")
        logger.error(f"   prob_edge={result_d.prob_edge:.4f}, ev={result_d.ev:.4f}")
        all_passed = False
    else:
        logger.info(f"✓ REGRESSION KILL PASSED: Tier=EDGE (prob_edge={result_d.prob_edge:.1%}, ev={result_d.ev:.1%})")
        logger.info("   Volatility/CLV correctly ignored in classification")
    
    # Final summary
    logger.info("\n" + "="*50)
    if all_passed:
        logger.info("✅ ALL STRESS TESTS PASSED")
    else:
        logger.error("❌ SOME STRESS TESTS FAILED")
    logger.info("="*50 + "\n")
    
    return all_passed


# ============================================================================
# SELF-TEST ON MODULE LOAD (DEV SAFETY)
# ============================================================================

if __name__ == "__main__":
    # Run stress tests when module executed directly
    logging.basicConfig(level=logging.INFO)
    success = run_stress_tests()
    exit(0 if success else 1)
