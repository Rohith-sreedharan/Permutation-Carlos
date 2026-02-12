#!/usr/bin/env python3
"""
Find valid EDGE SPREAD artifacts from production MongoDB
"""
import os
import sys
from pymongo import MongoClient

# MongoDB connection
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
client = MongoClient(MONGO_URI)
db = client["permu"]

print("=" * 80)
print("REQUIREMENT 1: Real sim_results in MongoDB")
print("=" * 80)

# Show real sim_results
real_sim = db["monte_carlo_simulations"].find_one(
    {
        "sharp_analysis.spread.model_spread": {"$exists": True, "$ne": 0},
        "team_a_win_probability": {"$ne": 0.5}
    }
)

if real_sim:
    print(f"✅ Real simulation found:")
    print(f"   game_id: {real_sim.get('game_id')}")
    print(f"   model_spread: {real_sim.get('sharp_analysis', {}).get('spread', {}).get('model_spread')}")
    print(f"   team_a_win_prob: {real_sim.get('team_a_win_probability')}")
    print(f"   created_at: {real_sim.get('created_at')}")
else:
    print("❌ No real simulations found")

print("\n" + "=" * 80)
print("REQUIREMENT 2: Fail-closed behavior")
print("=" * 80)

# Find event WITHOUT simulation
event_without_sim = db["events"].aggregate([
    {
        "$lookup": {
            "from": "monte_carlo_simulations",
            "localField": "game_id",
            "foreignField": "game_id",
            "as": "sims"
        }
    },
    {
        "$match": {
            "sims": {"$eq": []},
            "odds.spreads": {"$exists": True, "$ne": []}
        }
    },
    {"$limit": 1}
]).next()

if event_without_sim:
    print(f"✅ Event without simulation found:")
    print(f"   game_id: {event_without_sim['game_id']}")
    print(f"   league: {event_without_sim['league']}")
    print(f"   home: {event_without_sim.get('home_team', 'N/A')}")
    print(f"\nCurl command to prove fail-closed:")
    print(f"curl -v 'https://beta.beatvegas.app/api/games/{event_without_sim['league']}/{event_without_sim['game_id']}/decisions'")
else:
    print("⚠️  No events without simulations (all have sims)")

print("\n" + "=" * 80)
print("REQUIREMENT 4: Find EDGE SPREAD (edge >= 2.0, prob >= 0.55)")
print("=" * 80)

# Find EDGE spread candidates
edge_spreads = db["monte_carlo_simulations"].aggregate([
    {
        "$match": {
            "sharp_analysis.spread.model_spread": {"$exists": True, "$ne": None},
            "team_a_win_probability": {"$exists": True, "$ne": None}
        }
    },
    {
        "$lookup": {
            "from": "events",
            "localField": "game_id",
            "foreignField": "game_id",
            "as": "event"
        }
    },
    {"$unwind": "$event"},
    {
        "$match": {
            "event.odds.spreads": {"$exists": True, "$ne": []}
        }
    },
    {
        "$addFields": {
            "model_spread": "$sharp_analysis.spread.model_spread",
            "market_spread": {"$arrayElemAt": ["$event.odds.spreads.points", 0]},
            "home_win_prob": "$team_a_win_probability"
        }
    },
    {
        "$addFields": {
            "edge": {"$abs": {"$subtract": ["$model_spread", "$market_spread"]}}
        }
    },
    {
        "$match": {
            "edge": {"$gte": 2.0},
            "home_win_prob": {"$gte": 0.55}
        }
    },
    {"$limit": 5}
])

found_edge_spread = False
for sim in edge_spreads:
    found_edge_spread = True
    print(f"\n✅ EDGE SPREAD candidate:")
    print(f"   game_id: {sim['game_id']}")
    print(f"   league: {sim['event']['league']}")
    print(f"   home: {sim['event'].get('home_team', 'N/A')}")
    print(f"   away: {sim['event'].get('away_team', 'N/A')}")
    print(f"   model_spread: {sim['model_spread']:.2f}")
    print(f"   market_spread: {sim['market_spread']}")
    print(f"   edge: {sim['edge']:.2f}")
    print(f"   home_win_prob: {sim['home_win_prob']:.2%}")
    print(f"\nCurl command:")
    print(f"curl -s 'https://beta.beatvegas.app/api/games/{sim['event']['league']}/{sim['game_id']}/decisions' | jq '.spread'")

if not found_edge_spread:
    print("❌ No EDGE spreads found (edge >= 2.0 AND prob >= 0.55)")
    print("\nSearching for looser criteria (edge >= 1.5)...")
    
    # Try looser criteria
    looser = db["monte_carlo_simulations"].aggregate([
        {
            "$match": {
                "sharp_analysis.spread.model_spread": {"$exists": True, "$ne": None},
                "team_a_win_probability": {"$exists": True, "$ne": None}
            }
        },
        {
            "$lookup": {
                "from": "events",
                "localField": "game_id",
                "foreignField": "game_id",
                "as": "event"
            }
        },
        {"$unwind": "$event"},
        {
            "$match": {
                "event.odds.spreads": {"$exists": True, "$ne": []}
            }
        },
        {
            "$addFields": {
                "model_spread": "$sharp_analysis.spread.model_spread",
                "market_spread": {"$arrayElemAt": ["$event.odds.spreads.points", 0]},
                "home_win_prob": "$team_a_win_probability"
            }
        },
        {
            "$addFields": {
                "edge": {"$abs": {"$subtract": ["$model_spread", "$market_spread"]}}
            }
        },
        {"$sort": {"edge": -1}},
        {"$limit": 3}
    ])
    
    for sim in looser:
        print(f"\n⚠️  Best candidate (looser criteria):")
        print(f"   game_id: {sim['game_id']}")
        print(f"   league: {sim['event']['league']}")
        print(f"   model_spread: {sim['model_spread']:.2f}")
        print(f"   market_spread: {sim['market_spread']}")
        print(f"   edge: {sim['edge']:.2f}")
        print(f"   home_win_prob: {sim['home_win_prob']:.2%}")

print("\n" + "=" * 80)
