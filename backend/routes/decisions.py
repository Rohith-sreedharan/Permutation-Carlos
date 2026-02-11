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

# League-aware default totals to prevent cross-league data corruption
LEAGUE_DEFAULT_TOTALS = {
    "NBA": 220.0,
    "NCAAB": 145.0,
    "NFL": 45.0,
    "NCAAF": 50.0,
    "NHL": 5.5,
    "MLB": 8.5,
}

def get_default_total(league: str) -> float:
    """Return a sensible default total for the given league."""
    return LEAGUE_DEFAULT_TOTALS.get(league.upper(), 100.0)


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
    
    # Fetch simulation from monte_carlo_simulations (the actual simulation engine output)
    # DETERMINISTIC: Select latest by created_at to handle multiple sims per game
    sim_doc = db["monte_carlo_simulations"].find_one(
        {"$or": [{"game_id": game_id}, {"event_id": game_id}]},
        sort=[("created_at", -1)]  # Latest first
    )
    if not sim_doc:
        raise HTTPException(status_code=404, detail=f"Simulation not found for {game_id}")
    
    # Extract sharp_analysis structure
    sharp_analysis = sim_doc.get("sharp_analysis", {})
    spread_data = sharp_analysis.get("spread", {})
    total_data = sharp_analysis.get("total", {})
    
    # FAIL-CLOSED: Check for real spread data
    has_real_spread = spread_data.get("model_spread") is not None
    
    # FAIL-CLOSED: Check for real total data (rcl_total or model_total)
    rcl_total_value = sim_doc.get("rcl_total") or total_data.get("model_total")
    has_real_total = rcl_total_value is not None
    
    if not has_real_spread:
        raise HTTPException(
            status_code=503,
            detail=f"FAIL-CLOSED: No model_spread for {game_id}. Cannot classify spread."
        )
    
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
    
    # Helper function to convert European odds to American odds
    def european_to_american(euro_odds: float) -> int:
        if euro_odds >= 2.0:
            return int((euro_odds - 1) * 100)
        else:
            return int(-100 / (euro_odds - 1))
    
    # Parse spread lines
    spread_lines = {}
    for outcome in spread_outcomes:
        team_name = outcome.get("name", "")
        is_home = team_name == home_team
        team_id = home_id if is_home else away_id
        price = outcome.get("price", 1.91)
        # Convert European odds to American
        american_odds = european_to_american(price) if isinstance(price, float) and price < 10 else int(price)
        spread_lines[team_id] = {
            "line": outcome.get("point", 0),
            "odds": american_odds
        }
    
    # Parse total lines
    over_outcome = next((o for o in total_outcomes if o.get("name") == "Over"), None)
    under_outcome = next((o for o in total_outcomes if o.get("name") == "Under"), None)
    
    # Convert total odds to American
    over_price = over_outcome.get("price", 1.91) if over_outcome else 1.91
    over_odds = european_to_american(over_price) if isinstance(over_price, float) and over_price < 10 else int(over_price)
    
    # Get league-appropriate default total
    default_total = get_default_total(league)
    
    odds_snapshot = {
        'timestamp': event.get("updated_at", datetime.utcnow().isoformat()),
        'spread_lines': spread_lines,
        'total_lines': {
            'line': over_outcome.get("point", default_total) if over_outcome else default_total,
            'odds': over_odds
        }
    }
    
    # Build sim_result from MongoDB (using actual monte_carlo_simulations structure)
    # Field mappings based on actual document structure:
    # - sharp_analysis.spread.model_spread -> model spread
    # - rcl_total (top-level) or sharp_analysis.total.model_total -> fair total
    # - team_a_win_probability (top-level) -> home win prob (team_a = home)
    # - over_probability (top-level) -> over prob
    
    # Extract injury_impact - handle both numeric and list format
    injury_impact_raw = sim_doc.get("injury_impact")
    if isinstance(injury_impact_raw, (int, float)):
        injury_impact = float(injury_impact_raw)
    elif isinstance(injury_impact_raw, list):
        injury_impact = 0.0  # If it's a list, use the injury_impact_weighted field instead
    else:
        injury_impact = sim_doc.get("injury_impact_weighted") or 0.0
    
    sim_result = {
        'simulation_id': sim_doc.get("simulation_id", f"sim_{game_id}"),
        # Spread: model_spread is from sharp_analysis.spread.model_spread
        'model_spread_home_perspective': spread_data.get("model_spread", 0),
        # Cover probability: team_a_win_probability (team_a = home team)
        # This is a critical field for classifications
        'home_cover_probability': sim_doc.get("team_a_win_probability") or sim_doc.get("win_probability") or 0.5,
        # Total: use rcl_total_value computed earlier (fail-closed if None)
        'rcl_total': rcl_total_value if rcl_total_value is not None else default_total,
        # Over probability from top-level
        'over_probability': sim_doc.get("over_probability") or 0.5,
        'volatility': sim_doc.get("volatility_label") or sim_doc.get("mode") or "MODERATE",
        'total_injury_impact': injury_impact
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
    
    # FAIL-CLOSED for totals: only compute if we have real fair_total data
    total_decision = None
    if has_real_total:
        total_decision = computer.compute_total(odds_snapshot, sim_result, config, game_competitors)
    # If no real total data, total_decision stays None (blocked)
    
    # Build unified response
    decisions = GameDecisions(
        spread=spread_decision,
        moneyline=None,  # TODO: implement ML compute
        total=total_decision,
        home_team_name=home_team,
        away_team_name=away_team,
        inputs_hash=spread_decision.debug.inputs_hash,
        decision_version=spread_decision.debug.decision_version,
        computed_at=datetime.utcnow().isoformat()
    )
    
    return decisions
