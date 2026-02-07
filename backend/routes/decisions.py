"""
UNIFIED DECISIONS ENDPOINT
==========================

GET /games/{league}/{game_id}/decisions

Returns all three market decisions in ONE payload.
Prevents stale mixing across tabs.
"""

from fastapi import APIRouter, HTTPException
from typing import Optional
from backend.core.market_decision import GameDecisions
from backend.core.compute_market_decision import MarketDecisionComputer
from datetime import datetime

router = APIRouter()


@router.get("/games/{league}/{game_id}/decisions")
async def get_game_decisions(league: str, game_id: str) -> GameDecisions:
    """
    SINGLE ENDPOINT for all market decisions.
    
    Returns spread, moneyline, total in one atomic payload.
    UI must fetch this ONCE and render all tabs from it.
    
    NO separate endpoints for individual markets.
    """
    
    # TODO: Fetch from your data layer
    # For now, mock structure
    odds_snapshot = {
        'timestamp': datetime.utcnow().isoformat(),
        'spread_lines': {
            'team_a_id': {'line': -6.5, 'odds': -110},
            'team_b_id': {'line': 6.5, 'odds': -110}
        },
        'total_lines': {
            'line': 227.5,
            'odds': -110
        }
    }
    
    sim_result = {
        'simulation_id': f'sim_{game_id}',
        'model_spread_home_perspective': -5.2,
        'home_cover_probability': 0.62,
        'rcl_total': 230.5,
        'over_probability': 0.58,
        'volatility': 'MODERATE',
        'total_injury_impact': 0
    }
    
    config = {
        'profile': 'balanced',
        'edge_threshold': 2.0,
        'lean_threshold': 1.0,
        'prob_threshold': 0.55
    }
    
    game_competitors = {
        'team_a_id': 'Team A',
        'team_b_id': 'Team B'
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
