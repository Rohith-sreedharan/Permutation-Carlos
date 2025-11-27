"""
Behavioral Feedback Moat - Prediction Logging & Learning System

This module implements the "Moat" - a self-improving feedback loop
that makes the model smarter with every user action.

Features:
1. Log every prediction (predicted_prob, taken_odds, timestamp)
2. Compare predictions vs actual outcomes
3. Calculate Brier Score and Log Loss
4. Store error deltas for future weight tuning
5. Daily background job for outcome reconciliation
"""
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from db.mongo import db
import math

logger = logging.getLogger(__name__)


class PredictionLogger:
    """
    Logs predictions and calculates performance metrics
    
    Metrics:
    - Brier Score: Mean squared error of probability predictions (lower is better, target < 0.20)
    - Log Loss: Logarithmic loss function (lower is better, target < 0.60)
    """
    
    def __init__(self):
        self.collection = db.prediction_logs
        
    def log_prediction(
        self,
        user_id: str,
        event_id: str,
        predicted_prob: float,
        taken_odds: float,
        pick_type: str,
        selection: str,
        simulation_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Log a user prediction for future evaluation
        
        Args:
            user_id: User identifier
            event_id: Game/event identifier  
            predicted_prob: Model's predicted probability (0-1)
            taken_odds: Odds user accepted
            pick_type: "moneyline", "spread", "total", "prop"
            selection: "home", "away", "over", "under", etc.
            simulation_id: Optional reference to simulation
            metadata: Additional context
            
        Returns:
            log_id: Unique identifier for this prediction log
        """
        log_entry = {
            "user_id": user_id,
            "event_id": event_id,
            "predicted_prob": round(predicted_prob, 4),
            "taken_odds": taken_odds,
            "pick_type": pick_type,
            "selection": selection,
            "simulation_id": simulation_id,
            "metadata": metadata or {},
            "outcome": None,  # Will be filled when game settles
            "actual_result": None,  # 0 or 1
            "brier_score": None,
            "log_loss": None,
            "error_delta": None,
            "logged_at": datetime.utcnow(),
            "settled_at": None,
            "settled": False
        }
        
        result = self.collection.insert_one(log_entry)
        log_id = str(result.inserted_id)
        
        logger.info(f"📝 Logged prediction {log_id} for event {event_id}")
        return log_id
        
    def log_parlay_prediction(
        self,
        user_id: str,
        parlay_request_id: str,
        legs: List[Dict[str, Any]],
        combined_prob: float,
        parlay_odds: float
    ) -> str:
        """
        Log a parlay prediction
        """
        log_entry = {
            "user_id": user_id,
            "parlay_request_id": parlay_request_id,
            "type": "parlay",
            "legs": legs,
            "combined_predicted_prob": round(combined_prob, 4),
            "parlay_odds": parlay_odds,
            "outcome": None,
            "actual_result": None,
            "brier_score": None,
            "log_loss": None,
            "logged_at": datetime.utcnow(),
            "settled_at": None,
            "settled": False
        }
        
        result = self.collection.insert_one(log_entry)
        return str(result.inserted_id)
        
    def settle_prediction(
        self,
        log_id: str,
        outcome: str,
        actual_result: int
    ):
        """
        Settle a prediction with actual outcome
        
        Args:
            log_id: Prediction log identifier
            outcome: "win", "loss", "push"
            actual_result: 1 for win, 0 for loss
        """
        from bson import ObjectId
        
        log = self.collection.find_one({"_id": ObjectId(log_id)})
        if not log:
            logger.error(f"Prediction log {log_id} not found")
            return
        
        predicted_prob = log["predicted_prob"]
        
        # Calculate Brier Score: (predicted_prob - actual_result)^2
        brier_score = (predicted_prob - actual_result) ** 2
        
        # Calculate Log Loss: -[actual * log(predicted) + (1-actual) * log(1-predicted)]
        # Clip probabilities to avoid log(0)
        clipped_prob = max(0.0001, min(0.9999, predicted_prob))
        if actual_result == 1:
            log_loss = -math.log(clipped_prob)
        else:
            log_loss = -math.log(1 - clipped_prob)
        
        # Error delta for model tuning
        error_delta = actual_result - predicted_prob
        
        # Update log
        self.collection.update_one(
            {"_id": ObjectId(log_id)},
            {"$set": {
                "outcome": outcome,
                "actual_result": actual_result,
                "brier_score": round(brier_score, 4),
                "log_loss": round(log_loss, 4),
                "error_delta": round(error_delta, 4),
                "settled_at": datetime.utcnow(),
                "settled": True
            }}
        )
        
        logger.info(f"✅ Settled prediction {log_id}: Brier={brier_score:.4f}, LogLoss={log_loss:.4f}")
        
    def get_user_performance(
        self,
        user_id: str,
        days: int = 30
    ) -> Dict[str, Any]:
        """
        Calculate user's prediction performance
        """
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        # Get settled predictions
        predictions = list(self.collection.find({
            "user_id": user_id,
            "settled": True,
            "settled_at": {"$gte": cutoff_date}
        }))
        
        if not predictions:
            return {
                "total_predictions": 0,
                "avg_brier_score": None,
                "avg_log_loss": None,
                "win_rate": None
            }
        
        total = len(predictions)
        wins = sum(1 for p in predictions if p["actual_result"] == 1)
        
        brier_scores = [p["brier_score"] for p in predictions if p["brier_score"] is not None]
        log_losses = [p["log_loss"] for p in predictions if p["log_loss"] is not None]
        
        return {
            "total_predictions": total,
            "wins": wins,
            "losses": total - wins,
            "win_rate": round(wins / total, 3) if total > 0 else 0,
            "avg_brier_score": round(sum(brier_scores) / len(brier_scores), 4) if brier_scores else None,
            "avg_log_loss": round(sum(log_losses) / len(log_losses), 4) if log_losses else None,
            "days": days
        }
        
    def get_model_performance(
        self,
        days: int = 30
    ) -> Dict[str, Any]:
        """
        Calculate overall model performance across all users
        """
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        predictions = list(self.collection.find({
            "settled": True,
            "settled_at": {"$gte": cutoff_date}
        }))
        
        if not predictions:
            return {
                "total_predictions": 0,
                "avg_brier_score": None,
                "avg_log_loss": None,
                "model_accuracy": None
            }
        
        total = len(predictions)
        correct = sum(1 for p in predictions if p["actual_result"] == 1 and p["predicted_prob"] > 0.5)
        
        brier_scores = [p["brier_score"] for p in predictions if p["brier_score"] is not None]
        log_losses = [p["log_loss"] for p in predictions if p["log_loss"] is not None]
        error_deltas = [p["error_delta"] for p in predictions if p["error_delta"] is not None]
        
        return {
            "total_predictions": total,
            "avg_brier_score": round(sum(brier_scores) / len(brier_scores), 4) if brier_scores else None,
            "avg_log_loss": round(sum(log_losses) / len(log_losses), 4) if log_losses else None,
            "model_accuracy": round(correct / total, 3) if total > 0 else None,
            "avg_error_delta": round(sum(error_deltas) / len(error_deltas), 4) if error_deltas else None,
            "days": days,
            "target_brier": 0.20,
            "target_log_loss": 0.60
        }
        
    def get_unsettled_predictions(
        self,
        older_than_hours: int = 24
    ) -> List[Dict[str, Any]]:
        """
        Get predictions that should be settled by now
        Used by background job to reconcile outcomes
        """
        cutoff_date = datetime.utcnow() - timedelta(hours=older_than_hours)
        
        predictions = list(self.collection.find({
            "settled": False,
            "logged_at": {"$lte": cutoff_date}
        }))
        
        return predictions


# Global instance
prediction_logger = PredictionLogger()


def reconcile_outcomes_job():
    """
    Daily background job to reconcile prediction outcomes
    
    This runs daily to:
    1. Fetch actual game outcomes from database
    2. Compare against logged predictions
    3. Calculate Brier Score and Log Loss
    4. Store error deltas for future model tuning
    
    In production, this would be run by a scheduler (APScheduler, Celery, etc.)
    """
    logger.info("🔄 Starting outcome reconciliation job")
    
    # Get unsettled predictions from last 48 hours
    unsettled = prediction_logger.get_unsettled_predictions(older_than_hours=48)
    
    logger.info(f"Found {len(unsettled)} unsettled predictions")
    
    for prediction in unsettled:
        event_id = prediction.get("event_id")
        if not event_id:
            continue
        
        # Fetch actual game outcome from events/scores collection
        event = db.events.find_one({"event_id": event_id})
        
        if not event:
            # Event not found
            continue
        
        if "final_score" not in event:
            # Game not finished yet
            continue
        
        final_score = event["final_score"]
        pick_type = prediction["pick_type"]
        selection = prediction["selection"]
        
        # Determine if prediction was correct
        actual_result = determine_outcome(final_score, pick_type, selection, prediction.get("metadata", {}))
        
        if actual_result is not None:
            outcome_label = "win" if actual_result == 1 else "loss"
            prediction_logger.settle_prediction(
                str(prediction["_id"]),
                outcome_label,
                actual_result
            )
    
    # Log overall performance
    performance = prediction_logger.get_model_performance(days=7)
    logger.info(f"📊 Model Performance (7 days): Brier={performance['avg_brier_score']}, LogLoss={performance['avg_log_loss']}")
    
    # Count settled predictions
    settled_count = 0
    for p in unsettled:
        evt = db.events.find_one({"event_id": p.get("event_id")}, {})
        if evt and "final_score" in evt:
            settled_count += 1
    
    return {"settled": settled_count}


def determine_outcome(
    final_score: Dict[str, Any],
    pick_type: str,
    selection: str,
    metadata: Dict[str, Any]
) -> Optional[int]:
    """
    Determine if a pick was correct based on final score
    
    Returns:
        1 if win, 0 if loss, None if cannot determine
    """
    home_score = final_score.get("home", 0)
    away_score = final_score.get("away", 0)
    
    if pick_type == "moneyline":
        if selection == "home":
            return 1 if home_score > away_score else 0
        elif selection == "away":
            return 1 if away_score > home_score else 0
    
    elif pick_type == "spread":
        line = metadata.get("line", 0)
        if selection == "home":
            return 1 if (home_score + line) > away_score else 0
        elif selection == "away":
            return 1 if (away_score + line) > home_score else 0
    
    elif pick_type == "total":
        total = home_score + away_score
        line = metadata.get("line", 220)
        if selection == "over":
            return 1 if total > line else 0
        elif selection == "under":
            return 1 if total < line else 0
    
    return None
