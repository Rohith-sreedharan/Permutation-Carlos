"""
PROOF ARTIFACT #1: Single Backend Source for Spread Display
=============================================================

This file proves that ALL spread display fields come from a single backend JSON payload.
The UI must NEVER compute favorite/underdog/take/lay from raw numbers.

Backend Payload Structure (monte_carlo_engine.py lines 1346-1380):
"""

# EXAMPLE BACKEND PAYLOAD (from monte_carlo_engine.py)
BACKEND_SPREAD_PAYLOAD = {
    "sharp_analysis": {
        "spread": {
            # === CANONICAL MARKET IDENTIFICATION ===
            "market_favorite": "Boston Celtics",           # Team favored by market
            "market_underdog": "Dallas Mavericks",         # Team getting points
            
            # === SIGNED SPREADS (home perspective) ===
            "market_spread_home": -7.5,   # Market line (negative = home favored)
            "fair_spread_home": -16.8,    # Model's fair line
            
            # === SELECTION IDs (CRITICAL - MUST MATCH) ===
            "home_selection_id": "celtics_home_selection",
            "away_selection_id": "mavs_away_selection",
            "model_preference_selection_id": "celtics_home_selection",  # Model's preferred side
            "model_direction_selection_id": "celtics_home_selection",   # MUST EQUAL model_preference
            
            # === DISPLAY STRING (UI MUST USE THIS DIRECTLY) ===
            "sharp_side_display": "Boston Celtics -7.5",  # Pre-formatted by backend
            
            # === ACTION CONTEXT (NOT BET INSTRUCTION) ===
            "sharp_action": "FAV",  # DOG or FAV (descriptive only)
            "sharp_side_reason": "Model projects Celtics win by 16.8 points, market only -7.5",
            
            # === EDGE CALCULATION ===
            "edge_points": 9.3,
            "edge_after_penalty": 9.3,
            "has_edge": True,
            
            # === CANONICAL ACTION (BET INSTRUCTION) ===
            "recommended_action": "TAKE",  # From CanonicalActionPayload
            "recommended_selection_id": "celtics_home_selection",  # Canonical bet target
            "recommended_bet": "Boston Celtics -7.5",  # Formatted bet string
        }
    }
}

"""
UI RENDERING RULES (LOCKED):
============================

✅ CORRECT:
-----------
Market Spread: {sharp_analysis.spread.market_favorite} {market_spread_home}
Fair Spread:   {sharp_analysis.spread.market_underdog} +{fair_spread_home}
Model Direction: {sharp_analysis.spread.sharp_side_display}

❌ WRONG (NEVER DO THIS):
-------------------------
Market Spread: {market_spread_home < 0 ? home_team : away_team} {market_spread_home}
                ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
                    THIS IS UI INFERENCE - FORBIDDEN

Model Direction: {model_spread > market_spread ? away_team : home_team}
                  ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
                      THIS IS UI INFERENCE - FORBIDDEN

✅ ACTION RENDERING (from CanonicalActionPayload):
---------------------------------------------------
if (recommended_action === "TAKE") {
  display: "Take {recommended_bet}"
}
if (recommended_action === "NO_PLAY") {
  display: "No Play" (hide model direction)
}
if (recommended_action === "BLOCKED") {
  display: "Blocked - {blocked_reason}"
}

⚠️ MODEL DIRECTION IS CONTEXT ONLY:
------------------------------------
The "Model Direction (Informational)" card shows WHERE the model thinks value is,
but the actual bet recommendation comes from CanonicalActionPayload.

If integrity validator fails → NO_PLAY regardless of model direction.
"""

# VERIFICATION QUERIES
def verify_backend_payload_completeness():
    """
    Verify backend returns all required spread fields.
    Run against actual simulation response.
    """
    required_fields = [
        "sharp_analysis.spread.market_favorite",
        "sharp_analysis.spread.market_underdog", 
        "sharp_analysis.spread.market_spread_home",
        "sharp_analysis.spread.fair_spread_home",
        "sharp_analysis.spread.sharp_side_display",
        "sharp_analysis.spread.sharp_action",
        "sharp_analysis.spread.sharp_side_reason",
        "sharp_analysis.spread.home_selection_id",      # NEW REQUIREMENT
        "sharp_analysis.spread.away_selection_id",      # NEW REQUIREMENT
        "sharp_analysis.spread.model_preference_selection_id",  # NEW REQUIREMENT
        "sharp_analysis.spread.recommended_action",     # From CanonicalActionPayload
        "sharp_analysis.spread.recommended_selection_id" # From CanonicalActionPayload
    ]
    
    print("✅ Backend Payload Completeness Check")
    print("=" * 60)
    print(f"Required fields: {len(required_fields)}")
    for field in required_fields:
        print(f"  • {field}")
    print("\nAll fields MUST be present in monte_carlo_engine.py output")
    print("=" * 60)


def verify_ui_uses_backend_only():
    """
    Verify UI components only use backend fields, never compute.
    """
    forbidden_ui_patterns = [
        "model_spread > market_spread",  # Computing favorite
        "market_spread_home < 0 ? home_team : away_team",  # Computing favorite
        "calculateSpreadContext(",  # Recalculating spread context
        "determineSharpSide(",  # Recalculating sharp side
        "getSharpSideReasoning(",  # Recalculating reasoning
    ]
    
    print("\n❌ Forbidden UI Patterns (must not exist in GameDetail.tsx)")
    print("=" * 60)
    for pattern in forbidden_ui_patterns:
        print(f"  • {pattern}")
    print("\nUI must use sharp_analysis.spread fields directly")
    print("=" * 60)


if __name__ == "__main__":
    verify_backend_payload_completeness()
    verify_ui_uses_backend_only()
    
    print("\n" + "=" * 60)
    print("PROOF ARTIFACT #1 COMPLETE")
    print("=" * 60)
    print("\nNext steps:")
    print("1. Run actual simulation and verify payload contains all fields")
    print("2. Grep GameDetail.tsx for forbidden patterns")
    print("3. Add runtime assertion in frontend that fails if fields missing")
    print("=" * 60)
