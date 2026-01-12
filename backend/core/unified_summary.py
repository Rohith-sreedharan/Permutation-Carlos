"""
Unified Summary v2 — Deterministic, Per-Game, No Default Leak
==============================================================

Purpose:
    final_unified_summary is a read-only presentation object for a single game,
    generated only after the engine finalizes risk gating. It must never be
    "guessed" by the UI.

Core rule:
    If the engine would not allow deployment, the summary must not imply an edge exists.

Canonical Inputs (per game):
    - final_action ∈ {EDGE, LEAN, NO_PLAY, NO_ACTION}
    - spread_state ∈ {EDGE, LEAN, NO_PLAY, NO_ACTION} (or null if no spread market)
    - total_state ∈ {EDGE, LEAN, NO_PLAY, NO_ACTION} (or null if no total market)
    - risk_controls_active (boolean)
    - block_reasons[] (array of strings; empty if none)
    - volatility_level ∈ {LOW, MEDIUM, HIGH}
    - sigma (number; optional)
    - market_efficiency_flag (boolean; optional)
    - sim_power (e.g., 100000)

Backend Contract:
    - Compute summary only when canonical inputs exist
    - If not computable, return: "final_unified_summary": null
    - NEVER return filled "default" summary unless it is true for that game

Frontend Contract:
    - UI must render summary from backend object ONLY
    - NO fallback defaults, no hardcoded messages, no global store injection
    - If summary is null, render "Summary unavailable" or nothing

One-line "cannot fail" rule:
    If final_unified_summary is missing, UI must not invent it.
"""

from __future__ import annotations
from dataclasses import dataclass, asdict
from enum import Enum
from typing import Any, Dict, List, Optional


class Action(str, Enum):
    """Canonical action states for game/market analysis"""
    EDGE = "EDGE"
    LEAN = "LEAN"
    NO_PLAY = "NO_PLAY"
    NO_ACTION = "NO_ACTION"


class Volatility(str, Enum):
    """Volatility levels for risk assessment"""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


@dataclass(frozen=True)
class UnifiedSummaryText:
    """Derived text strings for UI display (deterministic templates)"""
    spread_line: str
    total_line: str
    volatility_line: str
    action_line: str


@dataclass(frozen=True)
class FinalUnifiedSummary:
    """
    Complete unified summary for a single game.
    
    All fields are canonical inputs or deterministically derived.
    No defaults, no placeholders.
    """
    # Canonical inputs
    final_action: Action
    spread_state: Optional[Action]  # None if not applicable
    total_state: Optional[Action]   # None if not applicable
    risk_controls_active: bool
    block_reasons: List[str]
    volatility_level: Volatility
    sigma: Optional[float]
    market_efficiency_flag: bool
    sim_power: int
    
    # Derived display text
    text: UnifiedSummaryText


def _analysis_line(label: str, state: Optional[Action]) -> str:
    """
    Generate market analysis line (spread/total).
    
    Templates:
        - EDGE → "Spread: Eligible"
        - LEAN → "Spread: Signal present — execution blocked"
        - NO_PLAY → "Spread: No play"
        - NO_ACTION → "Spread: No action"
        - None → "Spread: N/A"
    """
    if state is None:
        return f"{label}: N/A"
    if state == Action.EDGE:
        return f"{label}: Eligible"
    if state == Action.LEAN:
        return f"{label}: Signal present — execution blocked"
    if state == Action.NO_PLAY:
        return f"{label}: No play"
    # NO_ACTION
    return f"{label}: No action"


def _action_line(
    final_action: Action,
    risk_controls_active: bool,
    market_efficiency_flag: bool,
) -> str:
    """
    Generate action summary line (deterministic based on final_action).
    
    Templates:
        - EDGE → "Action: Execution eligible."
        - LEAN → "Action: Informational only — not execution eligible."
        - NO_PLAY → "Action: No play — signals not sufficient."
        - NO_ACTION (risk controls) → "Action: No action — risk controls active."
        - NO_ACTION (market efficient) → "Action: No action — market appears efficient."
        - NO_ACTION (default) → "Action: No action."
    """
    if final_action == Action.EDGE:
        return "Action: Execution eligible."
    if final_action == Action.LEAN:
        return "Action: Informational only — not execution eligible."
    if final_action == Action.NO_PLAY:
        return "Action: No play — signals not sufficient."
    # NO_ACTION
    if risk_controls_active:
        return "Action: No action — risk controls active."
    if market_efficiency_flag:
        return "Action: No action — market appears efficient."
    return "Action: No action."


def build_final_unified_summary(
    *,
    final_action: str,
    spread_state: Optional[str],
    total_state: Optional[str],
    risk_controls_active: bool,
    block_reasons: Optional[List[str]],
    volatility_level: str,
    sigma: Optional[float],
    market_efficiency_flag: bool = False,
    sim_power: int = 100000,
) -> Optional[Dict[str, Any]]:
    """
    Deterministic, per-game Unified Summary generator.
    
    HARD RULES:
        - No placeholders: if canonical inputs are missing/invalid, return None
        - Never invent copy in the UI; UI should render None as hidden/unavailable
        - No "Model signal detected" language (banned from user-facing UI)
        - No fallback defaults that leak across games
    
    Args:
        final_action: Game-level action (EDGE/LEAN/NO_PLAY/NO_ACTION)
        spread_state: Spread market action (or None if not applicable)
        total_state: Total market action (or None if not applicable)
        risk_controls_active: Whether risk controls blocked this game
        block_reasons: List of specific block reasons (e.g., ["HIGH_VOLATILITY"])
        volatility_level: LOW/MEDIUM/HIGH
        sigma: Standard deviation (optional)
        market_efficiency_flag: Whether market appears efficient
        sim_power: Simulation power (e.g., 100000)
    
    Returns:
        dict payload suitable for API response as `final_unified_summary`,
        or None if not computable (prevents default-leak bugs).
    
    Example:
        >>> summary = build_final_unified_summary(
        ...     final_action="NO_ACTION",
        ...     spread_state="NO_ACTION",
        ...     total_state="NO_ACTION",
        ...     risk_controls_active=True,
        ...     block_reasons=["HIGH_VOLATILITY", "LOW_STABILITY"],
        ...     volatility_level="HIGH",
        ...     sigma=200.83,
        ...     market_efficiency_flag=False,
        ...     sim_power=100000,
        ... )
        >>> summary["text"]["action_line"]
        'Action: No action — risk controls active.'
    """
    # ---- Validate canonical inputs (prevents default text across games) ----
    if final_action is None or volatility_level is None or risk_controls_active is None:
        return None
    
    try:
        fa = Action(final_action)
        vs = Action(spread_state) if spread_state is not None else None
        ts = Action(total_state) if total_state is not None else None
        vol = Volatility(volatility_level)
    except Exception:
        # Schema mismatch or invalid enums → DO NOT FALL BACK TO DEFAULT
        return None
    
    if sim_power is None or not isinstance(sim_power, int) or sim_power <= 0:
        return None
    
    # Normalize reasons
    reasons = [r for r in (block_reasons or []) if isinstance(r, str) and r.strip()]
    
    # ---- Derived text (locked templates) ----
    spread_line = _analysis_line("Spread", vs)
    total_line = _analysis_line("Total", ts)
    
    if sigma is None:
        volatility_line = f"Volatility: {vol.value}"
    else:
        try:
            sigma_f = float(sigma)
        except Exception:
            return None
        volatility_line = f"Volatility: {vol.value} (σ={sigma_f:.2f})"
    
    action_line = _action_line(
        final_action=fa,
        risk_controls_active=bool(risk_controls_active),
        market_efficiency_flag=bool(market_efficiency_flag),
    )
    
    summary = FinalUnifiedSummary(
        final_action=fa,
        spread_state=vs,
        total_state=ts,
        risk_controls_active=bool(risk_controls_active),
        block_reasons=reasons,
        volatility_level=vol,
        sigma=float(sigma) if sigma is not None else None,
        market_efficiency_flag=bool(market_efficiency_flag),
        sim_power=sim_power,
        text=UnifiedSummaryText(
            spread_line=spread_line,
            total_line=total_line,
            volatility_line=volatility_line,
            action_line=action_line,
        ),
    )
    
    payload = asdict(summary)
    
    # Optional: omit empty reasons for cleaner UI
    if not payload.get("block_reasons"):
        payload.pop("block_reasons", None)
    
    return payload


# ------------------------------
# Example integration usage
# ------------------------------
if __name__ == "__main__":
    # Example 1: A blocked game (risk controls active)
    print("Example 1: Blocked game (risk controls active)")
    print("=" * 60)
    blocked_summary = build_final_unified_summary(
        final_action="NO_ACTION",
        spread_state="NO_ACTION",
        total_state="NO_ACTION",
        risk_controls_active=True,
        block_reasons=["HIGH_VOLATILITY", "LOW_STABILITY"],
        volatility_level="HIGH",
        sigma=200.83,
        market_efficiency_flag=False,
        sim_power=100000,
    )
    if blocked_summary:
        print(f"Final Action: {blocked_summary['final_action']}")
        print(f"Text:\n  {blocked_summary['text']['spread_line']}")
        print(f"  {blocked_summary['text']['total_line']}")
        print(f"  {blocked_summary['text']['volatility_line']}")
        print(f"  {blocked_summary['text']['action_line']}")
        print(f"Block Reasons: {blocked_summary.get('block_reasons', [])}")
    else:
        print("Summary: None (not computable)")
    
    print("\n" + "=" * 60 + "\n")
    
    # Example 2: An EDGE game (execution eligible)
    print("Example 2: EDGE game (execution eligible)")
    print("=" * 60)
    edge_summary = build_final_unified_summary(
        final_action="EDGE",
        spread_state="EDGE",
        total_state="NO_ACTION",
        risk_controls_active=False,
        block_reasons=[],
        volatility_level="LOW",
        sigma=45.2,
        market_efficiency_flag=False,
        sim_power=100000,
    )
    if edge_summary:
        print(f"Final Action: {edge_summary['final_action']}")
        print(f"Text:\n  {edge_summary['text']['spread_line']}")
        print(f"  {edge_summary['text']['total_line']}")
        print(f"  {edge_summary['text']['volatility_line']}")
        print(f"  {edge_summary['text']['action_line']}")
    else:
        print("Summary: None (not computable)")
    
    print("\n" + "=" * 60 + "\n")
    
    # Example 3: A LEAN game (informational only)
    print("Example 3: LEAN game (informational only)")
    print("=" * 60)
    lean_summary = build_final_unified_summary(
        final_action="LEAN",
        spread_state="LEAN",
        total_state="LEAN",
        risk_controls_active=False,
        block_reasons=["INSUFFICIENT_EDGE"],
        volatility_level="MEDIUM",
        sigma=120.5,
        market_efficiency_flag=False,
        sim_power=100000,
    )
    if lean_summary:
        print(f"Final Action: {lean_summary['final_action']}")
        print(f"Text:\n  {lean_summary['text']['spread_line']}")
        print(f"  {lean_summary['text']['total_line']}")
        print(f"  {lean_summary['text']['volatility_line']}")
        print(f"  {lean_summary['text']['action_line']}")
        print(f"Block Reasons: {lean_summary.get('block_reasons', [])}")
    else:
        print("Summary: None (not computable)")
    
    print("\n" + "=" * 60 + "\n")
    
    # Example 4: Invalid inputs (should return None)
    print("Example 4: Invalid inputs (should return None)")
    print("=" * 60)
    invalid_summary = build_final_unified_summary(
        final_action="INVALID_ACTION",  # Invalid enum value
        spread_state="NO_ACTION",
        total_state="NO_ACTION",
        risk_controls_active=False,
        block_reasons=[],
        volatility_level="LOW",
        sigma=50.0,
        market_efficiency_flag=False,
        sim_power=100000,
    )
    print(f"Summary: {invalid_summary}")  # Should print None
    
    print("\n" + "=" * 60)
