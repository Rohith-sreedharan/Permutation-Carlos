#!/usr/bin/env python3
"""
Artifact Finder - DB-driven script to find valid MARKET_ALIGNED and EDGE spreads.

Outputs real game_ids that can be used for curl commands.

MARKET_ALIGNED: |model_spread - vegas_spread| < 1.0 (tight alignment)
EDGE: |model_spread - vegas_spread| >= 2.0 AND team_a_win_probability >= 0.55
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db.mongo import db


def find_market_aligned_spreads(limit: int = 10):
    """
    Find games where model spread is tightly aligned with market spread.
    MARKET_ALIGNED: edge_points < 1.0
    """
    print("\n=== MARKET_ALIGNED SPREAD CANDIDATES ===")
    print("Criteria: |model_spread - vegas_spread| < 1.0")
    print("-" * 60)
    
    # Query for sims with real spread data
    pipeline = [
        {
            "$match": {
                "sharp_analysis.spread.model_spread": {"$exists": True, "$ne": None},
                "sharp_analysis.spread.vegas_spread": {"$exists": True, "$ne": None},
            }
        },
        {
            "$addFields": {
                "edge_points": {
                    "$abs": {
                        "$subtract": [
                            "$sharp_analysis.spread.model_spread",
                            "$sharp_analysis.spread.vegas_spread"
                        ]
                    }
                }
            }
        },
        {
            "$match": {
                "edge_points": {"$lt": 1.0}  # MARKET_ALIGNED threshold
            }
        },
        {
            "$sort": {"edge_points": 1}  # Smallest edge first (most aligned)
        },
        {
            "$limit": limit
        },
        {
            "$project": {
                "event_id": 1,
                "game_id": 1,
                "sport_key": 1,
                "model_spread": "$sharp_analysis.spread.model_spread",
                "vegas_spread": "$sharp_analysis.spread.vegas_spread",
                "edge_points": 1,
                "team_a_win_probability": 1,
                "created_at": 1
            }
        }
    ]
    
    results = list(db.monte_carlo_simulations.aggregate(pipeline))
    
    if not results:
        print("❌ No MARKET_ALIGNED spreads found")
        return []
    
    for i, doc in enumerate(results, 1):
        game_id = doc.get("event_id") or doc.get("game_id")
        sport = doc.get("sport_key", "unknown")
        model = doc.get("model_spread", 0)
        vegas = doc.get("vegas_spread", 0)
        edge = doc.get("edge_points", 0)
        prob = doc.get("team_a_win_probability", 0.5)
        
        print(f"{i}. game_id: {game_id}")
        print(f"   sport: {sport}")
        print(f"   model_spread: {model:.2f}, vegas_spread: {vegas:.2f}")
        print(f"   edge_points: {edge:.2f} (< 1.0 = MARKET_ALIGNED)")
        print(f"   win_probability: {prob}")
        print()
    
    return results


def find_edge_spreads(limit: int = 10):
    """
    Find games with significant edge AND high probability.
    EDGE: edge_points >= 2.0 AND probability >= 0.55
    """
    print("\n=== EDGE SPREAD CANDIDATES ===")
    print("Criteria: |model_spread - vegas_spread| >= 2.0 AND win_probability >= 0.55")
    print("-" * 60)
    
    pipeline = [
        {
            "$match": {
                "sharp_analysis.spread.model_spread": {"$exists": True, "$ne": None},
                "sharp_analysis.spread.vegas_spread": {"$exists": True, "$ne": None},
                "team_a_win_probability": {"$exists": True, "$gte": 0.55}  # Probability threshold
            }
        },
        {
            "$addFields": {
                "edge_points": {
                    "$abs": {
                        "$subtract": [
                            "$sharp_analysis.spread.model_spread",
                            "$sharp_analysis.spread.vegas_spread"
                        ]
                    }
                }
            }
        },
        {
            "$match": {
                "edge_points": {"$gte": 2.0}  # EDGE threshold
            }
        },
        {
            "$sort": {"edge_points": -1}  # Largest edge first
        },
        {
            "$limit": limit
        },
        {
            "$project": {
                "event_id": 1,
                "game_id": 1,
                "sport_key": 1,
                "model_spread": "$sharp_analysis.spread.model_spread",
                "vegas_spread": "$sharp_analysis.spread.vegas_spread",
                "edge_points": 1,
                "team_a_win_probability": 1,
                "created_at": 1
            }
        }
    ]
    
    results = list(db.monte_carlo_simulations.aggregate(pipeline))
    
    if not results:
        # Try relaxed criteria (without probability threshold)
        print("⚠️  No EDGE spreads with probability >= 0.55 found")
        print("    Trying relaxed criteria (edge >= 2.0 only)...")
        
        pipeline[0]["$match"].pop("team_a_win_probability", None)
        results = list(db.monte_carlo_simulations.aggregate(pipeline))
        
        if not results:
            print("❌ No EDGE spreads found")
            return []
    
    for i, doc in enumerate(results, 1):
        game_id = doc.get("event_id") or doc.get("game_id")
        sport = doc.get("sport_key", "unknown")
        model = doc.get("model_spread", 0)
        vegas = doc.get("vegas_spread", 0)
        edge = doc.get("edge_points", 0)
        prob = doc.get("team_a_win_probability", 0.5)
        
        print(f"{i}. game_id: {game_id}")
        print(f"   sport: {sport}")
        print(f"   model_spread: {model:.2f}, vegas_spread: {vegas:.2f}")
        print(f"   edge_points: {edge:.2f} (>= 2.0 = EDGE)")
        print(f"   win_probability: {prob}")
        print()
    
    return results


def output_curl_commands(market_aligned: list, edge: list):
    """Output curl commands for the found artifacts."""
    print("\n" + "=" * 60)
    print("CURL COMMANDS FOR ARTIFACTS")
    print("=" * 60)
    
    if market_aligned:
        doc = market_aligned[0]
        game_id = doc.get("event_id") or doc.get("game_id")
        sport = doc.get("sport_key", "basketball_nba")
        league = sport.split("_")[-1].upper() if "_" in sport else sport.upper()
        print(f"\n# MARKET_ALIGNED SPREAD")
        print(f"curl -s 'https://beta.beatvegas.app/api/games/{league}/{game_id}/decisions' | jq '.spread'")
    
    if edge:
        doc = edge[0]
        game_id = doc.get("event_id") or doc.get("game_id")
        sport = doc.get("sport_key", "basketball_nba")
        league = sport.split("_")[-1].upper() if "_" in sport else sport.upper()
        print(f"\n# EDGE SPREAD")
        print(f"curl -s 'https://beta.beatvegas.app/api/games/{league}/{game_id}/decisions' | jq '.spread'")


if __name__ == "__main__":
    print("=" * 60)
    print("ARTIFACT FINDER - Finding valid MARKET_ALIGNED and EDGE spreads")
    print("=" * 60)
    
    market_aligned = find_market_aligned_spreads(limit=5)
    edge = find_edge_spreads(limit=5)
    
    output_curl_commands(market_aligned, edge)
    
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"MARKET_ALIGNED candidates: {len(market_aligned)}")
    print(f"EDGE candidates: {len(edge)}")
