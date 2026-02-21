"""
ODDS ALIGNMENT GATE - PROOF ARTIFACT GENERATOR
===============================================

Per ENGINE LOCK Specification Section 4 - REQUIREMENT 5.

Generates proof artifacts showing:
1. One PASS case (line_delta <= 0.25)
2. One BLOCKED_BY_ODDS_MISMATCH case (line_delta > 0.25)
3. Verification that edge is NOT calculated when blocked

Run on production server:
    cd /root/permu && python3 backend/scripts/generate_odds_alignment_proof.py
"""

from backend.db.mongo import db
from datetime import datetime, timezone
import json


def create_proof_artifacts():
    """Generate proof artifacts for Section 4"""
    
    print("=" * 70)
    print("ODDS ALIGNMENT GATE - PROOF ARTIFACT GENERATOR")
    print("=" * 70)
    print()
    
    # Find an existing NBA game
    event = db["events"].find_one({
        "sport_key": "basketball_nba",
        "bookmakers": {"$exists": True, "$ne": []}
    })
    
    if not event:
        print("❌ No NBA games found in database")
        return
    
    event_id = event.get("event_id") or event.get("id")
    home_team = event.get("home_team", "Home Team")
    away_team = event.get("away_team", "Away Team")
    
    print(f"Using game: {away_team} @ {home_team}")
    print(f"Event ID: {event_id}")
    print()
    
    # Get current market lines
    bookmaker = event["bookmakers"][0]
    markets = {m["key"]: m for m in bookmaker.get("markets", [])}
    spread_market = markets.get("spreads", {})
    outcomes = spread_market.get("outcomes", [])
    
    if not outcomes:
        print("❌ No spread market found")
        return
    
    home_outcome = next((o for o in outcomes if o.get("name") == home_team), None)
    if not home_outcome:
        print("❌ No home team spread found")
        return
    
    current_market_line = home_outcome.get("point", -3.5)
    print(f"Current market line (home): {current_market_line}")
    print()
    
    # ==========================================
    # ARTIFACT 1: PASS CASE (line_delta = 0.20)
    # ==========================================
    print("=" * 70)
    print("ARTIFACT 1: PASS CASE (line_delta = 0.20 < 0.25)")
    print("=" * 70)
    print()
    
    sim_market_spread_pass = current_market_line - 0.20  # Within tolerance
    
    simulation_pass = {
        "game_id": event_id,
        "event_id": event_id,
        "simulation_id": f"proof_pass_{event_id}",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "team_a_win_probability": 0.58,
        "over_probability": 0.52,
        "volatility_label": "MODERATE",
        "injury_impact": 0.0,
        "sharp_analysis": {
            "spread": {
                "model_spread": current_market_line + 0.5,  # Model has small edge
                "market_spread": sim_market_spread_pass  # What sim saw
            },
            "total": {
                "model_total": 220.5,
                "market_total": 220.0
            }
        }
    }
    
    # Save to database
    db["monte_carlo_simulations"].delete_many({"simulation_id": simulation_pass["simulation_id"]})
    db["monte_carlo_simulations"].insert_one(simulation_pass)
    
    print(f"Created simulation:")
    print(f"  simulation_market_spread_home: {sim_market_spread_pass}")
    print(f"  current_market_line_home: {current_market_line}")
    print(f"  line_delta: {abs(sim_market_spread_pass - current_market_line):.3f}")
    print()
    print("VERIFICATION COMMAND:")
    print(f"curl -s 'https://beta.beatvegas.app/api/games/NBA/{event_id}/decisions' | jq '.spread | {{release_status, classification, edge_points: .edge.edge_points, model_prob: .probabilities.model_prob, blocked_reason: .risk.blocked_reason}}'")
    print()
    print("EXPECTED:")
    print("  release_status: APPROVED")
    print("  classification: NOT null")
    print("  edge_points: NOT null (edge was calculated)")
    print("  model_prob: NOT null")
    print("  blocked_reason: null")
    print()
    
    # ==========================================
    # ARTIFACT 2: BLOCKED CASE (line_delta = 0.50)
    # ==========================================
    print("=" * 70)
    print("ARTIFACT 2: BLOCKED CASE (line_delta = 0.50 > 0.25)")
    print("=" * 70)
    print()
    
    sim_market_spread_block = current_market_line - 0.50  # EXCEEDS tolerance
    
    # Create a different event for the BLOCKED case
    event_2 = db["events"].find_one({
        "sport_key": "basketball_nba",
        "event_id": {"$ne": event_id},
        "bookmakers": {"$exists": True, "$ne": []}
    })
    
    if event_2:
        event_id_2 = event_2.get("event_id") or event_2.get("id")
        home_team_2 = event_2.get("home_team", "Home Team 2")
        away_team_2 = event_2.get("away_team", "Away Team 2")
        
        # Get market line for second game
        bookmaker_2 = event_2["bookmakers"][0]
        markets_2 = {m["key"]: m for m in bookmaker_2.get("markets", [])}
        spread_market_2 = markets_2.get("spreads", {})
        outcomes_2 = spread_market_2.get("outcomes", [])
        home_outcome_2 = next((o for o in outcomes_2 if o.get("name") == home_team_2), outcomes_2[0] if outcomes_2 else None)
        
        if home_outcome_2:
            current_market_line_2 = home_outcome_2.get("point", -4.5)
            sim_market_spread_block = current_market_line_2 - 0.50
            
            simulation_block = {
                "game_id": event_id_2,
                "event_id": event_id_2,
                "simulation_id": f"proof_block_{event_id_2}",
                "created_at": datetime.now(timezone.utc).isoformat(),
                "team_a_win_probability": 0.62,
                "over_probability": 0.54,
                "volatility_label": "MODERATE",
                "injury_impact": 0.0,
                "sharp_analysis": {
                    "spread": {
                        "model_spread": current_market_line_2 + 2.0,  # Huge edge (if it passed)
                        "market_spread": sim_market_spread_block  # What sim saw (stale)
                    },
                    "total": {
                        "model_total": 225.0,
                        "market_total": 224.0
                    }
                }
            }
            
            # Save to database
            db["monte_carlo_simulations"].delete_many({"simulation_id": simulation_block["simulation_id"]})
            db["monte_carlo_simulations"].insert_one(simulation_block)
            
            print(f"Using game: {away_team_2} @ {home_team_2}")
            print(f"Event ID: {event_id_2}")
            print()
            print(f"Created simulation:")
            print(f"  simulation_market_spread_home: {sim_market_spread_block}")
            print(f"  current_market_line_home: {current_market_line_2}")
            print(f"  line_delta: {abs(sim_market_spread_block - current_market_line_2):.3f}")
            print(f"  model_spread: {current_market_line_2 + 2.0} (would be EDGE if not blocked)")
            print()
            print("VERIFICATION COMMAND:")
            print(f"curl -s 'https://beta.beatvegas.app/api/games/NBA/{event_id_2}/decisions' | jq '.spread | {{release_status, classification, edge_points: .edge.edge_points, model_prob: .probabilities.model_prob, blocked_reason: .risk.blocked_reason}}'")
            print()
            print("EXPECTED:")
            print("  release_status: BLOCKED_BY_ODDS_MISMATCH")
            print("  classification: null")
            print("  edge_points: null (edge NOT calculated - proves REQUIREMENT 3)")
            print("  model_prob: null")
            print("  blocked_reason: 'Odds movement: line_delta=0.5000 > 0.25...'")
            print()
    
    print("=" * 70)
    print("PROOF ARTIFACTS READY")
    print("=" * 70)
    print()
    print("Run the curl commands above to generate JSON proof artifacts.")
    print()
    print("Save outputs to:")
    print("  proof/ODDS_ALIGNMENT_PASS_ARTIFACT.json")
    print("  proof/ODDS_ALIGNMENT_BLOCKED_ARTIFACT.json")
    print()


if __name__ == "__main__":
    create_proof_artifacts()
