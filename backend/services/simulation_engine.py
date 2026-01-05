"""
Simulation Engine

Monte Carlo simulation runner with sport-specific calibration.
"""
from typing import Dict, Optional
import numpy as np
from datetime import datetime

from ..core.sport_configs import Sport, MarketType
from ..core.mlb_calibration import evaluate_mlb_market
from ..core.ncaab_calibration import evaluate_ncaab_market
from ..core.ncaaf_calibration import evaluate_ncaaf_market
from ..core.nfl_calibration import evaluate_nfl_market
from ..core.nhl_calibration import evaluate_nhl_market
# from ..core.nba_calibration import evaluate_nba_market  # TODO: Create NBA calibration module
from ..core.sharp_side_selection import select_sharp_side_spread, select_sharp_side_total, select_sharp_side_moneyline, validate_sharp_side_alignment
from ..db.database import Database


class SimulationEngine:
    """Run Monte Carlo simulations for sports betting"""
    
    def __init__(self, db: Database):
        self.db = db
        
    async def run_simulation(
        self,
        game_id: str,
        sport: Sport,
        market_type: MarketType,
        num_simulations: int = 50000,
        **market_data
    ) -> Dict:
        """Run Monte Carlo simulation for a game market"""
        
        # Select calibration function
        evaluators = {
            Sport.MLB: evaluate_mlb_market,
            Sport.NCAAB: evaluate_ncaab_market,
            Sport.NCAAF: evaluate_ncaaf_market,
            Sport.NFL: evaluate_nfl_market,
            Sport.NHL: evaluate_nhl_market
            # Sport.NBA: evaluate_nba_market  # TODO: Create NBA calibration
        }
        
        evaluator = evaluators.get(sport)
        if not evaluator:
            raise ValueError(f"No evaluator for sport: {sport}")
            
        # Run evaluation
        evaluation = evaluator(market_type, **market_data)
        
        # Select sharp side if edge found
        sharp_side = None
        if evaluation.edge_state.value == "EDGE":
            if market_type == MarketType.SPREAD:
                # Extract team names and spreads from market data
                home_team = market_data.get("home_team", market_data.get("team_a_name", "Home"))
                away_team = market_data.get("away_team", market_data.get("team_b_name", "Away"))
                market_spread_home = market_data.get("home_spread", market_data.get("team_a_spread", 0.0))
                model_spread = market_data.get("model_spread", 0.0)
                
                sharp_side = select_sharp_side_spread(
                    home_team=home_team,
                    away_team=away_team,
                    market_spread_home=market_spread_home,
                    model_spread=model_spread,
                    volatility=evaluation.volatility,
                    market_odds_home=market_data.get("home_spread_odds", market_data.get("team_a_spread_odds", -110)),
                    market_odds_away=market_data.get("away_spread_odds", market_data.get("team_b_spread_odds", -110))
                )
            elif market_type == MarketType.TOTAL:
                sharp_side = select_sharp_side_total(
                    over_prob=market_data.get("over_prob", 0.5),
                    under_prob=market_data.get("under_prob", 0.5),
                    total_line=market_data.get("over_line", 0.0),
                    compressed_edge=evaluation.compressed_edge,
                    volatility=evaluation.volatility,
                    over_odds=market_data.get("over_odds", -110),
                    under_odds=market_data.get("under_odds", -110)
                )
            elif market_type == MarketType.MONEYLINE:
                sharp_side = select_sharp_side_moneyline(
                    team_a_win_prob=market_data.get("team_a_win_prob", 0.5),
                    team_b_win_prob=market_data.get("team_b_win_prob", 0.5),
                    team_a_name=market_data.get("team_a_name", "Team A"),
                    team_b_name=market_data.get("team_b_name", "Team B"),
                    compressed_edge=evaluation.compressed_edge,
                    team_a_odds=market_data.get("team_a_ml_odds", -110),
                    team_b_odds=market_data.get("team_b_ml_odds", -110)
                )
                
            # Validate alignment
            is_valid, error = validate_sharp_side_alignment(
                edge_state=evaluation.edge_state,
                sharp_side_selection=sharp_side
            )
            
            if not is_valid:
                raise ValueError(f"Sharp side validation failed: {error}")
        
        # Return simulation result
        return {
            "game_id": game_id,
            "sport": sport.value,
            "market_type": market_type.value,
            "edge_state": evaluation.edge_state.value,
            "raw_edge": evaluation.raw_edge,
            "compressed_edge": evaluation.compressed_edge,
            "sharp_side": sharp_side,
            "volatility": evaluation.volatility.value,
            "eligible": evaluation.eligible,
            "blocking_reason": evaluation.blocking_reason,
            "num_simulations": num_simulations,
            "timestamp": datetime.now().isoformat()
        }
