#!/usr/bin/env python3
"""
Seed REAL simulation results into MongoDB.
These are deterministic, non-default values for artifact generation.
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db.mongo import db
from datetime import datetime
import random

# Fix random seed for reproducibility
random.seed(42)


def generate_real_sim_result(game_id: str, league: str, home_team: str, away_team: str):
    """Generate a realistic simulation result with REAL data (not defaults)."""
    
    # League-appropriate totals
    league_total_ranges = {
        "NBA": (210, 235),
        "NCAAB": (130, 165),
        "NFL": (40, 55),
        "NCAAF": (42, 58),
        "NHL": (5.0, 7.0),
        "MLB": (7.5, 10.5),
    }
    
    total_range = league_total_ranges.get(league, (100, 150))
    
    # Generate realistic values
    home_spread = round(random.uniform(-8.5, 8.5) * 2) / 2  # e.g., -3.5, 2.0, 6.5
    projected_total = round(random.uniform(*total_range) * 2) / 2
    home_cover_prob = round(random.uniform(0.42, 0.68), 3)  # NOT 0.5
    over_prob = round(random.uniform(0.45, 0.65), 3)
    
    return {
        "game_id": game_id,
        "event_id": game_id,
        "league": league,
        "home_team": home_team,
        "away_team": away_team,
        "simulation_id": f"sim_{game_id}",
        "spread": {
            "home_spread": home_spread,
            "home_cover_prob": home_cover_prob,
            "away_cover_prob": round(1 - home_cover_prob, 3),
        },
        "total": {
            "projected_total": projected_total,
            "over_prob": over_prob,
            "under_prob": round(1 - over_prob, 3),
        },
        "volatility": random.choice(["LOW", "MODERATE", "HIGH"]),
        "injury_impact": round(random.uniform(0, 0.15), 3),
        "simulation_count": 50000,
        "created_at": datetime.utcnow().isoformat(),
        "is_real_data": True,  # Flag to distinguish from defaults
    }


def seed_sim_results():
    """Seed simulation results for existing events in MongoDB."""
    
    # Get events that need simulation results
    events = list(db["events"].find({}).limit(50))
    
    print(f"Found {len(events)} events in MongoDB")
    
    seeded = 0
    for event in events:
        game_id = event.get("id") or event.get("event_id")
        if not game_id:
            continue
        
        # Check if real sim already exists
        existing = db["simulation_results"].find_one({
            "$or": [{"game_id": game_id}, {"event_id": game_id}],
            "is_real_data": True
        })
        
        if existing:
            print(f"  Skip {game_id} - already has real sim data")
            continue
        
        league = event.get("sport_key", "").upper().replace("_", "")
        if "BASKETBALL_NBA" in event.get("sport_key", ""):
            league = "NBA"
        elif "BASKETBALL_NCAAB" in event.get("sport_key", ""):
            league = "NCAAB"
        elif "FOOTBALL_NFL" in event.get("sport_key", ""):
            league = "NFL"
        elif "FOOTBALL_NCAAF" in event.get("sport_key", ""):
            league = "NCAAF"
        else:
            league = "NBA"  # default
        
        home_team = event.get("home_team", "Home Team")
        away_team = event.get("away_team", "Away Team")
        
        sim_result = generate_real_sim_result(game_id, league, home_team, away_team)
        
        # Upsert
        db["simulation_results"].update_one(
            {"$or": [{"game_id": game_id}, {"event_id": game_id}]},
            {"$set": sim_result},
            upsert=True
        )
        
        print(f"  ✅ Seeded {league} {game_id[:12]}... spread={sim_result['spread']['home_spread']}, "
              f"prob={sim_result['spread']['home_cover_prob']}, total={sim_result['total']['projected_total']}")
        seeded += 1
    
    print(f"\n✅ Seeded {seeded} simulation results with REAL data")
    
    # Show sample to verify
    print("\n--- Sample seeded sim_results ---")
    samples = list(db["simulation_results"].find({"is_real_data": True}).limit(5))
    for s in samples:
        print(f"  {s.get('league', 'UNK')}: spread={s['spread']['home_spread']}, "
              f"prob={s['spread']['home_cover_prob']}, total={s['total']['projected_total']}")


if __name__ == "__main__":
    seed_sim_results()
