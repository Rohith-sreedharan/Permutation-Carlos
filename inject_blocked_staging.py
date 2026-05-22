"""
Staging data injector - two BLOCKED-state simulations for screenshot evidence.
Uses correct collection: monte_carlo_simulations (not simulations)
"""
import sys, os
sys.path.insert(0, '/root/Permutation-Carlos')
os.chdir('/root/Permutation-Carlos')

from pymongo import MongoClient
from datetime import datetime, timezone

MONGO_URI = 'mongodb+srv://crmmanager_db_user:crmmanager_db_user@beatvegas.varyfzx.mongodb.net/?appName=beatvegas'
client = MongoClient(MONGO_URI)
db = client['beatvegas']

def make_sim(event_id, home_team, away_team, sport_key):
    """
    BLOCKED state logic:
    - edge_class='LEAN' + confidence>=25 → Classification.LEAN
    - EV=(model_prob - market_prob)*100 = (0.48-0.52)*100 = -4 → EV_POSITIVE fails
    - LEAN + blocked EV → release_status=BLOCKED_BY_EV → isApproved=False
    - show_action_summary=False, classification=LEAN → ACTION_SUMMARY_PARITY fails
    - canPublish=False → analysisBlocked=True → BLOCKED banner shown
    """
    now = datetime.now(timezone.utc)
    return {
        "simulation_id": f"staging_{event_id}",
        "event_id": event_id,
        "team_a": home_team,
        "team_b": away_team,
        "confidence_score": 0.51,
        "volatility_score": 80,
        "volatility_index": 80,
        "iterations": 10000,
        "avg_margin": 0.5,
        "avg_team_a_score": 105.0,
        "avg_team_b_score": 104.5,
        "avg_total": 209.5,
        "avg_total_score": 209.5,
        "can_publish": False,
        "can_parlay": False,
        "created_at": now,
        "variance": 0.08,
        "market_context": {
            "sport_key": sport_key,
            "commence_time": "2026-05-17T02:00:00+00:00",
            "total_line": 209.5,
        },
        "outcome": {
            "confidence": 0.51,
            "home_win_prob": 0.51,
            "away_win_prob": 0.49,
        },
        "metadata": {
            "user_tier": "free",
            "iterations_run": 10000,
            "sim_count_used": 10000,
            "variance": 0.08,
            "ci_95": [-8, 8],
        },
        "confidence_intervals": {
            "ci_68": [-4, 4],
            "ci_95": [-8, 8],
            "ci_99": [-12, 12],
        },
        "market_views": {
            "spread": {
                "edge_class": "LEAN",
                "snapshot_hash": f"staging-{event_id}-spread",
                "integrity_status": "DEGRADED",
                "model_preference_selection_id": f"sel_{event_id}_home",
                "edge_points": 0.5,
                "grade": None,
                "ev": -2.3,
                "confidence_score": 51,
                "volatility_score": 80,
                "selections": [
                    {
                        "selection_id": f"sel_{event_id}_home",
                        "name": home_team,
                        "side": "HOME",
                        "model_probability": 0.48,
                        "market_probability": 0.52,
                        "market_line_for_selection": -1.5,
                        "model_fair_line_for_selection": -1.0,
                    },
                    {
                        "selection_id": f"sel_{event_id}_away",
                        "name": away_team,
                        "side": "AWAY",
                        "model_probability": 0.52,
                        "market_probability": 0.48,
                        "market_line_for_selection": 1.5,
                        "model_fair_line_for_selection": 1.0,
                    }
                ],
                "cover_probability_home": 48,
                "cover_probability_away": 52,
                "edge_gap": 0.5,
            },
            "total": {
                "edge_class": "LEAN",
                "snapshot_hash": f"staging-{event_id}-total",
                "integrity_status": "DEGRADED",
                "model_preference_selection_id": f"sel_{event_id}_over",
                "edge_points": 0.3,
                "grade": None,
                "ev": -1.8,
                "confidence_score": 51,
                "volatility_score": 80,
                "selections": [
                    {
                        "selection_id": f"sel_{event_id}_over",
                        "name": "Over",
                        "side": "OVER",
                        "model_probability": 0.47,
                        "market_probability": 0.52,
                        "market_line_for_selection": 209.5,
                        "model_fair_line_for_selection": 207.5,
                    },
                    {
                        "selection_id": f"sel_{event_id}_under",
                        "name": "Under",
                        "side": "UNDER",
                        "model_probability": 0.53,
                        "market_probability": 0.48,
                        "market_line_for_selection": 209.5,
                        "model_fair_line_for_selection": 207.5,
                    }
                ],
                "over_probability": 47,
                "under_probability": 53,
                "edge_gap": 0.3,
            },
            "moneyline": {
                "edge_class": "MARKET_ALIGNED",
                "snapshot_hash": f"staging-{event_id}-ml",
                "integrity_status": "DEGRADED",
                "ev": -3.0,
                "confidence_score": 51,
                "selections": [],
            }
        }
    }

def make_event(event_id, home_team, away_team, sport_key):
    return {
        "event_id": event_id,
        "sport_key": sport_key,
        "sport_title": "NBA",
        "commence_time": "2026-05-17T02:00:00Z",
        "home_team": home_team,
        "away_team": away_team,
        "bookmakers": [],
        "odds_timestamp": None,
    }

STAGING_GAMES = [
    {
        "event_id": "staging_blocked_001_evidence",
        "home_team": "Memphis Grizzlies",
        "away_team": "Sacramento Kings",
        "sport_key": "basketball_nba",
    },
    {
        "event_id": "staging_blocked_002_evidence",
        "home_team": "Denver Nuggets",
        "away_team": "Oklahoma City Thunder",
        "sport_key": "basketball_nba",
    }
]

for g in STAGING_GAMES:
    eid = g["event_id"]
    # Clean up ALL related collections
    for col in ["simulations", "monte_carlo_simulations", "events"]:
        db[col].delete_many({"event_id": eid})

    sim = make_sim(eid, g["home_team"], g["away_team"], g["sport_key"])
    evt = make_event(eid, g["home_team"], g["away_team"], g["sport_key"])

    db.monte_carlo_simulations.insert_one(sim)
    db.events.insert_one(evt)
    print(f"Inserted: {g['away_team']} @ {g['home_team']} → {eid}")

print("\nNavigate to:")
for g in STAGING_GAMES:
    print(f"  https://beta.beatvegas.app/?gameId={g['event_id']}")

client.close()
