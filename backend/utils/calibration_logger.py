"""
Calibration Logger - Track predictions vs actual results for model validation
"""
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from pymongo import MongoClient
import os

logger = logging.getLogger(__name__)


class CalibrationLogger:
    """
    Logs predictions and actual results for calibration analysis
    
    Purpose: Catch bugs like the cover probability inversion BEFORE going 0-3
    Validates that model probabilities match reality over time
    """
    
    def __init__(self):
        mongo_uri = os.getenv("MONGODB_URI", "mongodb://localhost:27017/")
        self.client = MongoClient(mongo_uri)
        self.db = self.client.beatvegas
        self.predictions_collection = self.db.prediction_tracking
        
        # Create indexes for fast lookups
        self.predictions_collection.create_index([("event_id", 1), ("created_at", -1)])
        self.predictions_collection.create_index([("prediction_time", -1)])
    
    def log_prediction(
        self,
        event_id: str,
        home_team: str,
        away_team: str,
        home_team_key: str,
        away_team_key: str,
        market_spread_home: float,
        fair_spread_home: float,
        p_cover_home: float,
        p_cover_away: float,
        p_win_home: float,
        p_win_away: float,
        sharp_selection: Optional[str] = None,
        sharp_market: Optional[str] = None,
        edge_state: Optional[str] = None
    ) -> str:
        """
        Log a prediction when simulation is generated
        
        Returns: prediction_id for tracking
        """
        prediction = {
            "event_id": event_id,
            "home_team": home_team,
            "away_team": away_team,
            "home_team_key": home_team_key,  # CRITICAL: Team identity tracking
            "away_team_key": away_team_key,
            "prediction_time": datetime.utcnow().isoformat(),
            
            # Market data
            "market_spread_home": market_spread_home,
            "fair_spread_home": fair_spread_home,
            "edge_pts_home": market_spread_home - fair_spread_home,
            
            # Predictions
            "p_cover_home": p_cover_home,
            "p_cover_away": p_cover_away,
            "p_win_home": p_win_home,
            "p_win_away": p_win_away,
            
            # Recommendation
            "sharp_selection": sharp_selection,
            "sharp_market": sharp_market,
            "edge_state": edge_state,
            
            # Actual result (filled in later)
            "actual_result": None,
            "actual_margin": None,
            "actual_home_score": None,
            "actual_away_score": None,
            "actual_home_covered": None,
            "actual_home_won": None,
            
            # Calibration metrics (calculated after game)
            "prediction_correct": None,
            "brier_score_cover": None,
            "brier_score_win": None,
            "cover_deviation": None  # |predicted - actual|
        }
        
        result = self.predictions_collection.insert_one(prediction)
        
        logger.info(
            f"📊 Logged prediction for {event_id}: "
            f"{home_team} {market_spread_home:+.1f} ({p_cover_home*100:.1f}% cover, {p_win_home*100:.1f}% win)"
        )
        
        return str(result.inserted_id)
    
    def log_actual_result(
        self,
        event_id: str,
        home_score: int,
        away_score: int
    ):
        """
        Log actual game result and calculate calibration metrics
        """
        prediction = self.predictions_collection.find_one(
            {"event_id": event_id},
            sort=[("prediction_time", -1)]
        )
        
        if not prediction:
            logger.warning(f"No prediction found for {event_id}")
            return
        
        # Calculate actual outcomes
        actual_margin = home_score - away_score
        market_spread = prediction["market_spread_home"]
        
        actual_home_won = actual_margin > 0
        actual_home_covered = (actual_margin + market_spread) > 0
        
        # Calculate Brier scores (0 = perfect, 1 = worst)
        p_cover_home = prediction["p_cover_home"]
        p_win_home = prediction["p_win_home"]
        
        brier_score_cover = (p_cover_home - (1 if actual_home_covered else 0)) ** 2
        brier_score_win = (p_win_home - (1 if actual_home_won else 0)) ** 2
        cover_deviation = abs(p_cover_home - (1 if actual_home_covered else 0))
        
        # Update prediction with actuals
        self.predictions_collection.update_one(
            {"_id": prediction["_id"]},
            {"$set": {
                "actual_result": f"{home_score}-{away_score}",
                "actual_margin": actual_margin,
                "actual_home_score": home_score,
                "actual_away_score": away_score,
                "actual_home_covered": actual_home_covered,
                "actual_home_won": actual_home_won,
                "brier_score_cover": brier_score_cover,
                "brier_score_win": brier_score_win,
                "cover_deviation": cover_deviation,
                "prediction_correct": (
                    actual_home_covered if prediction.get("sharp_market") == "SPREAD" 
                    else actual_home_won
                ),
                "result_logged_at": datetime.utcnow().isoformat()
            }}
        )
        
        # Alert if prediction was way off (Brier > 0.5 = very bad)
        if brier_score_cover > 0.5:
            logger.warning(
                f"⚠️ CALIBRATION ALERT: {event_id} - "
                f"{prediction['home_team']} vs {prediction['away_team']} "
                f"Predicted {p_cover_home*100:.1f}% cover but actual={actual_home_covered}. "
                f"Brier score: {brier_score_cover:.3f}"
            )
        
        # Alert if cover formula might be inverted (high confidence wrong)
        if p_cover_home > 0.7 and not actual_home_covered:
            logger.error(
                f"🚨 POSSIBLE FORMULA INVERSION: {event_id} - "
                f"Predicted {p_cover_home*100:.1f}% but home didn't cover. "
                f"Check if cover probability formula is correct!"
            )
        elif p_cover_home < 0.3 and actual_home_covered:
            logger.error(
                f"🚨 POSSIBLE FORMULA INVERSION: {event_id} - "
                f"Predicted {p_cover_home*100:.1f}% but home DID cover. "
                f"Check if cover probability formula is correct!"
            )
    
    def get_calibration_report(self, days: int = 7) -> Dict[str, Any]:
        """
        Get calibration metrics for last N days
        
        Returns: Summary of prediction accuracy
        """
        cutoff = datetime.utcnow() - timedelta(days=days)
        
        predictions = list(self.predictions_collection.find({
            "prediction_time": {"$gte": cutoff.isoformat()},
            "actual_result": {"$ne": None}
        }))
        
        if not predictions:
            return {"error": "No completed predictions in this period"}
        
        total = len(predictions)
        correct = sum(1 for p in predictions if p.get("prediction_correct"))
        avg_brier_cover = sum(p.get("brier_score_cover", 0) for p in predictions) / total
        avg_brier_win = sum(p.get("brier_score_win", 0) for p in predictions) / total
        
        # Calibration buckets (are 70% predictions actually right 70% of time?)
        buckets = {
            "0-20%": {"predicted": [], "actual": []},
            "20-40%": {"predicted": [], "actual": []},
            "40-60%": {"predicted": [], "actual": []},
            "60-80%": {"predicted": [], "actual": []},
            "80-100%": {"predicted": [], "actual": []}
        }
        
        for p in predictions:
            p_cover = p.get("p_cover_home", 0.5)
            actual = 1 if p.get("actual_home_covered") else 0
            
            if p_cover < 0.2:
                buckets["0-20%"]["predicted"].append(p_cover)
                buckets["0-20%"]["actual"].append(actual)
            elif p_cover < 0.4:
                buckets["20-40%"]["predicted"].append(p_cover)
                buckets["20-40%"]["actual"].append(actual)
            elif p_cover < 0.6:
                buckets["40-60%"]["predicted"].append(p_cover)
                buckets["40-60%"]["actual"].append(actual)
            elif p_cover < 0.8:
                buckets["60-80%"]["predicted"].append(p_cover)
                buckets["60-80%"]["actual"].append(actual)
            else:
                buckets["80-100%"]["predicted"].append(p_cover)
                buckets["80-100%"]["actual"].append(actual)
        
        calibration_summary = {}
        for bucket, data in buckets.items():
            if data["predicted"]:
                avg_predicted = sum(data["predicted"]) / len(data["predicted"])
                avg_actual = sum(data["actual"]) / len(data["actual"])
                calibration_summary[bucket] = {
                    "count": len(data["predicted"]),
                    "avg_predicted": avg_predicted,
                    "avg_actual": avg_actual,
                    "calibration_error": abs(avg_predicted - avg_actual)
                }
        
        # Calculate overall calibration error
        total_predicted_sum = sum(p.get("p_cover_home", 0) for p in predictions)
        total_actual_sum = sum(1 if p.get("actual_home_covered") else 0 for p in predictions)
        overall_calibration_error = abs((total_predicted_sum / total) - (total_actual_sum / total))
        
        return {
            "period_days": days,
            "total_predictions": total,
            "predictions_with_results": total,
            "correct_predictions": correct,
            "accuracy": correct / total if total > 0 else 0,
            "avg_brier_score_cover": avg_brier_score_cover,
            "avg_brier_score_win": avg_brier_score_win,
            "overall_calibration_error": overall_calibration_error,
            "calibration_by_bucket": calibration_summary,
            "status": "WELL_CALIBRATED" if avg_brier_cover < 0.2 else "NEEDS_ATTENTION",
            "alert": "CHECK_FORMULA" if avg_brier_cover > 0.4 else None
        }


# Global instance
calibration_logger = CalibrationLogger()
