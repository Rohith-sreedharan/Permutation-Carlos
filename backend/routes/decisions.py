"""
UNIFIED DECISIONS ENDPOINT
==========================

GET /games/{league}/{game_id}/decisions

Returns all three market decisions in ONE payload.
Prevents stale mixing across tabs.
"""

from fastapi import APIRouter, HTTPException
from typing import Optional
from core.market_decision import GameDecisions
from core.compute_market_decision import MarketDecisionComputer
from datetime import datetime
from db.mongo import db

router = APIRouter()


@router.get("/games/{league}/{game_id}/decisions")
async def get_game_decisions(league: str, game_id: str) -> GameDecisions:
    """
    SINGLE ENDPOINT for all market decisions.
    
    Returns spread, moneyline, total in one atomic payload.
    UI must fetch this ONCE and render all tabs from it.
    
    NO separate endpoints for individual markets.
    """
    
    # Fetch event from MongoDB (try both 'id' and 'event_id' fields)
    event = db["events"].find_one({"$or": [{"id": game_id}, {"event_id": game_id}]})
    if not event:
        raise HTTPException(status_code=404, detail=f"Game {game_id} not found")
    
    # Fetch simulation result (try both game_id and event_id)
    sim_doc = db["simulation_results"].find_one({"$or": [{"game_id": game_id}, {"event_id": game_id}]})
    if not sim_doc:
        raise HTTPException(status_code=404, detail=f"Simulation not found for {game_id}")
    
    # Extract odds from event (OddsAPI format)
    bookmakers = event.get("bookmakers", [])
    if not bookmakers:
        raise HTTPException(status_code=404, detail=f"No odds available for {game_id}")
    
    # Use first bookmaker with markets
    primary_book = bookmakers[0]
    markets = {m["key"]: m for m in primary_book.get("markets", [])}
    
    # Build odds_snapshot
    spread_market = markets.get("spreads", {})
    total_market = markets.get("totals", {})
    
    home_team = event.get("home_team", "")
    away_team = event.get("away_team", "")
    home_id = event.get("home_team_normalized", home_team.replace(" ", "_").lower())
    away_id = event.get("away_team_normalized", away_team.replace(" ", "_").lower())
    
    spread_outcomes = spread_market.get("outcomes", [])
    total_outcomes = total_market.get("outcomes", [])
    
    # Parse spread lines
    spread_lines = {}
    for outcome in spread_outcomes:
        team_name = outcome.get("name", "")
        is_home = team_name == home_team
        team_id = home_id if is_home else away_id
        spread_lines[team_id] = {
            "line": outcome.get("point", 0),
            "odds": outcome.get("price", -110)
        }
    
    # Parse total lines
    over_outcome = next((o for o in total_outcomes if o.get("name") == "Over"), None)
    under_outcome = next((o for o in total_outcomes if o.get("name") == "Under"), None)
    
    odds_snapshot = {
        'timestamp': event.get("updated_at", datetime.utcnow().isoformat()),
        'spread_lines': spread_lines,
        'total_lines': {
            'line': over_outcome.get("point", 220) if over_outcome else 220,
            'odds': over_outcome.get("price", -110) if over_outcome else -110
        }
    }
    
    # Build sim_result from MongoDB
    sim_result = {
        'simulation_id': sim_doc.get("simulation_id", f"sim_{game_id}"),
        'model_spread_home_perspective': sim_doc.get("spread", {}).get("home_spread", 0),
        'home_cover_probability': sim_doc.get("spread", {}).get("home_cover_prob", 0.5),
        'rcl_total': sim_doc.get("total", {}).get("projected_total", 220),
        'over_probability': sim_doc.get("total", {}).get("over_prob", 0.5),
        'volatility': sim_doc.get("volatility", "MODERATE"),
        'total_injury_impact': sim_doc.get("injury_impact", 0)
    }
    
    config = {
        'profile': 'balanced',
        'edge_threshold': 2.0,
        'lean_threshold': 1.0,
        'prob_threshold': 0.55
    }
    
    game_competitors = {
        home_id: home_team,
        away_id: away_team
    }
    
    # Compute all markets
    computer = MarketDecisionComputer(league, game_id, f'odds_event_{game_id}')
    
    spread_decision = computer.compute_spread(odds_snapshot, sim_result, config, game_competitors)
    total_decision = computer.compute_total(odds_snapshot, sim_result, config, game_competitors)
    
    # Build unified response
    decisions = GameDecisions(
        spread=spread_decision,
        moneyline=None,  # TODO: implement ML compute
        total=total_decision,
        inputs_hash=spread_decision.debug.inputs_hash,
        decision_version=spread_decision.debug.decision_version,
        computed_at=datetime.utcnow().isoformat()
    )
    
    return decisions
