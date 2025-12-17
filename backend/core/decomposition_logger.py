"""
Decomposition Logger - ROOT CAUSE TRACKING
Logs game-level scoring components to detect double-counting and structural bias

THIS IS THE #1 MISSING PIECE - IT CATCHES OVER-BIAS AT THE SOURCE

For every simulation, logs:
- Drives per team
- Points per drive (PPD)
- TD rate / FG rate
- Turnover rate
- Pace / possessions
- Red-zone conversion

These are compared to league baselines DAILY.
If pace OR efficiency exceeds baseline → auto dampen
"""

from typing import Dict, Any, Optional, List
from datetime import datetime, timezone, date as date_type
from db.mongo import db
import logging
import numpy as np

logger = logging.getLogger(__name__)


def _convert_to_native_types(obj: Any) -> Any:
    """Convert numpy types to Python native types for MongoDB"""
    if isinstance(obj, np.integer):
        return int(obj)
    elif isinstance(obj, np.floating):
        return float(obj)
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    elif isinstance(obj, dict):
        return {k: _convert_to_native_types(v) for k, v in obj.items()}
    elif isinstance(obj, (list, tuple)):
        return [_convert_to_native_types(item) for item in obj]
    return obj


# League baseline constants (from historical data)
LEAGUE_BASELINES = {
    # NFL
    "americanfootball_nfl": {
        "drives_per_team": 11.2,
        "points_per_drive": 1.95,  # ~22 pts / 11.2 drives
        "td_rate": 0.22,           # 22% of drives end in TD
        "fg_rate": 0.17,           # 17% end in FG
        "turnover_rate": 0.13,     # 13% turnovers
        "possessions_per_game": 11.2,
        "avg_total": 44.5
    },
    # NCAA Football
    "americanfootball_ncaaf": {
        "drives_per_team": 12.8,
        "points_per_drive": 2.15,  # ~27.5 pts / 12.8 drives
        "td_rate": 0.25,
        "fg_rate": 0.15,
        "turnover_rate": 0.15,
        "possessions_per_game": 12.8,
        "avg_total": 55.0
    },
    # NBA
    "basketball_nba": {
        "possessions_per_team": 100.0,
        "points_per_possession": 1.12,  # ~112 pts / 100 poss
        "pace": 100.0,
        "avg_total": 224.0
    },
    # NCAA Basketball
    "basketball_ncaab": {
        "possessions_per_team": 70.0,
        "points_per_possession": 1.01,  # ~71 pts / 70 poss
        "pace": 70.0,
        "avg_total": 142.0
    },
    # MLB
    "baseball_mlb": {
        "innings_per_game": 9.0,
        "runs_per_inning": 0.50,  # ~4.5 runs / 9 innings
        "avg_total": 9.0
    },
    # NHL
    "icehockey_nhl": {
        "periods_per_game": 3.0,
        "goals_per_period": 1.0,  # ~3.0 goals / 3 periods
        "avg_total": 6.0
    }
}


class DecompositionLogger:
    """
    Logs scoring decomposition for every simulation
    Enables daily baseline checks to detect structural bias
    """
    
    def __init__(self):
        self.collection = db["decomposition_logs"]
        self._ensure_indexes()
    
    def _ensure_indexes(self):
        """Create indexes for efficient queries"""
        try:
            self.collection.create_index([("game_id", 1)])
            self.collection.create_index([("sport", 1), ("timestamp", -1)])
            self.collection.create_index([("sport", 1), ("date", -1)])
        except Exception as e:
            logger.warning(f"Failed to create decomposition indexes: {e}")
    
    def log_decomposition(
        self,
        game_id: str,
        sport: str,
        simulation_id: str,
        team_a_name: str,
        team_b_name: str,
        decomposition_data: Dict[str, Any],
        model_total: float,
        vegas_total: float,
        timestamp: Optional[datetime] = None
    ) -> None:
        """
        Log simulation decomposition for baseline comparison
        
        Args:
            game_id: Unique game identifier
            sport: Sport key (americanfootball_nfl, etc.)
            simulation_id: Simulation ID
            team_a_name: Home team name
            team_b_name: Away team name
            decomposition_data: Component metrics (drives, PPD, pace, etc.)
            model_total: Model projected total
            vegas_total: Market total line
            timestamp: Log timestamp (defaults to now)
        """
        if timestamp is None:
            timestamp = datetime.now(timezone.utc)
        
        baseline = LEAGUE_BASELINES.get(sport, {})
        
        # Calculate deviation from baseline
        deviations = self._calculate_deviations(sport, decomposition_data, baseline)
        
        # Convert all numpy types to native Python types for MongoDB
        decomposition_clean = _convert_to_native_types(decomposition_data)
        deviations_clean = _convert_to_native_types(deviations)
        
        # Build log entry
        log_entry = {
            "game_id": game_id,
            "sport": sport,
            "simulation_id": simulation_id,
            "timestamp": timestamp,
            "date": datetime.combine(timestamp.date(), datetime.min.time()).replace(tzinfo=timezone.utc),
            "team_a": team_a_name,
            "team_b": team_b_name,
            
            # Raw decomposition data
            "decomposition": decomposition_clean,
            
            # League baseline comparison
            "baseline": baseline,
            "deviations": deviations_clean,
            
            # Model vs market
            "model_total": model_total,
            "vegas_total": vegas_total,
            "model_vs_market": model_total - vegas_total,
            
            # Flags for anomaly detection
            "flags": self._generate_flags(deviations, model_total - vegas_total)
        }
        
        # Store in MongoDB
        try:
            self.collection.insert_one(log_entry)
            logger.info(f"📊 Decomposition logged: {game_id} ({sport})")
        except Exception as e:
            logger.error(f"Failed to log decomposition: {e}")
    
    def _calculate_deviations(
        self,
        sport: str,
        decomposition: Dict[str, Any],
        baseline: Dict[str, Any]
    ) -> Dict[str, float]:
        """Calculate deviations from league baseline"""
        deviations = {}
        
        if "football" in sport:
            # Football metrics
            if "drives_per_team" in decomposition and "drives_per_team" in baseline:
                deviations["drives_per_team"] = decomposition["drives_per_team"] - baseline["drives_per_team"]
            
            if "points_per_drive" in decomposition and "points_per_drive" in baseline:
                deviations["points_per_drive"] = decomposition["points_per_drive"] - baseline["points_per_drive"]
            
            if "td_rate" in decomposition and "td_rate" in baseline:
                deviations["td_rate"] = decomposition["td_rate"] - baseline["td_rate"]
            
            if "fg_rate" in decomposition and "fg_rate" in baseline:
                deviations["fg_rate"] = decomposition["fg_rate"] - baseline["fg_rate"]
        
        elif "basketball" in sport:
            # Basketball metrics
            if "possessions_per_team" in decomposition and "possessions_per_team" in baseline:
                deviations["possessions_per_team"] = decomposition["possessions_per_team"] - baseline["possessions_per_team"]
            
            if "points_per_possession" in decomposition and "points_per_possession" in baseline:
                deviations["points_per_possession"] = decomposition["points_per_possession"] - baseline["points_per_possession"]
            
            if "pace" in decomposition and "pace" in baseline:
                deviations["pace"] = decomposition["pace"] - baseline["pace"]
        
        elif sport == "baseball_mlb":
            if "runs_per_inning" in decomposition and "runs_per_inning" in baseline:
                deviations["runs_per_inning"] = decomposition["runs_per_inning"] - baseline["runs_per_inning"]
        
        elif sport == "icehockey_nhl":
            if "goals_per_period" in decomposition and "goals_per_period" in baseline:
                deviations["goals_per_period"] = decomposition["goals_per_period"] - baseline["goals_per_period"]
        
        return deviations
    
    def _generate_flags(
        self,
        deviations: Dict[str, float],
        model_vs_market: float
    ) -> List[str]:
        """Generate warning flags for anomaly detection"""
        flags = []
        
        # Check pace/drives deviation
        if "drives_per_team" in deviations and abs(deviations["drives_per_team"]) > 2.0:
            flags.append("EXCESSIVE_DRIVES")
        
        if "possessions_per_team" in deviations and abs(deviations["possessions_per_team"]) > 8.0:
            flags.append("EXCESSIVE_PACE")
        
        # Check efficiency deviation
        if "points_per_drive" in deviations and deviations["points_per_drive"] > 0.5:
            flags.append("EXCESSIVE_EFFICIENCY")
        
        if "points_per_possession" in deviations and deviations["points_per_possession"] > 0.15:
            flags.append("EXCESSIVE_EFFICIENCY")
        
        # Check TD/scoring rate deviation
        if "td_rate" in deviations and deviations["td_rate"] > 0.08:
            flags.append("EXCESSIVE_TD_RATE")
        
        # Check model vs market
        if model_vs_market > 6.0:
            flags.append("LARGE_OVER_BIAS")
        elif model_vs_market < -6.0:
            flags.append("LARGE_UNDER_BIAS")
        
        # CRITICAL: Double-counting detector
        if ("EXCESSIVE_DRIVES" in flags or "EXCESSIVE_PACE" in flags) and \
           ("EXCESSIVE_EFFICIENCY" in flags):
            flags.append("DOUBLE_COUNTING_LIKELY")
        
        return flags
    
    def compute_daily_baseline_check(
        self,
        sport: str,
        date: Optional[date_type] = None
    ) -> Dict[str, Any]:
        """
        Compute daily aggregate metrics vs baseline
        
        Returns dampening recommendation if thresholds exceeded
        """
        if date is None:
            date = datetime.now(timezone.utc).date()
        
        # Query all decompositions for this sport on this date
        logs = list(self.collection.find({
            "sport": sport,
            "date": date
        }))
        
        if not logs:
            logger.info(f"No decomposition logs found for {sport} on {date}")
            return {"games": 0, "dampening_needed": False}
        
        baseline = LEAGUE_BASELINES.get(sport, {})
        
        # Aggregate metrics
        total_games = len(logs)
        flagged_games = sum(1 for log in logs if len(log.get("flags", [])) > 0)
        double_counting_games = sum(1 for log in logs if "DOUBLE_COUNTING_LIKELY" in log.get("flags", []))
        
        # Average deviations
        avg_deviations = {}
        for key in ["drives_per_team", "points_per_drive", "possessions_per_team", "points_per_possession"]:
            values = [log["deviations"].get(key, 0) for log in logs if key in log.get("deviations", {})]
            if values:
                avg_deviations[key] = sum(values) / len(values)
        
        # Average model vs market
        avg_model_vs_market = sum(log.get("model_vs_market", 0) for log in logs) / total_games
        
        # Determine if dampening needed
        dampening_needed = False
        dampening_reasons = []
        
        # Check pace/drives
        if "drives_per_team" in avg_deviations and avg_deviations["drives_per_team"] > 1.5:
            dampening_needed = True
            dampening_reasons.append(f"Drives per team +{avg_deviations['drives_per_team']:.1f} above baseline")
        
        if "possessions_per_team" in avg_deviations and avg_deviations["possessions_per_team"] > 5.0:
            dampening_needed = True
            dampening_reasons.append(f"Possessions per team +{avg_deviations['possessions_per_team']:.1f} above baseline")
        
        # Check efficiency
        if "points_per_drive" in avg_deviations and avg_deviations["points_per_drive"] > 0.3:
            dampening_needed = True
            dampening_reasons.append(f"Points per drive +{avg_deviations['points_per_drive']:.2f} above baseline")
        
        if "points_per_possession" in avg_deviations and avg_deviations["points_per_possession"] > 0.10:
            dampening_needed = True
            dampening_reasons.append(f"Points per possession +{avg_deviations['points_per_possession']:.3f} above baseline")
        
        # Check double-counting frequency
        if double_counting_games / total_games > 0.20:  # 20% threshold
            dampening_needed = True
            dampening_reasons.append(f"Double-counting detected in {double_counting_games}/{total_games} games ({double_counting_games/total_games:.1%})")
        
        # Check model vs market bias
        if avg_model_vs_market > 3.0:
            dampening_needed = True
            dampening_reasons.append(f"Average model bias +{avg_model_vs_market:.1f} pts above market")
        
        result = {
            "sport": sport,
            "date": str(date),
            "games": total_games,
            "flagged_games": flagged_games,
            "double_counting_games": double_counting_games,
            "avg_deviations": avg_deviations,
            "avg_model_vs_market": avg_model_vs_market,
            "dampening_needed": dampening_needed,
            "dampening_reasons": dampening_reasons,
            "recommended_damp_factor": 0.90 if dampening_needed else 1.0
        }
        
        logger.info(
            f"📊 Daily baseline check ({sport}): "
            f"{total_games} games, {flagged_games} flagged, "
            f"dampening_needed={dampening_needed}"
        )
        
        return result
