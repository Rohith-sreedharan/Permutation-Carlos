"""
UI DISPLAY CONTRACT - STRESS TEST SUITE
Status: COMPREHENSIVE VALIDATION (LOCKED)
Generated: 2026-02-02

PURPOSE:
Validates UI display contract against all invariants.
Proves UI cannot override or contradict engine tier.

TEST GROUPS:
1. Mutual exclusivity (badges/banners cannot conflict)
2. Tier-by-tier snapshot tests (exact flag validation)
3. Copy linting (prevents forbidden phrases)
"""

import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from backend.services.ui_display_contract import (
    TierClassification,
    ModelDirectionMode,
    compute_ui_display_flags,
    compute_ui_display_copy,
    validate_ui_display_invariants,
    check_copy_violations,
    render_ui_display_state
)


# ==============================================================================
# TEST GROUP 1: MUTUAL EXCLUSIVITY (CRITICAL INVARIANTS)
# ==============================================================================

def test_mutual_exclusivity_edge():
    """EDGE: Official badge and market aligned banner can never both be true."""
    flags = compute_ui_display_flags(TierClassification.EDGE)
    
    # CRITICAL: These two can NEVER both be True
    assert not (flags.show_official_edge_badge and flags.show_market_aligned_banner), \
        "FAILED: show_official_edge_badge and show_market_aligned_banner both True"
    
    # For EDGE specifically
    assert flags.show_official_edge_badge == True
    assert flags.show_market_aligned_banner == False
    
    print("✅ Test 1.1 PASSED: EDGE - mutual exclusivity")


def test_mutual_exclusivity_lean():
    """LEAN: Lean badge and market aligned banner can never both be true."""
    flags = compute_ui_display_flags(TierClassification.LEAN)
    
    # CRITICAL: These two can NEVER both be True
    assert not (flags.show_lean_badge and flags.show_market_aligned_banner), \
        "FAILED: show_lean_badge and show_market_aligned_banner both True"
    
    # For LEAN specifically
    assert flags.show_lean_badge == True
    assert flags.show_market_aligned_banner == False
    assert flags.show_official_edge_badge == False
    
    print("✅ Test 1.2 PASSED: LEAN - mutual exclusivity")


def test_mutual_exclusivity_market_aligned():
    """MARKET_ALIGNED: Market aligned banner must be true, all edge badges false."""
    flags = compute_ui_display_flags(TierClassification.MARKET_ALIGNED)
    
    # CRITICAL: No edge badges when market aligned
    assert flags.show_market_aligned_banner == True
    assert flags.show_official_edge_badge == False
    assert flags.show_lean_badge == False
    
    print("✅ Test 1.3 PASSED: MARKET_ALIGNED - mutual exclusivity")


def test_mutual_exclusivity_blocked():
    """BLOCKED: Blocked banner must be true, all other banners false."""
    flags = compute_ui_display_flags(TierClassification.BLOCKED)
    
    # CRITICAL: Only blocked banner shown
    assert flags.show_blocked_banner == True
    assert flags.show_official_edge_badge == False
    assert flags.show_lean_badge == False
    assert flags.show_market_aligned_banner == False
    
    print("✅ Test 1.4 PASSED: BLOCKED - mutual exclusivity")


def test_action_summary_official_edge_only_for_edge():
    """Action summary 'official edge' can ONLY be true when tier == EDGE."""
    
    # EDGE: should be True
    edge_flags = compute_ui_display_flags(TierClassification.EDGE)
    assert edge_flags.show_action_summary_official_edge == True
    
    # LEAN: must be False
    lean_flags = compute_ui_display_flags(TierClassification.LEAN)
    assert lean_flags.show_action_summary_official_edge == False
    
    # MARKET_ALIGNED: must be False
    ma_flags = compute_ui_display_flags(TierClassification.MARKET_ALIGNED)
    assert ma_flags.show_action_summary_official_edge == False
    
    # BLOCKED: must be False
    blocked_flags = compute_ui_display_flags(TierClassification.BLOCKED)
    assert blocked_flags.show_action_summary_official_edge == False
    
    print("✅ Test 1.5 PASSED: show_action_summary_official_edge only True for EDGE")


def test_no_valid_edge_detected_never_for_edge_lean():
    """'No valid edge detected' can NEVER be true when tier is EDGE or LEAN."""
    
    # EDGE: must be False
    edge_flags = compute_ui_display_flags(TierClassification.EDGE)
    assert edge_flags.show_no_valid_edge_detected == False
    
    # LEAN: must be False
    lean_flags = compute_ui_display_flags(TierClassification.LEAN)
    assert lean_flags.show_no_valid_edge_detected == False
    
    # MARKET_ALIGNED: should be True
    ma_flags = compute_ui_display_flags(TierClassification.MARKET_ALIGNED)
    assert ma_flags.show_no_valid_edge_detected == True
    
    # BLOCKED: False (different message)
    blocked_flags = compute_ui_display_flags(TierClassification.BLOCKED)
    assert blocked_flags.show_no_valid_edge_detected == False
    
    print("✅ Test 1.6 PASSED: show_no_valid_edge_detected never True for EDGE/LEAN")


# ==============================================================================
# TEST GROUP 2: TIER-BY-TIER SNAPSHOT TESTS (EXACT FLAG VALIDATION)
# ==============================================================================

def test_edge_snapshot():
    """EDGE tier: Complete snapshot of all flags."""
    flags = compute_ui_display_flags(TierClassification.EDGE)
    copy = compute_ui_display_copy(TierClassification.EDGE)
    
    # Header badges
    assert flags.show_official_edge_badge == True, "EDGE must show official badge"
    assert flags.show_lean_badge == False
    assert flags.show_market_aligned_banner == False, "EDGE must NOT show market aligned"
    assert flags.show_blocked_banner == False
    
    # Panels
    assert flags.show_model_preference_panel == True, "EDGE must show Model Preference"
    assert flags.model_direction_mode == ModelDirectionMode.MIRROR_OFFICIAL, \
        "EDGE Model Direction must MIRROR official selection"
    
    # Action summary
    assert flags.show_action_summary_official_edge == True
    assert flags.show_action_summary_lean == False
    assert flags.show_no_valid_edge_detected == False
    
    # Telegram
    assert flags.show_telegram_cta == True, "EDGE is post-eligible"
    assert flags.show_post_eligible_indicator == True
    
    # Metrics
    assert flags.show_cover_prob == True
    assert flags.show_win_prob == True
    assert flags.show_ev == True
    assert flags.show_prob_edge == True
    
    # Copy
    assert "OFFICIAL EDGE" in copy.header_text
    assert copy.action_summary is not None
    assert "official" in copy.action_summary.lower()
    
    # Forbidden patterns
    assert "MARKET ALIGNED" in flags.forbidden_copy_patterns
    assert "NO EDGE" in flags.forbidden_copy_patterns
    
    print("✅ Test 2.1 PASSED: EDGE snapshot - all flags correct")


def test_lean_snapshot():
    """LEAN tier: Complete snapshot of all flags."""
    flags = compute_ui_display_flags(TierClassification.LEAN)
    copy = compute_ui_display_copy(TierClassification.LEAN)
    
    # Header badges
    assert flags.show_official_edge_badge == False, "LEAN is NOT official edge"
    assert flags.show_lean_badge == True, "LEAN must show lean badge"
    assert flags.show_market_aligned_banner == False
    assert flags.show_blocked_banner == False
    
    # Panels
    assert flags.show_model_preference_panel == True, "LEAN must show Model Preference"
    assert flags.model_direction_mode == ModelDirectionMode.MIRROR_OFFICIAL, \
        "LEAN Model Direction must match official selection"
    
    # Action summary
    assert flags.show_action_summary_official_edge == False, "LEAN is NOT official edge"
    assert flags.show_action_summary_lean == True
    assert flags.show_no_valid_edge_detected == False
    
    # Telegram
    assert flags.show_telegram_cta == False, "LEAN typically not auto-posted"
    assert flags.show_post_eligible_indicator == False
    
    # Copy
    assert "LEAN" in copy.header_text
    assert "caution" in copy.summary_text.lower() or "soft" in copy.summary_text.lower()
    
    # Forbidden patterns
    assert "OFFICIAL EDGE" in flags.forbidden_copy_patterns
    assert "Official edge" in flags.forbidden_copy_patterns
    
    print("✅ Test 2.2 PASSED: LEAN snapshot - all flags correct")


def test_market_aligned_snapshot():
    """MARKET_ALIGNED tier: Complete snapshot of all flags."""
    flags = compute_ui_display_flags(TierClassification.MARKET_ALIGNED)
    copy = compute_ui_display_copy(TierClassification.MARKET_ALIGNED)
    
    # Header badges
    assert flags.show_official_edge_badge == False
    assert flags.show_lean_badge == False
    assert flags.show_market_aligned_banner == True, "MARKET_ALIGNED must show banner"
    assert flags.show_blocked_banner == False
    
    # Panels
    assert flags.show_model_preference_panel == False, "No preference when market aligned"
    assert flags.model_direction_mode == ModelDirectionMode.INFORMATIONAL_ONLY, \
        "Model Direction must be informational only"
    
    # Action summary
    assert flags.show_action_summary_official_edge == False
    assert flags.show_action_summary_lean == False
    assert flags.show_no_valid_edge_detected == True, "Must show 'no edge detected'"
    
    # Telegram
    assert flags.show_telegram_cta == False
    assert flags.show_post_eligible_indicator == False
    
    # Copy
    assert "MARKET ALIGNED" in copy.header_text or "NO EDGE" in copy.header_text
    assert "No valid edge" in copy.summary_text or "efficiently priced" in copy.summary_text
    assert copy.disclaimer is not None, "Must have disclaimer for informational data"
    
    # Forbidden patterns (THIS IS THE KEY FIX)
    # More specific patterns to avoid false positives in disclaimers
    assert "OFFICIAL EDGE" in flags.forbidden_copy_patterns
    assert "Official edge" in flags.forbidden_copy_patterns
    assert "TAKE_POINTS" in flags.forbidden_copy_patterns or "Take the points" in flags.forbidden_copy_patterns
    assert "Action Summary: Official" in flags.forbidden_copy_patterns or "official spread edge" in flags.forbidden_copy_patterns
    
    print("✅ Test 2.3 PASSED: MARKET_ALIGNED snapshot - all flags correct")


def test_market_aligned_with_big_gap():
    """MARKET_ALIGNED with large gap: Informational gap shown with disclaimer."""
    gap_pts = 7.2
    flags = compute_ui_display_flags(TierClassification.MARKET_ALIGNED, gap_pts=gap_pts)
    copy = compute_ui_display_copy(TierClassification.MARKET_ALIGNED, gap_pts=gap_pts)
    
    # Must still show market aligned (not edge)
    assert flags.show_market_aligned_banner == True
    assert flags.show_official_edge_badge == False
    
    # Informational gap shown
    assert flags.show_informational_gap == True, "Large gap should show informational note"
    
    # Copy must include gap mention
    assert "gap" in copy.summary_text.lower()
    assert "informational" in copy.summary_text.lower()
    
    # Still forbidden to show "official edge" (not just "official" in disclaimers)
    assert "OFFICIAL EDGE" in flags.forbidden_copy_patterns or "Official edge" in flags.forbidden_copy_patterns
    
    print("✅ Test 2.4 PASSED: MARKET_ALIGNED with big gap - informational only")


def test_blocked_snapshot():
    """BLOCKED tier: Complete snapshot of all flags."""
    flags = compute_ui_display_flags(TierClassification.BLOCKED)
    copy = compute_ui_display_copy(TierClassification.BLOCKED, block_reason="Stale odds detected")
    
    # Header badges
    assert flags.show_official_edge_badge == False
    assert flags.show_lean_badge == False
    assert flags.show_market_aligned_banner == False
    assert flags.show_blocked_banner == True, "BLOCKED must show blocked banner"
    
    # Panels
    assert flags.show_model_preference_panel == False
    assert flags.model_direction_mode == ModelDirectionMode.HIDDEN, "No Model Direction when blocked"
    
    # Action summary
    assert flags.show_action_summary_official_edge == False
    assert flags.show_action_summary_lean == False
    assert flags.show_no_valid_edge_detected == False
    
    # Telegram
    assert flags.show_telegram_cta == False
    assert flags.show_post_eligible_indicator == False
    
    # Metrics (all hidden)
    assert flags.show_cover_prob == False
    assert flags.show_win_prob == False
    assert flags.show_ev == False
    assert flags.show_prob_edge == False
    
    # Copy
    assert "BLOCKED" in copy.header_text
    assert "Stale odds" in copy.summary_text
    
    print("✅ Test 2.5 PASSED: BLOCKED snapshot - all flags correct")


# ==============================================================================
# TEST GROUP 3: COPY LINTING (PREVENTS FORBIDDEN PHRASES)
# ==============================================================================

def test_copy_linting_market_aligned_forbids_official():
    """MARKET_ALIGNED: Must forbid 'OFFICIAL EDGE' and 'Official edge' in rendered text."""
    flags = compute_ui_display_flags(TierClassification.MARKET_ALIGNED)
    
    # Simulate bad UI rendering (regression case)
    bad_text = """
    MARKET ALIGNED — NO EDGE
    
    But wait! OFFICIAL EDGE detected in spread!
    Action Summary: Official spread edge — take the points!
    """
    
    violations = check_copy_violations(bad_text, flags)
    
    # Should catch violations
    assert len(violations) > 0, "Should detect 'OFFICIAL EDGE' violation"
    assert any("OFFICIAL EDGE" in v for v in violations), "Should specifically catch 'OFFICIAL EDGE'"
    assert any("official spread edge" in v for v in violations)
    
    print("✅ Test 3.1 PASSED: MARKET_ALIGNED copy linting - 'OFFICIAL EDGE' caught")


def test_copy_linting_market_aligned_forbids_take_points():
    """MARKET_ALIGNED: Must forbid 'TAKE_POINTS', 'Take the points', 'Lay the points'."""
    flags = compute_ui_display_flags(TierClassification.MARKET_ALIGNED)
    
    bad_text = "MARKET ALIGNED but Take the points — gap validated edge"
    violations = check_copy_violations(bad_text, flags)
    
    assert len(violations) > 0, "Should detect 'Take the points' violation"
    
    print("✅ Test 3.2 PASSED: MARKET_ALIGNED copy linting - 'Take the points' caught")


def test_copy_linting_lean_forbids_official_edge():
    """LEAN: Must forbid 'OFFICIAL EDGE' or 'Official edge'."""
    flags = compute_ui_display_flags(TierClassification.LEAN)
    
    bad_text = "LEAN — but actually this is an OFFICIAL EDGE"
    violations = check_copy_violations(bad_text, flags)
    
    assert len(violations) > 0, "Should detect 'OFFICIAL EDGE' violation"
    
    print("✅ Test 3.3 PASSED: LEAN copy linting - 'OFFICIAL EDGE' caught")


def test_copy_linting_edge_forbids_market_aligned():
    """EDGE: Must forbid 'MARKET ALIGNED' and 'NO EDGE'."""
    flags = compute_ui_display_flags(TierClassification.EDGE)
    
    bad_text = "OFFICIAL EDGE but also MARKET ALIGNED — NO EDGE"
    violations = check_copy_violations(bad_text, flags)
    
    assert len(violations) > 0, "Should detect 'MARKET ALIGNED' and 'NO EDGE' violations"
    
    print("✅ Test 3.4 PASSED: EDGE copy linting - 'MARKET ALIGNED' caught")


def test_copy_linting_clean_edge_passes():
    """EDGE: Clean copy should pass validation."""
    flags = compute_ui_display_flags(TierClassification.EDGE)
    
    clean_text = """
    ✅ OFFICIAL EDGE
    
    Official spread edge detected. Supporting metrics: cover probability,
    win probability, EV, prob-edge. Model Preference (This Market) highlights
    the official selection.
    
    Action Summary: Official edge — post eligible
    """
    
    violations = check_copy_violations(clean_text, flags)
    
    assert len(violations) == 0, f"Clean EDGE copy should pass, got: {violations}"
    
    print("✅ Test 3.5 PASSED: EDGE clean copy - no violations")


def test_copy_linting_clean_market_aligned_passes():
    """MARKET_ALIGNED: Clean copy should pass validation."""
    flags = compute_ui_display_flags(TierClassification.MARKET_ALIGNED)
    
    clean_text = """
    🔵 MARKET ALIGNED — NO EDGE
    
    No valid edge detected. Market efficiently priced.
    
    Probabilities and fair line shown for informational purposes only.
    This is NOT an official play.
    
    Model Direction (Informational only — not an official play)
    """
    
    violations = check_copy_violations(clean_text, flags)
    
    assert len(violations) == 0, f"Clean MARKET_ALIGNED copy should pass, got: {violations}"
    
    print("✅ Test 3.6 PASSED: MARKET_ALIGNED clean copy - no violations")


# ==============================================================================
# TEST GROUP 4: INVARIANT VALIDATION (HARD ASSERTIONS)
# ==============================================================================

def test_validate_invariants_edge_valid():
    """EDGE flags should pass all invariant checks."""
    flags = compute_ui_display_flags(TierClassification.EDGE)
    errors = validate_ui_display_invariants(flags)
    
    assert len(errors) == 0, f"EDGE should pass all invariants, got: {errors}"
    
    print("✅ Test 4.1 PASSED: EDGE invariants - all valid")


def test_validate_invariants_lean_valid():
    """LEAN flags should pass all invariant checks."""
    flags = compute_ui_display_flags(TierClassification.LEAN)
    errors = validate_ui_display_invariants(flags)
    
    assert len(errors) == 0, f"LEAN should pass all invariants, got: {errors}"
    
    print("✅ Test 4.2 PASSED: LEAN invariants - all valid")


def test_validate_invariants_market_aligned_valid():
    """MARKET_ALIGNED flags should pass all invariant checks."""
    flags = compute_ui_display_flags(TierClassification.MARKET_ALIGNED)
    errors = validate_ui_display_invariants(flags)
    
    assert len(errors) == 0, f"MARKET_ALIGNED should pass all invariants, got: {errors}"
    
    print("✅ Test 4.3 PASSED: MARKET_ALIGNED invariants - all valid")


def test_validate_invariants_blocked_valid():
    """BLOCKED flags should pass all invariant checks."""
    flags = compute_ui_display_flags(TierClassification.BLOCKED)
    errors = validate_ui_display_invariants(flags)
    
    assert len(errors) == 0, f"BLOCKED should pass all invariants, got: {errors}"
    
    print("✅ Test 4.4 PASSED: BLOCKED invariants - all valid")


def test_validate_invariants_catches_contradiction():
    """Invariant validator should catch manual flag contradictions."""
    from backend.services.ui_display_contract import UIDisplayFlags
    
    # Manually create contradictory flags
    bad_flags = UIDisplayFlags(
        show_official_edge_badge=True,  # EDGE
        show_lean_badge=False,
        show_market_aligned_banner=True,  # Also MARKET_ALIGNED! Contradiction!
        show_blocked_banner=False,
        show_model_preference_panel=True,
        model_direction_mode=ModelDirectionMode.MIRROR_OFFICIAL,
        show_action_summary_official_edge=True,
        show_action_summary_lean=False,
        show_no_valid_edge_detected=False,
        show_telegram_cta=True,
        show_post_eligible_indicator=True,
        show_cover_prob=True,
        show_win_prob=True,
        show_ev=True,
        show_prob_edge=True,
        show_informational_gap=False,
        forbidden_copy_patterns=[],
        tier=TierClassification.EDGE
    )
    
    errors = validate_ui_display_invariants(bad_flags)
    
    assert len(errors) > 0, "Should detect contradiction"
    assert any("mutual exclusivity" in e.lower() for e in errors), \
        "Should specifically catch mutual exclusivity violation"
    
    print("✅ Test 4.5 PASSED: Invariant validator - catches contradictions")


# ==============================================================================
# TEST GROUP 5: END-TO-END RENDER VALIDATION
# ==============================================================================

def test_render_ui_display_state_edge():
    """End-to-end: Render complete UI state for EDGE."""
    state = render_ui_display_state(TierClassification.EDGE)
    
    assert state['is_valid'] == True, "EDGE state should be valid"
    assert len(state['validation_errors']) == 0
    assert state['tier'] == TierClassification.EDGE
    
    # Flags
    assert state['flags'].show_official_edge_badge == True
    assert state['flags'].show_market_aligned_banner == False
    
    # Copy
    assert "OFFICIAL EDGE" in state['copy'].header_text
    
    print("✅ Test 5.1 PASSED: End-to-end render - EDGE")


def test_render_ui_display_state_market_aligned_with_gap():
    """End-to-end: Render complete UI state for MARKET_ALIGNED with gap."""
    state = render_ui_display_state(
        TierClassification.MARKET_ALIGNED,
        gap_pts=7.2
    )
    
    assert state['is_valid'] == True, "MARKET_ALIGNED state should be valid"
    assert len(state['validation_errors']) == 0
    assert state['tier'] == TierClassification.MARKET_ALIGNED
    
    # Flags
    assert state['flags'].show_market_aligned_banner == True
    assert state['flags'].show_official_edge_badge == False
    assert state['flags'].show_informational_gap == True
    
    # Copy
    assert "gap" in state['copy'].summary_text.lower()
    assert "informational" in state['copy'].summary_text.lower()
    
    print("✅ Test 5.2 PASSED: End-to-end render - MARKET_ALIGNED with gap")


def test_render_ui_display_state_blocked():
    """End-to-end: Render complete UI state for BLOCKED."""
    state = render_ui_display_state(
        TierClassification.BLOCKED,
        block_reason="Stale odds detected (last update > 5 minutes)"
    )
    
    assert state['is_valid'] == True, "BLOCKED state should be valid"
    assert len(state['validation_errors']) == 0
    assert state['tier'] == TierClassification.BLOCKED
    
    # Flags
    assert state['flags'].show_blocked_banner == True
    assert state['flags'].show_official_edge_badge == False
    assert state['flags'].model_direction_mode == ModelDirectionMode.HIDDEN
    
    # Copy
    assert "BLOCKED" in state['copy'].header_text
    assert "Stale odds" in state['copy'].summary_text
    
    print("✅ Test 5.3 PASSED: End-to-end render - BLOCKED")


# ==============================================================================
# MAIN TEST RUNNER
# ==============================================================================

if __name__ == '__main__':
    print("\n" + "="*80)
    print("UI DISPLAY CONTRACT - STRESS TEST SUITE")
    print("="*80 + "\n")
    
    # Group 1: Mutual Exclusivity
    print("\n📊 TEST GROUP 1: MUTUAL EXCLUSIVITY (CRITICAL INVARIANTS)")
    print("-" * 80)
    test_mutual_exclusivity_edge()
    test_mutual_exclusivity_lean()
    test_mutual_exclusivity_market_aligned()
    test_mutual_exclusivity_blocked()
    test_action_summary_official_edge_only_for_edge()
    test_no_valid_edge_detected_never_for_edge_lean()
    
    # Group 2: Tier-by-Tier Snapshots
    print("\n📊 TEST GROUP 2: TIER-BY-TIER SNAPSHOT TESTS")
    print("-" * 80)
    test_edge_snapshot()
    test_lean_snapshot()
    test_market_aligned_snapshot()
    test_market_aligned_with_big_gap()
    test_blocked_snapshot()
    
    # Group 3: Copy Linting
    print("\n📊 TEST GROUP 3: COPY LINTING (FORBIDDEN PHRASES)")
    print("-" * 80)
    test_copy_linting_market_aligned_forbids_official()
    test_copy_linting_market_aligned_forbids_take_points()
    test_copy_linting_lean_forbids_official_edge()
    test_copy_linting_edge_forbids_market_aligned()
    test_copy_linting_clean_edge_passes()
    test_copy_linting_clean_market_aligned_passes()
    
    # Group 4: Invariant Validation
    print("\n📊 TEST GROUP 4: INVARIANT VALIDATION (HARD ASSERTIONS)")
    print("-" * 80)
    test_validate_invariants_edge_valid()
    test_validate_invariants_lean_valid()
    test_validate_invariants_market_aligned_valid()
    test_validate_invariants_blocked_valid()
    test_validate_invariants_catches_contradiction()
    
    # Group 5: End-to-End Render
    print("\n📊 TEST GROUP 5: END-TO-END RENDER VALIDATION")
    print("-" * 80)
    test_render_ui_display_state_edge()
    test_render_ui_display_state_market_aligned_with_gap()
    test_render_ui_display_state_blocked()
    
    # Summary
    print("\n" + "="*80)
    print("✅ ALL 24 TESTS PASSED")
    print("="*80)
    print("\nCANONICAL INVARIANTS VALIDATED:")
    print("  ✅ 1. Single source of truth (engine tier → UI flags)")
    print("  ✅ 2. Mutual exclusivity (EDGE badge + MARKET_ALIGNED banner never both true)")
    print("  ✅ 3. No tier overrides (UI cannot show 'official edge' when tier != EDGE)")
    print("  ✅ 4. Copy consistency (forbidden patterns blocked)")
    print("\n🚀 READY FOR DEPLOYMENT\n")
