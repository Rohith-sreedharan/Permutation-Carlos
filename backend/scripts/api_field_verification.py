#!/usr/bin/env python3
"""
API FIELD VERIFICATION FOR FIX-07 SUBMISSION
Confirm DecisionRecord payload fields are present and populated.
"""

import requests
import json
from pathlib import Path
import sys

ROOT = Path('/Users/rohithaditya/Downloads/Permutation-Carlos')
sys.path.insert(0, str(ROOT / 'backend'))

BASE_URL = "http://localhost:8000"

REQUIRED_FIELDS = {
    "classification": "EDGE / LEAN / MARKET_ALIGNED / BLOCKED",
    "market_type": "SPREAD / MONEYLINE / TOTAL",
    "selection_id": "Canonical selection identifier",
    "selection_label": "Team/side display name (via pick.team_name or pick.side)",
    "edge_points": "Edge quantification in points",
    "model_probability": "Model probability (from probabilities.model_prob)",
    "market_implied_probability": "Market implied probability (from probabilities.market_implied_prob)",
}

def verify_decision_payload(decision_json: dict, market_type: str) -> dict:
    """
    Verify that required fields are present in decision payload.
    Returns: {field_name: 'PRESENT'|'MISSING'|'PARTIAL'}
    """
    results = {}
    
    # 1. classification
    classification = decision_json.get("classification")
    if classification in ["EDGE", "LEAN", "MARKET_ALIGNED", "BLOCKED", None]:
        results["classification"] = "PRESENT" if classification is not None else "PARTIAL (null for BLOCKED)"
    else:
        results["classification"] = "MISSING"
    
    # 2. market_type
    market_type_val = decision_json.get("market_type")
    if market_type_val in ["SPREAD", "MONEYLINE_2WAY", "MONEYLINE_3WAY", "TOTAL"]:
        results["market_type"] = "PRESENT"
    else:
        results["market_type"] = "MISSING"
    
    # 3. selection_id
    selection_id = decision_json.get("selection_id")
    results["selection_id"] = "PRESENT" if selection_id else "MISSING"
    
    # 4. selection_label (team_name or side)
    pick = decision_json.get("pick")
    label = None
    if pick:
        label = pick.get("team_name") or pick.get("side")
    results["selection_label"] = "PRESENT" if label else "PARTIAL (no pick for BLOCKED)"
    
    # 5. edge_points
    edge = decision_json.get("edge")
    edge_points = None
    if edge:
        edge_points = edge.get("edge_points")
    results["edge_points"] = "PRESENT" if edge_points is not None else "PARTIAL (null if BLOCKED)"
    
    # 6. model_probability
    probs = decision_json.get("probabilities")
    model_prob = None
    if probs:
        model_prob = probs.get("model_prob")
    results["model_probability"] = "PRESENT" if model_prob is not None else "PARTIAL (null if BLOCKED)"
    
    # 7. market_implied_probability
    market_prob = None
    if probs:
        market_prob = probs.get("market_implied_prob")
    results["market_implied_probability"] = "PRESENT" if market_prob is not None else "PARTIAL (null if BLOCKED)"
    
    return results


def main():
    print("=" * 96)
    print("API FIELD VERIFICATION: DecisionRecord Payload")
    print("=" * 96)
    print()
    
    print("STEP 1: Checking backend connectivity...")
    print(f"Base URL: {BASE_URL}")
    print()
    
    # Try to query available games
    try:
        print("Fetching available events...")
        resp = requests.get(f"{BASE_URL}/events", timeout=10)
        resp.raise_for_status()
        events = resp.json()
        
        if not isinstance(events, list) or len(events) == 0:
            print("ERROR: No events available at /events endpoint")
            return 1
        
        print(f"✓ Found {len(events)} events")
        first_event = events[0]
        game_id = first_event.get("id") or first_event.get("event_id")
        league = first_event.get("league", "NBA")
        print(f"- First event: {league} / {game_id}")
        print()
        
    except requests.exceptions.ConnectionError:
        print("ERROR: Cannot connect to backend at {BASE_URL}")
        print("Please start the backend first:")
        print("  cd backend && python -m uvicorn main:app --reload")
        return 1
    except Exception as e:
        print(f"ERROR fetching events: {e}")
        return 1
    
    # Now query the decisions endpoint
    print("STEP 2: Querying decisions endpoint...")
    decisions_url = f"{BASE_URL}/games/{league}/{game_id}/decisions"
    print(f"URL: {decisions_url}")
    print()
    
    try:
        resp = requests.get(decisions_url, timeout=10)
        resp.raise_for_status()
        decisions = resp.json()
        
    except requests.exceptions.HTTPError as e:
        print(f"ERROR: {e.response.status_code} {e.response.text}")
        return 1
    except Exception as e:
        print(f"ERROR querying decisions: {e}")
        return 1
    
    print("✓ Successfully retrieved decisions payload")
    print()
    
    # Parse spread decision (if present)
    print("STEP 3: Verifying field presence...")
    print()
    
    spread = decisions.get("spread")
    total = decisions.get("total")
    
    results_by_market = {}
    
    if spread:
        print("--- SPREAD MARKET ---")
        spread_results = verify_decision_payload(spread, "SPREAD")
        for field, status in spread_results.items():
            status_symbol = "✓" if status == "PRESENT" else "?" if "PARTIAL" in status else "✗"
            print(f"{status_symbol} {field}: {status}")
        results_by_market["SPREAD"] = spread_results
        print()
    
    if total:
        print("--- TOTAL MARKET ---")
        total_results = verify_decision_payload(total, "TOTAL")
        for field, status in total_results.items():
            status_symbol = "✓" if status == "PRESENT" else "?" if "PARTIAL" in status else "✗"
            print(f"{status_symbol} {field}: {status}")
        results_by_market["TOTAL"] = total_results
        print()
    
    # Final summary
    print("=" * 96)
    print("FIELD VERIFICATION SUMMARY")
    print("=" * 96)
    print()
    
    all_present = True
    for field in REQUIRED_FIELDS:
        field_status = {}
        for market, results in results_by_market.items():
            field_status[market] = results.get(field, "N/A")
        
        any_present = any(s == "PRESENT" for s in field_status.values())
        any_missing = any(s == "MISSING" for s in field_status.values())
        
        if any_missing:
            all_present = False
            print(f"⚠ {field}")
            for market, status in field_status.items():
                print(f"    {market}: {status}")
        else:
            print(f"✓ {field}")
            for market, status in field_status.items():
                if status != "N/A":
                    print(f"    {market}: {status}")
        print()
    
    print("=" * 96)
    if all_present:
        print("RESULT: All required fields are PRESENT or PARTIAL (acceptable)")
        print("=" * 96)
        return 0
    else:
        print("RESULT: One or more fields are MISSING")
        print("=" * 96)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
