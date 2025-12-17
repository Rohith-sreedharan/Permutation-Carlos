"""
Automated Calibration Logging System
Daily aggregate tracking and bias detection

NON-NEGOTIABLE: This must run or you will keep getting embarrassed
"""
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone, timedelta, date as date_type
from db.mongo import db
import numpy as np
import logging

logger = logging.getLogger(__name__)


class CalibrationLogger:
    """
    Automated daily calibration logging
    
    Tracks:
    - Projected vs actual totals
    - Over/under hit rates
    - Bias drift by week
    - Automatic coefficient adjustments
    """
    
    def log_pick_audit(
        self,
        game_id: str,
        sport: str,
        market_type: str,
        vegas_line: float,
        model_line: float,
        raw_model_line: float,
        std_total: float,
        p_raw: float,
        p_adjusted: float,
        edge_raw: float,
        edge_adjusted: float,
        publish_decision: bool,
        block_reasons: List[str],
        confidence_score: float,
        data_quality: float,
        sharp_side: str,
        edge_direction: str,
        pick_state: str,
        state_machine_reasons: List[str]
    ):
        """
        Log every pick decision for audit trail
        Includes pick_state and complete reason codes for NO_PLAY/LEAN/PICK classification
        """
        try:
            db.pick_audit.insert_one({
                "game_id": game_id,
                "sport": sport,
                "market_type": market_type,
                "vegas_line": vegas_line,
                "model_line": model_line,
                "raw_model_line": raw_model_line,
                "std_total": std_total,
                "p_raw": p_raw,
                "p_adjusted": p_adjusted,
                "edge_raw": edge_raw,
                "edge_adjusted": edge_adjusted,
                "publish_decision": publish_decision,
                "block_reasons": block_reasons,  # Calibration engine reasons
                "confidence_score": confidence_score,
                "data_quality": data_quality,
                "sharp_side": sharp_side,
                "edge_direction": edge_direction,
                "pick_state": pick_state,  # PICK / LEAN / NO_PLAY
                "state_machine_reasons": state_machine_reasons,  # Pick state machine reasons
                "timestamp": datetime.now(timezone.utc).isoformat()
            })
        except Exception as e:
            logger.error(f"Failed to log pick audit: {e}")
    
    def compute_daily_calibration(self, sport: str, date: Optional[date_type] = None):
        """
        Compute daily calibration metrics
        Must run every day at EOD for each sport
        """
        if date is None:
            date = datetime.now(timezone.utc).date()
        
        try:
            # Get all completed games for this sport/date
            games = self._get_completed_games(sport, date)
            
            if not games:
                logger.info(f"No completed games for {sport} on {date}")
                return
            
            # Aggregate metrics
            avg_actual_total = np.mean([g["actual_total"] for g in games])
            avg_model_total = np.mean([g["model_total"] for g in games])
            avg_vegas_close_total = np.mean([g["vegas_close_total"] for g in games])
            
            # Bias calculations
            bias = avg_model_total - avg_actual_total
            bias_vs_market = avg_model_total - avg_vegas_close_total
            
            # Over/under rates
            model_overs = sum(1 for g in games if g["model_pick"] == "over")
            actual_overs = sum(1 for g in games if g["actual_result"] == "over")
            
            over_rate_model = model_overs / len(games) if games else 0.5
            over_rate_actual = actual_overs / len(games) if games else 0.5
            
            # Model win rate
            correct_picks = sum(1 for g in games if g["model_pick"] == g["actual_result"])
            model_win_rate = correct_picks / len(games) if games else 0.5
            
            # Determine if dampening needed
            from core.sport_calibration_config import get_sport_config
            config = get_sport_config(sport)
            
            damp_factor_applied = 1.0
            damp_reasons = []
            
            if abs(bias) > config.max_bias_vs_actual:
                damp_reasons.append("bias_vs_actual")
            if over_rate_model > config.max_over_rate:
                damp_reasons.append("all_overs_syndrome")
            if abs(bias_vs_market) > config.max_bias_vs_market:
                damp_reasons.append("market_drift")
            
            if damp_reasons:
                if sport in ["baseball_mlb", "icehockey_nhl"]:
                    damp_factor_applied = np.clip(0.92, 1.0, 1.0 - (bias / 4.0))
                else:
                    damp_factor_applied = np.clip(0.90, 1.0, 1.0 - (bias / 20.0))
            
            # Log to database
            db.calibration_daily.insert_one({
                "sport": sport,
                "date": date.isoformat(),
                "games_count": len(games),
                "avg_actual_total": float(avg_actual_total),
                "avg_model_total": float(avg_model_total),
                "avg_vegas_close_total": float(avg_vegas_close_total),
                "bias": float(bias),
                "bias_vs_market": float(bias_vs_market),
                "over_rate_model": float(over_rate_model),
                "over_rate_actual": float(over_rate_actual),
                "model_win_rate": float(model_win_rate),
                "damp_factor_applied": float(damp_factor_applied),
                "damp_reasons": damp_reasons,
                "timestamp": datetime.now(timezone.utc).isoformat()
            })
            
            logger.info(
                f"📊 [{sport}] Daily calibration: "
                f"bias={bias:+.2f}, over_rate={over_rate_model:.1%}, "
                f"win_rate={model_win_rate:.1%}, damp={damp_factor_applied:.3f}"
            )
            
        except Exception as e:
            logger.error(f"Failed to compute daily calibration: {e}")
    
    def _get_completed_games(self, sport: str, date: date_type) -> List[Dict[str, Any]]:
        """
        Get all completed games with model predictions and actual results
        """
        # Query events that happened on this date
        start_time = datetime.combine(date, datetime.min.time()).replace(tzinfo=timezone.utc)
        end_time = start_time + timedelta(days=1)
        
        games = []
        
        try:
            # Find all events for this sport/date
            events = db.events.find({
                "sport_key": sport,
                "commence_time": {
                    "$gte": start_time.isoformat(),
                    "$lt": end_time.isoformat()
                }
            })
            
            for event in events:
                event_id = str(event["_id"])
                
                # Get simulation
                sim = db.monte_carlo_simulations.find_one({"event_id": event_id})
                if not sim:
                    continue
                
                # Get actual result from ESPN scores
                score = db.espn_scores.find_one({"event_id": event_id})
                if not score or not score.get("completed"):
                    continue
                
                # Extract data
                model_total = sim.get("median_total", sim.get("mean_total"))
                vegas_close_total = event.get("bookmakers", [{}])[0].get("totals", {}).get("line")
                actual_total = score.get("home_score", 0) + score.get("away_score", 0)
                
                if not all([model_total, vegas_close_total, actual_total]):
                    continue
                
                # Determine picks and results
                model_pick = "over" if model_total > vegas_close_total else "under"
                actual_result = "over" if actual_total > vegas_close_total else "under"
                
                games.append({
                    "event_id": event_id,
                    "model_total": model_total,
                    "vegas_close_total": vegas_close_total,
                    "actual_total": actual_total,
                    "model_pick": model_pick,
                    "actual_result": actual_result
                })
        
        except Exception as e:
            logger.error(f"Failed to get completed games: {e}")
        
        return games
    
    def generate_weekly_report(self, sport: str) -> Dict[str, Any]:
        """
        Generate weekly calibration report
        """
        end_date = datetime.now(timezone.utc).date()
        start_date = end_date - timedelta(days=7)
        
        try:
            # Get last 7 days of calibration data
            calibrations = list(db.calibration_daily.find({
                "sport": sport,
                "date": {
                    "$gte": start_date.isoformat(),
                    "$lte": end_date.isoformat()
                }
            }).sort("date", 1))
            
            if not calibrations:
                return {"error": "No calibration data available"}
            
            # Aggregate weekly metrics
            avg_bias = np.mean([c["bias"] for c in calibrations])
            avg_bias_vs_market = np.mean([c["bias_vs_market"] for c in calibrations])
            avg_over_rate_model = np.mean([c["over_rate_model"] for c in calibrations])
            avg_over_rate_actual = np.mean([c["over_rate_actual"] for c in calibrations])
            avg_win_rate = np.mean([c["model_win_rate"] for c in calibrations])
            
            # Trend detection
            bias_trend = "increasing" if calibrations[-1]["bias"] > calibrations[0]["bias"] else "decreasing"
            
            return {
                "sport": sport,
                "period": f"{start_date} to {end_date}",
                "days_analyzed": len(calibrations),
                "avg_bias": avg_bias,
                "avg_bias_vs_market": avg_bias_vs_market,
                "avg_over_rate_model": avg_over_rate_model,
                "avg_over_rate_actual": avg_over_rate_actual,
                "avg_win_rate": avg_win_rate,
                "bias_trend": bias_trend,
                "needs_adjustment": abs(avg_bias) > 1.0 or avg_over_rate_model > 0.62
            }
        
        except Exception as e:
            logger.error(f"Failed to generate weekly report: {e}")
            return {"error": str(e)}


# Singleton
calibration_logger = CalibrationLogger()
