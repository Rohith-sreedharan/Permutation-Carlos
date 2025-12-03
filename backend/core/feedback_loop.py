"""
Feedback Loop / Trust Loop System

Stores predictions, fetches actual results, calculates error metrics.
This is the "Reflexive Learning Loop" that grades model performance.

CRITICAL FOR:
- Trust Loop UI (7-day accuracy, 30-day ROI, Brier score)
- Model calibration
- Drift detection
- B2B licensing proof
- Investor confidence
"""

from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional
import logging
from db.mongo import db

logger = logging.getLogger(__name__)


def store_prediction(
    game_id: str,
    event_id: str,
    sport_key: str,
    commence_time: str,
    home_team: str,
    away_team: str,
    market_type: str,
    predicted_outcome: Dict,
    vegas_line: Dict,
    sim_count: int,
    model_version: str = "v1.0"
) -> str:
    """
    Store a prediction for future grading
    
    Args:
        game_id: Unique game identifier
        event_id: Event ID from simulation
        sport_key: Sport (basketball_nba, etc.)
        commence_time: Game start time
        home_team, away_team: Team names
        market_type: 'spread', 'total', 'moneyline', 'prop'
        predicted_outcome: {
            'prediction_value': float,  # Model's predicted line/total
            'win_probability': float,   # Model's confidence
            'sharp_side': str,          # Which side is +EV
            'edge_points': float,       # Magnitude of mispricing
            'edge_grade': str           # S/A/B/C/D/F
        }
        vegas_line: {
            'line_value': float,
            'bookmaker': str,
            'timestamp': str
        }
        sim_count: Number of simulations used
    
    Returns:
        Prediction ID
    """
    prediction = {
        "prediction_id": f"pred_{game_id}_{market_type}_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
        "game_id": game_id,
        "event_id": event_id,
        "sport_key": sport_key,
        "commence_time": commence_time,
        "home_team": home_team,
        "away_team": away_team,
        "market_type": market_type,
        
        # Predictions
        "predicted_value": predicted_outcome.get("prediction_value"),
        "predicted_win_probability": predicted_outcome.get("win_probability"),
        "sharp_side": predicted_outcome.get("sharp_side"),
        "edge_points": predicted_outcome.get("edge_points"),
        "edge_grade": predicted_outcome.get("edge_grade"),
        
        # Vegas line at prediction time
        "vegas_line_value": vegas_line.get("line_value"),
        "vegas_bookmaker": vegas_line.get("bookmaker"),
        "vegas_timestamp": vegas_line.get("timestamp"),
        
        # Metadata
        "sim_count_used": sim_count,
        "model_version": model_version,
        "prediction_timestamp": datetime.now(timezone.utc).isoformat(),
        
        # Grading (filled in later)
        "actual_result": None,
        "prediction_error": None,
        "was_correct": None,
        "brier_score": None,
        "graded_at": None,
        "grading_status": "pending"
    }
    
    result = db["predictions"].insert_one(prediction)
    logger.info(f"Stored prediction: {prediction['prediction_id']} for {game_id} ({market_type})")
    
    return str(result.inserted_id)


def grade_predictions(lookback_hours: int = 24):
    """
    Grade predictions for games that have completed
    
    Runs at 4:15 AM EST daily to grade previous day's games
    
    Args:
        lookback_hours: How far back to check for completed games
    """
    cutoff_time = datetime.now(timezone.utc) - timedelta(hours=lookback_hours)
    
    # Find ungraded predictions for games that should be complete
    ungraded = db["predictions"].find({
        "grading_status": "pending",
        "commence_time": {"$lt": cutoff_time.isoformat()}
    })
    
    graded_count = 0
    error_count = 0
    
    for prediction in ungraded:
        try:
            # Fetch actual game result
            actual_result = fetch_game_result(
                prediction["game_id"],
                prediction["sport_key"]
            )
            
            if actual_result is None:
                logger.warning(f"No result found for {prediction['game_id']}")
                continue
            
            # Get actual values with None checks
            actual_value = actual_result.get("actual_value")
            actual_outcome = actual_result.get("outcome_binary")
            
            if actual_value is None or actual_outcome is None:
                logger.warning(f"Incomplete actual data for {prediction['game_id']}")
                continue
            
            # Calculate error metrics
            error_metrics = calculate_prediction_error(
                predicted_value=prediction["predicted_value"],
                actual_value=float(actual_value),
                predicted_probability=prediction["predicted_win_probability"],
                actual_outcome=int(actual_outcome)  # 1 or 0
            )
            
            # Update prediction with grading
            db["predictions"].update_one(
                {"_id": prediction["_id"]},
                {"$set": {
                    "actual_result": actual_result,
                    "prediction_error": error_metrics["error"],
                    "was_correct": error_metrics["was_correct"],
                    "brier_score": error_metrics["brier_score"],
                    "graded_at": datetime.now(timezone.utc).isoformat(),
                    "grading_status": "graded"
                }}
            )
            
            graded_count += 1
            logger.info(f"Graded prediction {prediction['prediction_id']}: Error={error_metrics['error']:.2f}, Brier={error_metrics['brier_score']:.4f}")
            
        except Exception as e:
            logger.error(f"Error grading prediction {prediction.get('prediction_id')}: {str(e)}")
            error_count += 1
    
    logger.info(f"Grading complete: {graded_count} graded, {error_count} errors")
    
    # Log calibration metrics
    log_calibration_metrics()


def fetch_game_result(game_id: str, sport_key: str) -> Optional[Dict]:
    """
    Fetch actual game result from scores API or database
    
    Returns:
        {
            'home_score': int,
            'away_score': int,
            'actual_total': int,
            'actual_margin': int,
            'actual_value': float,  # For the specific market predicted
            'outcome_binary': int   # 1 if prediction side won, 0 if lost
        }
    """
    # Check local scores cache first
    result = db["game_results"].find_one({"game_id": game_id})
    
    if result:
        return result
    
    # TODO: Fetch from odds API scores endpoint
    # from integrations.odds_api import fetch_scores
    # scores = fetch_scores(sport=sport_key)
    # Parse and store...
    
    return None


def calculate_prediction_error(
    predicted_value: float,
    actual_value: float,
    predicted_probability: float,
    actual_outcome: int
) -> Dict:
    """
    Calculate prediction error metrics
    
    Args:
        predicted_value: Model's predicted line/total
        actual_value: Actual result
        predicted_probability: Model's confidence (0-1)
        actual_outcome: 1 if prediction correct, 0 if wrong
    
    Returns:
        {
            'error': MAE (Mean Absolute Error),
            'squared_error': MSE component,
            'brier_score': Brier score for probability prediction,
            'was_correct': bool
        }
    """
    # Mean Absolute Error
    error = abs(predicted_value - actual_value)
    
    # Mean Squared Error component
    squared_error = (predicted_value - actual_value) ** 2
    
    # Brier Score (for probability predictions)
    # Perfect prediction = 0, worst = 1
    brier_score = (predicted_probability - actual_outcome) ** 2
    
    # Was prediction directionally correct?
    was_correct = bool(actual_outcome == 1)
    
    return {
        "error": error,
        "squared_error": squared_error,
        "brier_score": brier_score,
        "was_correct": was_correct
    }


def log_calibration_metrics():
    """
    Calculate and log calibration metrics for Trust Loop
    
    Metrics calculated:
    - 7-day accuracy
    - 30-day ROI
    - Brier score (overall and by market type)
    - MAE, RMSE
    - Drift detection
    """
    now = datetime.now(timezone.utc)
    
    # 7-day window
    seven_days_ago = now - timedelta(days=7)
    recent_predictions = list(db["predictions"].find({
        "grading_status": "graded",
        "graded_at": {"$gte": seven_days_ago.isoformat()}
    }))
    
    if not recent_predictions:
        logger.warning("No recent graded predictions for calibration")
        return
    
    # Calculate metrics
    total_count = len(recent_predictions)
    correct_count = sum(1 for p in recent_predictions if p.get("was_correct"))
    accuracy_7d = correct_count / total_count if total_count > 0 else 0
    
    # Brier score (lower = better, 0 = perfect)
    brier_scores = [p.get("brier_score", 0) for p in recent_predictions if p.get("brier_score") is not None]
    avg_brier = sum(brier_scores) / len(brier_scores) if brier_scores else 0
    
    # MAE and RMSE
    errors = [p.get("prediction_error", 0) for p in recent_predictions if p.get("prediction_error") is not None]
    mae = sum(errors) / len(errors) if errors else 0
    rmse = (sum(e**2 for e in errors) / len(errors)) ** 0.5 if errors else 0
    
    # Store calibration log
    calibration_log = {
        "log_id": f"cal_{now.strftime('%Y%m%d%H%M%S')}",
        "timestamp": now.isoformat(),
        "window_days": 7,
        "total_predictions": total_count,
        "correct_predictions": correct_count,
        "accuracy": round(accuracy_7d, 4),
        "brier_score": round(avg_brier, 4),
        "mae": round(mae, 2),
        "rmse": round(rmse, 2),
        "drift_detected": avg_brier > 0.25,  # Flag if Brier > 0.25
        "model_version": "v1.0"
    }
    
    db["calibration_logs"].insert_one(calibration_log)
    logger.info(f"Calibration: Accuracy={accuracy_7d:.2%}, Brier={avg_brier:.4f}, MAE={mae:.2f}, RMSE={rmse:.2f}")
    
    # Check for drift
    if calibration_log["drift_detected"]:
        logger.warning("⚠️ DRIFT DETECTED: Model performance degraded. Consider recalibration.")


def get_trust_loop_metrics() -> Dict:
    """
    Get Trust Loop metrics for UI display
    
    Returns:
        {
            '7_day_accuracy': float,
            '30_day_roi': float,
            'brier_score': float,
            'total_predictions': int,
            'trend': 'improving' | 'stable' | 'declining'
        }
    """
    # Get most recent calibration log
    recent_log = db["calibration_logs"].find_one(
        sort=[("timestamp", -1)]
    )
    
    if not recent_log:
        return {
            "7_day_accuracy": 0,
            "30_day_roi": 0,
            "brier_score": 0,
            "total_predictions": 0,
            "trend": "insufficient_data"
        }
    
    # TODO: Calculate 30-day ROI from graded predictions
    # Requires tracking bet outcomes and stake sizes
    
    return {
        "7_day_accuracy": recent_log.get("accuracy", 0),
        "30_day_roi": 0,  # Placeholder
        "brier_score": recent_log.get("brier_score", 0),
        "total_predictions": recent_log.get("total_predictions", 0),
        "trend": "stable"  # Placeholder - calculate from historical logs
    }
