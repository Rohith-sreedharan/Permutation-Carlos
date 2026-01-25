"""
core/ev_calculator.py
Expected Value (EV) calculation - standardized formulas.

Convention: EV = expected profit per $100 wagered, expressed as percentage.

vFinal.1 Multi-Sport Patch Implementation
"""


def compute_ev_2way(
    win_probability_pct: float,
    push_probability_pct: float,
    american_odds: int
) -> float:
    """
    Compute EV for 2-way market (spread, total, 2-way moneyline).
    
    Formula:
        EV = P(win) × payout - P(loss) × 100
        
    Where:
        P(win) = win_probability_pct / 100
        P(push) = push_probability_pct / 100
        P(loss) = 1 - P(win) - P(push)
        payout = profit on $100 wager at given odds
    
    Args:
        win_probability_pct: Probability of winning (0-100)
        push_probability_pct: Probability of push (0-100)
        american_odds: American odds (e.g., -110, +150)
    
    Returns:
        EV as percentage of $100 wager
    
    Examples:
        50% win, 0% push, -110 odds → -4.55% EV (house edge)
        52.38% win, 0% push, -110 odds → ~0% EV (break-even)
        55% win, 0% push, -110 odds → +4.55% EV (player edge)
    """
    win_prob = win_probability_pct / 100.0
    push_prob = push_probability_pct / 100.0
    loss_prob = 1.0 - win_prob - push_prob
    
    # Validate probabilities
    if loss_prob < 0 or loss_prob > 1:
        raise ValueError(
            f"Invalid probabilities: win={win_probability_pct}, "
            f"push={push_probability_pct}, loss={loss_prob*100}"
        )
    
    # Calculate payout on $100 wager
    if american_odds < 0:
        # Favorite: risk |odds| to win $100
        # Payout on $100 = 100 / (|odds| / 100) = 10000 / |odds|
        payout = 10000.0 / abs(american_odds)
    else:
        # Underdog: risk $100 to win odds
        # Payout on $100 = odds
        payout = float(american_odds)
    
    # EV = E[profit] on $100 wager
    ev = (win_prob * payout) - (loss_prob * 100.0)
    
    return ev


def compute_ev_3way(
    win_probability_pct: float,
    draw_probability_pct: float,
    loss_probability_pct: float,
    american_odds: int
) -> float:
    """
    Compute EV for 3-way market (soccer moneyline with draw).
    
    Formula:
        EV = P(win) × payout - P(loss) × 100 - P(draw) × 100
        
    Draw is a loss for moneyline_3way (unlike 2-way where tie = push).
    """
    win_prob = win_probability_pct / 100.0
    draw_prob = draw_probability_pct / 100.0
    loss_prob = loss_probability_pct / 100.0
    
    # Validate
    total = win_prob + draw_prob + loss_prob
    if abs(total - 1.0) > 0.001:
        raise ValueError(f"Probabilities sum to {total*100}%, not 100%")
    
    # Payout
    if american_odds < 0:
        payout = 10000.0 / abs(american_odds)
    else:
        payout = float(american_odds)
    
    # EV (draw and loss both lose stake)
    ev = (win_prob * payout) - (loss_prob * 100.0) - (draw_prob * 100.0)
    
    return ev


def american_odds_to_implied_prob(american_odds: int) -> float:
    """
    Convert American odds to implied probability (0-100 scale).
    
    Args:
        american_odds: American odds (e.g., -110, +150)
    
    Returns:
        Implied probability percentage (0-100)
    """
    if american_odds < 0:
        # Favorite
        implied = abs(american_odds) / (abs(american_odds) + 100) * 100
    else:
        # Underdog
        implied = 100 / (american_odds + 100) * 100
    
    return implied


def validate_symmetry(
    prob_a: float,
    prob_b: float,
    prob_push: float,
    n_sims: int = 10000
) -> None:
    """
    Validate that probabilities sum to 100% within tolerance.
    
    Tolerance accounts for:
    1. Floating-point rounding (negligible with modern precision)
    2. Monte Carlo sampling variance: ~1/sqrt(n)
    
    Tolerance: max(0.15%, 2 × sqrt(1/n) × 100)
    
    Raises ValueError if symmetry violated.
    """
    total = prob_a + prob_b + prob_push
    
    # Adaptive tolerance
    base_tolerance = 0.15  # percentage points
    sampling_tolerance = 2.0 * (1.0 / (n_sims ** 0.5)) * 100.0
    tolerance = max(base_tolerance, sampling_tolerance)
    
    deviation = abs(total - 100.0)
    
    if deviation > tolerance:
        raise ValueError(
            f"Symmetry violation: sum={total:.4f}% (tolerance={tolerance:.4f}%)\n"
            f"prob_a={prob_a:.4f}%, prob_b={prob_b:.4f}%, prob_push={prob_push:.4f}%"
        )


# ============================================================================
# SANITY CHECKS (MUST PASS)
# ============================================================================

if __name__ == "__main__":
    # Test: 50% at -110 is negative
    ev = compute_ev_2way(50.0, 0.0, -110)
    assert -5.0 < ev < -4.0, f"Expected ~-4.55%, got {ev:.2f}%"
    
    # Test: Break-even
    ev = compute_ev_2way(52.38, 0.0, -110)
    assert abs(ev) < 0.5, f"Expected ~0%, got {ev:.2f}%"
    
    # Test: Positive EV
    ev = compute_ev_2way(55.0, 0.0, -110)
    assert ev > 4.0, f"Expected >4%, got {ev:.2f}%"
    
    # Test: Symmetry validation (valid)
    try:
        validate_symmetry(62.3, 36.2, 1.5, n_sims=10000)
        print("✓ Symmetry validation passed")
    except ValueError as e:
        assert False, f"Symmetry validation failed: {e}"
    
    # Test: Symmetry validation (invalid)
    try:
        validate_symmetry(62.3, 36.2, 5.0, n_sims=10000)
        assert False, "Should have raised ValueError"
    except ValueError:
        print("✓ Symmetry violation detected correctly")
    
    print("✓ All EV calculator sanity checks passed")
