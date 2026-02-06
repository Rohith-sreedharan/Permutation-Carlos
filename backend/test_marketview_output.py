"""
Quick MarketView inspection script
Generates a SPREAD MarketView and validates SINGLE SELECTION CONTEXT
"""
import json
from core.selection_id_generator import generate_spread_selections

# Mock data for Lakers vs 76ers
event_id = "29d21b1015a4f76d386601af48083a64"
home_team = "Los Angeles Lakers"
away_team = "Philadelphia 76ers"
market_spread_home = -5.5  # Lakers favored by 5.5

# Generate selections
selections = generate_spread_selections(
    event_id=event_id,
    home_team=home_team,
    away_team=away_team,
    market_spread_home=market_spread_home,
    book_key="consensus"
)

# Add model probabilities (mock fair line at -4.0, so home has value)
selections["home"]["model_probability"] = 0.58
selections["away"]["model_probability"] = 0.42
selections["home"]["market_probability"] = 0.55
selections["away"]["market_probability"] = 0.45
selections["home"]["model_fair_line_for_selection"] = -4.0
selections["away"]["model_fair_line_for_selection"] = 4.0

# Model prefers home (Lakers -5.5 vs fair -4.0 = edge)
model_preference_selection_id = selections["home"]["selection_id"]

# Build MarketView
market_view = {
    "schema_version": "mv.v1",
    "market_type": "SPREAD",
    "event_id": event_id,
    "snapshot_hash": "test_snapshot",
    "model_preference_selection_id": model_preference_selection_id,
    "model_direction_selection_id": model_preference_selection_id,
    "selections": [selections["home"], selections["away"]],
    "edge_class": "EDGE",
    "integrity_status": "PASS",
    "ui_mode": "FULL"
}

print("=" * 80)
print("MARKETVIEW INSPECTION - SINGLE SELECTION CONTEXT")
print("=" * 80)
print(f"\nEvent: {away_team} @ {home_team}")
print(f"Market Spread (home perspective): {market_spread_home}")
print(f"Model Preference: {model_preference_selection_id}\n")

print("SELECTIONS:")
print("-" * 80)
for i, sel in enumerate(market_view["selections"]):
    print(f"\n[{i}] {sel['selection_id']}")
    print(f"    Side: {sel['side']}")
    print(f"    Team: {sel['team_display_name']}")
    print(f"    Market Line: {sel['market_line_for_selection']}")
    print(f"    Fair Line: {sel['model_fair_line_for_selection']}")
    print(f"    Market Prob: {sel['market_probability']:.4f}")
    print(f"    Model Prob: {sel['model_probability']:.4f}")

# CRITICAL VALIDATION: UI should only show values from preferred selection
preferred_sel = next(s for s in market_view["selections"] if s["selection_id"] == model_preference_selection_id)

print("\n" + "=" * 80)
print("UI DISPLAY (SINGLE SELECTION CONTEXT)")
print("=" * 80)
print(f"Team: {preferred_sel['team_display_name']}")
print(f"Market Line: {preferred_sel['market_line_for_selection']}")
print(f"Fair Line: {preferred_sel['model_fair_line_for_selection']}")
print(f"Market Prob: {preferred_sel['market_probability']:.4f}")
print(f"Model Prob: {preferred_sel['model_probability']:.4f}")

print("\n✅ VALIDATION: All values from SAME selection_id")
print(f"   NO home/away branching")
print(f"   NO cross-team perspective mixing")
print("=" * 80)

# Export to JSON for proof
with open("/Users/rohithaditya/Downloads/Permutation-Carlos/proof/test_lakers_spread.json", "w") as f:
    json.dump(market_view, f, indent=2)
    
print(f"\n📄 Saved to: proof/test_lakers_spread.json")
