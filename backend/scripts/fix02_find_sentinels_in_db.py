#!/usr/bin/env python3
"""
FIX-02 Root Cause Probe: Find where sentinel values (-9999, -999) exist in rendered cards or simulated outcomes.
"""

import sys
import os
import json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from db.mongo import db

def find_affected_teams():
    """Search for the 4 affected teams mentioned in FIX-02."""
    
    affected_teams = ["Illinois", "Gonzaga", "Houston", "Detroit Pistons"]
    
    print("=" * 80)
    print("FIX-02 ROOT CAUSE PROBE: Sentinel Value Tracking")
    print("=" * 80)
    print()
    print("Searching for affected teams in DB...")
    print(f"Target teams: {affected_teams}")
    print()
    
    results = {team: [] for team in affected_teams}
    
    # Search events collection
    for team in affected_teams:
        events = list(db.events.find({
            "$or": [
                {"home_team": {"$regex": team, "$options": "i"}},
                {"away_team": {"$regex": team, "$options": "i"}}
            ]
        }).limit(3))
        
        if events:
            for event in events:
                print(f"📌 EVENT: {event.get('away_team')} @ {event.get('home_team')}")
                print(f"   Event ID: {event.get('event_id')}")
                print(f"   Sport: {event.get('sport_key')}")
                print()
                
                # Find daily cards with this event
                daily_cards = list(db.daily_best_cards.find({}))
                if daily_cards:
                    for card_dict in daily_cards:
                        for card_key in ["best_game_overall", "top_ncaab_game", "top_ncaaf_game"]:
                            card = card_dict.get(card_key)
                            if card and team in card.get("matchup", ""):
                                print(f"   Found in daily_best_cards['{card_key}']:")
                                print(f"     matchup: {card.get('matchup')}")
                                print(f"     odds: {card.get('odds')}")
                                print(f"     recommended_bet: {card.get('recommended_bet')}")
                                print()
                                
                                # Check if odds are sentinel
                                odds = card.get("odds")
                                if odds in [-9999, -999, 9999, 999, -9999999, -999999]:
                                    print(f"   ⚠️  SENTINEL ODDS DETECTED: {odds}")
                                    print()
                
                results[team].append(event)
    
    print()
    print("=" * 80)
    print("SEARCHING FOR SENTINEL PATTERNS IN ALL CARDS")
    print("=" * 80)
    print()
    
    # Scan all daily_best_cards for sentinel values
    all_cards = list(db.daily_best_cards.find({}))
    sentinel_found_count = 0
    
    for card_dict in all_cards:
        for card_key in ["best_game_overall", "top_nba_game", "top_ncaab_game", "top_ncaaf_game", "top_prop_mispricing", "parlay_preview"]:
            card = card_dict.get(card_key)
            if not card:
                continue
            
            odds = card.get("odds")
            parlay_odds = card.get("parlay_odds")
            
            # Check for sentinel values
            sentinel_values = {-9999, -999, 9999, 999, -9999999, -999999}
            
            if odds in sentinel_values:
                sentinel_found_count += 1
                print(f"🔴 SENTINEL in daily_best_cards['{card_key}']:")
                print(f"   matchup: {card.get('matchup')}")
                print(f"   odds: {odds}")
                print(f"   card_type: {card.get('card_type')}")
                print()
            
            if parlay_odds in sentinel_values:
                sentinel_found_count += 1
                print(f"🔴 SENTINEL in parlay daily_best_cards['{card_key}']:")
                print(f"   parlay_odds: {parlay_odds}")
                print(f"   card_type: {card.get('card_type')}")
                print()
    
    print()
    print(f"Total sentinel values found: {sentinel_found_count}")
    print()
    
    # Search simulations for sentinel in "outcome" field
    print("=" * 80)
    print("SEARCHING FOR SENTINEL OUTCOMES IN SIMULATIONS")
    print("=" * 80)
    print()
    
    sims_with_sentinels = list(db.monte_carlo_simulations.find({
        "$or": [
            {"outcome.odds": {"$in": [-9999, -999, 9999, 999]}},
            {"outcome.odds": {"$exists": True, "$lte": -9000}},
            {"outcome.odds": {"$exists": True, "$gte": 9000}}
        ]
    }).limit(5))
    
    for sim in sims_with_sentinels:
        outcome = sim.get("outcome", {})
        odds = outcome.get("odds")
        event_id = sim.get("event_id")
        
        # Find event
        event = db.events.find_one({"event_id": event_id})
        if event:
            print(f"⚠️  SIMULATION WITH SENTINEL OUTCOME:")
            print(f"   Event: {event.get('away_team')} @ {event.get('home_team')}")
            print(f"   Event ID: {event_id}")
            print(f"   Outcome odds: {odds}")
            print(f"   Outcome recommended_bet: {outcome.get('recommended_bet')}")
            print()
    
    print()
    print("=" * 80)
    print("ANALYSIS COMPLETE")
    print("=" * 80)
    print()
    if sentinel_found_count > 0:
        print("✅ ROOT CAUSE IDENTIFIED: Sentinel values present in rendered card output")
        print("   Passthrough point: daily_cards.py → daily_best_cards collection")
    else:
        print("❌ No sentinel values found in current DB snapshot")
        print("   (May be cached; run /api/daily-cards/regenerate to refresh)")

if __name__ == "__main__":
    find_affected_teams()
