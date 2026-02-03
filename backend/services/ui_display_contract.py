"""
UI DISPLAY CONTRACT v1.0 - TRUTH-MAPPING STATE MACHINE
Status: HARD-CODED (LOCKED)
Generated: 2026-02-02

PURPOSE:
Prevents UI contradictions by enforcing strict display rules based on engine tier.
UI is FORBIDDEN from creating its own tier - must use engine output only.

CANONICAL INVARIANTS:
1. Single source of truth: Engine produces tier, UI obeys
2. Mutual exclusivity: EDGE badge and MARKET_ALIGNED banner never both show
3. No tier overrides: UI cannot show "official edge" when tier != EDGE
4. Copy consistency: Text must match tier classification

TIER STATES:
- EDGE: Official edge detected, post-eligible
- LEAN: Soft edge, proceed with caution
- MARKET_ALIGNED: No edge detected, market efficiently priced
- BLOCKED: Invalid state (stale odds, missing data, failed risk controls)
"""

from dataclasses import dataclass
from typing import Optional, List
from enum import Enum


class TierClassification(str, Enum):
    """Engine tier classification (single source of truth)."""
    EDGE = "EDGE"
    LEAN = "LEAN"
    MARKET_ALIGNED = "MARKET_ALIGNED"
    BLOCKED = "BLOCKED"


class ModelDirectionMode(str, Enum):
    """How to display Model Direction panel."""
    MIRROR_OFFICIAL = "MIRROR_OFFICIAL"  # Show same as Model Preference (EDGE/LEAN)
    INFORMATIONAL_ONLY = "INFORMATIONAL_ONLY"  # Show but labeled "informational only" (MARKET_ALIGNED)
    HIDDEN = "HIDDEN"  # Don't show at all (BLOCKED)


@dataclass
class UIDisplayFlags:
    """
    Hard-coded display flags based on tier.
    
    UI MUST use these flags - forbidden from computing own tier or creating
    conflicting display logic.
    
    CRITICAL RULES:
    - show_official_edge_badge and show_market_aligned_banner can NEVER both be True
    - show_action_summary_official_edge can ONLY be True when tier == EDGE
    - show_no_valid_edge_detected can NEVER be True when tier in {EDGE, LEAN}
    """
    
    # Header badges
    show_official_edge_badge: bool
    show_lean_badge: bool
    show_market_aligned_banner: bool
    show_blocked_banner: bool
    
    # Model Preference panel
    show_model_preference_panel: bool
    
    # Model Direction panel
    model_direction_mode: ModelDirectionMode
    
    # Action summary / Final Unified Summary
    show_action_summary_official_edge: bool
    show_action_summary_lean: bool
    show_no_valid_edge_detected: bool
    
    # Telegram/Post eligibility
    show_telegram_cta: bool
    show_post_eligible_indicator: bool
    
    # Supporting metrics
    show_cover_prob: bool
    show_win_prob: bool
    show_ev: bool
    show_prob_edge: bool
    
    # Informational gap (when gap_pts large but MARKET_ALIGNED)
    show_informational_gap: bool
    
    # Copy/text restrictions
    forbidden_copy_patterns: List[str]
    
    # Original tier (for validation)
    tier: TierClassification


@dataclass
class UIDisplayCopy:
    """
    Canonical copy templates for each tier.
    
    UI MUST use these templates - forbidden from generating conflicting copy.
    """
    
    header_text: str
    summary_text: str
    model_direction_label: Optional[str]
    action_summary: Optional[str]
    disclaimer: Optional[str]


def compute_ui_display_flags(
    tier: TierClassification,
    gap_pts: Optional[float] = None
) -> UIDisplayFlags:
    """
    Compute UI display flags from engine tier.
    
    HARD-CODED RULES - DO NOT MODIFY WITHOUT SPEC UPDATE.
    
    Args:
        tier: Engine tier classification (SINGLE SOURCE OF TRUTH)
        gap_pts: Optional gap between model fair line and market line (for informational display)
    
    Returns:
        UIDisplayFlags with hard-coded display rules
    
    Example:
        >>> flags = compute_ui_display_flags(TierClassification.EDGE)
        >>> assert flags.show_official_edge_badge == True
        >>> assert flags.show_market_aligned_banner == False
        >>> assert flags.show_telegram_cta == True
    """
    
    if tier == TierClassification.EDGE:
        return UIDisplayFlags(
            # Header badges
            show_official_edge_badge=True,
            show_lean_badge=False,
            show_market_aligned_banner=False,
            show_blocked_banner=False,
            
            # Model Preference panel
            show_model_preference_panel=True,
            
            # Model Direction panel (MUST match official selection)
            model_direction_mode=ModelDirectionMode.MIRROR_OFFICIAL,
            
            # Action summary
            show_action_summary_official_edge=True,
            show_action_summary_lean=False,
            show_no_valid_edge_detected=False,
            
            # Telegram/Post eligibility
            show_telegram_cta=True,
            show_post_eligible_indicator=True,
            
            # Supporting metrics
            show_cover_prob=True,
            show_win_prob=True,
            show_ev=True,
            show_prob_edge=True,
            
            # Informational gap
            show_informational_gap=False,  # Not needed when EDGE
            
            # Forbidden copy patterns
            forbidden_copy_patterns=[
                "MARKET ALIGNED",
                "NO EDGE",
                "No valid edge detected",
                "market efficiently priced",
                "blocked by risk controls"  # Risk controls can exist but worded as execution/sizing
            ],
            
            # Original tier
            tier=tier
        )
    
    elif tier == TierClassification.LEAN:
        return UIDisplayFlags(
            # Header badges
            show_official_edge_badge=False,
            show_lean_badge=True,
            show_market_aligned_banner=False,
            show_blocked_banner=False,
            
            # Model Preference panel
            show_model_preference_panel=True,
            
            # Model Direction panel (MUST match official selection)
            model_direction_mode=ModelDirectionMode.MIRROR_OFFICIAL,
            
            # Action summary
            show_action_summary_official_edge=False,
            show_action_summary_lean=True,
            show_no_valid_edge_detected=False,
            
            # Telegram/Post eligibility
            show_telegram_cta=False,  # LEAN may not be auto-posted
            show_post_eligible_indicator=False,
            
            # Supporting metrics
            show_cover_prob=True,
            show_win_prob=True,
            show_ev=True,
            show_prob_edge=True,
            
            # Informational gap
            show_informational_gap=False,
            
            # Forbidden copy patterns
            forbidden_copy_patterns=[
                "MARKET ALIGNED",
                "NO EDGE",
                "No valid edge detected",
                "OFFICIAL EDGE",  # LEAN is not "official edge"
                "Official edge"
            ],
            
            # Original tier
            tier=tier
        )
    
    elif tier == TierClassification.MARKET_ALIGNED:
        # Special case: large gap but still market aligned
        show_gap = False
        if gap_pts is not None and abs(gap_pts) > 5.0:
            show_gap = True
        
        return UIDisplayFlags(
            # Header badges
            show_official_edge_badge=False,
            show_lean_badge=False,
            show_market_aligned_banner=True,
            show_blocked_banner=False,
            
            # Model Preference panel
            show_model_preference_panel=False,  # No preference when market aligned
            
            # Model Direction panel (informational only with disclaimer)
            model_direction_mode=ModelDirectionMode.INFORMATIONAL_ONLY,
            
            # Action summary
            show_action_summary_official_edge=False,
            show_action_summary_lean=False,
            show_no_valid_edge_detected=True,
            
            # Telegram/Post eligibility
            show_telegram_cta=False,
            show_post_eligible_indicator=False,
            
            # Supporting metrics (can show as informational)
            show_cover_prob=True,  # Informational only
            show_win_prob=True,  # Informational only
            show_ev=False,  # No EV when market aligned
            show_prob_edge=False,  # No edge when market aligned
            
            # Informational gap
            show_informational_gap=show_gap,
            
            # Forbidden copy patterns (THIS IS THE KEY FIX)
            # Use specific phrases to avoid false positives in disclaimers
            forbidden_copy_patterns=[
                "OFFICIAL EDGE",
                "Official edge",
                "official spread edge",
                "Action Summary: Official",
                "TAKE_POINTS",
                "LAY_FAV",
                "Post eligible",
                "Take the points",
                "Lay the points",
                "post-eligible"
            ],
            
            # Original tier
            tier=tier
        )
    
    elif tier == TierClassification.BLOCKED:
        return UIDisplayFlags(
            # Header badges
            show_official_edge_badge=False,
            show_lean_badge=False,
            show_market_aligned_banner=False,
            show_blocked_banner=True,
            
            # Model Preference panel
            show_model_preference_panel=False,
            
            # Model Direction panel
            model_direction_mode=ModelDirectionMode.HIDDEN,
            
            # Action summary
            show_action_summary_official_edge=False,
            show_action_summary_lean=False,
            show_no_valid_edge_detected=False,
            
            # Telegram/Post eligibility
            show_telegram_cta=False,
            show_post_eligible_indicator=False,
            
            # Supporting metrics
            show_cover_prob=False,
            show_win_prob=False,
            show_ev=False,
            show_prob_edge=False,
            
            # Informational gap
            show_informational_gap=False,
            
            # Forbidden copy patterns
            forbidden_copy_patterns=[
                "OFFICIAL EDGE",
                "LEAN",
                "MARKET ALIGNED"
            ],
            
            # Original tier
            tier=tier
        )
    
    else:
        raise ValueError(f"Unknown tier: {tier}")


def compute_ui_display_copy(
    tier: TierClassification,
    gap_pts: Optional[float] = None,
    block_reason: Optional[str] = None
) -> UIDisplayCopy:
    """
    Compute canonical copy templates for tier.
    
    HARD-CODED TEMPLATES - DO NOT MODIFY WITHOUT SPEC UPDATE.
    
    Args:
        tier: Engine tier classification
        gap_pts: Optional gap (for MARKET_ALIGNED informational gap)
        block_reason: Reason for BLOCKED tier (stale odds, missing data, etc.)
    
    Returns:
        UIDisplayCopy with canonical text templates
    """
    
    if tier == TierClassification.EDGE:
        return UIDisplayCopy(
            header_text="✅ OFFICIAL EDGE",
            summary_text="Official spread edge detected. Supporting metrics: cover probability, win probability, EV, prob-edge. Model Preference (This Market) highlights the official selection.",
            model_direction_label="Model Direction (matches official selection)",
            action_summary="Action Summary: Official edge — post eligible",
            disclaimer=None
        )
    
    elif tier == TierClassification.LEAN:
        return UIDisplayCopy(
            header_text="⚠️ LEAN",
            summary_text="Soft edge detected — proceed with caution. Watch/limit sizing. Supporting metrics available.",
            model_direction_label="Model Direction (matches LEAN selection)",
            action_summary="Action Summary: LEAN — soft edge, not official",
            disclaimer="LEAN is not an official edge. Use appropriate sizing."
        )
    
    elif tier == TierClassification.MARKET_ALIGNED:
        gap_text = ""
        if gap_pts is not None and abs(gap_pts) > 5.0:
            gap_text = f" Model/Market gap detected ({gap_pts:+.1f} pts — informational only). Monitor live."
        
        return UIDisplayCopy(
            header_text="🔵 MARKET ALIGNED — NO EDGE",
            summary_text=f"No valid edge detected. Market efficiently priced.{gap_text}",
            model_direction_label="Model Direction (Informational only — not an official play)",
            action_summary=None,
            disclaimer="Probabilities and fair line shown for informational purposes only. This is NOT an official play."
        )
    
    elif tier == TierClassification.BLOCKED:
        reason_text = block_reason or "Invalid state detected"
        return UIDisplayCopy(
            header_text="🚫 BLOCKED",
            summary_text=f"Unable to generate recommendation. Reason: {reason_text}",
            model_direction_label=None,
            action_summary=None,
            disclaimer="No metrics available for BLOCKED state."
        )
    
    else:
        raise ValueError(f"Unknown tier: {tier}")


def validate_ui_display_invariants(flags: UIDisplayFlags) -> List[str]:
    """
    Validate UI display flags against hard-coded invariants.
    
    CRITICAL INVARIANTS (MUST ALWAYS PASS):
    1. Mutual exclusivity: EDGE badge and MARKET_ALIGNED banner never both True
    2. No tier override: show_action_summary_official_edge only True when tier == EDGE
    3. No false negatives: show_no_valid_edge_detected never True when tier in {EDGE, LEAN}
    
    Args:
        flags: UIDisplayFlags to validate
    
    Returns:
        List of validation errors (empty if valid)
    
    Example:
        >>> flags = compute_ui_display_flags(TierClassification.EDGE)
        >>> errors = validate_ui_display_invariants(flags)
        >>> assert len(errors) == 0
    """
    
    errors = []
    
    # INVARIANT 1: Mutual exclusivity
    if flags.show_official_edge_badge and flags.show_market_aligned_banner:
        errors.append(
            "CRITICAL: show_official_edge_badge and show_market_aligned_banner both True (mutual exclusivity violation)"
        )
    
    # INVARIANT 2: No tier override for official edge
    if flags.show_action_summary_official_edge and flags.tier != TierClassification.EDGE:
        errors.append(
            f"CRITICAL: show_action_summary_official_edge is True but tier is {flags.tier} (must be EDGE)"
        )
    
    # INVARIANT 3: No false negatives
    if flags.show_no_valid_edge_detected and flags.tier in {TierClassification.EDGE, TierClassification.LEAN}:
        errors.append(
            f"CRITICAL: show_no_valid_edge_detected is True but tier is {flags.tier} (cannot show 'no edge' for EDGE/LEAN)"
        )
    
    # INVARIANT 4: Telegram CTA only for EDGE
    if flags.show_telegram_cta and flags.tier != TierClassification.EDGE:
        errors.append(
            f"WARNING: show_telegram_cta is True but tier is {flags.tier} (typically only EDGE is auto-posted)"
        )
    
    # INVARIANT 5: Model Direction consistency
    if flags.tier == TierClassification.EDGE and flags.model_direction_mode != ModelDirectionMode.MIRROR_OFFICIAL:
        errors.append(
            f"CRITICAL: tier is EDGE but model_direction_mode is {flags.model_direction_mode} (must MIRROR_OFFICIAL)"
        )
    
    if flags.tier == TierClassification.MARKET_ALIGNED and flags.model_direction_mode == ModelDirectionMode.MIRROR_OFFICIAL:
        errors.append(
            "WARNING: tier is MARKET_ALIGNED but model_direction_mode is MIRROR_OFFICIAL (should be INFORMATIONAL_ONLY)"
        )
    
    return errors


def check_copy_violations(
    rendered_text: str,
    flags: UIDisplayFlags
) -> List[str]:
    """
    Check for forbidden copy patterns in rendered UI text.
    
    COPY LINTING RULES:
    - If tier == MARKET_ALIGNED, forbid: "OFFICIAL EDGE", "Official edge", "TAKE_POINTS", "Action Summary: Official spread edge"
      BUT ALLOW: "NOT an official play" (negation is OK in disclaimers)
    - If tier == LEAN, forbid: "OFFICIAL EDGE", "Official edge"
    - If tier == BLOCKED, forbid: "EDGE" (except in "NO EDGE"), "LEAN", "MARKET ALIGNED"
    
    Args:
        rendered_text: Complete rendered UI text (all panels concatenated)
        flags: UIDisplayFlags for this render
    
    Returns:
        List of copy violations (empty if valid)
    
    Example:
        >>> flags = compute_ui_display_flags(TierClassification.MARKET_ALIGNED)
        >>> text = "OFFICIAL EDGE detected"
        >>> violations = check_copy_violations(text, flags)
        >>> assert len(violations) > 0  # Should catch "OFFICIAL EDGE" violation
    """
    
    violations = []
    
    # Convert to lowercase for case-insensitive matching
    text_lower = rendered_text.lower()
    
    # Context-aware pattern matching
    for pattern in flags.forbidden_copy_patterns:
        pattern_lower = pattern.lower()
        
        # Skip if pattern is found but in an allowed context
        if pattern_lower in text_lower:
            # Check for negations (allowed in disclaimers)
            if _is_pattern_in_negation_context(text_lower, pattern_lower):
                continue  # Allowed
            
            violations.append(
                f"COPY VIOLATION ({flags.tier}): Forbidden pattern '{pattern}' found in rendered text"
            )
    
    return violations


def _is_pattern_in_negation_context(text: str, pattern: str) -> bool:
    """
    Check if pattern appears in a negation context (which is allowed).
    
    Allowed negation contexts:
    - "NOT an official play"
    - "not official"
    - "no edge"
    - "not the official"
    
    Args:
        text: Full text (lowercase)
        pattern: Pattern to check (lowercase)
    
    Returns:
        True if pattern is in negation context, False otherwise
    """
    
    # Find all occurrences of the pattern
    start = 0
    while True:
        idx = text.find(pattern, start)
        if idx == -1:
            break
        
        # Check context before pattern (up to 20 chars)
        context_start = max(0, idx - 20)
        context_before = text[context_start:idx]
        
        # Look for negation words
        negation_words = ["not", "no", "not an", "isn't", "aren't", "never"]
        has_negation = any(neg in context_before for neg in negation_words)
        
        if not has_negation:
            # Found pattern NOT in negation context
            return False
        
        start = idx + len(pattern)
    
    # All occurrences are in negation context
    return True


def render_ui_display_state(
    tier: TierClassification,
    gap_pts: Optional[float] = None,
    block_reason: Optional[str] = None,
    validate: bool = True
) -> dict:
    """
    Render complete UI display state from engine tier.
    
    MAIN ENTRY POINT for UI components.
    
    Args:
        tier: Engine tier classification (SINGLE SOURCE OF TRUTH)
        gap_pts: Optional gap between model fair line and market line
        block_reason: Reason for BLOCKED tier
        validate: Whether to validate invariants (default True)
    
    Returns:
        dict with:
            - flags: UIDisplayFlags
            - copy: UIDisplayCopy
            - is_valid: bool
            - validation_errors: List[str]
    
    Example:
        >>> state = render_ui_display_state(TierClassification.EDGE)
        >>> assert state['is_valid'] == True
        >>> assert state['flags'].show_official_edge_badge == True
        >>> assert "OFFICIAL EDGE" in state['copy'].header_text
    """
    
    # Compute display flags
    flags = compute_ui_display_flags(tier, gap_pts)
    
    # Compute copy templates
    copy = compute_ui_display_copy(tier, gap_pts, block_reason)
    
    # Validate invariants
    validation_errors = []
    if validate:
        validation_errors = validate_ui_display_invariants(flags)
    
    is_valid = len(validation_errors) == 0
    
    return {
        'flags': flags,
        'copy': copy,
        'is_valid': is_valid,
        'validation_errors': validation_errors,
        'tier': tier
    }


# EXPORT FOR FRONTEND
def get_display_contract_for_ui(
    tier: str,
    gap_pts: Optional[float] = None,
    block_reason: Optional[str] = None
) -> dict:
    """
    Frontend-friendly wrapper for render_ui_display_state.
    
    Args:
        tier: Tier classification as string ("EDGE", "LEAN", "MARKET_ALIGNED", "BLOCKED")
        gap_pts: Optional gap
        block_reason: Optional block reason
    
    Returns:
        Serializable dict for frontend consumption
    """
    
    tier_enum = TierClassification(tier)
    state = render_ui_display_state(tier_enum, gap_pts, block_reason)
    
    # Serialize for JSON
    return {
        'flags': {
            'show_official_edge_badge': state['flags'].show_official_edge_badge,
            'show_lean_badge': state['flags'].show_lean_badge,
            'show_market_aligned_banner': state['flags'].show_market_aligned_banner,
            'show_blocked_banner': state['flags'].show_blocked_banner,
            'show_model_preference_panel': state['flags'].show_model_preference_panel,
            'model_direction_mode': state['flags'].model_direction_mode.value,
            'show_action_summary_official_edge': state['flags'].show_action_summary_official_edge,
            'show_action_summary_lean': state['flags'].show_action_summary_lean,
            'show_no_valid_edge_detected': state['flags'].show_no_valid_edge_detected,
            'show_telegram_cta': state['flags'].show_telegram_cta,
            'show_post_eligible_indicator': state['flags'].show_post_eligible_indicator,
            'show_cover_prob': state['flags'].show_cover_prob,
            'show_win_prob': state['flags'].show_win_prob,
            'show_ev': state['flags'].show_ev,
            'show_prob_edge': state['flags'].show_prob_edge,
            'show_informational_gap': state['flags'].show_informational_gap,
            'tier': state['flags'].tier.value
        },
        'copy': {
            'header_text': state['copy'].header_text,
            'summary_text': state['copy'].summary_text,
            'model_direction_label': state['copy'].model_direction_label,
            'action_summary': state['copy'].action_summary,
            'disclaimer': state['copy'].disclaimer
        },
        'is_valid': state['is_valid'],
        'validation_errors': state['validation_errors']
    }
